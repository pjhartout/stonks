"""Demo data generation for stonks.

Generates realistic ML training experiments with varied hyperparameters,
metrics, and run configurations.
"""

from __future__ import annotations

import math
import random
import tempfile
import time
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

import stonks


@dataclass
class CurveParams:
    """Parameters for generating realistic training curves.

    Attributes:
        base_loss: Starting loss value for exponential decay.
        decay: Decay rate for loss curve.
        noise_std: Standard deviation of Gaussian noise.
        max_acc: Maximum achievable accuracy.
        growth: Growth rate for sigmoid accuracy curve.
        midpoint: Inflection point for sigmoid curve.
    """

    base_loss: float
    decay: float
    noise_std: float
    max_acc: float
    growth: float
    midpoint: float


@dataclass
class RunConfig:
    """Configuration for a demo run.

    Attributes:
        name: Display name for the run.
        config: Hyperparameter configuration dict.
        tags: Tags for the run.
        group: Group name for the run.
        notes: Optional notes string.
        status: Target status (completed or running).
        curves: Parameters for metric curve generation.
    """

    name: str
    config: dict[str, Any]
    tags: list[str]
    group: str
    notes: str | None
    status: str
    curves: CurveParams


@dataclass
class ExperimentConfig:
    """Configuration for a demo experiment.

    Attributes:
        name: Experiment name.
        runs: List of run configurations.
    """

    name: str
    runs: list[RunConfig] = field(default_factory=list)


# Experiment configurations
EXPERIMENTS: list[ExperimentConfig] = [
    ExperimentConfig(
        name="image-classification",
        runs=[
            RunConfig(
                name="resnet18-baseline",
                config={
                    "model": "resnet18",
                    "learning_rate": 0.001,
                    "batch_size": 64,
                    "epochs": 50,
                    "optimizer": "adam",
                    "dataset": "cifar-10",
                },
                tags=["baseline"],
                group="architecture-search",
                notes="Baseline configuration with ResNet-18",
                status="completed",
                curves=CurveParams(
                    base_loss=2.3,
                    decay=0.06,
                    noise_std=0.02,
                    max_acc=0.92,
                    growth=0.12,
                    midpoint=25,
                ),
            ),
            RunConfig(
                name="resnet50-large",
                config={
                    "model": "resnet50",
                    "learning_rate": 0.001,
                    "batch_size": 32,
                    "epochs": 50,
                    "optimizer": "adam",
                    "dataset": "cifar-10",
                },
                tags=["experiment", "best"],
                group="architecture-search",
                notes="Best performing model with ResNet-50",
                status="completed",
                curves=CurveParams(
                    base_loss=2.3,
                    decay=0.08,
                    noise_std=0.015,
                    max_acc=0.95,
                    growth=0.14,
                    midpoint=22,
                ),
            ),
            RunConfig(
                name="resnet18-high-lr",
                config={
                    "model": "resnet18",
                    "learning_rate": 0.1,
                    "batch_size": 128,
                    "epochs": 50,
                    "optimizer": "sgd",
                    "dataset": "cifar-10",
                },
                tags=["experiment"],
                group="hyperparameter-sweep",
                notes=None,
                status="completed",
                curves=CurveParams(
                    base_loss=2.3,
                    decay=0.03,
                    noise_std=0.05,
                    max_acc=0.85,
                    growth=0.08,
                    midpoint=30,
                ),
            ),
        ],
    ),
    ExperimentConfig(
        name="text-generation",
        runs=[
            RunConfig(
                name="transformer-small",
                config={
                    "model": "transformer",
                    "learning_rate": 0.0001,
                    "batch_size": 32,
                    "epochs": 30,
                    "optimizer": "adamw",
                    "dataset": "wikitext-2",
                    "hidden_dim": 256,
                    "n_layers": 4,
                    "n_heads": 4,
                },
                tags=["baseline"],
                group="architecture-search",
                notes="Small transformer baseline",
                status="completed",
                curves=CurveParams(
                    base_loss=8.5,
                    decay=0.05,
                    noise_std=0.1,
                    max_acc=0.45,
                    growth=0.15,
                    midpoint=15,
                ),
            ),
            RunConfig(
                name="transformer-medium",
                config={
                    "model": "transformer",
                    "learning_rate": 0.0003,
                    "batch_size": 64,
                    "epochs": 30,
                    "optimizer": "adamw",
                    "dataset": "wikitext-2",
                    "hidden_dim": 512,
                    "n_layers": 6,
                    "n_heads": 8,
                },
                tags=["experiment", "best"],
                group="architecture-search",
                notes="Best performing transformer config",
                status="completed",
                curves=CurveParams(
                    base_loss=8.5,
                    decay=0.07,
                    noise_std=0.08,
                    max_acc=0.52,
                    growth=0.18,
                    midpoint=12,
                ),
            ),
            RunConfig(
                name="transformer-lr-sweep",
                config={
                    "model": "transformer",
                    "learning_rate": 0.01,
                    "batch_size": 64,
                    "epochs": 30,
                    "optimizer": "adamw",
                    "dataset": "wikitext-2",
                    "hidden_dim": 512,
                    "n_layers": 6,
                    "n_heads": 8,
                },
                tags=["experiment"],
                group="hyperparameter-sweep",
                notes=None,
                status="running",
                curves=CurveParams(
                    base_loss=8.5,
                    decay=0.04,
                    noise_std=0.15,
                    max_acc=0.38,
                    growth=0.1,
                    midpoint=18,
                ),
            ),
        ],
    ),
    ExperimentConfig(
        name="reinforcement-learning",
        runs=[
            RunConfig(
                name="ppo-cartpole",
                config={
                    "model": "mlp",
                    "learning_rate": 0.001,
                    "batch_size": 64,
                    "epochs": 100,
                    "algorithm": "ppo",
                    "env": "CartPole-v1",
                    "gamma": 0.99,
                    "clip_eps": 0.2,
                },
                tags=["baseline"],
                group="hyperparameter-sweep",
                notes="PPO baseline on CartPole",
                status="completed",
                curves=CurveParams(
                    base_loss=1.5,
                    decay=0.04,
                    noise_std=0.03,
                    max_acc=0.98,
                    growth=0.08,
                    midpoint=50,
                ),
            ),
            RunConfig(
                name="ppo-cartpole-tuned",
                config={
                    "model": "mlp",
                    "learning_rate": 0.0003,
                    "batch_size": 128,
                    "epochs": 100,
                    "algorithm": "ppo",
                    "env": "CartPole-v1",
                    "gamma": 0.995,
                    "clip_eps": 0.1,
                },
                tags=["experiment", "best"],
                group="hyperparameter-sweep",
                notes="Tuned PPO with lower clip epsilon",
                status="running",
                curves=CurveParams(
                    base_loss=1.5,
                    decay=0.05,
                    noise_std=0.025,
                    max_acc=0.99,
                    growth=0.1,
                    midpoint=45,
                ),
            ),
        ],
    ),
]


