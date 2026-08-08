import pytest

from brainlib import extract


def test_toc_levels_and_tokens(vault):
    text = (vault / "wiki/areas/Contrato Grande.md").read_text(encoding="utf-8")
    sections = extract.toc(text)
    titles = [s.title for s in sections]
    assert "Identificacao" in titles
    assert titles.count("Faturas 2026") == 2
    assert all(s.tokens > 0 for s in sections)


def test_get_section_includes_subsections(vault):
    text = (vault / "wiki/areas/Contrato Grande.md").read_text(encoding="utf-8")
    parts = extract.get_sections(text, "faturas 2026")
    assert len(parts) == 2
    assert "NFs emitidas" in parts[0]
    assert "Bloco duplicado" in parts[1]


def test_get_section_prefix_and_accent_insensitive_exact_first():
    text = "# T\n\n## Identificacao Completa\n\nA.\n\n## Ident\n\nB.\n"
    assert extract.get_sections(text, "ident") == ["## Ident\n\nB.\n"]
    assert "A." in extract.get_sections(text, "identificacao")[0]


def test_resolve_by_title_and_path(vault):
    p = extract.resolve_page(vault, "contrato grande")
    assert p.name == "Contrato Grande.md"
    p2 = extract.resolve_page(vault, "wiki/sources/Pagina Um.md")
    assert p2.name == "Pagina Um.md"


def test_resolve_missing_raises(vault):
    with pytest.raises(extract.ExtractError):
        extract.resolve_page(vault, "nao existe")


def test_big_page_estimate():
    body = "# T\n" + ("## S\n" + "x" * 400 + "\n") * 700  # ~280KB
    assert extract.estimate_tokens(body) > 8000


def test_resolve_permalink_beats_prefix(vault):
    """Permalink match should win over accidental prefix match."""
    wiki = vault / "wiki"
    # Create a page with permalink: abc
    (wiki / "sources/Permalink ABC.md").write_text(
        "---\ntype: source\ntitle: \"Permalink ABC\"\npermalink: abc\ncreated: 2026-05-01\nupdated: 2026-06-01\n---\n\nBody.\n",
        encoding="utf-8",
    )
    # Create another page whose stem starts with "abc"
    (wiki / "sources/Abcdef Page.md").write_text(
        "---\ntype: source\ntitle: \"Abcdef Page\"\ncreated: 2026-05-01\nupdated: 2026-06-01\n---\n\nBody.\n",
        encoding="utf-8",
    )
    # Resolve by "abc" should return the one with permalink, not the prefix match
    p = extract.resolve_page(vault, "abc")
    assert p.name == "Permalink ABC.md"
