import json

from brainlib import validate


def _v(vault, rel, **kw):
    return validate.validate_file(vault, vault / rel, **kw)


def test_good_page_passes(vault):
    assert _v(vault, "wiki/journal/Pagina Um.md").ok


def test_missing_frontmatter_fails(vault):
    p = vault / "wiki/journal/Solta.md"
    p.write_text("# Sem frontmatter\n", encoding="utf-8")
    r = _v(vault, "wiki/journal/Solta.md")
    assert not r.ok and any("frontmatter" in e for e in r.errors)


def test_bad_type_and_status_fail(vault):
    p = vault / "wiki/journal/Ruim.md"
    p.write_text(
        "---\ntype: banana\ntitle: \"R\"\ncreated: 2026-01-01\nupdated: 2025-12-31\n"
        "tags: []\nstatus: verde\n---\ncorpo\n",
        encoding="utf-8",
    )
    r = _v(vault, "wiki/journal/Ruim.md")
    joined = " ".join(r.errors)
    assert "type" in joined and "status" in joined and "updated" in joined


def test_nested_frontmatter_fails(vault):
    p = vault / "wiki/journal/Nested.md"
    p.write_text("---\ntype: source\nmetadata:\n  a: b\n---\ncorpo\n", encoding="utf-8")
    assert not _v(vault, "wiki/journal/Nested.md").ok


def test_hot_over_500_words_fails(vault):
    hot = vault / "wiki/hot.md"
    hot.write_text(
        "---\ntype: meta\ntitle: \"Hot\"\nupdated: 2026-06-01\n---\n\n" + ("palavra " * 501),
        encoding="utf-8",
    )
    r = _v(vault, "wiki/hot.md")
    assert not r.ok and any("500" in e for e in r.errors)


def test_hot_anteriormente_heading_passes(vault):
    """A bare substring match on "anterior" false-flagged "anteriormente"."""
    hot = vault / "wiki/hot.md"
    hot.write_text(
        "---\ntype: meta\ntitle: \"Hot\"\nupdated: 2026-06-01\n---\n\n"
        "## Contexto anteriormente relevante\n\nok\n",
        encoding="utf-8",
    )
    assert _v(vault, "wiki/hot.md").ok


def test_hot_anterior_section_fails(vault):
    hot = vault / "wiki/hot.md"
    hot.write_text(
        "---\ntype: meta\ntitle: \"Hot\"\nupdated: 2026-06-01\n---\n\n"
        "## Last Updated\n\nok\n\n## Last Updated (anterior)\n\nnope\n",
        encoding="utf-8",
    )
    assert not _v(vault, "wiki/hot.md").ok


def test_index_blocked_unless_by_brain(vault):
    assert not _v(vault, "wiki/index.md").ok
    assert _v(vault, "wiki/index.md", by_brain=True).ok


def test_raw_new_ok_edit_fails(vault):
    raw = vault / ".raw" / "artigo.md"
    raw.write_text("original", encoding="utf-8")
    assert _v(vault, ".raw/artigo.md").ok          # first sighting: registered
    assert not _v(vault, ".raw/artigo.md").ok      # second write: immutable
    manifest = json.loads((vault / ".vault-meta/raw-manifest.json").read_text(encoding="utf-8"))
    assert "artigo.md" in manifest["files"]


def test_non_md_ignored(vault):
    (vault / "_attachments").mkdir(exist_ok=True)
    p = vault / "_attachments/foto.png"
    p.write_bytes(b"\x89PNG")
    assert _v(vault, "_attachments/foto.png").ok


def test_cli_validate(vault, monkeypatch, capsys):
    from brainlib import cli
    monkeypatch.setenv("BRAIN_VAULT", str(vault))
    assert cli.main(["validate", str(vault / "wiki/journal/Pagina Um.md")]) == 0
    assert cli.main(["validate", str(vault / "wiki/index.md")]) == 1
