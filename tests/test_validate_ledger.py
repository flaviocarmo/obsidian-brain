from brainlib import validate


def test_chronological_ok():
    text = "# L\n\n## Pagamentos 10/03/2026\n\nx\n\n## Pagamentos 15/04/2026\n\ny\n"
    assert validate.check_ledger_chronology(text) == []


def test_out_of_order_warns():
    text = (
        "# L\n\n## Maio (2026-05-01)\n\nx\n\n## Junho (2026-06-01)\n\ny\n\n"
        "## Abril (2026-04-16)\n\nz\n"
    )
    warns = validate.check_ledger_chronology(text)
    assert len(warns) == 1 and "Abril" in warns[0]


def test_headings_without_dates_ignored():
    assert validate.check_ledger_chronology("# L\n\n## Contexto\n\nx\n") == []


def test_area_page_gets_warning_not_error(vault):
    p = vault / "wiki/contracts/Contrato Grande.md"
    text = p.read_text(encoding="utf-8").replace(
        "## Identificacao",
        "## Registro 05/06/2026\n\nz\n\n## Registro 01/05/2026",
    )
    p.write_text(text, encoding="utf-8")
    r = validate.validate_file(vault, p)
    assert r.ok and len(r.warnings) == 1
