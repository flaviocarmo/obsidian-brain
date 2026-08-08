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
