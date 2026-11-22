"""Proteções HTTP: limite de tamanho do corpo, limite de frequência, cabeçalhos de segurança e rastreio."""
from __future__ import annotations

import json
import logging
import re
import threading
import time
import uuid
from collections import OrderedDict, deque

from ..logs import correlation_id

log = logging.getLogger(__name__)
_CORRELACAO_RE = re.compile(r"^[A-Za-z0-9-]{8,64}$")


class LimitadorJanela:
    """Limite de requisições por chave numa janela deslizante (RNF-11).

    Em memória: vale para um processo. O número de chaves é limitado para o limitador
    não virar, ele mesmo, um vetor de esgotamento de memória.
    """

    def __init__(self, maximo: int, janela_s: float = 60.0, max_chaves: int = 10_000, relogio=time.monotonic):
        self.maximo, self._janela, self._max_chaves, self._relogio = maximo, janela_s, max_chaves, relogio
        self._eventos: OrderedDict[str, deque] = OrderedDict()
        self._lock = threading.Lock()

    def permitir(self, chave: str) -> bool:
        agora = self._relogio()
        with self._lock:
            fila = self._eventos.get(chave)
            if fila is None:
                if len(self._eventos) >= self._max_chaves:
                    self._eventos.popitem(last=False)
                fila = self._eventos[chave] = deque()
            self._eventos.move_to_end(chave)
            while fila and agora - fila[0] >= self._janela:
                fila.popleft()
            if len(fila) >= self.maximo:
                return False
            fila.append(agora)
            return True


async def _responder_json(send, status: int, corpo: dict) -> None:
    dados = json.dumps(corpo, ensure_ascii=False).encode()
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(dados)).encode())]})
    await send({"type": "http.response.body", "body": dados})


class ProtecaoHttp:
    """Middleware ASGI: rastreio, limite de corpo (413) e cabeçalhos de segurança em toda resposta."""

    def __init__(self, app, max_bytes: int, csp_documentacao: bool) -> None:
        self.app = app
        self._max = max_bytes
        self._csp_documentacao = csp_documentacao

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        cabecalhos = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        recebido = cabecalhos.get("x-correlation-id", "")
        cid = recebido if _CORRELACAO_RE.fullmatch(recebido) else uuid.uuid4().hex
        token = correlation_id.set(cid)
        caminho = scope.get("path", "")
        documentacao = caminho.startswith("/docs") or caminho == "/openapi.json"

        iniciado = False

        async def enviar(mensagem):
            nonlocal iniciado
            if mensagem["type"] == "http.response.start":
                iniciado = True
                h = list(mensagem.get("headers", []))
                h += [(b"x-correlation-id", cid.encode()), (b"x-content-type-options", b"nosniff"),
                      (b"x-frame-options", b"DENY"), (b"referrer-policy", b"no-referrer"),
                      (b"cache-control", b"no-store")]
                if not (documentacao and self._csp_documentacao):
                    h.append((b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"))
                mensagem = {**mensagem, "headers": h}
            await send(mensagem)

        try:
            tamanho = cabecalhos.get("content-length")
            if tamanho is not None and (not tamanho.isdigit() or int(tamanho) > self._max):
                return await _responder_json(enviar, 413, {"erro": "CORPO_GRANDE", "mensagem": "Requisição muito grande.",
                                                           "correlation_id": cid})
            total = 0

            async def receber():
                nonlocal total
                mensagem = await receive()
                if mensagem["type"] == "http.request":
                    total += len(mensagem.get("body", b""))
                    if total > self._max:
                        raise _CorpoGrande()
                return mensagem

            try:
                await self.app(scope, receber, enviar)
            except _CorpoGrande:
                await _responder_json(enviar, 413, {"erro": "CORPO_GRANDE", "mensagem": "Requisição muito grande.",
                                                    "correlation_id": cid})
            except Exception:  # noqa: BLE001 - última barreira: nunca expor detalhes internos (RNF-06)
                log.exception("erro inesperado na requisição", extra={"dados": {"rota": caminho}})
                if not iniciado:
                    await _responder_json(enviar, 500, {"erro": "ERRO_INTERNO", "correlation_id": cid,
                                                        "mensagem": "Erro interno. Informe o código de rastreio ao suporte."})
        finally:
            correlation_id.reset(token)


class _CorpoGrande(Exception):
    pass
