"""Conta, posição em carteira e limite de risco (RN-03, RN-04, RN-05)."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from .dinheiro import Dinheiro
from .enums import MotivoRejeicao
from .erros import DadosInvalidos, RegraViolada


def _quantidade_valida(q: int) -> int:
    if isinstance(q, bool) or not isinstance(q, int) or q <= 0:
        raise DadosInvalidos("Quantidade inválida.")
    return q


class Conta:
    def __init__(self, *, id: int, usuario_id: int, saldo_disponivel: Dinheiro,
                 saldo_bloqueado: Dinheiro, ativa: bool) -> None:
        self._id = id
        self._usuario_id = usuario_id
        self._disponivel = saldo_disponivel
        self._bloqueado = saldo_bloqueado
        self._ativa = ativa

    id = property(lambda self: self._id)
    usuario_id = property(lambda self: self._usuario_id)
    saldo_disponivel = property(lambda self: self._disponivel)
    saldo_bloqueado = property(lambda self: self._bloqueado)
    ativa = property(lambda self: self._ativa)

    def bloquear(self, valor: Dinheiro) -> None:
        if valor.centavos <= 0:
            raise DadosInvalidos("Valor a bloquear deve ser positivo.")
        if self._disponivel < valor:
            raise RegraViolada(MotivoRejeicao.SALDO_INSUFICIENTE)
        self._disponivel = self._disponivel - valor
        self._bloqueado = self._bloqueado + valor

    def liberar(self, valor: Dinheiro) -> None:
        if valor.e_negativo() or self._bloqueado < valor:
            raise DadosInvalidos("Liberação maior que o saldo bloqueado.")
        self._bloqueado = self._bloqueado - valor
        self._disponivel = self._disponivel + valor

    def consumir_bloqueado(self, valor: Dinheiro) -> None:
        if valor.e_negativo() or self._bloqueado < valor:
            raise DadosInvalidos("Consumo maior que o saldo bloqueado.")
        self._bloqueado = self._bloqueado - valor

    def debitar_disponivel(self, valor: Dinheiro) -> None:
        if valor.e_negativo() or self._disponivel < valor:
            raise RegraViolada(MotivoRejeicao.SALDO_INSUFICIENTE)
        self._disponivel = self._disponivel - valor

    def creditar(self, valor: Dinheiro) -> None:
        if valor.e_negativo():
            raise DadosInvalidos("Crédito negativo.")
        self._disponivel = self._disponivel + valor


class Posicao:
    def __init__(self, *, conta_id: int, ativo_id: int, quantidade_disponivel: int = 0,
                 quantidade_bloqueada: int = 0, preco_medio: Dinheiro | None = None) -> None:
        self._conta_id = conta_id
        self._ativo_id = ativo_id
        self._disponivel = quantidade_disponivel
        self._bloqueada = quantidade_bloqueada
        self._preco_medio = preco_medio or Dinheiro.zero()

    conta_id = property(lambda self: self._conta_id)
    ativo_id = property(lambda self: self._ativo_id)
    quantidade_disponivel = property(lambda self: self._disponivel)
    quantidade_bloqueada = property(lambda self: self._bloqueada)
    preco_medio = property(lambda self: self._preco_medio)

    @property
    def quantidade_total(self) -> int:
        return self._disponivel + self._bloqueada

    def bloquear(self, quantidade: int) -> None:
        _quantidade_valida(quantidade)
        if self._disponivel < quantidade:
            raise RegraViolada(MotivoRejeicao.POSICAO_INSUFICIENTE)
        self._disponivel -= quantidade
        self._bloqueada += quantidade

    def liberar(self, quantidade: int) -> None:
        if quantidade == 0:
            return
        _quantidade_valida(quantidade)
        if quantidade > self._bloqueada:
            raise DadosInvalidos("Liberação maior que a quantidade bloqueada.")
        self._bloqueada -= quantidade
        self._disponivel += quantidade

    def consumir_bloqueada(self, quantidade: int) -> None:
        """Venda executada: a quantidade bloqueada sai da carteira."""
        _quantidade_valida(quantidade)
        if quantidade > self._bloqueada:
            raise DadosInvalidos("Venda maior que a quantidade bloqueada.")
        self._bloqueada -= quantidade

    def adicionar(self, quantidade: int, preco: Dinheiro) -> None:
        """Compra executada: soma a quantidade e recalcula o preço médio."""
        _quantidade_valida(quantidade)
        total_antes = self.quantidade_total
        custo = Decimal(self._preco_medio.centavos) * total_antes + Decimal(preco.centavos) * quantidade
        novo_medio = (custo / (total_antes + quantidade)).to_integral_value(rounding=ROUND_HALF_UP)
        self._preco_medio = Dinheiro(int(novo_medio))
        self._disponivel += quantidade


class LimiteRisco:
    def __init__(self, *, conta_id: int, valor_maximo_ordem: Dinheiro, exposicao_maxima: Dinheiro) -> None:
        if valor_maximo_ordem.centavos <= 0 or exposicao_maxima.centavos <= 0:
            raise DadosInvalidos("Limites devem ser positivos.")
        self._conta_id = conta_id
        self._valor_maximo_ordem = valor_maximo_ordem
        self._exposicao_maxima = exposicao_maxima

    conta_id = property(lambda self: self._conta_id)
    valor_maximo_ordem = property(lambda self: self._valor_maximo_ordem)
    exposicao_maxima = property(lambda self: self._exposicao_maxima)

    def verificar(self, valor_ordem: Dinheiro, exposicao_atual: Dinheiro, conta_exposicao: bool) -> None:
        if valor_ordem > self._valor_maximo_ordem:
            raise RegraViolada(MotivoRejeicao.LIMITE_RISCO_EXCEDIDO)
        if conta_exposicao and exposicao_atual + valor_ordem > self._exposicao_maxima:
            raise RegraViolada(MotivoRejeicao.LIMITE_RISCO_EXCEDIDO)
