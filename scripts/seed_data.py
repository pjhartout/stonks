"""Seed a stonks database with realistic neural network training data.

Simulates three experiments:
  1. ResNet-50 on CIFAR-10 — three runs with different learning rates
  2. Transformer LM on WikiText — two runs comparing model sizes
  3. VAE on MNIST — two runs with different latent dimensions

Usage:
    uv run python scripts/seed_data.py [--db ./stonks.db]
"""

from __future__ import annotations

import argparse
import math
import random

import stonks


def _noisy(base: float, noise: float = 0.02) -> float:
    """Add Gaussian noise to a base value."""
    return base + random.gauss(0, noise)


def _seed_resnet_cifar10(db_path: str) -> None:
    """Simulate ResNet-50 training on CIFAR-10 with three learning rates."""
    configs = [
        {
            "model": "resnet50",
            "dataset": "cifar10",
            "lr": 0.1,
            "batch_size": 128,
            "epochs": 100,
            "optimizer": "sgd",
            "weight_decay": 5e-4,
            "momentum": 0.9,
        },
        {
            "model": "resnet50",
            "dataset": "cifar10",
            "lr": 0.01,
            "batch_size": 128,
            "epochs": 100,
            "optimizer": "sgd",
            "weight_decay": 5e-4,
            "momentum": 0.9,
        },
        {
            "model": "resnet50",
            "dataset": "cifar10",
            "lr": 0.001,
            "batch_size": 128,
            "epochs": 100,
            "optimizer": "adam",
            "weight_decay": 1e-4,
        },
    ]

    for i, config in enumerate(configs):
        lr = config["lr"]
        with stonks.start_run(
            experiment="resnet50-cifar10",
            config=config,
            db=db_path,
            run_name=f"lr={lr}",
        ) as run:
            num_epochs = 100
            steps_per_epoch = 390  # ~50K images / 128 batch

            # Different convergence profiles per learning rate
            if lr == 0.1:
                final_train_loss, final_val_loss = 0.08, 0.35
                final_train_acc, final_val_acc = 0.98, 0.93
                convergence_speed = 3.0
            elif lr == 0.01:
                final_train_loss, final_val_loss = 0.15, 0.40
                final_train_acc, final_val_acc = 0.96, 0.91
                convergence_speed = 2.0
            else:
                final_train_loss, final_val_loss = 0.45, 0.55
                final_train_acc, final_val_acc = 0.88, 0.85
                convergence_speed = 1.0

            global_step = 0
            for epoch in range(num_epochs):
                progress = (epoch + 1) / num_epochs
                decay = 1 - math.exp(-convergence_speed * progress)

                # Log per-batch train metrics (sample every 10 steps)
                for batch in range(0, steps_per_epoch, 10):
                    train_loss = 2.5 * (1 - decay) + final_train_loss * decay
                    train_acc = 0.1 * (1 - decay) + final_train_acc * decay
                    run.log(
                        {
                            "train/loss": _noisy(train_loss, 0.05),
                            "train/accuracy": min(1.0, _noisy(train_acc, 0.02)),
                        },
                        step=global_step,
                    )
                    global_step += 10

                # Log per-epoch validation metrics
                val_loss = 2.5 * (1 - decay) + final_val_loss * decay
                val_acc = 0.1 * (1 - decay) + final_val_acc * decay

                # Simulate LR schedule (step decay at epoch 50 and 75)
                current_lr = lr
                if epoch >= 75:
                    current_lr = lr * 0.01
                elif epoch >= 50:
                    current_lr = lr * 0.1

                run.log(
                    {
                        "val/loss": _noisy(val_loss, 0.03),
                        "val/accuracy": min(1.0, _noisy(val_acc, 0.015)),
                        "lr": current_lr,
                    },
                    step=global_step,
                )

        print(f"  ResNet run {i + 1}/3 (lr={lr}) done — {global_step} steps")


