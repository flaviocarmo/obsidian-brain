"""Vault location resolution: CLI arg > BRAIN_VAULT env > ~/.claude/brain.json."""

import json
import os
from pathlib import Path

CONFIG_FILE = Path.home() / ".claude" / "brain.json"


class ConfigError(Exception):
    pass


def vault_path(cli_override: str | None = None) -> Path:
    raw = cli_override or os.environ.get("BRAIN_VAULT")
    if not raw:
        if not CONFIG_FILE.exists():
            raise ConfigError(
                f"no vault configured. ASK THE USER for their Obsidian vault folder, "
                f'then write {CONFIG_FILE} with {{"vault": "<absolute path>"}} and retry'
            )
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise ConfigError(f"cannot read {CONFIG_FILE}: {e}") from e
        raw = data.get("vault")
        if not raw:
            raise ConfigError(f"{CONFIG_FILE} has no 'vault' key")
    p = Path(raw)
    if not p.is_dir():
        raise ConfigError(f"vault path is not a directory: {p}")
    return p.resolve()