def _generate_loss(rng: random.Random, step: int, curves: CurveParams) -> float:
    """Generate a realistic loss value with exponential decay and noise.

    Args:
        rng: Random number generator instance.
        step: Current training step.
        curves: Curve parameters.

    Returns:
        Simulated loss value.
    """
    base = curves.base_loss * math.exp(-curves.decay * step)
    noise = rng.gauss(0, curves.noise_std)
    return max(0.001, base + noise)


def _generate_accuracy(rng: random.Random, step: int, curves: CurveParams) -> float:
    """Generate a realistic accuracy value with sigmoid curve and noise.

    Args:
        rng: Random number generator instance.
        step: Current training step.
        curves: Curve parameters.

    Returns:
        Simulated accuracy value clamped to [0, 1].
    """
    sigmoid = curves.max_acc / (1 + math.exp(-curves.growth * (step - curves.midpoint)))
    noise = rng.gauss(0, curves.noise_std * 0.5)
    return max(0.0, min(1.0, sigmoid + noise))


def generate_demo_data(db_path: str) -> str:
    """Generate demo experiment data in the given database.

    Creates multiple experiments with varied runs, realistic training curves,
    and different configurations.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        The database path used.
    """
    rng = random.Random(42)
    logger.info(f"Generating demo data in {db_path}")

    for exp_config in EXPERIMENTS:
        logger.info(f"Creating experiment: {exp_config.name}")

        for run_config in exp_config.runs:
            total_steps: int = run_config.config["epochs"]

            # Running runs only have partial data
            is_running = run_config.status == "running"
            num_steps = int(total_steps * 0.6) if is_running else total_steps

            with stonks.start_run(
                experiment=exp_config.name,
                name=run_config.name,
                config=run_config.config,
                tags=run_config.tags,
                group=run_config.group,
                notes=run_config.notes,
                save_dir=db_path,
            ) as run:
                for step in range(num_steps):
                    loss = _generate_loss(rng, step, run_config.curves)
                    acc = _generate_accuracy(rng, step, run_config.curves)

                    lr: float = run_config.config["learning_rate"]
                    metrics: dict[str, float] = {
                        "train/loss": loss,
                        "train/accuracy": acc,
                        "val/loss": loss * (1.0 + rng.gauss(0.1, 0.05)),
                        "val/accuracy": acc * (1.0 - rng.gauss(0.02, 0.01)),
                        "train/learning_rate": lr,
                    }

                    run.log(metrics, step=step)

                # Small delay between runs so timestamps differ
                time.sleep(0.01)

            logger.info(
                f"  Created run: {run_config.name} ({num_steps} steps, status={run_config.status})"
            )

    logger.info("Demo data generation complete")
    return db_path


def get_default_demo_db() -> str:
    """Get the default temporary database path for demos.

    Returns:
        Path to a temporary database file.
    """
    return tempfile.mkdtemp() + "/stonks-demo.db"
