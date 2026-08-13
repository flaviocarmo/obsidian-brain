"""Noise scoring for pages: what got pasted in and never digested.

Adapted from the idea in Mnemosyne's memory hygiene, with one inversion that
matters here. Their subject is agent memory rows, where a stack trace is
almost always junk. This vault is technical: code, commands and configuration
are the *value*. What is noise here is **undigested execution output** — 200
lines of `kubectl get pods`, a raw traceback, a directory listing — pasted
into a page and never turned into a claim about the world.

Two properties are copied deliberately because they are what keep a linter
worth reading:

* The score is **not additive**. Each rule raises it to at least its own
  floor, so one strong signal is enough and three weak ones never compound
  into a false positive.
* A page that states something (`decidimos`, `causa`, `porque`, `nunca`,
  `regra`) is **clamped to 0.3**, however much output it also carries. A
  session page that shows the log AND explains it is exactly what we want.

Deterministic: regex and arithmetic, no LLM, no embeddings. Same answer twice.
"""

import re
from dataclasses import dataclass, field

# Lines that are machine output rather than authored text.
_TERMINAL = re.compile(
    r"^(?:\s*)(?:drwx|[-l]rw[-x]|total \d+|Collecting |Requirement already satisfied|"
    r"npm (?:warn|error)|WARNING: |\d+ upgraded, \d+ newly installed|"
    r"Reading package lists|Get:\d+ http|Unpacking |Setting up |"
    r"\[INFO\]|\[DEBUG\]|\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}|"
    r"NAME\s+READY\s+STATUS|NAME\s+TYPE\s+CLUSTER-IP)", re.MULTILINE)
_STACK = re.compile(r"^\s*(?:Traceback \(most recent call last\)|  File \"|\s+at [\w.$]+\(|"
                    r"Caused by: |\tat [\w.$]+\()", re.MULTILINE)
# A row of a CLI table: three or more columns split by runs of spaces, no
# sentence punctuation. `kubectl get pods` pasted raw is mostly these, and no
# single line of it matches a keyword pattern.
_TABLE_ROW = re.compile(r"^\S+(?: {2,}\S+){2,}\s*$")
# `**Campo**: valor` and `Campo: valor` — the shape of a fact sheet.
_FIELD = re.compile(r"^\*{0,2}[A-Za-zÀ-ÿ][\w À-ÿ/()-]{2,40}\*{0,2}\s*:\s+\S")
# Writing that makes a claim: the page is doing its job whatever else is in it.
_VALUE = re.compile(
    r"\bdecid|\bdecis|\bporque\b|\bcausa\b|\bmotivo\b|\bregra\b|\bconven[çc]|"
    r"\bsempre\b|\bnunca\b|\bevit|\bprefer|\bconclus|\blicao\b|\bli[çc][ãa]o\b|"
    r"\barquitetur|\btrade-?off|\bpendencia\b|\bpend[êe]ncia\b|\bproxim[ao] passo|"
    r"\bfica\b.*\bpendente\b|\bresolv", re.IGNORECASE)

TERMINAL_DUMP = 0.85
STACK_TRACE = 0.8
LIKELY_DUMP = 0.65
THIN_PAGE = 0.5
VALUE_CLAMP = 0.3
REPORT_AT = 0.5


@dataclass
class Noise:
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)

    def raise_to(self, value: float, reason: str) -> None:
        """Floor, not sum: one strong signal decides, weak ones do not stack."""
        self.reasons.append(reason)
        self.score = max(self.score, value)

    def message(self) -> str:
        return (f"page reads as undigested output (score {self.score:.2f}): "
                f"{', '.join(self.reasons)}; destile o que ficou provado ou "
                f"mova o bruto para .raw/")


def _outside_code_fences(body: str) -> str:
    """Text with fenced blocks removed.

    Output inside a fence is quoted evidence and usually fine; the same output
    dumped raw into the prose is what nobody ever reads again.
    """
    out, fenced = [], False
    for line in body.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if not fenced:
            out.append(line)
    return "\n".join(out)


def score(body: str) -> Noise:
    n = Noise()
    prose = _outside_code_fences(body)
    lines = [l for l in prose.splitlines() if l.strip()]
    stripped = prose.strip()

    if not stripped:
        n.raise_to(THIN_PAGE, "empty_body")
        return n

    table_rows = sum(1 for l in lines if _TABLE_ROW.match(l) and not l.lstrip().startswith(("|", "-", "*", ">")))
    terminal_hits = len(_TERMINAL.findall(prose)) + table_rows
    if terminal_hits >= 5 and terminal_hits / max(1, len(lines)) > 0.25:
        n.raise_to(TERMINAL_DUMP, f"terminal_output ({terminal_hits} linhas)")
    if len(_STACK.findall(prose)) >= 3:
        n.raise_to(STACK_TRACE, "stack_trace")

    # Structured markdown (bullets, tables, headings, `**Campo**: valor`) has
    # few full sentences by construction — a person page or a checklist is not
    # a dump. Only unstructured lines count toward the sentence ratio.
    structured = sum(1 for l in lines
                     if l.lstrip().startswith(("-", "*", "|", ">", "#", "1.", "2.", "3."))
                     or _FIELD.match(l.lstrip()))
    freeform = len(lines) - structured
    sentences = stripped.count(". ") + stripped.count(".\n") + stripped.count("?") + stripped.count("!")
    if freeform >= 30 and len(stripped) >= 1000 and sentences < freeform / 10:
        n.raise_to(LIKELY_DUMP, f"likely_dump ({freeform} linhas sem estrutura, {sentences} frases)")

    # Thinness is judged on the whole body: a page whose substance is a large
    # code block is not thin, it is a code page.
    whole = body.strip()
    if len(whole) < 200 and len(whole.splitlines()) < 5:
        n.raise_to(THIN_PAGE, "thin_page")

    if n.score and _VALUE.search(prose):
        n.score = min(n.score, VALUE_CLAMP)
        n.reasons.append("clamped: a pagina afirma algo")
    return n
