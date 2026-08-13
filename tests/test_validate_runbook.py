from brainlib import validate

GOOD = """---
type: runbook
title: "Certificado nao renovou"
created: 2026-08-13
updated: 2026-08-13
tags: [cert-manager]
status: mature
---

# Certificado nao renovou

## Quando usar

Navegador reclama de certificado expirado num host do cluster.

## Pre-requisitos

VPN ativa (sem ela nao ha kubectl).

## Passos

1. Olhe o certificado servido.
2. Reinicie o controller.

## Verificacao

`curl` sem `-k` devolve 200 e a data nova aparece no secret.
"""


def _write(vault, text, name="Runbook Teste.md"):
    p = vault / "wiki/domains" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def test_complete_runbook_passes(vault):
    p = _write(vault, GOOD)
    r = validate.validate_file(vault, p)
    assert r.ok, r.errors


def test_runbook_without_verification_is_rejected(vault):
    """The section every informal runbook omits is the one that says whether
    the procedure worked."""
    p = _write(vault, GOOD.replace("## Verificacao", "## Notas"))
    r = validate.validate_file(vault, p)
    assert not r.ok and any("verificacao" in e for e in r.errors)


def test_runbook_without_steps_is_rejected(vault):
    p = _write(vault, GOOD.replace("## Passos", "## Historia"))
    r = validate.validate_file(vault, p)
    assert not r.ok and any("passos" in e for e in r.errors)


def test_accented_headings_are_accepted(vault):
    p = _write(vault, GOOD.replace("## Verificacao", "## Verificação")
                          .replace("## Quando usar", "## Quando Usar"))
    assert validate.validate_file(vault, p).ok


def test_other_types_are_not_checked_for_sections(vault):
    p = _write(vault, GOOD.replace("type: runbook", "type: concept")
                          .replace("## Verificacao", "## Notas"))
    assert validate.validate_file(vault, p).ok


def test_runbook_is_a_valid_type(vault):
    assert "runbook" in validate.TYPES
    assert validate.check_schema({"type": "runbook", "title": "x", "created": "2026-08-13",
                                  "updated": "2026-08-13", "tags": [], "status": "seed"}) == []
