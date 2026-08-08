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
