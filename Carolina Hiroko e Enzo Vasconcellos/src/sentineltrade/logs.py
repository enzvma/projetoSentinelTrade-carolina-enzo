"""Logs estruturados em JSON, sem segredos e com identificador de rastreio (RNF-25, RNF-27).

Cada linha é um objeto JSON: quebras de linha vindas de entradas não conseguem forjar
novas linhas de log. Chaves sensíveis são mascaradas e textos longos são truncados.
"""
from __future__ import annotations

import contextvars
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default="-")

_SENSIVEL = re.compile(r"senha|password|secret|segredo|token|authorization|api[_-]?key|cookie|codigo|otpauth", re.I)
_LIMITE = 300


def mascarar(valor: Any, chave: str | None = None) -> Any:
    if chave is not None and _SENSIVEL.search(chave):
        return "***"
    if isinstance(valor, dict):
        return {str(k): mascarar(v, str(k)) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [mascarar(v) for v in valor]
    if isinstance(valor, str) and len(valor) > _LIMITE:
        return valor[:_LIMITE] + "...[truncado]"
    return valor


class FormatadorJson(logging.Formatter):
    def format(self, registro: logging.LogRecord) -> str:
        saida: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "nivel": registro.levelname,
            "origem": registro.name,
            "msg": mascarar(registro.getMessage()),
            "correlation_id": correlation_id.get(),
        }
        dados = getattr(registro, "dados", None)
        if dados:
            saida["dados"] = mascarar(dados)
        if registro.exc_info and registro.exc_info[0] is not None:
            saida["excecao"] = registro.exc_info[0].__name__   # só o tipo; detalhes ficam fora do log
        return json.dumps(saida, ensure_ascii=False, default=str)


def configurar_logs(nivel: str = "INFO") -> None:
    raiz = logging.getLogger()
    if not any(isinstance(h.formatter, FormatadorJson) for h in raiz.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(FormatadorJson())
        raiz.addHandler(handler)
    raiz.setLevel(nivel)
