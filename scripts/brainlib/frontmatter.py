"""Restricted-YAML frontmatter for Modo D vaults.

Supported: `key: scalar`, `key:` + dash list, inline `[a, b]`, quoted
strings, empty list `[]`. Nested mappings are a schema violation by design
(Obsidian Properties UI does not support them).
"""

import re
from pathlib import Path

_DELIM = "---"
_KEY = re.compile(r"^([A-Za-z0-9_-]+):(.*)$")
# An indented line is a nested mapping only if it looks like "key: value" (or
# "key:"). Anything else indented is a folded continuation of the previous
# scalar or list item (how Obsidian wraps long values at ~80 cols).
_NESTED_KEY = re.compile(r"^[A-Za-z0-9_-]+:(\s|$)")


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


def _scan_line(line: str, open_quote: str | None) -> tuple[bool, str | None]:
    """Walk the line tracking quote state, which may already be open from a
    folded value. Returns (starts a comment, quote still open at end).

    A '#' only opens a comment when it is outside quotes AND begins a token;
    `pagina#secao` is literal, `issue #200` inside quotes is literal too.
    """
    prev = ""
    for ch in line:
        if open_quote is not None:
            if ch == open_quote:
                open_quote = None
            prev = ch
            continue
        if ch in "'\"":
            open_quote = ch
        elif ch == "#" and (prev == "" or prev in " \t[,"):
            return True, open_quote
        prev = ch
    return False, open_quote


def parse(yaml_text: str) -> dict:
    """Reject '#' outright: it opens a YAML comment, so `tags: [#a, #b]` is a
    flow sequence that never closes. Our regex reader would happily accept it,
    but the real YAML parsers downstream (basic-memory, Obsidian) fail and one
    of them repairs the page by prepending a second frontmatter block."""
    meta: dict = {}
    current_list: str | None = None
    current_scalar: str | None = None
    open_quote: str | None = None  # quote char still open from a folded line
    for raw in yaml_text.splitlines():
        if "\t" in raw:
            raise FrontmatterError("tab character in frontmatter")
        has_comment, open_quote = _scan_line(raw, open_quote)
        if has_comment:
            raise FrontmatterError(
                f"'#' starts a YAML comment and breaks the block: {raw.strip()!r} "
                "(use plain tags: 'deploy', not '#deploy')")
        line = raw.rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        if stripped.startswith("- "):
            if current_list is None:
                raise FrontmatterError(f"list item without key: {stripped!r}")
            meta[current_list].append(_unquote(stripped[2:]))
            current_scalar = None
            continue
        if line[0] in " \t":
            if _NESTED_KEY.match(stripped):
                raise FrontmatterError(f"nested object not allowed: {stripped!r}")
            # Folded continuation: re-run _unquote on the concatenated value so
            # a quote opened on the first line and closed on a later one still
            # strips correctly, however many lines the fold spans.
            if current_list is not None and meta[current_list]:
                meta[current_list][-1] = _unquote(f"{meta[current_list][-1]} {stripped}")
            elif current_scalar is not None:
                meta[current_scalar] = _unquote(f"{meta[current_scalar]} {stripped}")
            else:
                raise FrontmatterError(f"unexpected continuation line: {stripped!r}")
            continue
        m = _KEY.match(stripped)
        if not m:
            raise FrontmatterError(f"unparseable line: {stripped!r}")
        key, value = m.group(1), m.group(2).strip()
        if value == "":
            meta[key] = []
            current_list = key
            current_scalar = None
        elif value == "[]":
            meta[key] = []
            current_list = None
            current_scalar = None
        elif value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            meta[key] = [_unquote(x) for x in inner.split(",")] if inner else []
            current_list = None
            current_scalar = None
        else:
            meta[key] = _unquote(value)
            current_list = None
            current_scalar = key
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
