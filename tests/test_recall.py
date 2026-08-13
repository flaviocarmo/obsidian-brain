import json
import subprocess

from brainlib import recall


def _bm_results(paths):
    return json.dumps({"results": [
        {"title": p.split("/")[-1], "file_path": p, "matched_chunk": "trecho"} for p in paths]})


def _fake_bm(hybrid, title):
    def run(cmd, **kwargs):
        out = _bm_results(title if "--title" in cmd else hybrid)
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")
    return run


def test_identifiers_are_extracted_from_the_query():
    ids = recall.identifiers_in("por que a NF 1142 do dbt8 em 20.0.0.248 ficou invertida")
    assert "1142" in ids and "20.0.0.248" in ids and "dbt8" in ids


def test_plain_words_yield_no_identifiers():
    assert recall.identifiers_in("por que o certificado nao renovou") == []


def test_grep_route_finds_the_exact_number(vault):
    """The page that literally says NF 1142 is the answer; an embedding blurs
    exactly this kind of token."""
    p = vault / "wiki/contracts/Ledger.md"
    p.write_text('---\ntype: area\ntitle: "Ledger"\ncreated: 2026-05-01\nupdated: 2026-06-01\n'
                 "tags: [x]\nstatus: mature\n---\n\n- NF 1142 emitida com liquido invertido\n",
                 encoding="utf-8")
    hits = recall.grep_identifiers(vault, ["1142"])
    assert hits and hits[0][0] == "wiki/contracts/Ledger.md"
    assert "1142" in hits[0][2]


def test_folds_and_meta_are_not_grepped(vault):
    (vault / "wiki/folds/velho.md").write_text("NF 9999 antiga", encoding="utf-8")
    assert recall.grep_identifiers(vault, ["9999"]) == []


def test_two_routes_outrank_one(vault, monkeypatch):
    """Reciprocal rank fusion: a page found twice beats a page found deeper by
    a single route."""
    p = vault / "wiki/contracts/Ledger.md"
    p.write_text('---\ntype: area\ntitle: "Ledger"\ncreated: 2026-05-01\nupdated: 2026-06-01\n'
                 "tags: [x]\nstatus: mature\n---\n\n- NF 1142 emitida\n", encoding="utf-8")
    monkeypatch.setattr(recall.subprocess, "run", _fake_bm(
        hybrid=["wiki/journal/Outra.md", "wiki/contracts/Ledger.md"],
        title=[]))
    results = recall.run(vault, "NF 1142")
    assert results[0].file_path == "wiki/contracts/Ledger.md"
    assert set(results[0].routes) == {"hybrid", "identifier"}
    assert results[0].score > results[1].score


def test_search_failure_degrades_to_grep(vault, monkeypatch):
    """basic-memory down must not take recall down with it."""
    p = vault / "wiki/contracts/Ledger.md"
    p.write_text('---\ntype: area\ntitle: "L"\ncreated: 2026-05-01\nupdated: 2026-06-01\n'
                 "tags: [x]\nstatus: mature\n---\n\nOS 115/2026 parada na fila\n", encoding="utf-8")

    def boom(cmd, **kwargs):
        raise OSError("basic-memory not found")

    monkeypatch.setattr(recall.subprocess, "run", boom)
    results = recall.run(vault, "OS 115/2026")
    assert results and results[0].routes == {"identifier": 1}


def test_malformed_search_output_is_ignored(vault, monkeypatch):
    monkeypatch.setattr(recall.subprocess, "run",
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout="nao e json", stderr=""))
    assert recall.run(vault, "qualquer coisa") == []


def test_rrf_score_is_rank_based():
    r = recall.Result(file_path="a", title="a", routes={"hybrid": 1})
    s = recall.Result(file_path="b", title="b", routes={"hybrid": 2})
    assert r.score > s.score
    both = recall.Result(file_path="c", title="c", routes={"hybrid": 5, "identifier": 5})
    assert both.score > r.score
