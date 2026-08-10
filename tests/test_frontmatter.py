import pytest

from brainlib import frontmatter as fm

DOC = """---
type: source
title: "Pagina de Teste: com dois-pontos"
created: 2026-05-06
updated: 2026-05-10
tags:
- financeiro
- notas-fiscais
status: mature
related:
- "[[Outra Pagina]]"
sources: []
---

# Corpo

Texto.
"""


def test_split():
    block, body = fm.split(DOC)
    assert block is not None and block.startswith("type: source")
    assert body.startswith("\n# Corpo")


def test_split_no_frontmatter():
    block, body = fm.split("# Sem nada\n")
    assert block is None and body == "# Sem nada\n"


def test_parse_scalars_and_lists():
    meta = fm.parse(fm.split(DOC)[0])
    assert meta["type"] == "source"
    assert meta["title"] == "Pagina de Teste: com dois-pontos"
    assert meta["tags"] == ["financeiro", "notas-fiscais"]
    assert meta["related"] == ["[[Outra Pagina]]"]
    assert meta["sources"] == []


def test_inline_list():
    meta = fm.parse("tags: [a, b, c]")
    assert meta["tags"] == ["a", "b", "c"]


def test_nested_object_rejected():
    with pytest.raises(fm.FrontmatterError):
        fm.parse("metadata:\n  type: user")


def test_roundtrip():
    block, _ = fm.split(DOC)
    meta = fm.parse(block)
    again = fm.parse(fm.split(fm.serialize(meta) + "\ncorpo")[0])
    assert again == meta


def test_folded_list_item_round_trips_into_one_item():
    """A quoted list item wrapped at ~80 cols (2-space continuation indent)
    must fold into a single item, not be misread as a nested mapping."""
    block = (
        "type: source\n"
        "title: \"T\"\n"
        "related:\n"
        "- '[[Sessao 2026-07-28 Link de Senha do SmartGIS Prefeitura - Rota Migrada e CR no\n"
        "  ConfigMap]]'\n"
    )
    meta = fm.parse(block)
    assert len(meta["related"]) == 1
    assert "ConfigMap]]" in meta["related"][0]
    assert meta["related"][0].startswith("[[Sessao 2026-07-28")


def test_folded_scalar_concatenates():
    block = (
        "type: source\n"
        "verdict: Playwright MCP fica como default local; browser-use\n"
        "  so pra scraping massivo.\n"
    )
    meta = fm.parse(block)
    assert meta["verdict"] == (
        "Playwright MCP fica como default local; browser-use so pra scraping massivo."
    )


def test_true_nested_mapping_still_rejected():
    with pytest.raises(fm.FrontmatterError):
        fm.parse("related:\n  child: value\n")


def test_hash_in_tags_is_rejected():
    """'#' opens a YAML comment: `tags: [#a, #b]` is a sequence that never
    closes. Real vault regression: basic-memory failed to parse and prepended
    a second frontmatter block, breaking three digest-generated pages."""
    with pytest.raises(fm.FrontmatterError):
        fm.parse("tags: [#deploy, #kubernetes]")
    with pytest.raises(fm.FrontmatterError):
        fm.parse("tags:\n- #deploy")


def test_hash_inside_quotes_is_allowed():
    """Inside quotes '#' is literal YAML; rejecting it would block legitimate
    titles like 'NF #1130'."""
    assert fm.parse('title: "Custo #1 do projeto"')["title"] == "Custo #1 do projeto"
    assert fm.parse("title: 'NF #1130 corrigida'")["title"] == "NF #1130 corrigida"


def test_hash_mid_token_is_allowed():
    assert fm.parse("permalink: work/wiki/pagina#secao")["permalink"] == "work/wiki/pagina#secao"


def test_trailing_comment_is_rejected():
    with pytest.raises(fm.FrontmatterError):
        fm.parse("status: mature # revisar depois")
