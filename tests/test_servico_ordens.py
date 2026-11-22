"""Envio de ordens: validação, bloqueio de saldo e posição e prevenção de duplicidade (RF-05, RF-07, RN-12)."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest

from conftest import criar_usuario, dar_posicao, definir_cotacao, saldo
from sentineltrade.dominio.dinheiro import Dinheiro
from sentineltrade.dominio.enums import EstadoOrdem as E, Lado, Perfil, TipoOrdem
from sentineltrade.dominio.erros import (AcessoNegado, ConflitoIdempotencia, DadosInvalidos, NaoEncontrado,
                                         ServicoIndisponivel)
from sentineltrade.servicos.ordens import DadosOrdem

R = Dinheiro.de_decimal


def compra(chave="chave-compra-000001", quantidade=10, preco="38.50", ticker="PETR4", tipo=TipoOrdem.LIMITADA):
    return DadosOrdem(ticker, Lado.COMPRA, tipo, quantidade, Decimal(preco) if preco else None, chave)


def venda(chave="chave-venda-0000001", quantidade=10, preco="38.50", ticker="PETR4"):
    return DadosOrdem(ticker, Lado.VENDA, TipoOrdem.LIMITADA, quantidade, Decimal(preco), chave)


def test_compra_valida_bloqueia_saldo_e_entra_na_fila(app, investidor):
    usuario, conta_id = investidor
    ordem, criada = app.ordens.criar(usuario, compra())
    assert criada and ordem.estado is E.VALIDADA
    disponivel, bloqueado = saldo(app, conta_id)
    assert bloqueado == R("385.20")                     # 385,00 + taxa de 0,05% arredondada para cima
    assert disponivel == R("10000.00") - R("385.20")
    with app.uow(somente_leitura=True) as uow:
        assert uow.fila.existe(ordem.id, "ENVIAR")


def test_saldo_insuficiente_rejeita_sem_bloquear(app, investidor):
    usuario, conta_id = investidor
    ordem, _ = app.ordens.criar(usuario, compra(quantidade=300))        # 11.550,00 > 10.000,00
    assert ordem.estado is E.REJEITADA and ordem.motivo == "SALDO_INSUFICIENTE"
    assert saldo(app, conta_id) == (R("10000.00"), Dinheiro.zero())
    with app.uow(somente_leitura=True) as uow:
        assert not uow.fila.existe(ordem.id, "ENVIAR")


def test_venda_sem_posicao_e_rejeitada(app, investidor):
    usuario, _ = investidor
    ordem, _ = app.ordens.criar(usuario, venda())
    assert ordem.estado is E.REJEITADA and ordem.motivo == "POSICAO_INSUFICIENTE"


def test_venda_com_posicao_bloqueia_quantidade(app, investidor):
    from conftest import posicao
    usuario, conta_id = investidor
    dar_posicao(app, conta_id, "PETR4", 50, "30.00")
    ordem, _ = app.ordens.criar(usuario, venda(quantidade=20))
    assert ordem.estado is E.VALIDADA
    p = posicao(app, conta_id, "PETR4")
    assert (p.quantidade_disponivel, p.quantidade_bloqueada) == (30, 20)


def test_ativo_suspenso_e_cotacao_desatualizada(app, investidor, relogio):
    usuario, _ = investidor
    suspensa, _ = app.ordens.criar(usuario, compra(chave="chave-suspenso-0001", ticker="SUSP3", preco="1.50"))
    assert suspensa.motivo == "ATIVO_INDISPONIVEL"
    relogio.avancar(seconds=6)
    velha, _ = app.ordens.criar(usuario, compra(chave="chave-cotacao-00001"))
    assert velha.motivo == "COTACAO_INDISPONIVEL"


def test_ativo_inexistente_e_dado_invalido(app, investidor):
    with pytest.raises(DadosInvalidos):
        app.ordens.criar(investidor[0], compra(ticker="XXXX3"))


def test_mesma_chave_devolve_a_mesma_ordem(app, investidor):
    usuario, conta_id = investidor
    primeira, criada1 = app.ordens.criar(usuario, compra())
    segunda, criada2 = app.ordens.criar(usuario, compra())
    assert criada1 and not criada2 and primeira.id == segunda.id
    assert saldo(app, conta_id)[1] == R("385.20")                  # bloqueou uma vez só


def test_mesma_chave_com_conteudo_diferente_e_conflito(app, investidor):
    usuario, _ = investidor
    app.ordens.criar(usuario, compra())
    with pytest.raises(ConflitoIdempotencia):
        app.ordens.criar(usuario, compra(quantidade=11))


def test_envios_simultaneos_com_a_mesma_chave_criam_uma_ordem(app, investidor):
    usuario, conta_id = investidor
    with ThreadPoolExecutor(max_workers=8) as executor:
        resultados = list(executor.map(lambda _: app.ordens.criar(usuario, compra()), range(8)))
    assert len({o.id for o, _ in resultados}) == 1
    assert sum(1 for _, criada in resultados if criada) == 1
    assert saldo(app, conta_id)[1] == R("385.20")


def test_limite_de_risco_por_ordem(app, investidor, relogio):
    usuario, conta_id = investidor
    gestor, _ = criar_usuario(app, "risco@exemplo.com", Perfil.ANALISTA_RISCO)
    app.administracao.definir_limite(gestor, conta_id, Decimal("100.00"), Decimal("1000.00"))
    ordem, _ = app.ordens.criar(usuario, compra())
    assert ordem.motivo == "LIMITE_RISCO_EXCEDIDO"


def test_modo_restrito_bloqueia_novas_ordens(app, investidor, relogio):
    with app.uow() as uow:
        uow.estado_sistema.definir(True, "TESTE", relogio.agora())
        uow.confirmar()
    with pytest.raises(ServicoIndisponivel):
        app.ordens.criar(investidor[0], compra())


def test_so_investidor_envia_ordem(app):
    admin, _ = criar_usuario(app, "admin@exemplo.com", Perfil.ADMINISTRADOR)
    with pytest.raises(AcessoNegado):
        app.ordens.criar(admin, compra())


def test_investidor_nao_ve_ordem_de_outro(app, investidor):
    usuario, _ = investidor
    outro, _ = criar_usuario(app, "outro@exemplo.com", saldo="1000.00")
    ordem, _ = app.ordens.criar(usuario, compra())
    with pytest.raises(NaoEncontrado):
        app.ordens.consultar(outro, ordem.id)
    with pytest.raises(NaoEncontrado):
        app.ordens.cancelar(outro, ordem.id)
    assert app.ordens.listar(outro) == []


def test_historico_registra_cada_transicao(app, investidor):
    usuario, _ = investidor
    ordem, _ = app.ordens.criar(usuario, compra())
    _, historico = app.ordens.consultar(usuario, ordem.id)
    assert [h["estado_novo"] for h in historico] == ["CRIADA", "VALIDADA"]
