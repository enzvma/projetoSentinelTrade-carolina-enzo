"""Objeto de valor para dinheiro (RT-05): inteiro em centavos, nunca ponto flutuante."""
from __future__ import annotations

from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal, InvalidOperation
from functools import total_ordering

_CENTAVO = Decimal("0.01")


@total_ordering
class Dinheiro:
    """Quantia em reais, imutável, guardada em centavos."""

    __slots__ = ("_centavos",)

    def __init__(self, centavos: int) -> None:
        if isinstance(centavos, bool) or not isinstance(centavos, int):
            raise TypeError("Dinheiro deve ser criado com um inteiro de centavos")
        object.__setattr__(self, "_centavos", centavos)

    def __setattr__(self, nome, valor):  # imutável
        raise AttributeError("Dinheiro é imutável")

    # ---- construção -------------------------------------------------------------------
    @classmethod
    def de_decimal(cls, valor: Decimal | str) -> "Dinheiro":
        if isinstance(valor, float):
            raise TypeError("float não é aceito para valores monetários")
        try:
            d = Decimal(valor)
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("valor monetário inválido") from exc
        if not d.is_finite():
            raise ValueError("valor monetário inválido")
        if d != d.quantize(_CENTAVO):
            raise ValueError("valor monetário com mais de duas casas decimais")
        return cls(int(d * 100))

    @classmethod
    def zero(cls) -> "Dinheiro":
        return cls(0)

    # ---- leitura ----------------------------------------------------------------------
    @property
    def centavos(self) -> int:
        return self._centavos

    def como_decimal(self) -> Decimal:
        return (Decimal(self._centavos) / 100).quantize(_CENTAVO)

    def __str__(self) -> str:
        return str(self.como_decimal())

    def __repr__(self) -> str:
        return f"Dinheiro({self.como_decimal()})"

    # ---- aritmética -------------------------------------------------------------------
    def __add__(self, outro: "Dinheiro") -> "Dinheiro":
        return Dinheiro(self._centavos + _exigir(outro)._centavos)

    def __sub__(self, outro: "Dinheiro") -> "Dinheiro":
        return Dinheiro(self._centavos - _exigir(outro)._centavos)

    def vezes(self, quantidade: int) -> "Dinheiro":
        if isinstance(quantidade, bool) or not isinstance(quantidade, int):
            raise TypeError("quantidade deve ser inteira")
        return Dinheiro(self._centavos * quantidade)

    def percentual(self, pontos_base: int, arredondar_para_cima: bool = False) -> "Dinheiro":
        """Fração do valor em pontos-base (1 bp = 0,01%)."""
        valor = Decimal(self._centavos) * Decimal(pontos_base) / Decimal(10_000)
        modo = ROUND_CEILING if arredondar_para_cima else ROUND_HALF_UP
        return Dinheiro(int(valor.to_integral_value(rounding=modo)))

    def e_negativo(self) -> bool:
        return self._centavos < 0

    # ---- comparação -------------------------------------------------------------------
    def __eq__(self, outro: object) -> bool:
        return isinstance(outro, Dinheiro) and self._centavos == outro._centavos

    def __lt__(self, outro: "Dinheiro") -> bool:
        return self._centavos < _exigir(outro)._centavos

    def __hash__(self) -> int:
        return hash(self._centavos)


def _exigir(valor: object) -> Dinheiro:
    if not isinstance(valor, Dinheiro):
        raise TypeError("operação permitida apenas entre valores Dinheiro")
    return valor
