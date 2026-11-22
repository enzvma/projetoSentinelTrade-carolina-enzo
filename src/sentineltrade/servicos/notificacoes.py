"""Entrega das notificações pendentes (RF-09, RN-15). Falha na entrega não desfaz a operação."""
from __future__ import annotations

import logging

from ..integracoes.notificacao import Notificador

log = logging.getLogger(__name__)
MAX_TENTATIVAS = 5


class ServicoNotificacoes:
    def __init__(self, fabrica_uow, notificador: Notificador) -> None:
        self._uow = fabrica_uow
        self._notificador = notificador

    def despachar(self, limite: int = 50) -> int:
        with self._uow(somente_leitura=True) as uow:
            pendentes = uow.notificacoes.pendentes(limite)
        entregues = 0
        for n in pendentes:
            try:
                self._notificador.enviar(n.usuario_id, n.tipo, n.mensagem)
                situacao, tentativas = "ENVIADA", n.tentativas + 1
                entregues += 1
            except Exception:  # noqa: BLE001 - qualquer falha do serviço externo: tentar depois
                tentativas = n.tentativas + 1
                situacao = "FALHA" if tentativas >= MAX_TENTATIVAS else "PENDENTE"
                log.warning("falha ao entregar notificação", extra={"dados": {"notificacao_id": n.id}})
            with self._uow() as uow:
                uow.notificacoes.marcar(n.id, situacao, tentativas)
                uow.confirmar()
        return entregues
