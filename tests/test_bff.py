"""BFF: sessão no servidor, proteção CSRF, agregação por perfil e mensagens traduzidas."""
import pytest
from fastapi.testclient import TestClient

from conftest import SENHA, codigo_mfa, criar_usuario
from sentineltrade.api.app import criar_app
from sentineltrade.bff.app import COOKIE, criar_bff
from sentineltrade.dominio.enums import Perfil


@pytest.fixture
def navegador(app, config):
    api = TestClient(criar_app(config, aplicacao=app))
    return TestClient(criar_bff(config, cliente_api=api))


def entrar(navegador, app, usuario, email):
    csrf = navegador.get("/bff/sessao").json()["csrf"]
    cab = {"X-CSRF-Token": csrf}
    assert navegador.post("/bff/login", json={"email": email, "senha": SENHA}, headers=cab).status_code == 200
    r = navegador.post("/bff/mfa", json={"codigo": codigo_mfa(app, usuario)}, headers=cab)
    assert r.status_code == 200, r.text
    return cab, r.json()


def test_login_guarda_token_so_no_servidor(navegador, app):
    usuario, _ = criar_usuario(app, "investidor@exemplo.com", saldo="10000")
    r = navegador.get("/bff/sessao")
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    cab, sessao = entrar(navegador, app, usuario, "investidor@exemplo.com")
    assert sessao == {"autenticado": True, "nome": "Pessoa Teste", "perfil": "INVESTIDOR"}
    assert "token" not in str(sessao).lower()


def test_escrita_sem_csrf_e_recusada(navegador, app):
    usuario, _ = criar_usuario(app, "investidor@exemplo.com", saldo="10000")
    navegador.get("/bff/sessao")
    assert navegador.post("/bff/login", json={"email": "investidor@exemplo.com", "senha": SENHA}).status_code == 403
    cab, _ = entrar(navegador, app, usuario, "investidor@exemplo.com")
    ordem = {"ticker": "PETR4", "lado": "COMPRA", "tipo": "LIMITADA", "quantidade": 10, "preco": "38.50",
             "chave_idempotencia": "chave-bff-0000000001"}
    assert navegador.post("/bff/ordens", json=ordem, headers={"X-CSRF-Token": "outro"}).status_code == 403


def test_sem_sessao_nao_acessa_painel(navegador):
    assert navegador.get("/bff/painel").status_code == 401


def test_painel_do_investidor_e_ordem_traduzida(navegador, app):
    usuario, _ = criar_usuario(app, "investidor@exemplo.com", saldo="10000")
    cab, _ = entrar(navegador, app, usuario, "investidor@exemplo.com")
    ordem = {"ticker": "PETR4", "lado": "COMPRA", "tipo": "LIMITADA", "quantidade": 10, "preco": "38.50",
             "chave_idempotencia": "chave-bff-0000000001"}
    o = navegador.post("/bff/ordens", json=ordem, headers=cab).json()
    assert o["estado_texto"] == "Validada" and o["pode_cancelar"] and "na fila" in o["mensagem"]
    venda = {**ordem, "lado": "VENDA", "chave_idempotencia": "chave-bff-0000000002"}
    rejeitada = navegador.post("/bff/ordens", json=venda, headers=cab).json()
    assert rejeitada["motivo_texto"] == "Quantidade do ativo insuficiente na carteira."
    painel = navegador.get("/bff/painel").json()
    assert {"saldo", "carteira", "cotacoes", "ordens", "mercado"} <= painel.keys()
    assert painel["mercado"]["aberto"] is True and len(painel["ordens"]) == 2
    detalhe = navegador.get(f"/bff/ordens/{o['id']}").json()
    assert [h["estado_texto"] for h in detalhe["historico"]] == ["Criada", "Validada"]
    c = navegador.post(f"/bff/ordens/{o['id']}/cancelar", headers=cab)
    assert c.status_code == 200


def test_erros_da_api_viram_mensagens_claras(navegador, app):
    usuario, _ = criar_usuario(app, "investidor@exemplo.com", saldo="10000")
    csrf = navegador.get("/bff/sessao").json()["csrf"]
    r = navegador.post("/bff/login", json={"email": "investidor@exemplo.com", "senha": "errada-123456"},
                       headers={"X-CSRF-Token": csrf})
    assert r.status_code == 401 and "incorretos" in r.json()["mensagem"]
    cab, _ = entrar(navegador, app, usuario, "investidor@exemplo.com")
    r = navegador.post("/bff/ordens", json={"ticker": "PETR4", "lado": "COMPRA", "tipo": "LIMITADA",
                                            "quantidade": 0, "chave_idempotencia": "x"}, headers=cab)
    assert r.status_code == 422 and r.json()["mensagem"].startswith("Confira")


def test_perfis_sem_permissao_sao_barrados_no_bff(navegador, app):
    usuario, _ = criar_usuario(app, "auditor@exemplo.com", perfil=Perfil.AUDITOR)
    cab, _ = entrar(navegador, app, usuario, "auditor@exemplo.com")
    assert navegador.put("/bff/admin/parametros/PREGAO_DIAS", json={"valor": "TODOS"}, headers=cab).status_code == 403
    painel = navegador.get("/bff/painel").json()
    assert "auditoria" in painel and "saldo" not in painel
    assert navegador.get("/bff/auditoria/verificacao").json()["integra"] is True


def test_sair_encerra_a_sessao(navegador, app):
    usuario, _ = criar_usuario(app, "investidor@exemplo.com", saldo="10000")
    cab, _ = entrar(navegador, app, usuario, "investidor@exemplo.com")
    assert navegador.post("/bff/sair", headers=cab).status_code == 200
    assert navegador.get("/bff/painel").status_code == 401


def test_pagina_com_cabecalhos_de_seguranca(navegador):
    r = navegador.get("/")
    assert r.status_code == 200 and "script-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-frame-options"] == "DENY"
