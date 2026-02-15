"""Shared test fixtures for stonks."""

import pytest

from stonks.store import create_connection, create_experiment, create_run, initialize_db


@pytest.fixture
def db_path(tmp_path):
    """Provide a temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture
def db_conn(db_path):
    """Provide an initialized test database connection."""
    conn = create_connection(str(db_path))
    initialize_db(conn)
    yield conn
    conn.close()


@pytest.fixture
def sample_experiment(db_conn):
    """Create and return a sample experiment."""
    return create_experiment(db_conn, name="test-experiment")


@pytest.fixture
def sample_run(db_conn, sample_experiment):
    """Create and return a sample run within the sample experiment."""
    return create_run(
        db_conn,
        experiment_id=sample_experiment.id,
        name="test-run",
        config={"lr": 0.001, "batch_size": 32},
    )
