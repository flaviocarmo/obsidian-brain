from datetime import date

from brainlib import cli, fold, validate


TODAY = date(2026, 6, 20)


def test_plan_splits_by_age(vault):
    fp = fold.plan(vault, keep_days=30, today=TODAY)
    assert len(fp.keep) == 1 and "2026-06-01" in fp.keep[0]
    assert list(fp.archive) == ["2026-05"]
    assert "2026-05-01" in fp.archive["2026-05"][0]


def test_dry_run_does_not_touch_files(vault):
    before = (vault / "wiki/log.md").read_text(encoding="utf-8")
    fold.plan(vault, keep_days=30, today=TODAY)
    assert (vault / "wiki/log.md").read_text(encoding="utf-8") == before
    assert not list((vault / "wiki/folds").glob("log-archive-*.md"))


def test_apply_moves_and_updates_state(vault):
    validate.validate_file(vault, vault / "wiki/log.md")  # register state
    fp = fold.plan(vault, keep_days=30, today=TODAY)
    fold.apply(vault, fp)
    log = (vault / "wiki/log.md").read_text(encoding="utf-8")
    assert "2026-05-01" not in log and "2026-06-01" in log
    archive = (vault / "wiki/folds/log-archive-2026-05.md").read_text(encoding="utf-8")
    assert "Entrada velha" in archive
    # rewritten log passes validation because apply refreshed the state
    assert validate.validate_file(vault, vault / "wiki/log.md").ok


def test_apply_preserves_preamble(vault):
    """The real log.md has a "# Operations Log" preamble before the first
    entry; apply() used to silently drop everything before the first entry."""
    log = vault / "wiki/log.md"
    log.write_text(
        "---\ntype: meta\ntitle: \"Log\"\nupdated: 2026-06-01\n---\n\n"
        "# Operations Log\n\n"
        "## [2026-06-01] Entrada nova\n\ndetalhe\n\n"
        "## [2026-05-01] Entrada velha\n\ndetalhe\n",
        encoding="utf-8",
    )
    fp = fold.plan(vault, keep_days=30, today=TODAY)
    fold.apply(vault, fp)
    new_log = log.read_text(encoding="utf-8")
    assert "# Operations Log" in new_log
    assert new_log.index("# Operations Log") < new_log.index("## [2026-06-01]")


def test_apply_writes_backup_before_rewrite(vault):
    before = (vault / "wiki/log.md").read_text(encoding="utf-8")
    fp = fold.plan(vault, keep_days=30, today=TODAY)
    fold.apply(vault, fp)
    backup = vault / ".vault-meta/log.md.bak"
    assert backup.exists()
    assert backup.read_text(encoding="utf-8") == before


def test_apply_appends_to_existing_archive(vault):
    arch = vault / "wiki/folds/log-archive-2026-05.md"
    arch.write_text("---\ntype: meta\ntitle: \"Log Archive 2026-05\"\n---\n\n## [2026-05-20] Ja arquivada\n\nx\n", encoding="utf-8")
    fp = fold.plan(vault, keep_days=30, today=TODAY)
    fold.apply(vault, fp)
    text = arch.read_text(encoding="utf-8")
    assert "Ja arquivada" in text and "Entrada velha" in text


def test_cli_fold_missing_log_returns_2_no_traceback(vault, monkeypatch, capsys):
    (vault / "wiki/log.md").unlink()
    monkeypatch.setenv("BRAIN_VAULT", str(vault))
    rc = cli.main(["fold"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "Traceback" not in err


def test_size_cap_archives_past_the_date_cutoff(vault):
    """A date cutoff alone does not bound the file: 45 entries landed in 13
    days in the real vault, so 'last 30 days' still left a 50k-token log."""
    from datetime import date
    entries = "".join(
        f"## [2026-06-{day:02d}] Entrada {day}\n\n" + ("texto " * 400) + "\n\n"
        for day in range(1, 21)
    )
    (vault / "wiki/log.md").write_text(
        '---\ntype: meta\ntitle: "Log"\nupdated: 2026-06-20\n---\n\n# Operations Log\n\n' + entries,
        encoding="utf-8")
    generous = fold.plan(vault, keep_days=365, today=date(2026, 6, 21), max_tokens=10_000_000)
    assert len(generous.keep) == 20 and not generous.archive  # date rule alone keeps everything

    capped = fold.plan(vault, keep_days=365, today=date(2026, 6, 21), max_tokens=3000)
    assert len(capped.keep) < 20 and capped.archive
    kept_size = len("\n".join(capped.keep)) // 4
    assert kept_size <= 3000


def test_size_cap_keeps_the_newest_entries(vault):
    from datetime import date
    entries = "".join(
        f"## [2026-06-{day:02d}] Entrada {day}\n\n" + ("texto " * 400) + "\n\n"
        for day in (3, 2, 1)  # newest first, as the log is written
    )
    (vault / "wiki/log.md").write_text(
        '---\ntype: meta\ntitle: "Log"\nupdated: 2026-06-03\n---\n\n' + entries, encoding="utf-8")
    fp = fold.plan(vault, keep_days=365, today=date(2026, 6, 4), max_tokens=600)
    assert "Entrada 3" in "\n".join(fp.keep)
    assert any("Entrada 1" in e for entries in fp.archive.values() for e in entries)
