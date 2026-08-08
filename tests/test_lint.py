import json as jsonlib

from brainlib import cli, index, lint


def _sev(findings, s):
    return [f for f in findings if f.severity == s]


def test_dead_wikilink_detected(vault):
    p = vault / "wiki/sources/ComLinkMorto.md"
    p.write_text(
        "---\ntype: source\ntitle: \"ComLinkMorto\"\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
        "tags: []\nstatus: seed\n---\n\nVer [[Pagina Fantasma]].\n",
        encoding="utf-8",
    )
    index.compile(vault)
    findings = lint.run(vault)
    assert any("Pagina Fantasma" in f.message for f in _sev(findings, "warning"))


def test_orphan_detected(vault):
    index.compile(vault)
    findings = lint.run(vault)
    # Pagina Um links Contrato Grande; nothing links Pagina Um -> orphan info
    assert any("Pagina Um" in f.message for f in _sev(findings, "info"))


def test_empty_section_detected(vault):
    p = vault / "wiki/concepts/Vazio.md"
    p.write_text(
        "---\ntype: concept\ntitle: \"Vazio\"\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
        "tags: []\nstatus: seed\n---\n\n# Vazio\n\n## Secao Vazia\n\n## Outra\n\ntexto\n",
        encoding="utf-8",
    )
    index.compile(vault)
    findings = lint.run(vault)
    assert any("Secao Vazia" in f.message for f in findings)


def test_empty_section_not_flagged_across_fence(vault):
    p = vault / "wiki/concepts/ComFence.md"
    p.write_text(
        "---\ntype: concept\ntitle: \"ComFence\"\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
        "tags: []\nstatus: seed\n---\n\n# ComFence\n\n## Passos\n\n"
        "```bash\n# comentario\necho oi\n```\n\ntexto final\n",
        encoding="utf-8",
    )
    index.compile(vault)
    findings = lint.run(vault)
    assert not any("Passos" in f.message for f in findings)


def test_recompile_after_lint_write_matches_page_count(vault, monkeypatch):
    """wiki/meta/ holds generated reports, not content pages: index must skip
    it like lint._pages() already does, or the two disagree forever."""
    monkeypatch.setenv("BRAIN_VAULT", str(vault))
    index.compile(vault)
    cli.main(["lint", "--write"])  # creates wiki/meta/lint-report.md
    index.compile(vault)  # recompile AFTER the report exists
    findings = lint.run(vault)
    count_warnings = [f for f in _sev(findings, "warning") if "index lists" in f.message]
    assert len(count_warnings) == 0


def test_bad_schema_is_error_and_exit_1(vault, monkeypatch):
    (vault / "wiki/sources/Quebrada.md").write_text("---\ntype: banana\n---\nx\n", encoding="utf-8")
    index.compile(vault)
    monkeypatch.setenv("BRAIN_VAULT", str(vault))
    assert cli.main(["lint"]) == 1


def test_json_output(vault, monkeypatch, capsys):
    index.compile(vault)
    monkeypatch.setenv("BRAIN_VAULT", str(vault))
    cli.main(["lint", "--json"])
    data = jsonlib.loads(capsys.readouterr().out)
    assert isinstance(data, list) and all("severity" in f for f in data)


def test_write_report(vault, monkeypatch):
    index.compile(vault)
    monkeypatch.setenv("BRAIN_VAULT", str(vault))
    cli.main(["lint", "--write"])
    report = vault / "wiki/meta/lint-report.md"
    assert report.exists()
    assert report.read_text(encoding="utf-8").startswith("---")


def test_write_report_does_not_self_pollute(vault, monkeypatch):
    index.compile(vault)
    monkeypatch.setenv("BRAIN_VAULT", str(vault))
    # First write
    cli.main(["lint", "--write"])
    # Second lint should not report index staleness or count mismatch caused by lint-report.md
    findings = lint.run(vault)
    staleness_warnings = [f for f in _sev(findings, "warning") if "older than newest page" in f.message]
    count_warnings = [f for f in _sev(findings, "warning") if "index lists" in f.message]
    assert len(staleness_warnings) == 0
    assert len(count_warnings) == 0


def test_write_report_creates_meta_directory(vault, monkeypatch):
    index.compile(vault)
    # Remove meta directory to test mkdir
    import shutil
    meta_dir = vault / "wiki/meta"
    shutil.rmtree(meta_dir)
    assert not meta_dir.exists()
    monkeypatch.setenv("BRAIN_VAULT", str(vault))
    cli.main(["lint", "--write"])
    report = vault / "wiki/meta/lint-report.md"
    assert report.exists()
    assert report.read_text(encoding="utf-8").startswith("---")
