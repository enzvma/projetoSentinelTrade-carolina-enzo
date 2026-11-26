"""Integração com a Corretora/Bolsa Simulada (RF-12, RNF-12, RNF-13, RN-11).

- `CorretoraGateway`: interface (classe abstrata) usada pelos serviços.
- `CorretoraSimulada`: implementação em memória que executa ordens com base nas cotações simuladas.
- `CorretoraResiliente`: decorador que aplica tempo limite, retentativa com espera crescente e
  validação da resposta; converte qualquer falha em `FalhaIntegracao`.
"""
from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as TempoEsgotado
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..dominio.dinheiro import Dinheiro
from ..dominio.enums import Lado, TipoOrdem
from ..dominio.erros import FalhaIntegracao

log = logging.getLogger(__name__)

StatusCorretora = Literal["ACEITA", "EXECUTADA", "PARCIAL", "REJEITADA", "CANCELADA", "NAO_ENCONTRADA"]


@dataclass(frozen=True)
class PedidoCorretora:
    id_corretora: str
    ticker: str
    lado: Lado
    tipo: TipoOrdem
    quantidade: int
    preco: Dinheiro | None


@dataclass(frozen=True)
class ExecucaoCorretora:
    id_execucao: str
    quantidade: int
    preco: Dinheiro


@dataclass(frozen=True)
class RespostaCorretora:
    status: StatusCorretora
    execucoes: tuple[ExecucaoCorretora, ...] = ()


