"""Ativos, cotações e parâmetros operacionais do mercado simulado (RN-01, RN-02, RN-06, RN-07)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .dinheiro import Dinheiro
from .enums import TipoAtivo
from .erros import DadosInvalidos

TICKER_RE = re.compile(r"^[A-Z]{4}[0-9]{1,2}$")
_HORA_RE = re.compile(r"^([01][0-9]|2[0-3]):[0-5][0-9]$")


class Ativo:
    def __init__(self, *, id: int | None, ticker: str, nome: str, tipo: TipoAtivo,
                 lote_minimo: int = 1, negociavel: bool = True) -> None:
        if not TICKER_RE.fullmatch(ticker or ""):
            raise DadosInvalidos("Código de ativo inválido.")
        self._id = id
        self._ticker = ticker
        self._nome = nome
        self._tipo = TipoAtivo(tipo)
        self._lote_minimo = lote_minimo
        self._negociavel = negociavel

    id = property(lambda self: self._id)
    ticker = property(lambda self: self._ticker)
    nome = property(lambda self: self._nome)
    tipo = property(lambda self: self._tipo)
    lote_minimo = property(lambda self: self._lote_minimo)
    negociavel = property(lambda self: self._negociavel)

    def definir_negociavel(self, valor: bool) -> None:
        self._negociavel = bool(valor)


@dataclass(frozen=True)
class Cotacao:
    ativo_id: int
    preco: Dinheiro
    variacao_bps: int
    data_hora: datetime

    def idade_segundos(self, agora: datetime) -> float:
        return (agora - self.data_hora).total_seconds()

    def esta_valida(self, agora: datetime, idade_maxima_s: int) -> bool:
        return self.preco.centavos > 0 and 0 <= self.idade_segundos(agora) <= idade_maxima_s


@dataclass(frozen=True)
class ParametrosOperacionais:
    pregao_abertura: time
    pregao_fechamento: time
    fuso: ZoneInfo
    todos_os_dias: bool
    cotacao_idade_max_s: int
    faixa_preco_pct: int
    taxa_operacao_bps: int

    # Validação por chave: só valores previstos são aceitos (allowlist).
    VALIDADORES = {
        "PREGAO_ABERTURA": lambda v: bool(_HORA_RE.fullmatch(v)),
        "PREGAO_FECHAMENTO": lambda v: bool(_HORA_RE.fullmatch(v)),
        "PREGAO_FUSO": lambda v: v in ("America/Sao_Paulo", "UTC"),
        "PREGAO_DIAS": lambda v: v in ("UTEIS", "TODOS"),
        "COTACAO_IDADE_MAX_S": lambda v: v.isdigit() and 1 <= int(v) <= 3600,
        "FAIXA_PRECO_PCT": lambda v: v.isdigit() and 1 <= int(v) <= 50,
        "TAXA_OPERACAO_BPS": lambda v: v.isdigit() and 0 <= int(v) <= 500,
    }

    @classmethod
    def validar_valor(cls, chave: str, valor: str) -> None:
        validador = cls.VALIDADORES.get(chave)
        if validador is None or not isinstance(valor, str) or not validador(valor):
            raise DadosInvalidos("Parâmetro ou valor inválido.")

    @classmethod
    def de_dicionario(cls, dados: dict[str, str]) -> "ParametrosOperacionais":
        for chave in cls.VALIDADORES:
            if chave not in dados:
                raise DadosInvalidos(f"Parâmetro ausente: {chave}.")
            cls.validar_valor(chave, dados[chave])
        try:
            fuso = ZoneInfo(dados["PREGAO_FUSO"])
        except ZoneInfoNotFoundError as exc:  # pragma: no cover - depende do sistema
            raise DadosInvalidos("Fuso horário indisponível; instale o pacote tzdata.") from exc
        abertura = time.fromisoformat(dados["PREGAO_ABERTURA"])
        fechamento = time.fromisoformat(dados["PREGAO_FECHAMENTO"])
        if abertura >= fechamento:
            raise DadosInvalidos("Abertura do pregão deve ser antes do fechamento.")
        return cls(abertura, fechamento, fuso, dados["PREGAO_DIAS"] == "TODOS", int(dados["COTACAO_IDADE_MAX_S"]),
                   int(dados["FAIXA_PRECO_PCT"]), int(dados["TAXA_OPERACAO_BPS"]))

    def mercado_aberto(self, agora: datetime) -> bool:
        local = agora.astimezone(self.fuso)
        dia_permitido = self.todos_os_dias or local.weekday() < 5
        return dia_permitido and self.pregao_abertura <= local.time() < self.pregao_fechamento
