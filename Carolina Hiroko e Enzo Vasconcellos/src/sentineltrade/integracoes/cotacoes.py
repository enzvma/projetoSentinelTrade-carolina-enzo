"""Provedor de cotações (RF-14). A resposta externa é validada antes de ser gravada."""
from __future__ import annotations

import random
from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..dominio.dinheiro import Dinheiro
from ..relogio import Relogio


class CotacaoExterna(BaseModel):
    """Formato aceito de uma cotação recebida do provedor (dado não confiável)."""
    model_config = ConfigDict(extra="forbid", strict=True)
    ticker: str = Field(pattern=r"^[A-Z]{4}[0-9]{1,2}$")
    preco_centavos: int = Field(ge=1, le=10**10)
    data_hora: datetime


def interpretar_cotacao(dados: object) -> CotacaoExterna | None:
    try:
        return CotacaoExterna.model_validate(dados)
    except ValidationError:
        return None


class ProvedorCotacoes(ABC):
    @abstractmethod
    def obter(self, tickers: list[str]) -> list[dict]:
        """Devolve as cotações brutas (lista de dicionários) dos tickers pedidos."""


def _dividir_arredondando(numerador: int, divisor: int) -> int:
    """Divisão inteira arredondada ao mais próximo, simétrica para negativos (sem viés para baixo)."""
    q, r = divmod(abs(numerador), divisor)
    if 2 * r >= divisor:
        q += 1
    return q if numerador >= 0 else -q


class ProvedorCotacoesSimulado(ProvedorCotacoes):
    """Gera preços por passeio aleatório em torno do preço inicial (só simulação).

    Cada passo varia até ±0,5% com arredondamento sem viés e puxa 1% da distância de volta ao preço
    inicial, para os preços não derivarem para zero nem dispararem numa demonstração longa.
    """

    def __init__(self, relogio: Relogio, precos_iniciais: dict[str, Dinheiro], semente: int | None = None,
                 variacao_maxima_bps: int = 50) -> None:
        self._relogio = relogio
        self._precos = dict(precos_iniciais)
        self._referencia = dict(precos_iniciais)
        self._aleatorio = random.Random(semente)  # nosec B311 - simulação de preços, não é uso criptográfico
        self._variacao = variacao_maxima_bps
        self.indisponivel = False

    def preco_atual(self, ticker: str) -> Dinheiro | None:
        return self._precos.get(ticker)

    def definir_preco(self, ticker: str, preco: Dinheiro) -> None:
        self._precos[ticker] = preco
        self._referencia[ticker] = preco

    def obter(self, tickers: list[str]) -> list[dict]:
        if self.indisponivel:
            raise ConnectionError("provedor de cotações simulado indisponível")
        agora = self._relogio.agora()
        saida = []
        for t in tickers:
            if t not in self._precos:
                continue
            atual = self._precos[t].centavos
            referencia = self._referencia.get(t, self._precos[t]).centavos
            passo = self._aleatorio.randint(-self._variacao, self._variacao)
            variacao = _dividir_arredondando(atual * passo, 10_000)
            retorno = _dividir_arredondando(referencia - atual, 100)
            novo = max(1, atual + variacao + retorno)
            self._precos[t] = Dinheiro(novo)
            saida.append({"ticker": t, "preco_centavos": novo, "data_hora": agora})
        return saida
