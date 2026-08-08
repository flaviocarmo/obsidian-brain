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


def test_middle_edit_fails(vault):
    validate.validate_file(vault, vault / "wiki/log.md")
    tampered = _log_text(vault).replace("Entrada velha", "Entrada adulterada")
    (vault / "wiki/log.md").write_text(tampered, encoding="utf-8")
    r = validate.validate_file(vault, vault / "wiki/log.md")
    assert not r.ok and any("append" in e for e in r.errors)


def test_by_brain_rewrites_state(vault):
    validate.validate_file(vault, vault / "wiki/log.md")
    (vault / "wiki/log.md").write_text("---\ntype: meta\ntitle: \"Log\"\nupdated: 2026-06-20\n---\n\nreescrito\n", encoding="utf-8")
    assert validate.validate_file(vault, vault / "wiki/log.md", by_brain=True).ok
    assert validate.validate_file(vault, vault / "wiki/log.md").ok  # state was refreshed
