"""Regras de validação de ordens (RF-07, RN-01 a RN-07)."""
from datetime import datetime, timedelta, timezone

import pytest

from sentineltrade.dominio.conta import Conta, LimiteRisco, Posicao
from sentineltrade.dominio.dinheiro import Dinheiro
from sentineltrade.dominio.enums import Lado, MotivoRejeicao as M, TipoAtivo, TipoOrdem
from sentineltrade.dominio.erros import RegraViolada
from sentineltrade.dominio.mercado import Ativo, Cotacao, ParametrosOperacionais
from sentineltrade.dominio.ordem import Ordem
from sentineltrade.regras import ContextoValidacao, ValidadorOrdem, calcular_valores

PREGAO = datetime(2026, 11, 16, 17, 0, tzinfo=timezone.utc)       # segunda, 14h em Brasília
PARAMETROS = ParametrosOperacionais.de_dicionario({
    "PREGAO_ABERTURA": "10:00", "PREGAO_FECHAMENTO": "17:55", "PREGAO_FUSO": "America/Sao_Paulo", "PREGAO_DIAS": "UTEIS",
    "COTACAO_IDADE_MAX_S": "5", "FAIXA_PRECO_PCT": "10", "TAXA_OPERACAO_BPS": "5"})
R = Dinheiro.de_decimal


def contexto(*, lado=Lado.COMPRA, tipo=TipoOrdem.LIMITADA, quantidade=100, preco="10.00", saldo="5000.00",
             posicao=0, agora=PREGAO, cotacao="10.00", idade_cotacao=1, negociavel=True, ativa=True,
             limite_ordem="50000.00", exposicao_max="200000.00", exposicao_atual="0.00"):
    ordem = Ordem.nova(conta_id=1, ativo_id=1, ticker="PETR4", chave_idempotencia="chave-teste-000001", lado=lado,
                       tipo=tipo, quantidade=quantidade, preco=R(preco) if preco else None, agora=agora)
    cot = None if cotacao is None else Cotacao(1, R(cotacao), 0, agora - timedelta(seconds=idade_cotacao))
    valores = calcular_valores(ordem, cot, PARAMETROS)
    return ContextoValidacao(
        ordem=ordem, conta=Conta(id=1, usuario_id=1, saldo_disponivel=R(saldo), saldo_bloqueado=Dinheiro.zero(),
                                 ativa=ativa),
        ativo=Ativo(id=1, ticker="PETR4", nome="Petrobras PN", tipo=TipoAtivo.ACAO, negociavel=negociavel),
        cotacao=cot, posicao=Posicao(conta_id=1, ativo_id=1, quantidade_disponivel=posicao),
        limite=LimiteRisco(conta_id=1, valor_maximo_ordem=R(limite_ordem), exposicao_maxima=R(exposicao_max)),
        parametros=PARAMETROS, agora=agora, exposicao_atual=R(exposicao_atual),
        valor_estimado=valores.valor_estimado if valores else None,
        valor_bloqueio=valores.valor_bloqueio if valores else None)


def motivo(ctx):
    try:
        ValidadorOrdem().validar(ctx)
    except RegraViolada as exc:
        return exc.motivo
    return None


def test_compra_valida_passa():
    assert motivo(contexto()) is None


def test_venda_valida_passa():
    assert motivo(contexto(lado=Lado.VENDA, posicao=100, saldo="0.00")) is None


@pytest.mark.parametrize("kwargs, esperado", [
    ({"saldo": "999.99"}, M.SALDO_INSUFICIENTE),                                 # RN-03 (1000 + taxa)
    ({"lado": Lado.VENDA, "posicao": 99}, M.POSICAO_INSUFICIENTE),               # RN-04
    ({"limite_ordem": "500.00"}, M.LIMITE_RISCO_EXCEDIDO),                       # RN-05 por ordem
    ({"exposicao_atual": "199500.00"}, M.LIMITE_RISCO_EXCEDIDO),                 # RN-05 exposição total
    ({"preco": "11.01"}, M.PRECO_FORA_DA_FAIXA),                                 # RN-06
    ({"preco": "8.99"}, M.PRECO_FORA_DA_FAIXA),
    ({"idade_cotacao": 6}, M.COTACAO_INDISPONIVEL),                              # RN-07
    ({"cotacao": None}, M.COTACAO_INDISPONIVEL),
    ({"negociavel": False}, M.ATIVO_INDISPONIVEL),                               # RN-02
    ({"ativa": False}, M.CONTA_INATIVA),
    ({"agora": datetime(2026, 11, 16, 21, 0, tzinfo=timezone.utc)}, M.MERCADO_FECHADO),   # 18h em Brasília
    ({"agora": datetime(2026, 11, 15, 17, 0, tzinfo=timezone.utc)}, M.MERCADO_FECHADO),   # domingo
])
def test_regras_rejeitam(kwargs, esperado):
    assert motivo(contexto(**kwargs)) is esperado


def test_preco_no_limite_da_faixa_e_aceito():
    assert motivo(contexto(preco="11.00")) is None
    assert motivo(contexto(preco="9.00")) is None


def test_venda_nao_usa_saldo_e_exposicao_vale_so_para_compra():
    assert motivo(contexto(lado=Lado.VENDA, posicao=100, saldo="0.00", exposicao_atual="200000.00")) is None


def test_compra_a_mercado_bloqueia_com_margem_e_taxa():
    ctx = contexto(tipo=TipoOrdem.MERCADO, preco=None, quantidade=100, cotacao="10.00")
    assert ctx.valor_estimado == R("1000.00")
    assert ctx.valor_bloqueio == R("1100.55")      # 1000 + 10% de margem + 0,05% de taxa


def test_validador_aceita_regras_personalizadas():
    from sentineltrade.regras import RegraMercadoAberto
    assert motivo.__name__ and ValidadorOrdem([RegraMercadoAberto()]).regras[0].__class__ is RegraMercadoAberto


def test_parametro_pregao_todos_os_dias_abre_no_fim_de_semana():
    domingo = datetime(2026, 11, 15, 17, 0, tzinfo=timezone.utc)
    todos = ParametrosOperacionais.de_dicionario({
        "PREGAO_ABERTURA": "10:00", "PREGAO_FECHAMENTO": "17:55", "PREGAO_FUSO": "America/Sao_Paulo",
        "PREGAO_DIAS": "TODOS", "COTACAO_IDADE_MAX_S": "5", "FAIXA_PRECO_PCT": "10", "TAXA_OPERACAO_BPS": "5"})
    assert not PARAMETROS.mercado_aberto(domingo) and todos.mercado_aberto(domingo)