def _seed_transformer_lm(db_path: str) -> None:
    """Simulate Transformer language model training on WikiText."""
    configs = [
        {
            "model": "transformer",
            "dataset": "wikitext-103",
            "d_model": 256,
            "n_layers": 6,
            "n_heads": 8,
            "lr": 3e-4,
            "batch_size": 64,
            "max_seq_len": 512,
            "optimizer": "adamw",
            "warmup_steps": 4000,
        },
        {
            "model": "transformer",
            "dataset": "wikitext-103",
            "d_model": 512,
            "n_layers": 12,
            "n_heads": 8,
            "lr": 1e-4,
            "batch_size": 32,
            "max_seq_len": 512,
            "optimizer": "adamw",
            "warmup_steps": 4000,
        },
    ]

    for i, config in enumerate(configs):
        d_model = config["d_model"]
        with stonks.start_run(
            experiment="transformer-wikitext",
            config=config,
            db=db_path,
            run_name=f"d_model={d_model}",
        ) as run:
            total_steps = 50000
            warmup_steps = config["warmup_steps"]

            # Bigger model converges to lower loss
            if d_model == 512:
                final_loss = 3.33
            else:
                final_loss = 3.81

            for step in range(0, total_steps, 50):
                progress = step / total_steps

                # Warmup then cosine decay for learning rate
                if step < warmup_steps:
                    lr_mult = step / warmup_steps
                else:
                    lr_mult = 0.5 * (
                        1 + math.cos(math.pi * (step - warmup_steps) / (total_steps - warmup_steps))
                    )
                current_lr = config["lr"] * lr_mult

                # Loss with log-curve convergence
                loss = 7.0 * (1 - progress) ** 0.5 + final_loss * (1 - (1 - progress) ** 0.5)
                ppl = math.exp(min(loss, 10))  # cap to avoid overflow

                run.log(
                    {
                        "train/loss": _noisy(loss, 0.1),
                        "train/perplexity": _noisy(ppl, ppl * 0.02),
                        "lr": current_lr,
                    },
                    step=step,
                )

                # Validation every 1000 steps
                if step % 1000 == 0 and step > 0:
                    val_loss = loss * 1.05  # slightly worse than train
                    run.log(
                        {
                            "val/loss": _noisy(val_loss, 0.08),
                            "val/perplexity": _noisy(math.exp(min(val_loss, 10)), ppl * 0.03),
                        },
                        step=step,
                    )

        print(f"  Transformer run {i + 1}/2 (d_model={d_model}) done — {total_steps} steps")


def _seed_vae_mnist(db_path: str) -> None:
    """Simulate VAE training on MNIST with different latent dimensions."""
    configs = [
        {
            "model": "vae",
            "dataset": "mnist",
            "latent_dim": 2,
            "lr": 1e-3,
            "batch_size": 128,
            "epochs": 50,
            "optimizer": "adam",
            "beta": 1.0,
        },
        {
            "model": "vae",
            "dataset": "mnist",
            "latent_dim": 20,
            "lr": 1e-3,
            "batch_size": 128,
            "epochs": 50,
            "optimizer": "adam",
            "beta": 1.0,
        },
    ]

    for i, config in enumerate(configs):
        latent_dim = config["latent_dim"]
        with stonks.start_run(
            experiment="vae-mnist",
            config=config,
            db=db_path,
            run_name=f"latent_dim={latent_dim}",
        ) as run:
            num_epochs = 50
            steps_per_epoch = 468  # 60K / 128

            # Higher latent dim = lower reconstruction loss but higher KL
            if latent_dim == 20:
                final_recon = 25.0
                final_kl = 18.0
            else:
                final_recon = 55.0
                final_kl = 3.5

            global_step = 0
            for epoch in range(num_epochs):
                progress = (epoch + 1) / num_epochs
                decay = 1 - math.exp(-2.5 * progress)

                for batch in range(0, steps_per_epoch, 20):
                    recon_loss = 150.0 * (1 - decay) + final_recon * decay
                    kl_loss = 0.1 * (1 - decay) + final_kl * decay
                    total_loss = recon_loss + kl_loss

                    run.log(
                        {
                            "train/total_loss": _noisy(total_loss, 2.0),
                            "train/recon_loss": _noisy(recon_loss, 1.5),
                            "train/kl_loss": _noisy(kl_loss, 0.5),
                        },
                        step=global_step,
                    )
                    global_step += 20

                # Validation per epoch
                val_recon = (150.0 * (1 - decay) + final_recon * decay) * 1.02
                val_kl = (0.1 * (1 - decay) + final_kl * decay) * 1.01
                run.log(
                    {
                        "val/total_loss": _noisy(val_recon + val_kl, 1.5),
                        "val/recon_loss": _noisy(val_recon, 1.0),
                        "val/kl_loss": _noisy(val_kl, 0.3),
                    },
                    step=global_step,
                )

        print(f"  VAE run {i + 1}/2 (latent_dim={latent_dim}) done — {global_step} steps")


def main() -> None:
    """Seed the database with training simulation data."""
    parser = argparse.ArgumentParser(description="Seed stonks DB with training data")
    parser.add_argument(
        "--db",
        default="./stonks.db",
        help="Path to the SQLite database (default: ./stonks.db)",
    )
    args = parser.parse_args()

    random.seed(42)  # Reproducible data

    print(f"Seeding database at {args.db}...")
    print()

    print("Experiment 1: ResNet-50 on CIFAR-10 (3 runs)")
    _seed_resnet_cifar10(args.db)
    print()

    print("Experiment 2: Transformer LM on WikiText-103 (2 runs)")
    _seed_transformer_lm(args.db)
    print()

    print("Experiment 3: VAE on MNIST (2 runs)")
    _seed_vae_mnist(args.db)
    print()

    # Print summary
    with stonks.open(args.db) as db:
        experiments = db.list_experiments()
        total_runs = 0
        for exp in experiments:
            runs = db.list_runs(exp.id)
            total_runs += len(runs)
            print(f"  {exp.name}: {len(runs)} runs")
        print(f"\nTotal: {len(experiments)} experiments, {total_runs} runs")

    print(f"\nDone! View with: uv run stonks serve --db {args.db}")


if __name__ == "__main__":
    main()
