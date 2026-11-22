"""API: autenticação, autorização, validação de entradas e tratamento seguro de erros (RNF-03 a RNF-07, RNF-11)."""
import pytest
from fastapi.testclient import TestClient

from conftest import SENHA, codigo_mfa, criar_usuario
from sentineltrade.api.app import criar_app
from sentineltrade.dominio.enums import Perfil


@pytest.fixture
def cliente(app, config):
    return TestClient(criar_app(config, aplicacao=app))


def entrar(cliente, app, usuario, email):
    r = cliente.post("/auth/login", json={"email": email, "senha": SENHA})
    assert r.status_code == 200, r.text
    r = cliente.post("/auth/mfa", json={"token_mfa": r.json()["token_mfa"], "codigo": codigo_mfa(app, usuario)})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def auth_investidor(cliente, app, investidor):
    return entrar(cliente, app, investidor[0], "investidor@exemplo.com")


ORDEM = {"ticker": "PETR4", "lado": "COMPRA", "tipo": "LIMITADA", "quantidade": 10, "preco": "38.50",
         "chave_idempotencia": "chave-api-000000001"}


def test_fluxo_de_ordem_pela_api(cliente, auth_investidor):
    r = cliente.post("/ordens", json=ORDEM, headers=auth_investidor)
    assert r.status_code == 201 and r.json()["estado"] == "VALIDADA" and r.json()["preco"] == "38.50"
    repetida = cliente.post("/ordens", json=ORDEM, headers=auth_investidor)
    assert repetida.status_code == 200 and repetida.json()["id"] == r.json()["id"]
    detalhe = cliente.get(f"/ordens/{r.json()['id']}", headers=auth_investidor).json()
    assert [h["estado_novo"] for h in detalhe["historico"]] == ["CRIADA", "VALIDADA"]
    assert cliente.get("/conta/saldo", headers=auth_investidor).json()["bloqueado"] == "385.20"
    c = cliente.post(f"/ordens/{r.json()['id']}/cancelamento", headers=auth_investidor)
    assert c.status_code == 202


def test_sem_token_ou_token_invalido(cliente):
    assert cliente.get("/conta/saldo").status_code == 401
    r = cliente.get("/conta/saldo", headers={"Authorization": "Bearer abc.def.ghi"})
    assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"


def test_token_de_mfa_nao_da_acesso(cliente, investidor):
    token_mfa = cliente.post("/auth/login", json={"email": "investidor@exemplo.com", "senha": SENHA}).json()["token_mfa"]
    assert cliente.get("/conta/saldo", headers={"Authorization": f"Bearer {token_mfa}"}).status_code == 401


def test_investidor_nao_acessa_rotas_de_outros_perfis(cliente, auth_investidor):
    assert cliente.post("/admin/ativos", json={"ticker": "NOVO3", "nome": "Novo", "tipo": "ACAO",
                                               "preco_referencia": "1.00"}, headers=auth_investidor).status_code == 403
    assert cliente.get("/auditoria", headers=auth_investidor).status_code == 403
    assert cliente.put("/risco/contas/1/limites", json={"valor_maximo_ordem": "1.00", "exposicao_maxima": "1.00"},
                       headers=auth_investidor).status_code == 403


def test_investidor_nao_ve_ordem_de_outro(cliente, app, auth_investidor):
    outro, _ = criar_usuario(app, "outro@exemplo.com", saldo="100.00")
    auth_outro = entrar(cliente, app, outro, "outro@exemplo.com")
    ordem_id = cliente.post("/ordens", json=ORDEM, headers=auth_investidor).json()["id"]
    assert cliente.get(f"/ordens/{ordem_id}", headers=auth_outro).status_code == 404
    assert cliente.post(f"/ordens/{ordem_id}/cancelamento", headers=auth_outro).status_code == 404
    lista = cliente.get("/ordens", params={"conta_id": 1}, headers=auth_outro).json()   # tenta ver a conta 1
    assert lista == []


