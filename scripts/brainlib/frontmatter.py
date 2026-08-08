"""Restricted-YAML frontmatter for Modo D vaults.

Supported: `key: scalar`, `key:` + dash list, inline `[a, b]`, quoted
strings, empty list `[]`. Nested mappings are a schema violation by design
(Obsidian Properties UI does not support them).
"""

import re
from pathlib import Path

_DELIM = "---"
_KEY = re.compile(r"^([A-Za-z0-9_-]+):(.*)$")


class FrontmatterError(Exception):
    pass


def split(text: str) -> tuple[str | None, str]:
    if not text.startswith(_DELIM + "\n"):
        return None, text
    # find closing delimiter on its own line
    end = text.find("\n---", 3)
    if end == -1:
        return None, text
    block = text[len(_DELIM) + 1 : end]
    rest = text[end + len("\n---") :]
    if rest.startswith("\n"):
        rest = rest[1:]
    return block, rest


def _unquote(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
        return v[1:-1]
    return v


def parse(yaml_text: str) -> dict:
    meta: dict = {}
    current_list: str | None = None
    for raw in yaml_text.splitlines():
        if "\t" in raw:
            raise FrontmatterError("tab character in frontmatter")
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.startswith(("  ", "    ")) and not line.lstrip().startswith("-"):
            raise FrontmatterError(f"nested object not allowed: {line.strip()!r}")
        stripped = line.strip()
        if stripped.startswith("- "):
            if current_list is None:
                raise FrontmatterError(f"list item without key: {stripped!r}")
            meta[current_list].append(_unquote(stripped[2:]))
            continue
        m = _KEY.match(stripped)
        if not m:
            raise FrontmatterError(f"unparseable line: {stripped!r}")
        key, value = m.group(1), m.group(2).strip()
        if value == "":
            meta[key] = []
            current_list = key
        elif value == "[]":
            meta[key] = []
            current_list = None
        elif value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            meta[key] = [_unquote(x) for x in inner.split(",")] if inner else []
            current_list = None
        else:
            meta[key] = _unquote(value)
            current_list = None
    return meta


def _quote_if_needed(v: str) -> str:
    if v == "" or ":" in v or v.startswith(("[", "'", '"', "-", "{", "*", "&")):
        return '"' + v.replace('"', '\\"') + '"'
    return v


def serialize(data: dict) -> str:
    out = [_DELIM]
    for key, value in data.items():
        if isinstance(value, list):
            if not value:
                out.append(f"{key}: []")
            else:
                out.append(f"{key}:")
                out.extend(f"- {_quote_if_needed(str(item))}" for item in value)
        else:
            out.append(f"{key}: {_quote_if_needed(str(value))}")
    out.append(_DELIM)
    return "\n".join(out) + "\n"


def load(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    block, body = split(text)
    if block is None:
        raise FrontmatterError(f"no frontmatter: {path}")
    return parse(block), body
