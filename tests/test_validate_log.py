from brainlib import validate


def _log_text(vault):
    return (vault / "wiki/log.md").read_text(encoding="utf-8")


def test_first_sight_registers_and_passes(vault):
    r = validate.validate_file(vault, vault / "wiki/log.md")
    assert r.ok
    assert (vault / ".vault-meta/log-state.json").exists()


def test_append_at_top_passes(vault):
    validate.validate_file(vault, vault / "wiki/log.md")  # register
    old = _log_text(vault)
    block_end = old.index("\n---", 3) + len("\n---\n")
    new = old[:block_end] + "\n## [2026-06-15] Novissima\n\nx\n" + old[block_end:]
    (vault / "wiki/log.md").write_text(new, encoding="utf-8")
    assert validate.validate_file(vault, vault / "wiki/log.md").ok


def test_append_below_the_title_passes(vault):
    """The real log opens with '# Operations Log' and new entries go under it,
    so the old body is NOT a suffix of the new one. Hashing the whole body
    flagged every legitimate append as tampering, silently, for weeks."""
    validate.validate_file(vault, vault / "wiki/log.md")  # register
    old = _log_text(vault)
    anchor = "# Operations Log\n\n"
    new = old.replace(anchor, anchor + "## [2026-06-15] Novissima\n\nx\n\n", 1)
    (vault / "wiki/log.md").write_text(new, encoding="utf-8")
    r = validate.validate_file(vault, vault / "wiki/log.md")
    assert r.ok, r.errors


def test_stale_v1_state_rebaselines_instead_of_blocking(vault):
    import json
    validate.validate_file(vault, vault / "wiki/log.md")
    sp = vault / ".vault-meta/log-state.json"
    sp.write_text(json.dumps({"length": 999999, "sha256": "deadbeef"}), encoding="utf-8")  # v1 shape
    r = validate.validate_file(vault, vault / "wiki/log.md")
    assert r.ok
    assert json.loads(sp.read_text(encoding="utf-8"))["version"] == validate.LOG_STATE_VERSION


def test_middle_edit_fails(vault):
    validate.validate_file(vault, vault / "wiki/log.md")
    tampered = _log_text(vault).replace("Entrada velha", "Entrada adulterada")
    (vault / "wiki/log.md").write_text(tampered, encoding="utf-8")
    r = validate.validate_file(vault, vault / "wiki/log.md")
    assert not r.ok and any("append" in e for e in r.errors)


def test_first_append_to_empty_bodied_log_passes(vault):
    """body[-old_len:] with old_len == 0 used to return the whole body,
    falsely blocking the very first append to a log with no entries yet."""
    log = vault / "wiki/log.md"
    log.write_text("---\ntype: meta\ntitle: \"Log\"\nupdated: 2026-06-01\n---\n", encoding="utf-8")
    r = validate.validate_file(vault, log)
    assert r.ok  # registers state for the empty body

    log.write_text(
        "---\ntype: meta\ntitle: \"Log\"\nupdated: 2026-06-01\n---\n\n"
        "## [2026-06-01] Primeira entrada\n\nx\n",
        encoding="utf-8",
    )
    assert validate.validate_file(vault, log).ok


def test_by_brain_rewrites_state(vault):
    validate.validate_file(vault, vault / "wiki/log.md")
    (vault / "wiki/log.md").write_text("---\ntype: meta\ntitle: \"Log\"\nupdated: 2026-06-20\n---\n\nreescrito\n", encoding="utf-8")
    assert validate.validate_file(vault, vault / "wiki/log.md", by_brain=True).ok
    assert validate.validate_file(vault, vault / "wiki/log.md").ok  # state was refreshed
