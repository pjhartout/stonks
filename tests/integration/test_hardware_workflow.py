"""Integration tests for hardware monitoring in the full workflow."""

import time

import stonks
from stonks.store import create_connection, get_metric_keys


class TestHardwareWorkflow:
    def test_hardware_enabled_produces_sys_keys(self, db_path):
        """hardware=True should produce sys/ prefixed keys in the database."""
        db = str(db_path)

        with stonks.start_run(
            "hw-test",
            db=db,
            hardware=True,
            hardware_interval=1.0,
            hardware_gpu=False,
        ) as run:
            run.log({"train/loss": 0.5}, step=0)
            # Give the hardware monitor time for at least one poll + buffer flush
            time.sleep(1.5)
            run.flush()

        conn = create_connection(db)
        keys = get_metric_keys(conn, run.id)
        conn.close()

        sys_keys = [k for k in keys if k.startswith("sys/")]
        assert len(sys_keys) > 0, f"Expected sys/ keys but got: {keys}"
        assert "sys/cpu_percent" in sys_keys
        assert "train/loss" in keys

    def test_hardware_disabled_produces_no_sys_keys(self, db_path):
        """hardware=False (default) should produce no sys/ keys."""
        db = str(db_path)

        with stonks.start_run("no-hw-test", db=db) as run:
            run.log({"train/loss": 0.5}, step=0)

        conn = create_connection(db)
        keys = get_metric_keys(conn, run.id)
        conn.close()

        sys_keys = [k for k in keys if k.startswith("sys/")]
        assert len(sys_keys) == 0, f"Expected no sys/ keys but got: {sys_keys}"
        assert "train/loss" in keys
