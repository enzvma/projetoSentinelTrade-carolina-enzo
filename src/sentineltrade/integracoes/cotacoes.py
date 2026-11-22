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


class ProvedorCotacoesSimulado(ProvedorCotacoes):
    """Gera preços por passeio aleatório a partir de um preço inicial (só simulação)."""

    def __init__(self, relogio: Relogio, precos_iniciais: dict[str, Dinheiro], semente: int | None = None,
                 variacao_maxima_bps: int = 50) -> None:
        self._relogio = relogio
        self._precos = dict(precos_iniciais)
        self._aleatorio = random.Random(semente)  # nosec B311 - simulação de preços, não é uso criptográfico
        self._variacao = variacao_maxima_bps
        self.indisponivel = False

    def preco_atual(self, ticker: str) -> Dinheiro | None:
        return self._precos.get(ticker)

    def definir_preco(self, ticker: str, preco: Dinheiro) -> None:
        self._precos[ticker] = preco

    def obter(self, tickers: list[str]) -> list[dict]:
        if self.indisponivel:
            raise ConnectionError("provedor de cotações simulado indisponível")
        agora = self._relogio.agora()
        saida = []
        for t in tickers:
            if t not in self._precos:
                continue
            atual = self._precos[t].centavos
            passo = self._aleatorio.randint(-self._variacao, self._variacao)
            novo = max(1, atual + atual * passo // 10_000)
            self._precos[t] = Dinheiro(novo)
            saida.append({"ticker": t, "preco_centavos": novo, "data_hora": agora})
        return saida
