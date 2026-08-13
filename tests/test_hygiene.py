from brainlib import hygiene

KUBECTL_DUMP = "\n".join(
    ["NAME                     READY   STATUS    RESTARTS   AGE"]
    + [f"pod-{i}-abcdef           1/1     Running   0          {i}d" for i in range(12)]
)

APT_DUMP = "\n".join([
    "Reading package lists...",
    "Get:1 http://archive.ubuntu.com jammy InRelease",
    "Collecting fastembed",
    "Requirement already satisfied: numpy",
    "Unpacking libpq5 (14.9-0ubuntu0.22.04.1)",
    "Setting up libpq5 (14.9-0ubuntu0.22.04.1)",
    "12 upgraded, 3 newly installed",
])

TRACE = "\n".join([
    "Traceback (most recent call last):",
    '  File "app.py", line 12, in <module>',
    '  File "lib.py", line 40, in run',
    "ValueError: boom",
])


def test_pasted_terminal_output_scores_high():
    n = hygiene.score(KUBECTL_DUMP)
    assert n.score >= hygiene.TERMINAL_DUMP
    assert any("terminal_output" in r for r in n.reasons)


def test_apt_output_scores_high():
    assert hygiene.score(APT_DUMP).score >= hygiene.TERMINAL_DUMP


def test_stack_trace_scores_high():
    n = hygiene.score(TRACE)
    assert n.score >= hygiene.STACK_TRACE and "stack_trace" in n.reasons


def test_a_page_that_states_something_is_clamped():
    """A session page that shows the log AND explains it is exactly what the
    vault is for; only undigested output is noise."""
    body = (KUBECTL_DUMP + "\n\nA causa foi o liveness apontando para a porta errada; "
            "a regra que fica: nunca copiar o probe do template sem conferir a porta.\n")
    n = hygiene.score(body)
    assert n.score <= hygiene.VALUE_CLAMP
    assert any("clamped" in r for r in n.reasons)
    assert n.score < hygiene.REPORT_AT  # therefore not reported


def test_output_inside_a_code_fence_is_evidence_not_noise():
    fenced = "Rodei o comando e o resultado abaixo prova o ponto:\n\n```\n" + KUBECTL_DUMP + "\n```\n"
    assert hygiene.score(fenced).score < hygiene.REPORT_AT


def test_score_is_a_floor_not_a_sum():
    """Three weak signals must not add up into a false positive."""
    n = hygiene.Noise()
    n.raise_to(0.5, "a")
    n.raise_to(0.5, "b")
    n.raise_to(0.4, "c")
    assert n.score == 0.5


def test_normal_technical_prose_is_quiet():
    body = (
        "# Cutover do pgbouncer\n\n"
        "O `DB_SERVER` passou a apontar para o pooler porque o pgpool nao sobrevivia "
        "ao restart do banco. A decisao foi tomada em 14/07 e o rollback exige redeploy.\n\n"
        "```bash\nkubectl -n geocloud-prod rollout restart deploy/api\n```\n\n"
        "O sizing foi validado com dez dias de metrica: pico de 38 conexoes ativas.\n"
    )
    assert hygiene.score(body).score < hygiene.REPORT_AT


def test_thin_page_is_flagged():
    assert hygiene.score("ok\n").score >= hygiene.THIN_PAGE


def test_empty_body_is_flagged():
    n = hygiene.score("   \n\n")
    assert n.score >= hygiene.THIN_PAGE and "empty_body" in n.reasons


def test_fact_sheet_is_not_a_dump():
    """A person page or a checklist has few full sentences by construction;
    counting them as a dump flagged a legitimate page in the real vault."""
    body = "# Fulano\n\n## Identificacao\n\n" + "\n".join(
        f"- **Campo {i}**: valor {i} do registro" for i in range(40))
    assert hygiene.score(body).score < hygiene.REPORT_AT


def test_unstructured_dump_still_scores():
    body = "\n".join(f"linha crua {i} sem pontuacao alguma seguindo direto" for i in range(40))
    n = hygiene.score(body)
    assert n.score >= hygiene.LIKELY_DUMP and any("likely_dump" in r for r in n.reasons)
