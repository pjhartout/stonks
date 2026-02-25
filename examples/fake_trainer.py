"""Fake training loop that logs realistic-looking metrics to stonks.

Simulates a classification training run with decaying loss,
climbing accuracy, and a learning rate schedule.
"""

from __future__ import annotations

import math
import os
import random
import time

import stonks

EPOCHS = int(os.environ.get("TRAIN_EPOCHS", "50"))
STEPS_PER_EPOCH = int(os.environ.get("STEPS_PER_EPOCH", "20"))
STEP_DELAY = float(os.environ.get("STEP_DELAY", "0.3"))
EXPERIMENT = os.environ.get("EXPERIMENT", "debug-experiment")
RUN_NAME = os.environ.get("RUN_NAME", None)


def lr_schedule(step: int, total: int, base_lr: float = 3e-4) -> float:
    """Cosine annealing LR schedule."""
    return base_lr * 0.5 * (1 + math.cos(math.pi * step / total))


def main() -> None:
    config = {
        "model": "resnet18",
        "optimizer": "adamw",
        "lr": 3e-4,
        "batch_size": 64,
        "epochs": EPOCHS,
        "dataset": "cifar10",
    }

    total_steps = EPOCHS * STEPS_PER_EPOCH

    with stonks.start_run(
        experiment=EXPERIMENT,
        name=RUN_NAME,
        config=config,
        tags=["debug", "fake"],
        job_type="train",
        hardware=True,
        hardware_interval=2.0,
        hardware_gpu=False,
    ) as run:
        step = 0
        for epoch in range(EPOCHS):
            epoch_loss = 0.0
            for batch in range(STEPS_PER_EPOCH):
                # Simulated training loss: decays with noise
                progress = step / total_steps
                base_loss = 2.5 * math.exp(-3 * progress) + 0.05
                noise = random.gauss(0, 0.02 * (1 - progress + 0.1))
                train_loss = max(0.01, base_loss + noise)
                epoch_loss += train_loss

                lr = lr_schedule(step, total_steps)

                run.log({"train/loss": train_loss, "train/lr": lr}, step=step)
                step += 1
                time.sleep(STEP_DELAY)

            # End-of-epoch validation metrics
            val_progress = (epoch + 1) / EPOCHS
            val_loss = 2.0 * math.exp(-2.8 * val_progress) + 0.08 + random.gauss(0, 0.015)
            val_acc = min(
                0.97, 0.4 + 0.55 * (1 - math.exp(-4 * val_progress)) + random.gauss(0, 0.005)
            )

            run.log(
                {
                    "val/loss": val_loss,
                    "val/accuracy": val_acc,
                    "epoch/train_loss": epoch_loss / STEPS_PER_EPOCH,
                },
                step=step,
            )
            print(f"Epoch {epoch + 1}/{EPOCHS}  val_loss={val_loss:.4f}  val_acc={val_acc:.4f}")

    print("Training complete.")


if __name__ == "__main__":
    main()
