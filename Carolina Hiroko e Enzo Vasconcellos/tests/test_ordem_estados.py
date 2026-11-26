"""Máquina de estados da ordem (RF-08, RN-09)."""
from datetime import datetime, timezone

import pytest

from sentineltrade.dominio.dinheiro import Dinheiro
from sentineltrade.dominio.enums import EstadoOrdem as E, Lado, MotivoRejeicao, OrigemTransicao, TipoOrdem
from sentineltrade.dominio.erros import DadosInvalidos, OperacaoNaoPermitida, TransicaoInvalida
from sentineltrade.dominio.ordem import TRANSICOES, Ordem

AGORA = datetime(2026, 11, 16, 17, 0, tzinfo=timezone.utc)


def nova(quantidade=10, tipo=TipoOrdem.LIMITADA, preco="10.00"):
    return Ordem.nova(conta_id=1, ativo_id=1, ticker="PETR4", chave_idempotencia="chave-teste-000001",
                      lado=Lado.COMPRA, tipo=tipo, quantidade=quantidade,
                      preco=Dinheiro.de_decimal(preco) if preco else None, agora=AGORA)


def enviada(quantidade=10):
    o = nova(quantidade)
    o.marcar_validada(Dinheiro(10_000), AGORA)
    o.marcar_enviada(AGORA)
    return o


def test_nova_ordem_comeca_criada_e_gera_evento():
    o = nova()
    assert o.estado is E.CRIADA
    eventos = o.coletar_eventos()
    assert [(e.anterior, e.novo) for e in eventos] == [(None, E.CRIADA)]
    assert o.coletar_eventos() == []


def test_fluxo_completo_ate_executada():
    o = enviada()
    o.registrar_execucao(4, AGORA)
    assert o.estado is E.PARCIALMENTE_EXECUTADA and o.quantidade_restante == 6
    o.registrar_execucao(6, AGORA)
    assert o.estado is E.EXECUTADA and o.quantidade_executada == 10


@pytest.mark.parametrize("final", [E.EXECUTADA, E.REJEITADA, E.CANCELADA])
def test_estado_final_nao_tem_saida(final):
    assert TRANSICOES[final] == frozenset()


def test_nenhum_estado_volta_ao_inicial():
    assert all(E.CRIADA not in destinos for destinos in TRANSICOES.values())


def test_ordem_executada_nao_pode_ser_cancelada_nem_rejeitada():
    o = enviada(5)
    o.registrar_execucao(5, AGORA)
    with pytest.raises(OperacaoNaoPermitida):
        o.cancelar(OrigemTransicao.USUARIO, AGORA)
    with pytest.raises(TransicaoInvalida):
        o.rejeitar(MotivoRejeicao.SALDO_INSUFICIENTE, OrigemTransicao.SISTEMA, AGORA)


def test_ordem_cancelada_nao_volta_a_ser_enviada():
    o = nova()
    o.cancelar(OrigemTransicao.USUARIO, AGORA)
    with pytest.raises(TransicaoInvalida):
        o.marcar_validada(Dinheiro.zero(), AGORA)


def test_nao_pula_validacao():
    with pytest.raises(TransicaoInvalida):
        nova().marcar_enviada(AGORA)


def test_execucao_acima_do_restante_e_recusada():
    o = enviada(10)
    with pytest.raises(DadosInvalidos):
        o.registrar_execucao(11, AGORA)
    assert o.estado is E.ENVIADA


def test_execucao_em_ordem_nao_enviada_e_recusada():
    o = nova()
    with pytest.raises(TransicaoInvalida):
        o.registrar_execucao(1, AGORA)


def test_rejeicao_guarda_motivo():
    o = nova()
    o.rejeitar(MotivoRejeicao.SALDO_INSUFICIENTE, OrigemTransicao.SISTEMA, AGORA)
    assert o.estado is E.REJEITADA and o.motivo == "SALDO_INSUFICIENTE"


@pytest.mark.parametrize("quantidade", [0, -1, 1_000_001, True])
def test_quantidade_invalida(quantidade):
    with pytest.raises(DadosInvalidos):
        nova(quantidade=quantidade)


def test_limitada_exige_preco_e_mercado_nao_aceita_preco():
    with pytest.raises(DadosInvalidos):
        nova(tipo=TipoOrdem.LIMITADA, preco=None)
    with pytest.raises(DadosInvalidos):
        nova(tipo=TipoOrdem.MERCADO, preco="10.00")


def test_bloqueio_da_ordem_nunca_fica_negativo():
    o = enviada()
    assert o.consumir_bloqueio(Dinheiro(25_000)) == Dinheiro(10_000)
    assert o.valor_bloqueado == Dinheiro.zero()
