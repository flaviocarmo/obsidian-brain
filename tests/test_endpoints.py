from pathlib import Path

from brainlib import endpoints


def _page(tmp_path: Path, name: str, body: str, type_: str = "concept", updated="2026-08-01") -> tuple[Path, str]:
    p = tmp_path / name
    p.write_text(f'---\ntype: {type_}\ntitle: "{name}"\nupdated: {updated}\nstatus: mature\n---\n\n{body}',
                 encoding="utf-8")
    return p, f"wiki/domains/infra/{name}"


def test_same_host_two_addresses_across_pages_is_drift(tmp_path):
    a = _page(tmp_path, "a.md", "O banco `dbt8` responde em 20.0.0.248.")
    b = _page(tmp_path, "b.md", "Conectar em dbt8 pelo 20.0.0.99 quando precisar.")
    drifts = endpoints.find([a, b])
    assert len(drifts) == 1
    assert drifts[0].host == "dbt8"
    assert set(drifts[0].values) == {"20.0.0.248", "20.0.0.99"}
    assert "divergencia de endereco" in drifts[0].message()


def test_agreement_is_not_reported(tmp_path):
    a = _page(tmp_path, "a.md", "`dbt8` em 20.0.0.248.")
    b = _page(tmp_path, "b.md", "O dbt8 (20.0.0.248) segue de pe.")
    assert endpoints.find([a, b]) == []


def test_session_pages_are_ignored(tmp_path):
    """A journal entry is a dated record: 'dbt6 era 20.0.0.31' stays true
    forever and must not fight with the live host."""
    a = _page(tmp_path, "a.md", "`dbt6` em 20.0.0.31.", type_="source")
    b = _page(tmp_path, "b.md", "dbt6 agora responde em 20.0.0.248.")
    assert endpoints.find([a, b]) == []


def test_decommissioned_mentions_do_not_conflict(tmp_path):
    a = _page(tmp_path, "a.md", "`dbt5` (20.0.0.12) foi TERMINATED em 2026-07-06.")
    b = _page(tmp_path, "b.md", "`dbt5` era 20.0.0.77 antes da consolidacao.")
    assert endpoints.find([a, b]) == []


def test_single_page_listing_a_fleet_is_not_a_conflict(tmp_path):
    a = _page(tmp_path, "a.md", "`wms-8` em 20.0.1.10\n\n`wms-8` tambem atende 20.0.1.11")
    assert endpoints.find([a]) == []


def test_line_with_two_addresses_is_too_ambiguous(tmp_path):
    a = _page(tmp_path, "a.md", "`dbt8` 20.0.0.248 replica para 20.0.0.9")
    b = _page(tmp_path, "b.md", "`dbt8` em 20.0.0.1")
    assert endpoints.find([a, b]) == []


def test_version_numbers_are_not_addresses(tmp_path):
    a = _page(tmp_path, "a.md", "postgres18 chegou na 18.4.1 sem novidade")
    b = _page(tmp_path, "b.md", "postgres18 agora na 18.5.2")
    assert endpoints.find([a, b]) == []  # no IPv4 in either line


def test_version_string_shaped_like_an_address_is_rejected(tmp_path):
    """'Serviço Automático 1.1.0.15' parses as an IPv4 and used to be reported
    against the same product's next release."""
    a = _page(tmp_path, "a.md", "Servico Automatico SINAFLOR v1.1.0.17 sucede a 1.1.0.15 de 21/07.")
    b = _page(tmp_path, "b.md", "Servico Automatico SINAFLOR na versao 1.1.0.20 agora.")
    assert endpoints.find([a, b]) == []


def test_name_far_from_the_address_is_not_associated(tmp_path):
    """A long prose line that opens with a host and mentions some other
    address 300 characters later is not stating that host's address."""
    filler = "texto de contexto " * 20
    a = _page(tmp_path, "a.md", f"- **SPOF do TG `rke2-lb-1`**: resolvido. {filler} host publico 54.197.165.152 no ALB.")
    b = _page(tmp_path, "b.md", "`rke2-lb-1` responde em 20.0.0.191.")
    assert endpoints.find([a, b]) == []


def test_prose_without_a_host_name_is_skipped(tmp_path):
    a = _page(tmp_path, "a.md", "O endereco antigo era 10.0.0.1 e ninguem lembra de quem.")
    b = _page(tmp_path, "b.md", "Outro texto qualquer com 10.0.0.2 solto.")
    assert endpoints.find([a, b]) == []
