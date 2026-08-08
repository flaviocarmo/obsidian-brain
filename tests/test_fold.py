from datetime import date

from brainlib import fold, validate


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


def test_apply_appends_to_existing_archive(vault):
    arch = vault / "wiki/folds/log-archive-2026-05.md"
    arch.write_text("---\ntype: meta\ntitle: \"Log Archive 2026-05\"\n---\n\n## [2026-05-20] Ja arquivada\n\nx\n", encoding="utf-8")
    fp = fold.plan(vault, keep_days=30, today=TODAY)
    fold.apply(vault, fp)
    text = arch.read_text(encoding="utf-8")
    assert "Ja arquivada" in text and "Entrada velha" in text
