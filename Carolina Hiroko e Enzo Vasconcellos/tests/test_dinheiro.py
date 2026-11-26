"""Valores monetários sem ponto flutuante (RT-05)."""
from decimal import Decimal

import pytest

from sentineltrade.dominio.dinheiro import Dinheiro


def test_rejeita_float():
    with pytest.raises(TypeError):
        Dinheiro.de_decimal(10.5)
    with pytest.raises(TypeError):
        Dinheiro(10.5)


def test_rejeita_mais_de_duas_casas_e_valores_nao_finitos():
    for valor in ("1.001", "NaN", "Infinity", "abc"):
        with pytest.raises(ValueError):
            Dinheiro.de_decimal(valor)


def test_aritmetica_e_percentual():
    a = Dinheiro.de_decimal("38.50")
    assert a.vezes(100) == Dinheiro.de_decimal("3850.00")
    assert a.vezes(100).percentual(5, arredondar_para_cima=True) == Dinheiro.de_decimal("1.93")
    assert (a + Dinheiro(50)).como_decimal() == Decimal("39.00")


def test_imutavel():
    a = Dinheiro(100)
    with pytest.raises(AttributeError):
        a._centavos = 1
