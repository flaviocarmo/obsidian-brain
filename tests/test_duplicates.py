from pathlib import Path

from brainlib import duplicates


def _p(rel: str) -> tuple[Path, str]:
    return Path(rel), f"wiki/{rel}"


def test_identical_titles_in_same_folder_are_flagged():
    found = duplicates.find([_p("journal/Sessao 2026-06-03 email-scan-corp-gap.md"),
                             _p("journal/Sessao 2026-06-04 email-scan-corp-gap.md")])
    assert len(found) == 1 and found[0].similarity == 1.0


def test_same_topic_across_folders_is_not_a_duplicate():
    """journal/ records the session, domains/ distils it: that is the pattern."""
    assert duplicates.find([_p("journal/Sessao 2026-05-22 SIMLAM2 Portal Credenciado E2E.md"),
                            _p("domains/platforms/SIMLAM2 Portal Credenciado E2E.md")]) == []


def test_session_date_prefix_does_not_make_pages_similar():
    assert duplicates.find([_p("journal/Sessao 2026-01-01 Postgres tuning no dbt8.md"),
                            _p("journal/Sessao 2026-01-02 Geoserver COG no S3.md")]) == []


def test_unrelated_titles_stay_below_threshold():
    assert duplicates.find([_p("domains/infra/Rancher RKE2 upgrade.md"),
                            _p("domains/infra/Gitlab registry policy.md")]) == []


def test_partial_overlap_below_threshold_is_ignored():
    found = duplicates.find([_p("domains/data/Postgres tuning para 64GB.md"),
                             _p("domains/data/Postgres upgrade 17 para 18.md")])
    assert found == []


def test_threshold_is_configurable():
    pages = [_p("domains/data/Postgres tuning para 64GB.md"),
             _p("domains/data/Postgres tuning para 32GB.md")]
    assert duplicates.find(pages, threshold=0.99) == []
    assert len(duplicates.find(pages, threshold=0.5)) == 1


def test_single_word_titles_are_skipped():
    """One token says nothing; comparing them produces noise, not signal."""
    assert duplicates.find([_p("domains/platforms/Orbit.md"),
                            _p("domains/platforms/Osmio.md")]) == []


def test_root_pages_group_together():
    found = duplicates.find([(Path("Visao geral do portfolio.md"), "wiki/Visao geral do portfolio.md"),
                             (Path("Visao geral portfolio.md"), "wiki/Visao geral portfolio.md")])
    assert len(found) == 1


def test_message_reports_both_pages_and_score():
    d = duplicates.find([_p("journal/Sessao 2026-06-03 email-scan-corp-gap.md"),
                         _p("journal/Sessao 2026-06-04 email-scan-corp-gap.md")])[0]
    msg = d.message()
    assert "100%" in msg and "2026-06-03" in msg and "2026-06-04" in msg


def test_results_sorted_by_similarity_desc():
    pages = [_p("domains/x/Alpha beta gama delta.md"),
             _p("domains/x/Alpha beta gama delta.md".replace("delta", "delta epsilon")),
             _p("domains/x/Alpha beta gama zeta.md")]
    found = duplicates.find(pages, threshold=0.5)
    assert found == sorted(found, key=lambda d: -d.similarity)


def test_lint_reports_duplicates_as_info(vault):
    from brainlib import lint
    fm = ("---\ntype: source\ntitle: \"T\"\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
          "tags: []\nstatus: mature\n---\n\ncorpo\n")
    for name in ("Sessao 2026-06-03 email-scan-corp-gap.md",
                 "Sessao 2026-06-04 email-scan-corp-gap.md"):
        (vault / "wiki" / "journal" / name).write_text(fm, encoding="utf-8")
    dups = [f for f in lint.run(vault) if "duplicata" in f.message]
    assert len(dups) == 1 and dups[0].severity == "info"


def test_digit_tokens_survive_and_distinguish_titles():
    """Ordinals are often the only discriminator; dropping them as 'short'
    made renamed-but-distinct pages look identical (real vault regression)."""
    a = duplicates.title_tokens("Sessao 2026-05-09 email-scan-deltas-3a-execucao")
    b = duplicates.title_tokens("Sessao 2026-05-09 email-scan-deltas-5a-execucao")
    assert "3a" in a and "5a" in b
    assert duplicates.similarity(a, b) < duplicates.SIMILARITY_THRESHOLD


def test_renamed_series_no_longer_flagged():
    pages = [_p("journal/Sessao 2026-05-27 email-scan-gap-corp-dia-1.md"),
             _p("journal/Sessao 2026-06-01 email-scan-gap-corp-dia-6.md"),
             _p("journal/Sessao 2026-06-03 email-scan-gap-corp-4a-execucao.md"),
             _p("journal/Sessao 2026-06-04 email-scan-gap-corp-5a-execucao.md")]
    assert duplicates.find(pages) == []
