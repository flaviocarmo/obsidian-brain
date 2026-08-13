"""Drift detection for host → address facts.

The existing contradiction check joins pages on strong identifiers (invoice
and service-order numbers). A whole class of fact has no such identifier and
drifts silently: `dbt8` is `20.0.0.248` on one page and something else on
another because a host was rebuilt, a database consolidated, a service moved.
Nothing flags it, and the wrong address is copied into a command months later.

The rule is deliberately narrow, because a noisy linter trains people to
ignore the linter:

* Only `host → IPv4` pairs stated on the same line, where the host name looks
  like infrastructure (`dbt8`, `wms-5`, `orclpdb`, `nfs-server-1`) rather than
  prose.
* Session pages (`type: source`) are EXCLUDED. A journal entry is a dated
  record: "dbt6 was 20.0.0.31" stays true forever and contradicts nothing.
  Only pages that claim current truth are compared.
* Decommissioned mentions are ignored on the line level, so "dbt5
  (20.0.0.12, TERMINATED)" does not fight with the live host.
* It never picks a winner. Both sides are reported with their `updated` dates.
"""

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from . import frontmatter

_IPV4 = re.compile(r"\b((?:\d{1,3}\.){3}\d{1,3})\b")
# Infra-looking names: a letter-led token with a digit or dash inside, which
# is what hosts are called and what ordinary Portuguese words are not.
_HOST = re.compile(r"\b([a-z][a-z0-9]*(?:[-_][a-z0-9]+)*\d[a-z0-9\-_]*|[a-z]+-[a-z]+-\d+)\b")
_DEAD = re.compile(
    r"terminated|descomissionad|desativad|antig[oa]|deprecad|desligad|substitu[ií]d|"
    r"\bera\b|migrou|migrad[oa]|stopped|removid[oa]", re.IGNORECASE)
# Words that match the host shape but never name a host.
_NOT_HOSTS = {
    "ipv4", "ipv6", "rke2", "k8s", "pg18", "postgres18", "utf8", "cp1252", "sha256",
    "md5", "x86", "amd64", "arm64", "s3", "ec2", "m7i", "r6i", "t3a", "t4g",
    "e2e", "route53", "v1", "v2", "v3", "v4", "v5", "v6", "v7", "v8", "v9",
    "oauth2", "http2", "log4j", "utf16", "b2b", "p2p",
}
# Four dotted numbers are a version string as often as an address. Only accept
# the ones stated the way an address is stated: in code ticks, with a port,
# after an `@`, in a URL, or on a line that says it is talking about a host.
_ADDRESS_CONTEXT = re.compile(
    r"\bIPs?\b|\bhost(?:name)?\b|\bendere[çc]o|\bssh\b|://|@|\bTarget\b|\bDNS\b|"
    r"respond\w*|apont\w*|conect\w*|acess\w*|\bkubectl\b|\bping\b|\bpsql\b|\bcurl\b",
    re.IGNORECASE)
_VERSION_CONTEXT = re.compile(
    r"\bv\d|\bvers[ãa]o\b|\bversion\b|\brelease\b|\bbuild\b|\bservi[çc]o\b|\bpatch\b",
    re.IGNORECASE)


def _looks_like_address(line: str, ip: str) -> bool:
    if any(int(o) > 255 for o in ip.split(".")):
        return False
    ticked = f"`{ip}" in line or f"{ip}`" in line
    ported = re.search(re.escape(ip) + r":\d{2,5}", line) is not None
    at = re.search(r"@\s*" + re.escape(ip), line) is not None
    if _VERSION_CONTEXT.search(line) and not (ticked or ported or at):
        return False  # "Serviço Automático 1.1.0.15" is a version, not a host
    return ticked or ported or at or bool(_ADDRESS_CONTEXT.search(line))


@dataclass
class Endpoint:
    page: str
    updated: str
    line_no: int
    line: str


@dataclass
class Drift:
    host: str
    values: dict[str, list[Endpoint]]  # ip -> where it is claimed

    def message(self) -> str:
        parts = []
        for ip in sorted(self.values):
            where = ", ".join(f"{e.page} (updated {e.updated or '?'}, linha {e.line_no})"
                              for e in self.values[ip])
            parts.append(f"{ip} em {where}")
        return f"divergencia de endereco para '{self.host}': " + " vs ".join(parts)


def scan_page(path: Path, rel: str) -> list[tuple[str, str, Endpoint]]:
    """(host, ip, endpoint) for each host→IPv4 pair claimed as current."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    block, body = frontmatter.split(text)
    updated, offset, page_type = "", 0, ""
    if block:
        try:
            meta = frontmatter.parse(block)
            updated = str(meta.get("updated", ""))
            page_type = str(meta.get("type", ""))
        except frontmatter.FrontmatterError:
            pass
        offset = len(block.splitlines()) + 2
    if page_type == "source":
        return []  # dated record: it describes a moment, not the present
    out = []
    for i, line in enumerate(body.splitlines(), start=1 + offset):
        ips = _IPV4.findall(line)
        if not ips or _DEAD.search(line):
            continue
        if len(ips) != 1 or not _looks_like_address(line, ips[0]):
            continue  # two addresses on a line, or a version string wearing a disguise
        ip = ips[0]
        host = _host_for(line, ip)
        if host:
            out.append((host, ip, Endpoint(page=rel, updated=updated, line_no=i,
                                           line=line.strip()[:160])))
    return out


MAX_NAME_DISTANCE = 80


def _host_for(line: str, ip: str) -> str | None:
    """The name the address belongs to: the closest infra-looking token.

    Attaching every candidate on the line produced pairs like `v8 -> the LB
    address` from a routing table row. Two things make the association
    trustworthy: proximity (a 500-character prose line mentioning a host at
    the start and an address in the middle is not stating a fact about that
    host) and backticks, which is how this vault writes identifiers.
    """
    lowered = line.lower()
    pos = lowered.find(ip)
    candidates = []
    for m in _HOST.finditer(lowered):
        host = m.group(1)
        if host in _NOT_HOSTS or _IPV4.match(host) or len(host) < 3:
            continue
        distance = abs(m.start() - pos)
        if distance > MAX_NAME_DISTANCE:
            continue
        ticked = f"`{host}`" in lowered
        candidates.append((0 if ticked else 1, distance, host))
    if not candidates:
        return None
    return min(candidates)[2]


def find(pages: list[tuple[Path, str]]) -> list[Drift]:
    index: dict[str, dict[str, list[Endpoint]]] = defaultdict(lambda: defaultdict(list))
    for path, rel in pages:
        for host, ip, endpoint in scan_page(path, rel):
            index[host][ip].append(endpoint)

    drifts = []
    for host in sorted(index):
        values = index[host]
        if len(values) < 2:
            continue
        pages_involved = {e.page for eps in values.values() for e in eps}
        if len(pages_involved) < 2:
            continue  # one page listing a range of machines is not a conflict
        drifts.append(Drift(host=host, values={ip: eps for ip, eps in sorted(values.items())}))
    return drifts
