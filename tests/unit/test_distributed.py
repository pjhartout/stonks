"""Tests for distributed environment detection."""

import os
from unittest.mock import patch

from stonks.distributed import (
    get_distributed_info,
    get_local_rank,
    get_node_rank,
    get_num_nodes,
    get_rank,
    get_world_size,
    is_distributed,
    is_rank_zero,
)


class TestDistributedDefaults:
    """Test default values when not in a distributed environment."""

    def test_defaults_non_distributed(self):
        """Without env vars or torch.distributed, returns single-process defaults."""
        with patch("stonks.distributed._HAS_TORCH_DIST", False):
            with patch.dict(os.environ, {}, clear=True):
                assert get_rank() == 0
                assert get_local_rank() == 0
                assert get_world_size() == 1
                assert get_node_rank() == 0
                assert get_num_nodes() == 1
                assert not is_distributed()
                assert is_rank_zero()


class TestTorchrunEnvVars:
    """Test detection of torchrun-style environment variables."""

    def test_torchrun_rank_and_world_size(self):
        env = {"RANK": "2", "LOCAL_RANK": "1", "WORLD_SIZE": "8"}
        with patch("stonks.distributed._HAS_TORCH_DIST", False):
            with patch.dict(os.environ, env, clear=True):
                assert get_rank() == 2
                assert get_local_rank() == 1
                assert get_world_size() == 8
                assert is_distributed()
                assert not is_rank_zero()

    def test_torchrun_node_info(self):
        env = {"GROUP_RANK": "1", "NODE_RANK": "1", "NUM_NODES": "4"}
        with patch("stonks.distributed._HAS_TORCH_DIST", False):
            with patch.dict(os.environ, env, clear=True):
                assert get_node_rank() == 1
                assert get_num_nodes() == 4

    def test_rank_zero_detected(self):
        env = {"RANK": "0", "WORLD_SIZE": "4"}
        with patch("stonks.distributed._HAS_TORCH_DIST", False):
            with patch.dict(os.environ, env, clear=True):
                assert is_rank_zero()
                assert is_distributed()


class TestSlurmEnvVars:
    """Test detection of SLURM environment variables."""

    def test_slurm_env_vars(self):
        env = {
            "SLURM_PROCID": "3",
            "SLURM_LOCALID": "1",
            "SLURM_NTASKS": "16",
            "SLURM_NODEID": "1",
            "SLURM_NNODES": "4",
        }
        with patch("stonks.distributed._HAS_TORCH_DIST", False):
            with patch.dict(os.environ, env, clear=True):
                assert get_rank() == 3
                assert get_local_rank() == 1
                assert get_world_size() == 16
                assert get_node_rank() == 1
                assert get_num_nodes() == 4

    def test_torchrun_takes_priority_over_slurm(self):
        env = {
            "RANK": "0",
            "WORLD_SIZE": "4",
            "SLURM_PROCID": "0",
            "SLURM_NTASKS": "16",
        }
        with patch("stonks.distributed._HAS_TORCH_DIST", False):
            with patch.dict(os.environ, env, clear=True):
                assert get_rank() == 0
                assert get_world_size() == 4


class TestDistributedInfo:
    """Test the get_distributed_info aggregation function."""

    def test_basic_info(self):
        env = {
            "RANK": "1",
            "LOCAL_RANK": "1",
            "WORLD_SIZE": "4",
            "NODE_RANK": "0",
            "NUM_NODES": "1",
        }
        with patch("stonks.distributed._HAS_TORCH_DIST", False):
            with patch.dict(os.environ, env, clear=True):
                info = get_distributed_info()
                assert info["rank"] == 1
                assert info["local_rank"] == 1
                assert info["world_size"] == 4
                assert info["node_rank"] == 0
                assert info["num_nodes"] == 1
                assert "backend" not in info

    def test_includes_master_addr(self):
        env = {"MASTER_ADDR": "10.0.0.1", "RANK": "0", "WORLD_SIZE": "2"}
        with patch("stonks.distributed._HAS_TORCH_DIST", False):
            with patch.dict(os.environ, env, clear=True):
                info = get_distributed_info()
                assert info["master_addr"] == "10.0.0.1"

    def test_includes_slurm_job_id(self):
        env = {"SLURM_JOB_ID": "99999", "SLURM_PROCID": "0", "SLURM_NTASKS": "2"}
        with patch("stonks.distributed._HAS_TORCH_DIST", False):
            with patch.dict(os.environ, env, clear=True):
                info = get_distributed_info()
                assert info["slurm_job_id"] == "99999"

    def test_no_optional_fields_when_absent(self):
        with patch("stonks.distributed._HAS_TORCH_DIST", False):
            with patch.dict(os.environ, {}, clear=True):
                info = get_distributed_info()
                assert "backend" not in info
                assert "slurm_job_id" not in info
                assert "master_addr" not in info


class TestEnvVarEdgeCases:
    """Test edge cases in environment variable parsing."""

    def test_invalid_rank_falls_back(self):
        env = {"RANK": "not_a_number", "WORLD_SIZE": "4"}
        with patch("stonks.distributed._HAS_TORCH_DIST", False):
            with patch.dict(os.environ, env, clear=True):
                assert get_rank() == 0
                assert get_world_size() == 4

    def test_empty_env_var_falls_back(self):
        env = {"RANK": "", "WORLD_SIZE": "2"}
        with patch("stonks.distributed._HAS_TORCH_DIST", False):
            with patch.dict(os.environ, env, clear=True):
                assert get_rank() == 0
                assert get_world_size() == 2


class TestTorchDistIntegration:
    """Test behavior when torch.distributed is available but not initialized."""

    def test_falls_back_to_env_when_not_initialized(self):
        """torch.distributed available but not initialized: use env vars."""
        env = {"RANK": "3", "WORLD_SIZE": "8"}
        with patch("stonks.distributed._HAS_TORCH_DIST", True):
            with patch("stonks.distributed._torch_dist") as mock_dist:
                mock_dist.is_initialized.return_value = False
                with patch.dict(os.environ, env, clear=True):
                    assert get_rank() == 3
                    assert get_world_size() == 8

    def test_uses_torch_dist_when_initialized(self):
        """torch.distributed initialized: use its values."""
        with patch("stonks.distributed._HAS_TORCH_DIST", True):
            with patch("stonks.distributed._torch_dist") as mock_dist:
                mock_dist.is_initialized.return_value = True
                mock_dist.get_rank.return_value = 5
                mock_dist.get_world_size.return_value = 16
                mock_dist.get_backend.return_value = "nccl"
                with patch.dict(os.environ, {}, clear=True):
                    assert get_rank() == 5
                    assert get_world_size() == 16
                    info = get_distributed_info()
                    assert info["backend"] == "nccl"
