from brainlib import conflicts

FM = ("---\ntype: source\ntitle: \"{t}\"\ncreated: 2026-01-01\nupdated: {u}\n"
      "tags: []\nstatus: mature\n---\n\n")


def _page(vault, rel, updated, body, title="P"):
    p = vault / "wiki" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(FM.format(t=title, u=updated) + body, encoding="utf-8")
    return (p, f"wiki/{rel}")


def test_pending_newer_than_issued_is_reported(vault):
    a = _page(vault, "journal/Snap.md", "2026-05-10",
              "| OS 081/2026 | SIMCAR | NF 1130 emitida |\n")
    b = _page(vault, "contracts/Contrato X.md", "2026-08-07",
              "| pend | OS 081/2026 | aguardando emissao |\n")
    found = conflicts.find([a, b])
    assert len(found) == 1
    c = found[0]
    assert c.identifier == "081/2026" and c.kind == "OS"
    assert "contracts/Contrato X.md" in c.message()
    assert "journal/Snap.md" in c.message()


def test_issued_newer_than_pending_is_progress_not_conflict(vault):
    a = _page(vault, "journal/Velha.md", "2026-05-10", "OS 090/2026 aguardando emissao\n")
    b = _page(vault, "contracts/C.md", "2026-08-07", "OS 090/2026 NF 1140 emitida\n")
    assert conflicts.find([a, b]) == []


def test_same_page_never_conflicts_with_itself(vault):
    a = _page(vault, "contracts/C.md", "2026-08-07",
              "OS 091/2026 aguardando emissao\nOS 091/2026 emitida em julho\n")
    assert conflicts.find([a]) == []


def test_page_recording_both_states_counts_as_issued(vault):
    ledger = _page(vault, "contracts/Ledger.md", "2026-08-07",
                   "OS 092/2026 aguardando emissao\nOS 092/2026 depois: NF 1148 emitida\n")
    other = _page(vault, "journal/S.md", "2026-08-07", "OS 092/2026 NF 1148 emitida\n")
    assert conflicts.find([ledger, other]) == []


def test_line_number_is_file_relative_not_body_relative(vault):
    a = _page(vault, "contracts/A.md", "2026-08-07", "linha1\nOS 100/2026 aguardando\n")
    b = _page(vault, "journal/B.md", "2026-01-01", "OS 100/2026 emitida\n")
    found = conflicts.find([a, b])
    assert len(found) == 1
    pending = found[0].mentions[0]
    # frontmatter has 7 keys + 2 delimiters + blank line, so body line 2 is far below 2
    assert pending.line_no > 8


def test_identifier_kinds_are_detected(vault):
    a = _page(vault, "contracts/A.md", "2026-08-07",
              "NF 1200 aguardando\nFatura 89/2026 aguardando\nOS 105/2026 aguardando\n")
    b = _page(vault, "journal/B.md", "2026-01-01",
              "NF 1200 emitida\nFatura 89/2026 emitida\nOS 105/2026 emitida\n")
    kinds = {c.kind for c in conflicts.find([a, b])}
    assert kinds == {"NF", "Fatura", "OS"}


def test_unknown_identifier_in_one_page_only_is_ignored(vault):
    a = _page(vault, "contracts/A.md", "2026-08-07", "NF 1300 aguardando emissao\n")
    assert conflicts.find([a]) == []


def test_page_without_frontmatter_does_not_crash(vault):
    p = vault / "wiki" / "contracts" / "Solta.md"
    p.write_text("OS 110/2026 aguardando\n", encoding="utf-8")
    b = _page(vault, "journal/B.md", "2026-01-01", "OS 110/2026 emitida\n")
    conflicts.find([(p, "wiki/contracts/Solta.md"), b])  # sem excecao


def test_lint_surfaces_conflicts_as_warnings(vault):
    from brainlib import lint
    _page(vault, "journal/Snap.md", "2026-05-10", "OS 081/2026 NF 1130 emitida\n")
    _page(vault, "contracts/Contrato X.md", "2026-08-07", "OS 081/2026 aguardando emissao\n")
    msgs = [f.message for f in lint.run(vault) if "conflito em" in f.message]
    assert len(msgs) == 1
    assert all(f.severity == "warning" for f in lint.run(vault) if "conflito em" in f.message)
