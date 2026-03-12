"""Tests for sync configuration parsing."""

import pytest

from stonks.sync.config import RemoteConfig, SyncConfigError, parse_remotes_config


@pytest.fixture
def config_file(tmp_path):
    """Create a temporary config file and return its path."""

    def _write(content: str):
        path = tmp_path / "remotes.toml"
        path.write_text(content)
        return path

    return _write


class TestRemoteConfig:
    def test_staging_path(self):
        remote = RemoteConfig(name="gpu1", host="user@host", db_path="/data/stonks.db")
        assert remote.staging_path.name == "stonks.db"
        assert "gpu1" in str(remote.staging_path)

    def test_rsync_source(self):
        remote = RemoteConfig(name="gpu1", host="user@host", db_path="/data/stonks.db")
        assert remote.rsync_source == "user@host:/data/stonks.db"

    def test_defaults(self):
        remote = RemoteConfig(name="gpu1", host="user@host", db_path="/data/stonks.db")
        assert remote.port == 22
        assert remote.ssh_key is None

    def test_is_scan_mode_false(self):
        remote = RemoteConfig(name="gpu1", host="user@host", db_path="/data/stonks.db")
        assert remote.is_scan_mode is False

    def test_is_scan_mode_true(self):
        remote = RemoteConfig(name="gpu1", host="user@host", scan_dir="/data/logs")
        assert remote.is_scan_mode is True

    def test_staging_dir(self):
        remote = RemoteConfig(name="gpu1", host="user@host", scan_dir="/data/logs")
        assert "gpu1" in str(remote.staging_dir)


class TestParseRemotesConfig:
    def test_valid_config(self, config_file):
        path = config_file('[remotes.gpu1]\nhost = "user@10.0.0.1"\ndb_path = "/data/stonks.db"\n')
        remotes = parse_remotes_config(path)
        assert len(remotes) == 1
        assert remotes[0].name == "gpu1"
        assert remotes[0].host == "user@10.0.0.1"
        assert remotes[0].db_path == "/data/stonks.db"

    def test_multiple_remotes(self, config_file):
        path = config_file(
            '[remotes.gpu1]\nhost = "user@host1"\ndb_path = "/data/a.db"\n\n'
            '[remotes.gpu2]\nhost = "user@host2"\ndb_path = "/data/b.db"\n'
        )
        remotes = parse_remotes_config(path)
        assert len(remotes) == 2
        names = {r.name for r in remotes}
        assert names == {"gpu1", "gpu2"}

    def test_optional_fields(self, config_file):
        path = config_file(
            "[remotes.gpu1]\n"
            'host = "user@host"\n'
            'db_path = "/data/stonks.db"\n'
            'ssh_key = "~/.ssh/my_key"\n'
            "port = 2222\n"
        )
        remotes = parse_remotes_config(path)
        assert remotes[0].port == 2222
        assert remotes[0].ssh_key is not None
        assert "my_key" in remotes[0].ssh_key

    def test_missing_file(self, tmp_path):
        with pytest.raises(SyncConfigError, match="not found"):
            parse_remotes_config(tmp_path / "nonexistent.toml")

    def test_invalid_toml(self, config_file):
        path = config_file("this is not valid toml [[[")
        with pytest.raises(SyncConfigError, match="Invalid TOML"):
            parse_remotes_config(path)

    def test_missing_remotes_section(self, config_file):
        path = config_file('[other]\nkey = "value"\n')
        with pytest.raises(SyncConfigError, match="No \\[remotes\\] section"):
            parse_remotes_config(path)

    def test_missing_host(self, config_file):
        path = config_file('[remotes.gpu1]\ndb_path = "/data/stonks.db"\n')
        with pytest.raises(SyncConfigError, match="missing required 'host'"):
            parse_remotes_config(path)

    def test_missing_db_path_and_scan_dir(self, config_file):
        path = config_file('[remotes.gpu1]\nhost = "user@host"\n')
        with pytest.raises(SyncConfigError, match="must have either"):
            parse_remotes_config(path)

    def test_both_db_path_and_scan_dir(self, config_file):
        path = config_file(
            '[remotes.gpu1]\nhost = "user@host"\n'
            'db_path = "/data/stonks.db"\nscan_dir = "/data/logs"\n'
        )
        with pytest.raises(SyncConfigError, match="cannot have both"):
            parse_remotes_config(path)

    def test_scan_dir_config(self, config_file):
        path = config_file('[remotes.mn5]\nhost = "user@mn5"\nscan_dir = "/gpfs/projects/logs"\n')
        remotes = parse_remotes_config(path)
        assert len(remotes) == 1
        assert remotes[0].scan_dir == "/gpfs/projects/logs"
        assert remotes[0].db_path is None
        assert remotes[0].is_scan_mode is True

    def test_invalid_port(self, config_file):
        path = config_file('[remotes.gpu1]\nhost = "user@host"\ndb_path = "/d.db"\nport = "abc"\n')
        with pytest.raises(SyncConfigError, match="invalid 'port'"):
            parse_remotes_config(path)

    def test_empty_remotes_section(self, config_file):
        path = config_file("[remotes]\n")
        remotes = parse_remotes_config(path)
        assert remotes == []
