"""Fonte única de tempo (UTC). Injetável para que regras de horário sejam testáveis."""
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone


class Relogio(ABC):
    @abstractmethod
    def agora(self) -> datetime: ...


class RelogioSistema(Relogio):
    def agora(self) -> datetime:
        return datetime.now(timezone.utc)


class RelogioFixo(Relogio):
    """Relógio controlado manualmente (testes e simulações)."""

    def __init__(self, inicio: datetime) -> None:
        if inicio.tzinfo is None:
            raise ValueError("o relógio exige datetime com fuso")
        self._agora = inicio

    def agora(self) -> datetime:
        return self._agora

    def avancar(self, **kwargs) -> None:
        self._agora += timedelta(**kwargs)
