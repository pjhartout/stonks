"""Tests for stonks CLI commands."""

import argparse
import json
from unittest.mock import MagicMock, patch

import pytest

import stonks
from stonks.cli import (
    delete_command,
    export_command,
    gc_command,
    info_command,
    ls_command,
    runs_command,
    serve_command,
)
from stonks.store import create_connection, finish_run, initialize_db, list_runs


@pytest.fixture
def seeded_db(tmp_path):
    """Create a database with two experiments and runs, return the db path string."""
    db = str(tmp_path / "cli_test.db")
    with stonks.start_run("exp-alpha", save_dir=db, config={"lr": 0.001}) as run:
        run.log({"loss": 1.0, "acc": 0.5}, step=0)
        run.log({"loss": 0.5, "acc": 0.8}, step=1)

    with stonks.start_run("exp-beta", save_dir=db, config={"epochs": 10}) as run:
        run.log({"val/loss": 0.3}, step=0)

    return db


def _ns(**kwargs):
    """Create an argparse.Namespace with defaults for common CLI args."""
    defaults = {"db": None, "json": False, "force": False}
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class TestLsCommand:
    def test_ls_table_output(self, seeded_db, capsys):
        """ls command prints a table of experiments."""
        ls_command(_ns(db=seeded_db))
        output = capsys.readouterr().out
        assert "exp-alpha" in output
        assert "exp-beta" in output

    def test_ls_json_output(self, seeded_db, capsys):
        """ls --json outputs valid JSON with experiment data."""
        ls_command(_ns(db=seeded_db, json=True))
        output = capsys.readouterr().out
        data = json.loads(output)
        assert len(data) == 2
        names = {e["name"] for e in data}
        assert names == {"exp-alpha", "exp-beta"}

    def test_ls_empty_database(self, tmp_path, capsys):
        """ls with empty database prints 'No experiments found.'"""
        db = str(tmp_path / "empty.db")
        conn = create_connection(db)
        initialize_db(conn)
        conn.close()
        ls_command(_ns(db=db))
        output = capsys.readouterr().out
        assert "No experiments found." in output


class TestRunsCommand:
    def test_runs_table_output(self, seeded_db, capsys):
        """runs command lists runs for an experiment."""
        runs_command(_ns(db=seeded_db, experiment="exp-alpha", status=None, tag=None))
        output = capsys.readouterr().out
        assert "completed" in output

    def test_runs_json_output(self, seeded_db, capsys):
        """runs --json outputs valid JSON."""
        runs_command(_ns(db=seeded_db, experiment="exp-alpha", status=None, tag=None, json=True))
        output = capsys.readouterr().out
        data = json.loads(output)
        assert len(data) == 1
        assert data[0]["status"] == "completed"

    def test_runs_experiment_not_found(self, seeded_db):
        """runs with unknown experiment exits with code 1."""
        with pytest.raises(SystemExit, match="1"):
            runs_command(_ns(db=seeded_db, experiment="nonexistent", status=None, tag=None))

    def test_runs_status_filter(self, seeded_db, capsys):
        """runs --status filters by run status."""
        runs_command(
            _ns(db=seeded_db, experiment="exp-alpha", status="failed", tag=None, json=True)
        )
        output = capsys.readouterr().out
        data = json.loads(output)
        assert len(data) == 0


class TestInfoCommand:
    def test_info_table_output(self, seeded_db, capsys):
        """info command prints database statistics."""
        info_command(_ns(db=seeded_db))
        output = capsys.readouterr().out
        assert "Experiments:" in output
        assert "Runs:" in output
        assert "Metrics:" in output

    def test_info_json_output(self, seeded_db, capsys):
        """info --json outputs valid JSON."""
        info_command(_ns(db=seeded_db, json=True))
        output = capsys.readouterr().out
        data = json.loads(output)
        assert data["experiments"] == 2
        assert data["runs"] == 2
        assert data["metrics"] > 0


class TestDeleteCommand:
    def test_delete_run_with_force(self, seeded_db, capsys):
        """delete --force deletes a run without confirmation."""
        conn = create_connection(seeded_db)
        runs = list_runs(conn)
        run_id = runs[0].id
        conn.close()

        delete_command(_ns(db=seeded_db, id=run_id, force=True))
        output = capsys.readouterr().out
        assert f"Deleted run {run_id}" in output

        conn = create_connection(seeded_db)
        remaining = list_runs(conn)
        conn.close()
        assert len(remaining) == 1

    def test_delete_experiment_with_force(self, seeded_db, capsys):
        """delete --force deletes an experiment by name."""
        delete_command(_ns(db=seeded_db, id="exp-alpha", force=True))
        output = capsys.readouterr().out
        assert "Deleted experiment 'exp-alpha'" in output

    def test_delete_run_aborted(self, seeded_db, capsys):
        """delete without --force prompts and aborts on 'n'."""
        conn = create_connection(seeded_db)
        runs = list_runs(conn)
        run_id = runs[0].id
        conn.close()

        with patch("builtins.input", return_value="n"):
            delete_command(_ns(db=seeded_db, id=run_id, force=False))
        output = capsys.readouterr().out
        assert "Aborted." in output

    def test_delete_run_confirmed(self, seeded_db, capsys):
        """delete without --force prompts and proceeds on 'y'."""
        conn = create_connection(seeded_db)
        runs = list_runs(conn)
        run_id = runs[0].id
        conn.close()

        with patch("builtins.input", return_value="y"):
            delete_command(_ns(db=seeded_db, id=run_id, force=False))
        output = capsys.readouterr().out
        assert f"Deleted run {run_id}" in output

    def test_delete_not_found(self, seeded_db):
        """delete with unknown ID exits with code 1."""
        with pytest.raises(SystemExit, match="1"):
            delete_command(_ns(db=seeded_db, id="nonexistent-id", force=True))


