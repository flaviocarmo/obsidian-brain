import pytest

from brainlib import split

PAGE = """---
type: concept
title: "Pagina Grande"
created: 2026-05-01
updated: 2026-06-01
tags: [infra, k8s]
status: mature
---

# Pagina Grande

Intro que fica.

## Diagnostico

Passo a passo do diagnostico.

Mais uma linha.

## Correcao

Como consertar.
"""


@pytest.fixture
def page(vault):
    p = vault / "wiki/domains/Pagina Grande.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(PAGE, encoding="utf-8")
    return p


def test_plan_does_not_write_anything(vault, page):
    before = page.read_text(encoding="utf-8")
    p = split.plan(vault, "Pagina Grande", "Diagnostico")
    assert not p.new_page.exists()
    assert page.read_text(encoding="utf-8") == before
    assert "Diagnostico" in p.describe(vault) and "--apply" in p.describe(vault)


def test_apply_moves_the_body_and_keeps_the_heading(vault, page):
    """Deleting the heading is how a manual split breaks [[Page#Section]]
    anchors; the pointer goes under a heading that stays."""
    p = split.plan(vault, "Pagina Grande", "Diagnostico")
    split.apply(p)
    source = page.read_text(encoding="utf-8")
    assert "## Diagnostico" in source
    assert "Passo a passo do diagnostico." not in source
    assert "Movido para [[Diagnostico]]" in source
    assert "## Correcao" in source and "Intro que fica." in source
    new = p.new_page.read_text(encoding="utf-8")
    assert "Passo a passo do diagnostico." in new


def test_new_page_inherits_type_status_and_tags(vault, page):
    """A new page that fails the schema validator on arrival is a split that
    made more work than it saved."""
    p = split.plan(vault, "Pagina Grande", "Diagnostico")
    split.apply(p)
    from brainlib import validate
    report = validate.validate_file(vault, p.new_page)
    assert report.ok, report.errors
    text = p.new_page.read_text(encoding="utf-8")
    assert "type: concept" in text and "status: mature" in text and "tags: [infra, k8s]" in text


def test_destination_folder_and_custom_title(vault, page):
    p = split.plan(vault, "Pagina Grande", "Correcao", to="domains/infra",
                   title="Runbook de Correcao")
    split.apply(p)
    assert p.new_page == vault / "wiki/domains/infra/Runbook de Correcao.md"
    assert "Movido para [[Runbook de Correcao]]" in page.read_text(encoding="utf-8")


def test_missing_section_is_an_error(vault, page):
    with pytest.raises(split.SplitError, match="nao encontrada"):
        split.plan(vault, "Pagina Grande", "Secao Que Nao Existe")


def test_existing_destination_is_refused(vault, page):
    (vault / "wiki/domains/Diagnostico.md").write_text("ja existe", encoding="utf-8")
    with pytest.raises(split.SplitError, match="ja existe"):
        split.plan(vault, "Pagina Grande", "Diagnostico")


def test_anchor_links_are_reported(vault, page):
    other = vault / "wiki/domains/Outra.md"
    other.write_text('---\ntype: concept\ntitle: "Outra"\ncreated: 2026-05-01\n'
                     'updated: 2026-05-01\ntags: [x]\nstatus: seed\n---\n\n'
                     "ver [[Pagina Grande#Diagnostico]] para detalhes\n", encoding="utf-8")
    p = split.plan(vault, "Pagina Grande", "Diagnostico")
    assert "wiki/domains/Outra.md" in p.anchor_links


def test_cli_dry_run_then_apply(vault, page, monkeypatch, capsys):
    from brainlib import cli
    monkeypatch.setenv("BRAIN_VAULT", str(vault))
    assert cli.main(["split", "Pagina Grande", "--heading", "Diagnostico"]) == 0
    assert not (vault / "wiki/domains/Diagnostico.md").exists()
    assert cli.main(["split", "Pagina Grande", "--heading", "Diagnostico", "--apply"]) == 0
    assert (vault / "wiki/domains/Diagnostico.md").is_file()
