import subprocess

import pytest

from brainlib import models, validate


@pytest.fixture
def model_page(vault):
    path = models.scaffold(vault, "Qual e a topologia do cluster?")
    return path


def test_scaffold_creates_a_valid_placeholder(vault):
    path = models.scaffold(vault, "Qual e o estado do contrato 071?")
    text = path.read_text(encoding="utf-8")
    assert "type: model" in text and 'question: "Qual e o estado do contrato 071?"' in text
    assert validate.validate_file(vault, path).ok


def test_model_without_question_is_rejected(vault, model_page):
    text = model_page.read_text(encoding="utf-8").replace(
        'question: "Qual e a topologia do cluster?"\n', "")
    model_page.write_text(text, encoding="utf-8")
    report = validate.validate_file(vault, model_page)
    assert not report.ok and any("question" in e for e in report.errors)


def test_model_without_body_is_rejected(vault, model_page):
    block = model_page.read_text(encoding="utf-8").split("---\n")[1]
    model_page.write_text(f"---\n{block}---\n\n#\n", encoding="utf-8")
    report = validate.validate_file(vault, model_page)
    assert not report.ok and any("sem corpo" in e for e in report.errors)


def test_load_reads_question_and_title(vault, model_page):
    loaded = models.load(vault)
    assert len(loaded) == 1 and loaded[0].question == "Qual e a topologia do cluster?"


def test_refresh_skips_models_whose_evidence_did_not_change(vault, model_page, monkeypatch):
    """No change, no LLM call: a nightly job that always spends is a job that
    gets turned off."""
    monkeypatch.setattr(models, "evidence_changed_since", lambda *a: False)
    called = []
    monkeypatch.setattr(models.subprocess, "run", lambda *a, **k: called.append(1))
    assert models.refresh(vault) == [] and not called


def test_refresh_rolls_back_an_invalid_rewrite(vault, model_page, monkeypatch):
    before = model_page.read_text(encoding="utf-8")

    def fake_run(cmd, **kwargs):
        model_page.write_text("---\ntype: model\ntitle: \"X\"\n---\n\nsem question\n", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(models, "evidence_changed_since", lambda *a: True)
    monkeypatch.setattr(models.subprocess, "run", fake_run)
    monkeypatch.setattr(models.recall, "run", lambda *a, **k: [])
    out = models.refresh(vault)
    assert "restaurado" in out[0]
    assert model_page.read_text(encoding="utf-8") == before


def test_refresh_accepts_a_valid_rewrite(vault, model_page, monkeypatch):
    good = ('---\ntype: model\ntitle: "Qual e a topologia do cluster?"\n'
            'question: "Qual e a topologia do cluster?"\ncreated: 2026-08-13\n'
            "updated: 2026-08-13\ntags: [mental-model]\nstatus: mature\n---\n\n"
            "# Topologia\n\nTres control-plane e tres workers, tudo em VPC privada com VPN.\n")

    def fake_run(cmd, **kwargs):
        assert kwargs.get("env", {}).get("BRAIN_DIGEST") == "1"  # never enqueue itself
        model_page.write_text(good, encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(models, "evidence_changed_since", lambda *a: True)
    monkeypatch.setattr(models.subprocess, "run", fake_run)
    monkeypatch.setattr(models.recall, "run", lambda *a, **k: [])
    assert models.refresh(vault) == ["Qual e a topologia do cluster.md: atualizado"]


def test_refresh_respects_the_limit(vault, monkeypatch):
    for q in ("Pergunta um?", "Pergunta dois?", "Pergunta tres?"):
        models.scaffold(vault, q)
    monkeypatch.setattr(models, "evidence_changed_since", lambda *a: True)
    monkeypatch.setattr(models, "refresh_one", lambda *a, **k: "ok")
    assert len(models.refresh(vault, limit=2)) == 2


def test_prompt_pins_the_question_and_forbids_other_files(vault, model_page):
    m = models.load(vault)[0]
    prompt = models.build_prompt(vault, m, [])
    assert m.question in prompt
    assert "NAO escreva em nenhum outro arquivo" in prompt
    assert "SOBRESCRITO" in prompt
