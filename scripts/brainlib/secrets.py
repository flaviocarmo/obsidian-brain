"""Where are the credentials? An inventory, not an alarm.

This vault is personal and deliberately holds credentials: passwords, tokens
and connection strings are part of what it is for. So a detector that treats
a secret as a violation would be a linter shouting against the file's purpose,
and would teach its owner to ignore the linter.

The real risks are different, and none is solved by blocking a write:

* **Rotation.** When a credential changes you need every page that states it.
  Finding those by memory is how a stale password survives in a runbook.
* **Propagation.** The danger is a credential leaving the vault — into an
  issue, a PR, an email, a commit. That is an instruction problem (stated in
  the vault's CLAUDE.md/AGENTS.md), not something a scanner can prevent.
* **Staleness.** A token nobody knows exists is a token nobody rotates.

So this module reports, on demand, and never as a lint finding. Values are
**masked** in the output: an inventory that prints secrets into a terminal
log has moved the problem rather than solved it.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from . import frontmatter

PATTERNS: list[tuple[str, re.Pattern]] = [
    ("aws-access-key", re.compile(r"\b((?:AKIA|ASIA)[0-9A-Z]{16})\b")),
    ("gitlab-pat", re.compile(r"\b(glpat-[0-9A-Za-z_-]{20,})")),
    ("github-token", re.compile(r"\b((?:ghp|gho|ghu|ghs|ghr)_[0-9A-Za-z]{36,})")),
    ("slack-token", re.compile(r"\b(xox[baprs]-[0-9A-Za-z-]{10,})")),
    ("google-api-key", re.compile(r"\b(AIza[0-9A-Za-z_-]{35})\b")),
    ("openai-key", re.compile(r"\b(sk-[A-Za-z0-9_-]{20,})")),
    ("jwt", re.compile(r"\b(eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,})")),
    ("private-key-block", re.compile(r"(-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----)")),
    ("connection-string", re.compile(
        r"\b((?:postgres|postgresql|mysql|mongodb|redis|amqp|amqps|https?|ssh|ftp)://"
        r"[^\s:@/]+:[^\s:@/]{3,}@[A-Za-z0-9._-]+)")),
    # `\b` before the keyword keeps NOPASSWD out; the value cannot be a path
    # (`NOPASSWD: /usr/bin/psql` is a sudoers rule, not a credential).
    ("password-assignment", re.compile(
        r"\b(?:senha|password|passwd|pwd|secret|token|api[_-]?key)\s*[:=]\s*[\"']?"
        r"(?!/)([^\s\"',;<>|`/]{6,})",
        re.IGNORECASE)),
]
# Values that match the shapes above but are placeholders, not credentials.
_PLACEHOLDER = re.compile(
    r"^(?:<.*>|\{\{.*\}\}|\$\{?\w+\}?|x{3,}|\*{3,}|\.{3,}|senha|password|secret|token|"
    r"changeme|redacted|omitid[oa]|exemplo|example|your[_-]?\w+|seu[_-]?\w+|"
    r"credencia\w*|credential\w*|\w*\(\)|\w+\.\w+\(.*)$",
    re.IGNORECASE)
# Source code reading a secret at runtime states no secret at all.
_RUNTIME_LOOKUP = re.compile(
    r"\b(?:process\.env|os\.getenv|os\.environ|System\.getenv|ConfigurationManager|"
    r"sessionStorage|localStorage|getItem|Environment\.GetEnvironmentVariable|"
    r"secrets\.|vault\.|\$env:)", re.IGNORECASE)


@dataclass
class Hit:
    page: str
    line_no: int
    kind: str
    masked: str
    context: str

    def line(self) -> str:
        return f"{self.page}:{self.line_no}  [{self.kind}] {self.masked}  — {self.context}"


def mask(value: str) -> str:
    """Enough to recognise it, not enough to use it."""
    if len(value) <= 8:
        return value[0] + "*" * (len(value) - 1) if value else ""
    return f"{value[:4]}…{value[-2:]} ({len(value)} chars)"


def scan_text(text: str, page: str) -> list[Hit]:
    block, body = frontmatter.split(text)
    offset = len(block.splitlines()) + 2 if block else 0
    hits: list[Hit] = []
    for i, line in enumerate(body.splitlines(), start=1 + offset):
        if _RUNTIME_LOOKUP.search(line):
            continue  # `const token = sessionStorage.getItem(...)` holds nothing
        for kind, pattern in PATTERNS:
            for value in pattern.findall(line):
                if _PLACEHOLDER.match(value.strip()):
                    continue
                context = line.strip()
                for _k, p in PATTERNS:
                    # Replace only the captured value: keeping `senha: ` around
                    # it is what makes the line findable when you go rotate it.
                    context = p.sub(lambda m: m.group(0).replace(m.group(1), mask(m.group(1))),
                                    context)
                hits.append(Hit(page=page, line_no=i, kind=kind, masked=mask(value),
                                context=context[:120]))
                break  # one finding per line is enough to send you there
    return hits


def scan_vault(vault: Path) -> list[Hit]:
    out: list[Hit] = []
    for path in sorted((vault / "wiki").rglob("*.md")):
        rel = path.relative_to(vault).as_posix()
        try:
            out += scan_text(path.read_text(encoding="utf-8"), rel)
        except OSError:
            continue
    return out


def main_cli(vault: Path, as_json: bool = False) -> int:
    import json
    hits = scan_vault(vault)
    if as_json:
        print(json.dumps([h.__dict__ for h in hits], ensure_ascii=False, indent=2))
        return 0
    if not hits:
        print("nenhuma credencial encontrada no vault")
        return 0
    by_kind: dict[str, int] = {}
    for h in hits:
        by_kind[h.kind] = by_kind.get(h.kind, 0) + 1
    for h in hits:
        print(h.line())
    print(f"\n{len(hits)} ocorrencia(s): " + ", ".join(f"{k}={v}" for k, v in sorted(by_kind.items())))
    print("valores mascarados de proposito. Use para rotacionar, nao para copiar.")
    return 0
