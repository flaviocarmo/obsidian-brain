import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


@pytest.fixture
def vault(tmp_path):
    """Minimal Modo D vault used across tests."""
    wiki = tmp_path / "wiki"
    for sub in ("contracts", "journal", "domains", "people", "meta", "folds"):
        (wiki / sub).mkdir(parents=True)
    (tmp_path / ".raw").mkdir()
    (tmp_path / ".vault-meta").mkdir()

    def page(rel, title, type_="source", status="mature", body="Corpo.\n", extra=""):
        text = (
            "---\n"
            f"type: {type_}\n"
            f'title: "{title}"\n'
            "created: 2026-05-01\n"
            "updated: 2026-06-01\n"
            "tags: [teste]\n"
            f"status: {status}\n"
            f"{extra}"
            "---\n\n"
            f"{body}"
        )
        p = wiki / rel
        p.write_text(text, encoding="utf-8")
        return p

    page("journal/Pagina Um.md", "Pagina Um", body="# Pagina Um\n\nTexto A.\n\nLink [[Contrato Grande]].\n")
    page(
        "contracts/Contrato Grande.md",
        "Contrato Grande",
        type_="area",
        body=(
            "# Contrato Grande\n\n"
            "## Identificacao\n\nDados.\n\n"
            "## Faturas 2026\n\nFatura 1.\n\n"
            "### NFs emitidas\n\nNF 100.\n\n"
            "## Faturas 2026\n\nBloco duplicado.\n"
        ),
    )
    (wiki / "hot.md").write_text(
        "---\ntype: meta\ntitle: \"Hot Cache\"\nupdated: 2026-06-01\n---\n\n# Recent Context\n\nCurto.\n",
        encoding="utf-8",
    )
    (wiki / "log.md").write_text(
        "---\ntype: meta\ntitle: \"Log\"\nupdated: 2026-06-01\n---\n\n"
        "## [2026-06-01] Entrada nova\n\ndetalhe\n\n"
        "## [2026-05-01] Entrada velha\n\ndetalhe\n",
        encoding="utf-8",
    )
    (wiki / "index.md").write_text("---\ntype: meta\ntitle: \"Wiki Index\"\nupdated: 2026-06-01\n---\n# Wiki Index\n", encoding="utf-8")
    return tmp_path
