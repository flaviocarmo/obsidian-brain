from brainlib import secrets

FM = '---\ntype: source\ntitle: "P"\ncreated: 2026-08-01\nupdated: 2026-08-01\ntags: [x]\nstatus: seed\n---\n\n'


def _scan(body: str):
    return secrets.scan_text(FM + body, "wiki/journal/P.md")


def test_finds_aws_key_and_masks_it():
    hits = _scan("chave: AKIAIOSFODNN7EXAMPLE no bucket\n")
    assert len(hits) == 1 and hits[0].kind == "aws-access-key"
    assert "AKIAIOSFODNN7EXAMPLE" not in hits[0].masked
    assert hits[0].masked.startswith("AKIA")


def test_context_keeps_the_label_around_the_mask():
    """An inventory that prints the secret into a terminal log has moved the
    problem, not solved it."""
    hits = _scan("token do runner glpat-abcdefghij1234567890 usado no CI\n")
    assert "glpat-abcdefghij1234567890" not in hits[0].context
    assert "token do runner" in hits[0].context  # findable when you go rotate it
    assert hits[0].kind == "gitlab-pat"


def test_connection_string_with_password():
    hits = _scan("psql postgres://flex:senhaforte123@20.0.0.248/geocloud\n")
    assert hits and hits[0].kind == "connection-string"


def test_sudoers_rule_is_not_a_password():
    """`NOPASSWD: /usr/bin/psql` is a sudoers line; it flooded the first run."""
    assert _scan("| sudoers | `ALL=(postgres) NOPASSWD: /usr/bin/psql` |\n") == []


def test_placeholders_are_ignored():
    for body in ('password: <sua-senha>\n', "senha: changeme\n", 'token: "${GITLAB_TOKEN}"\n',
                 "api_key: your_key_here\n"):
        assert _scan(body) == [], body


def test_line_numbers_account_for_frontmatter():
    hits = _scan("linha um\nlinha dois\nsenha: umaSenhaReal123\n")
    assert hits[0].line_no == 12  # 8 frontmatter lines + blank + 2 body lines + this one


def test_one_finding_per_line():
    hits = _scan("senha: umaSenhaReal123 e token: outroSegredo456\n")
    assert len(hits) == 1


def test_plain_prose_is_quiet():
    assert _scan("O acesso ao dbt8 e via peer auth, sem senha em arquivo.\n") == []


def test_mask_keeps_short_values_unusable():
    assert secrets.mask("abc123") == "a*****"
    assert "…" in secrets.mask("AKIAIOSFODNN7EXAMPLE")


def test_runtime_lookup_is_not_a_secret():
    """`const token = sessionStorage.getItem('key')` states no secret; the
    first run reported it as one."""
    assert _scan("const token = sessionStorage.getItem('jwt');\n") == []
    assert _scan('password = os.getenv("DB_PASSWORD")\n') == []


def test_the_word_credencial_is_not_a_value():
    assert _scan("- Key insight: o time trocou credencial de servico por OIDC\n") == []
