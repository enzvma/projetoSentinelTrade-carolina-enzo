"""Validador de ordens: aplica as regras em sequência e para na primeira violação."""
from __future__ import annotations

from dataclasses import dataclass

from ..dominio.dinheiro import Dinheiro
from ..dominio.enums import Lado, TipoOrdem
from ..dominio.mercado import Cotacao, ParametrosOperacionais
from ..dominio.ordem import Ordem
from .base import ContextoValidacao, RegraValidacao
from .regras import (RegraAtivoNegociavel, RegraContaAtiva, RegraCotacaoValida, RegraFaixaPreco,
                     RegraLimiteRisco, RegraMercadoAberto, RegraPosicao, RegraSaldo)


@dataclass(frozen=True)
class ValoresOrdem:
    valor_estimado: Dinheiro   # quantidade × preço de referência
    valor_bloqueio: Dinheiro   # compra: valor + taxa (+ margem da faixa, se a mercado); venda: zero


def calcular_valores(ordem: Ordem, cotacao: Cotacao | None, parametros: ParametrosOperacionais) -> ValoresOrdem | None:
    """Calcula os valores da ordem. Sem preço de referência (cotação ausente), devolve None."""
    if ordem.tipo is TipoOrdem.LIMITADA:
        referencia = ordem.preco
    elif cotacao is not None:
        referencia = cotacao.preco
    else:
        return None
    estimado = referencia.vezes(ordem.quantidade)
    if ordem.lado is Lado.VENDA:
        return ValoresOrdem(estimado, Dinheiro.zero())
    base = estimado
    if ordem.tipo is TipoOrdem.MERCADO:   # margem para variação do preço até a execução
        base = estimado + estimado.percentual(parametros.faixa_preco_pct * 100, arredondar_para_cima=True)
    taxa = base.percentual(parametros.taxa_operacao_bps, arredondar_para_cima=True)
    return ValoresOrdem(estimado, base + taxa)


class ValidadorOrdem:
    REGRAS_PADRAO: tuple[type[RegraValidacao], ...] = (
        RegraContaAtiva, RegraMercadoAberto, RegraAtivoNegociavel, RegraCotacaoValida,
        RegraFaixaPreco, RegraLimiteRisco, RegraSaldo, RegraPosicao,
    )

    def __init__(self, regras: list[RegraValidacao] | None = None) -> None:
        self._regras = list(regras) if regras is not None else [r() for r in self.REGRAS_PADRAO]

    @property
    def regras(self) -> tuple[RegraValidacao, ...]:
        return tuple(self._regras)

    def validar(self, ctx: ContextoValidacao) -> None:
        """Lança RegraViolada na primeira regra não cumprida."""
        for regra in self._regras:
            if regra.aplica_se(ctx):
                regra.verificar(ctx)
