"""Distributed training environment detection for stonks."""

from __future__ import annotations

import os

try:
    import torch.distributed as _torch_dist

    _HAS_TORCH_DIST = True
except ImportError:
    _torch_dist = None
    _HAS_TORCH_DIST = False


def _env_int(key: str, default: int) -> int:
    """Read an integer from an environment variable.

    Args:
        key: Environment variable name.
        default: Default value if not set or not a valid integer.

    Returns:
        The integer value or default.
    """
    val = os.environ.get(key)
    if val is not None:
        try:
            return int(val)
        except ValueError:
            pass
    return default


def get_rank() -> int:
    """Get the global rank of the current process.

    Checks torch.distributed first (if initialized), then falls back
    to RANK (torchrun) and SLURM_PROCID environment variables.

    Returns:
        Global rank, 0 if not in a distributed environment.
    """
    if _HAS_TORCH_DIST and _torch_dist.is_initialized():
        return _torch_dist.get_rank()
    return _env_int("RANK", _env_int("SLURM_PROCID", 0))


def get_local_rank() -> int:
    """Get the local rank (device index on this node).

    Checks LOCAL_RANK (torchrun) and SLURM_LOCALID environment variables.

    Returns:
        Local rank, 0 if not in a distributed environment.
    """
    return _env_int("LOCAL_RANK", _env_int("SLURM_LOCALID", 0))


def get_world_size() -> int:
    """Get the total number of distributed processes.

    Checks torch.distributed first (if initialized), then falls back
    to WORLD_SIZE (torchrun) and SLURM_NTASKS environment variables.

    Returns:
        World size, 1 if not in a distributed environment.
    """
    if _HAS_TORCH_DIST and _torch_dist.is_initialized():
        return _torch_dist.get_world_size()
    return _env_int("WORLD_SIZE", _env_int("SLURM_NTASKS", 1))


def get_node_rank() -> int:
    """Get the rank of the current node.

    Checks NODE_RANK (Lightning), GROUP_RANK (torchrun), and
    SLURM_NODEID environment variables.

    Returns:
        Node rank, 0 if not in a distributed environment.
    """
    return _env_int("NODE_RANK", _env_int("GROUP_RANK", _env_int("SLURM_NODEID", 0)))


def get_num_nodes() -> int:
    """Get the total number of nodes.

    Checks NUM_NODES and SLURM_NNODES environment variables.

    Returns:
        Number of nodes, 1 if not in a distributed environment.
    """
    return _env_int("NUM_NODES", _env_int("SLURM_NNODES", 1))


def is_distributed() -> bool:
    """Check if running in a distributed environment.

    Returns:
        True if world size > 1.
    """
    return get_world_size() > 1


def is_rank_zero() -> bool:
    """Check if this is the rank 0 (main) process.

    Returns:
        True if global rank is 0.
    """
    return get_rank() == 0


def get_distributed_info() -> dict:
    """Collect all distributed environment metadata.

    Returns a dict with rank, local_rank, world_size, node_rank, num_nodes,
    and optionally backend, slurm_job_id, and master_addr when available.

    Returns:
        Dictionary of distributed environment metadata.
    """
    info: dict = {
        "rank": get_rank(),
        "local_rank": get_local_rank(),
        "world_size": get_world_size(),
        "node_rank": get_node_rank(),
        "num_nodes": get_num_nodes(),
    }

    if _HAS_TORCH_DIST and _torch_dist.is_initialized():
        info["backend"] = _torch_dist.get_backend()

    slurm_job_id = os.environ.get("SLURM_JOB_ID")
    if slurm_job_id:
        info["slurm_job_id"] = slurm_job_id

    master_addr = os.environ.get("MASTER_ADDR")
    if master_addr:
        info["master_addr"] = master_addr

    return info
