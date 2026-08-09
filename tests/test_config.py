import json

import pytest

from brainlib import config


def test_env_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAIN_VAULT", str(tmp_path))
    assert config.vault_path() == tmp_path


def test_cli_override_wins_over_env(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAIN_VAULT", "C:/nope")
    assert config.vault_path(str(tmp_path)) == tmp_path


def test_brain_json(tmp_path, monkeypatch):
    monkeypatch.delenv("BRAIN_VAULT", raising=False)
    cfg_dir = tmp_path / ".claude"
    cfg_dir.mkdir()
    (cfg_dir / "brain.json").write_text(json.dumps({"vault": str(tmp_path)}), encoding="utf-8")
    monkeypatch.setattr(config, "CONFIG_FILE", cfg_dir / "brain.json")
    assert config.vault_path() == tmp_path


def test_missing_vault_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("BRAIN_VAULT", raising=False)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "absent.json")
    with pytest.raises(config.ConfigError):
        config.vault_path()


def test_nonexistent_dir_raises(monkeypatch):
    monkeypatch.setenv("BRAIN_VAULT", "C:/definitely/not/here-xyz")
    with pytest.raises(config.ConfigError):
        config.vault_path()
