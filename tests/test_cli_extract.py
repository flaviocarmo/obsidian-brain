from brainlib import cli


def test_extract_toc(vault, capsys, monkeypatch):
    monkeypatch.setenv("BRAIN_VAULT", str(vault))
    rc = cli.main(["extract", "Contrato Grande", "--toc"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Faturas 2026" in out and "tokens" in out


def test_extract_heading(vault, capsys, monkeypatch):
    monkeypatch.setenv("BRAIN_VAULT", str(vault))
    rc = cli.main(["extract", "Contrato Grande", "--heading", "identificacao"])
    out = capsys.readouterr().out
    assert rc == 0 and "Dados." in out


def test_extract_small_page_returns_full(vault, capsys, monkeypatch):
    monkeypatch.setenv("BRAIN_VAULT", str(vault))
    rc = cli.main(["extract", "Pagina Um"])
    assert rc == 0 and "Texto A." in capsys.readouterr().out


def test_extract_big_page_returns_toc(vault, capsys, monkeypatch):
    big = "# T\n\n" + "".join(f"## Sec {i}\n" + "x" * 2000 + "\n" for i in range(60))
    page = vault / "wiki/journal/Grande.md"
    page.write_text(
        "---\ntype: source\ntitle: \"Grande\"\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
        "tags: []\nstatus: mature\n---\n\n" + big,
        encoding="utf-8",
    )
    monkeypatch.setenv("BRAIN_VAULT", str(vault))
    rc = cli.main(["extract", "Grande"])
    out = capsys.readouterr().out
    assert rc == 0 and "--heading" in out and "xxxx" not in out


def test_extract_toc_level_zero_is_honored(vault, capsys, monkeypatch):
    """`if args.level:` treated --level 0 as falsy and skipped the filter
    entirely; 0 is a legitimate (if degenerate) level filter."""
    monkeypatch.setenv("BRAIN_VAULT", str(vault))
    rc = cli.main(["extract", "Contrato Grande", "--toc", "--level", "0"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Identificacao" not in out
    assert "Faturas 2026" not in out


def test_extract_missing_page(vault, capsys, monkeypatch):
    monkeypatch.setenv("BRAIN_VAULT", str(vault))
    assert cli.main(["extract", "Nao Existe"]) == 1
