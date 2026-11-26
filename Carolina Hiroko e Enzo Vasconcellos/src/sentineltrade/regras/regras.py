"""Regras concretas de validação de ordens (RN-01 a RN-07)."""
from __future__ import annotations

from ..dominio.enums import Lado, MotivoRejeicao, TipoOrdem
from ..dominio.erros import RegraViolada
from .base import ContextoValidacao, RegraPorLado, RegraValidacao


class RegraContaAtiva(RegraValidacao):
    def verificar(self, ctx: ContextoValidacao) -> None:
        if not ctx.conta.ativa:
            raise RegraViolada(MotivoRejeicao.CONTA_INATIVA)


class RegraMercadoAberto(RegraValidacao):
    """RN-01: ordens só com o pregão aberto."""

    def verificar(self, ctx: ContextoValidacao) -> None:
        if not ctx.parametros.mercado_aberto(ctx.agora):
            raise RegraViolada(MotivoRejeicao.MERCADO_FECHADO)


class RegraAtivoNegociavel(RegraValidacao):
    """RN-02: só ativos cadastrados e em situação ativa."""

    def verificar(self, ctx: ContextoValidacao) -> None:
        if not ctx.ativo.negociavel:
            raise RegraViolada(MotivoRejeicao.ATIVO_INDISPONIVEL)


class RegraCotacaoValida(RegraValidacao):
    """RN-07: sem cotação válida (recente), novas ordens do ativo são bloqueadas."""

    def verificar(self, ctx: ContextoValidacao) -> None:
        if ctx.cotacao is None or not ctx.cotacao.esta_valida(ctx.agora, ctx.parametros.cotacao_idade_max_s):
            raise RegraViolada(MotivoRejeicao.COTACAO_INDISPONIVEL)


class RegraFaixaPreco(RegraValidacao):
    """RN-06: preço de ordem limitada a no máximo X% da última cotação."""

    def aplica_se(self, ctx: ContextoValidacao) -> bool:
        return ctx.ordem.tipo is TipoOrdem.LIMITADA

    def verificar(self, ctx: ContextoValidacao) -> None:
        referencia = ctx.cotacao.preco
        tolerancia = referencia.percentual(ctx.parametros.faixa_preco_pct * 100)
        diferenca = abs(ctx.ordem.preco.centavos - referencia.centavos)
        if diferenca > tolerancia.centavos:
            raise RegraViolada(MotivoRejeicao.PRECO_FORA_DA_FAIXA)


class RegraLimiteRisco(RegraValidacao):
    """RN-05: valor máximo por ordem e exposição total das compras abertas."""

    def verificar(self, ctx: ContextoValidacao) -> None:
        conta_exposicao = ctx.ordem.lado is Lado.COMPRA
        valor = ctx.valor_bloqueio if conta_exposicao else ctx.valor_estimado
        ctx.limite.verificar(valor, ctx.exposicao_atual, conta_exposicao)


class RegraSaldo(RegraPorLado):
    """RN-03: compra exige saldo disponível para o valor da ordem mais taxas."""
    lado = Lado.COMPRA

    def verificar(self, ctx: ContextoValidacao) -> None:
        if ctx.conta.saldo_disponivel < ctx.valor_bloqueio:
            raise RegraViolada(MotivoRejeicao.SALDO_INSUFICIENTE)


class RegraPosicao(RegraPorLado):
    """RN-04: venda exige posição disponível; venda a descoberto é proibida."""
    lado = Lado.VENDA

    def verificar(self, ctx: ContextoValidacao) -> None:
        disponivel = ctx.posicao.quantidade_disponivel if ctx.posicao else 0
        if disponivel < ctx.ordem.quantidade:
            raise RegraViolada(MotivoRejeicao.POSICAO_INSUFICIENTE)
