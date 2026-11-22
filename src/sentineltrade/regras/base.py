"""Abstrações das regras de validação."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from ..dominio.conta import Conta, LimiteRisco, Posicao
from ..dominio.dinheiro import Dinheiro
from ..dominio.enums import Lado
from ..dominio.mercado import Ativo, Cotacao, ParametrosOperacionais
from ..dominio.ordem import Ordem


@dataclass(frozen=True)
class ContextoValidacao:
    """Tudo o que as regras precisam para decidir, carregado pelo serviço antes da validação."""
    ordem: Ordem
    conta: Conta
    ativo: Ativo
    cotacao: Cotacao | None
    posicao: Posicao | None
    limite: LimiteRisco
    parametros: ParametrosOperacionais
    agora: datetime
    exposicao_atual: Dinheiro          # soma do valor bloqueado pelas ordens de compra abertas
    valor_estimado: Dinheiro | None    # quantidade × preço de referência
    valor_bloqueio: Dinheiro | None    # valor a bloquear numa compra (inclui taxa e margem)


class RegraValidacao(ABC):
    """Uma regra de negócio. Lança RegraViolada quando a ordem não a cumpre."""

    def aplica_se(self, ctx: ContextoValidacao) -> bool:
        return True

    @abstractmethod
    def verificar(self, ctx: ContextoValidacao) -> None:
        """Lança `RegraViolada` se a regra não for cumprida."""


class RegraPorLado(RegraValidacao, ABC):
    """Regra que só se aplica a compras ou só a vendas."""
    lado: Lado

    def aplica_se(self, ctx: ContextoValidacao) -> bool:
        return ctx.ordem.lado is self.lado
