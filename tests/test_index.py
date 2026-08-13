from brainlib import cli, index


def test_compile_lists_pages_by_folder(vault):
    index.compile(vault)
    out = (vault / "wiki/index.md").read_text(encoding="utf-8")
    assert "## contracts (1)" in out
    assert "- [[Contrato Grande]] (area, mature, 2026-06-01)" in out
    assert "hot" not in out.split("## ")[0].lower() or "[[hot]]" not in out


def test_subfolders_get_their_own_heading(vault):
    """One `domains` heading is a single block mixing every subject: the
    cheapest way to load the infra map was to load all of it. Per-subfolder
    headings make `extract --heading` able to pull one theme."""
    (vault / "wiki/domains/infra").mkdir(parents=True, exist_ok=True)
    (vault / "wiki/domains/geo").mkdir(parents=True, exist_ok=True)
    (vault / "wiki/domains/infra/Kubernetes.md").write_text(
        '---\ntype: concept\ntitle: "Kubernetes"\nstatus: mature\n---\ncorpo', encoding="utf-8")
    (vault / "wiki/domains/geo/GeoServer.md").write_text(
        '---\ntype: concept\ntitle: "GeoServer"\nstatus: mature\n---\ncorpo', encoding="utf-8")
    index.compile(vault)
    out = (vault / "wiki/index.md").read_text(encoding="utf-8")
    assert "## domains/infra (1)" in out and "## domains/geo (1)" in out
    assert "## domains (2)" not in out


def test_compile_skips_folds(vault):
    (vault / "wiki/folds/arquivo-velho.md").write_text(
        "---\ntype: meta\ntitle: \"X\"\n---\ncorpo", encoding="utf-8"
    )
    index.compile(vault)
    assert "arquivo-velho" not in (vault / "wiki/index.md").read_text(encoding="utf-8")


def test_compile_skips_meta(vault):
    (vault / "wiki/meta/lint-report.md").write_text(
        "---\ntype: meta\ntitle: \"Lint Report\"\n---\ncorpo", encoding="utf-8"
    )
    index.compile(vault)
    assert "lint-report" not in (vault / "wiki/index.md").read_text(encoding="utf-8")


def test_compile_is_idempotent_module_date(vault, monkeypatch):
    index.compile(vault)
    first = (vault / "wiki/index.md").read_text(encoding="utf-8")
    index.compile(vault)
    assert first == (vault / "wiki/index.md").read_text(encoding="utf-8")


def test_cli_compile_and_hot_check(vault, monkeypatch, capsys):
    monkeypatch.setenv("BRAIN_VAULT", str(vault))
    assert cli.main(["compile-index"]) == 0
    assert cli.main(["hot-check"]) == 0
    (vault / "wiki/hot.md").write_text(
        "---\ntype: meta\ntitle: \"Hot\"\nupdated: 2026-06-01\n---\n\n" + "w " * 501,
        encoding="utf-8",
    )
    assert cli.main(["hot-check"]) == 1