def test_administrador_e_auditor(cliente, app, auth_investidor):
    admin, _ = criar_usuario(app, "admin@exemplo.com", Perfil.ADMINISTRADOR)
    auth_admin = entrar(cliente, app, admin, "admin@exemplo.com")
    r = cliente.patch("/admin/ativos/PETR4", json={"negociavel": False}, headers=auth_admin)
    assert r.status_code == 204
    ordem = cliente.post("/ordens", json=ORDEM, headers=auth_investidor).json()
    assert ordem["estado"] == "REJEITADA" and ordem["motivo"] == "ATIVO_INDISPONIVEL"
    auditor, _ = criar_usuario(app, "auditor@exemplo.com", Perfil.AUDITOR)
    auth_auditor = entrar(cliente, app, auditor, "auditor@exemplo.com")
    trilha = cliente.get("/auditoria", params={"entidade": "ativo"}, headers=auth_auditor).json()
    assert trilha[0]["acao"] == "ATIVO_SITUACAO"
    assert cliente.get("/auditoria/verificacao", headers=auth_auditor).json()["integra"] is True


@pytest.mark.parametrize("campo, valor", [
    ("ticker", "PETR4'; DROP TABLE ordens;--"),
    ("ticker", "petr4"),
    ("quantidade", 0),
    ("quantidade", "10"),
    ("quantidade", 10.5),
    ("preco", "38.505"),
    ("preco", "-1"),
    ("preco", "NaN"),
    ("lado", "EMPRESTIMO"),
    ("chave_idempotencia", "curta"),
    ("chave_idempotencia", "<script>alert(1)</script>-aaaa"),
])
def test_entradas_invalidas_sao_rejeitadas(cliente, auth_investidor, campo, valor):
    r = cliente.post("/ordens", json={**ORDEM, campo: valor}, headers=auth_investidor)
    assert r.status_code == 422
    corpo = r.json()
    assert corpo["erro"] == "DADOS_INVALIDOS"
    if isinstance(valor, str) and len(valor) > 3:
        assert valor not in r.text                       # o valor enviado não é devolvido


def test_campo_extra_e_rejeitado(cliente, auth_investidor):
    r = cliente.post("/ordens", json={**ORDEM, "conta_id": 99}, headers=auth_investidor)
    assert r.status_code == 422


def test_erro_de_login_nao_ecoa_a_senha(cliente):
    r = cliente.post("/auth/login", json={"email": "nao-e-email", "senha": "MinhaSenhaSecreta1"})
    assert r.status_code == 422 and "MinhaSenhaSecreta1" not in r.text


def test_limite_de_tentativas_de_login(cliente, investidor):
    for _ in range(5):
        cliente.post("/auth/login", json={"email": "investidor@exemplo.com", "senha": "Errada123456789"})
    r = cliente.post("/auth/login", json={"email": "investidor@exemplo.com", "senha": SENHA})
    assert r.status_code == 429


def test_corpo_grande_e_recusado(cliente, auth_investidor):
    r = cliente.post("/ordens", content=b"{" + b" " * 20_000 + b"}", headers={**auth_investidor,
                                                                              "content-type": "application/json"})
    assert r.status_code == 413


def test_erro_interno_nao_revela_detalhes(cliente, app, auth_investidor, monkeypatch):
    def quebrar(*args, **kwargs):
        raise RuntimeError("detalhe interno: caminho /segredo/banco.db")
    monkeypatch.setattr(app.consultas, "saldo", quebrar)
    r = cliente.get("/conta/saldo", headers=auth_investidor)
    assert r.status_code == 500
    assert "segredo" not in r.text and "Traceback" not in r.text
    assert r.json()["correlation_id"] == r.headers["x-correlation-id"]


def test_cabecalhos_de_seguranca(cliente):
    r = cliente.get("/saude")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["cache-control"] == "no-store"
    assert "default-src 'none'" in r.headers["content-security-policy"]


def test_correlation_id_externo_invalido_e_substituido(cliente):
    r = cliente.get("/saude", headers={"X-Correlation-ID": "abc\r\nSet-Cookie: x=1"})
    assert "\n" not in r.headers["x-correlation-id"] and len(r.headers["x-correlation-id"]) == 32
