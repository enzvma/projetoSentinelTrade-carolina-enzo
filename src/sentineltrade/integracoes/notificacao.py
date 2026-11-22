"""Serviço de notificação ao investidor (RF-09). A implementação simulada só registra as mensagens."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

log = logging.getLogger(__name__)


class Notificador(ABC):
    @abstractmethod
    def enviar(self, usuario_id: int, tipo: str, mensagem: str) -> None:
        """Entrega a mensagem; lança exceção se não conseguir."""


class NotificadorSimulado(Notificador):
    def __init__(self) -> None:
        self.enviadas: list[tuple[int, str, str]] = []
        self.indisponivel = False

    def enviar(self, usuario_id: int, tipo: str, mensagem: str) -> None:
        if self.indisponivel:
            raise ConnectionError("serviço de notificação simulado indisponível")
        self.enviadas.append((usuario_id, tipo, mensagem))
        log.info("notificação entregue", extra={"dados": {"usuario_id": usuario_id, "tipo": tipo}})