# ---- validação da resposta externa (não confiável) --------------------------------------------
class _ExecucaoExterna(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id_execucao: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    quantidade: int = Field(ge=1, le=1_000_000)
    preco_centavos: int = Field(ge=1, le=10**12)


class _RespostaExterna(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    status: StatusCorretora
    execucoes: list[_ExecucaoExterna] = Field(default_factory=list, max_length=1000)


def interpretar_resposta(dados: object) -> RespostaCorretora:
    """Converte a resposta bruta da corretora; formato inesperado vira FalhaIntegracao."""
    try:
        r = _RespostaExterna.model_validate(dados)
    except ValidationError as exc:
        raise FalhaIntegracao("Resposta da corretora em formato inesperado.") from exc
    return RespostaCorretora(r.status, tuple(ExecucaoCorretora(e.id_execucao, e.quantidade, Dinheiro(e.preco_centavos))
                                             for e in r.execucoes))


class CorretoraGateway(ABC):
    @abstractmethod
    def enviar(self, pedido: PedidoCorretora) -> RespostaCorretora: ...
    @abstractmethod
    def consultar(self, id_corretora: str) -> RespostaCorretora: ...
    @abstractmethod
    def cancelar(self, id_corretora: str) -> RespostaCorretora: ...
    @abstractmethod
    def saude(self) -> bool: ...


# ---- corretora simulada -----------------------------------------------------------------------
@dataclass
class _OrdemNaCorretora:
    pedido: PedidoCorretora
    status: str = "ACEITA"
    execucoes: list[dict] = field(default_factory=list)

    @property
    def executada(self) -> int:
        return sum(e["quantidade"] for e in self.execucoes)


class CorretoraSimulada(CorretoraGateway):
    """Bolsa simulada em memória. Devolve dicionários (como uma API externa faria).

    - Ordens a mercado executam no preço atual; limitadas, quando o preço atual as alcança.
    - `liquidez` limita a quantidade executada por rodada (para simular execução parcial).
    - O mesmo `id_corretora` nunca gera duas ordens: reenvios devolvem o estado já existente.
    - Para testes, é possível simular indisponibilidade, lentidão, rejeição e resposta malformada.
    """

    def __init__(self, preco_atual: Callable[[str], Dinheiro | None], liquidez: int | None = None) -> None:
        self._preco_atual = preco_atual
        self._liquidez = liquidez
        self._ordens: dict[str, _OrdemNaCorretora] = {}
        self._lock = threading.Lock()
        self._sequencia = 0
        self.indisponivel = False
        self.atraso_segundos = 0.0
        self.rejeitar_tickers: set[str] = set()
        self.resposta_malformada = False
        self.chamadas_enviar = 0

    def _simular_falhas(self) -> None:
        if self.atraso_segundos:
            time.sleep(self.atraso_segundos)
        if self.indisponivel:
            raise ConnectionError("corretora simulada indisponível")

    def _resposta(self, o: _OrdemNaCorretora | None) -> dict:
        if self.resposta_malformada:
            return {"status": "EXECUTADA", "execucoes": [{"quantidade": "muitas"}]}
        if o is None:
            return {"status": "NAO_ENCONTRADA", "execucoes": []}
        return {"status": o.status, "execucoes": [dict(e) for e in o.execucoes]}

    def _tentar_executar(self, o: _OrdemNaCorretora) -> None:
        if o.status not in ("ACEITA", "PARCIAL"):
            return
        preco = self._preco_atual(o.pedido.ticker)
        if preco is None:
            return
        p = o.pedido
        if p.tipo is TipoOrdem.LIMITADA:
            alcancou = preco <= p.preco if p.lado is Lado.COMPRA else preco >= p.preco
            if not alcancou:
                return
        restante = p.quantidade - o.executada
        quantidade = restante if self._liquidez is None else min(restante, self._liquidez)
        self._sequencia += 1
        o.execucoes.append({"id_execucao": f"EX-{p.id_corretora}-{self._sequencia}",
                            "quantidade": quantidade, "preco_centavos": preco.centavos})
        o.status = "EXECUTADA" if o.executada == p.quantidade else "PARCIAL"

    def enviar(self, pedido: PedidoCorretora) -> dict:  # type: ignore[override]
        self._simular_falhas()
        with self._lock:
            self.chamadas_enviar += 1
            o = self._ordens.get(pedido.id_corretora)
            if o is None:
                o = _OrdemNaCorretora(pedido)
                if pedido.ticker in self.rejeitar_tickers:
                    o.status = "REJEITADA"
                self._ordens[pedido.id_corretora] = o
                self._tentar_executar(o)
            return self._resposta(o)

    def consultar(self, id_corretora: str) -> dict:  # type: ignore[override]
        self._simular_falhas()
        with self._lock:
            o = self._ordens.get(id_corretora)
            if o is not None:
                self._tentar_executar(o)
            return self._resposta(o)

    def cancelar(self, id_corretora: str) -> dict:  # type: ignore[override]
        self._simular_falhas()
        with self._lock:
            o = self._ordens.get(id_corretora)
            if o is not None and o.status in ("ACEITA", "PARCIAL"):
                o.status = "CANCELADA"
            return self._resposta(o)

    def saude(self) -> bool:
        return not self.indisponivel


# ---- decorador resiliente ---------------------------------------------------------------------
class CorretoraResiliente(CorretoraGateway):
    """Tempo limite por chamada (RNF-12) e até N tentativas com espera crescente (RNF-13)."""

    def __init__(self, interna: CorretoraGateway, timeout_s: float = 3.0, tentativas: int = 3,
                 espera_inicial_s: float = 0.2, dormir: Callable[[float], None] = time.sleep) -> None:
        self._interna = interna
        self._timeout_s = timeout_s
        self._tentativas = tentativas
        self._espera_inicial_s = espera_inicial_s
        self._dormir = dormir
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="corretora")

    def _chamar(self, nome: str, *args) -> RespostaCorretora:
        ultima: Exception | None = None
        for tentativa in range(1, self._tentativas + 1):
            futuro = self._executor.submit(getattr(self._interna, nome), *args)
            try:
                bruto = futuro.result(timeout=self._timeout_s)
                return bruto if isinstance(bruto, RespostaCorretora) else interpretar_resposta(bruto)
            except FalhaIntegracao as exc:      # resposta malformada: repetir não resolve
                log.warning("resposta inválida da corretora", extra={"dados": {"operacao": nome}})
                raise exc
            except (TempoEsgotado, ConnectionError, OSError) as exc:
                ultima = exc
                log.warning("falha temporária na corretora",
                            extra={"dados": {"operacao": nome, "tentativa": tentativa, "erro": type(exc).__name__}})
                if tentativa < self._tentativas:
                    self._dormir(self._espera_inicial_s * (2 ** (tentativa - 1)))
        raise FalhaIntegracao() from ultima

    def enviar(self, pedido: PedidoCorretora) -> RespostaCorretora:
        return self._chamar("enviar", pedido)

    def consultar(self, id_corretora: str) -> RespostaCorretora:
        return self._chamar("consultar", id_corretora)

    def cancelar(self, id_corretora: str) -> RespostaCorretora:
        return self._chamar("cancelar", id_corretora)

    def saude(self) -> bool:
        futuro = self._executor.submit(self._interna.saude)
        try:
            return bool(futuro.result(timeout=self._timeout_s))
        except Exception:  # noqa: BLE001 - qualquer falha significa indisponível
            return False