class TestExportCommand:
    def test_export_csv(self, seeded_db, capsys):
        """export outputs CSV by default."""
        conn = create_connection(seeded_db)
        runs = list_runs(conn)
        run_id = runs[0].id
        conn.close()

        export_command(_ns(db=seeded_db, run_id=run_id, format="csv"))
        output = capsys.readouterr().out
        lines = output.strip().split("\n")
        assert "step" in lines[0]
        assert len(lines) > 1

    def test_export_json(self, seeded_db, capsys):
        """export --format json outputs valid JSON."""
        conn = create_connection(seeded_db)
        runs = list_runs(conn)
        run_id = runs[0].id
        conn.close()

        export_command(_ns(db=seeded_db, run_id=run_id, format="json"))
        output = capsys.readouterr().out
        data = json.loads(output)
        assert isinstance(data, list)
        assert all("step" in row for row in data)

    def test_export_run_not_found(self, seeded_db):
        """export with unknown run ID exits with code 1."""
        with pytest.raises(SystemExit, match="1"):
            export_command(_ns(db=seeded_db, run_id="nonexistent", format="csv"))


class TestGcCommand:
    def test_gc_no_candidates(self, seeded_db, capsys):
        """gc with no matching runs prints 'No runs to clean up.'"""
        gc_command(_ns(db=seeded_db, status="failed,interrupted", before=None, force=True))
        output = capsys.readouterr().out
        assert "No runs to clean up." in output

    def test_gc_deletes_failed_runs(self, tmp_path, capsys):
        """gc --force deletes failed runs."""
        db = str(tmp_path / "gc_test.db")
        with stonks.start_run("gc-exp", save_dir=db) as run:
            run.log({"loss": 1.0}, step=0)

        # Mark the run as failed
        conn = create_connection(db)
        runs = list_runs(conn)
        finish_run(conn, runs[0].id, "failed")
        conn.close()

        gc_command(_ns(db=db, status="failed", before=None, force=True))
        output = capsys.readouterr().out
        assert "Deleted 1 run(s)." in output

    def test_gc_aborted(self, tmp_path, capsys):
        """gc without --force prompts and aborts on 'n'."""
        db = str(tmp_path / "gc_test.db")
        with stonks.start_run("gc-exp", save_dir=db) as run:
            run.log({"loss": 1.0}, step=0)

        conn = create_connection(db)
        runs = list_runs(conn)
        finish_run(conn, runs[0].id, "failed")
        conn.close()

        with patch("builtins.input", return_value="n"):
            gc_command(_ns(db=db, status="failed", before=None, force=False))
        output = capsys.readouterr().out
        assert "Aborted." in output

    def test_gc_confirmed(self, tmp_path, capsys):
        """gc without --force prompts and proceeds on 'y'."""
        db = str(tmp_path / "gc_test.db")
        with stonks.start_run("gc-exp", save_dir=db) as run:
            run.log({"loss": 1.0}, step=0)

        conn = create_connection(db)
        runs = list_runs(conn)
        finish_run(conn, runs[0].id, "failed")
        conn.close()

        with patch("builtins.input", return_value="y"):
            gc_command(_ns(db=db, status="failed", before=None, force=False))
        output = capsys.readouterr().out
        assert "Deleted 1 run(s)." in output


class TestServeCommand:
    def test_serve_calls_uvicorn(self, seeded_db):
        """serve command calls uvicorn.run with correct args."""
        mock_uvicorn = MagicMock()
        mock_create_app = MagicMock()
        with (
            patch.dict("sys.modules", {"uvicorn": mock_uvicorn}),
            patch("stonks.server.app.create_app", mock_create_app),
        ):
            serve_command(_ns(db=seeded_db, host="127.0.0.1", port=8000, reload=False))
            mock_uvicorn.run.assert_called_once()

    def test_serve_reload_mode(self, seeded_db):
        """serve --reload uses factory string."""
        mock_uvicorn = MagicMock()
        with patch.dict("sys.modules", {"uvicorn": mock_uvicorn}):
            serve_command(_ns(db=seeded_db, host="127.0.0.1", port=8000, reload=True))
            mock_uvicorn.run.assert_called_once()
            call_args = mock_uvicorn.run.call_args
            assert call_args[0][0] == "stonks.server.app:create_app"
            assert call_args[1]["reload"] is True
