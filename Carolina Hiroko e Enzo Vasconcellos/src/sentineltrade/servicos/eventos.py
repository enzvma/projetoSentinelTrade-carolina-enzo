"""Publicação das mudanças de estado da ordem para os observadores (padrão Observer).

Cada transição da Ordem é entregue a: histórico de estados (RF-08), auditoria (RN-16) e
notificação ao investidor (RF-09, RN-20). Tudo na mesma transação da mudança.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..dominio.enums import EstadoOrdem, OrigemTransicao
from ..dominio.ordem import Ordem, TransicaoOrdem
from .auditoria import ServicoAuditoria


class ObservadorOrdem(ABC):
    @abstractmethod
    def ao_mudar_estado(self, uow, ordem: Ordem, transicao: TransicaoOrdem, ator: str) -> None: ...


class HistoricoEstados(ObservadorOrdem):
    def ao_mudar_estado(self, uow, ordem, transicao, ator):
        uow.ordens.registrar_transicao(ordem.id, transicao)


class AuditoriaDeOrdem(ObservadorOrdem):
    def __init__(self, auditoria: ServicoAuditoria) -> None:
        self._auditoria = auditoria

    def ao_mudar_estado(self, uow, ordem, transicao, ator):
        quem = ator if transicao.origem is OrigemTransicao.USUARIO else transicao.origem.value.lower()
        self._auditoria.registrar(
            uow, ator=quem, acao=f"ORDEM_{transicao.novo.value}", entidade="ordem", entidade_id=ordem.id,
            resultado="SUCESSO",
            detalhes={"de": transicao.anterior.value if transicao.anterior else None, "para": transicao.novo.value,
                      "motivo": transicao.motivo, "origem": transicao.origem.value,
                      "executada": ordem.quantidade_executada})


class NotificacaoDeOrdem(ObservadorOrdem):
    _TIPOS = {
        EstadoOrdem.EXECUTADA: ("EXECUCAO", "executada"),
        EstadoOrdem.PARCIALMENTE_EXECUTADA: ("EXECUCAO_PARCIAL", "parcialmente executada"),
        EstadoOrdem.REJEITADA: ("REJEICAO", "rejeitada"),
        EstadoOrdem.CANCELADA: ("CANCELAMENTO", "cancelada"),
    }

    def ao_mudar_estado(self, uow, ordem, transicao, ator):
        if transicao.novo not in self._TIPOS:
            return
        tipo, texto = self._TIPOS[transicao.novo]
        conta = uow.contas.buscar(ordem.conta_id)
        mensagem = (f"Ordem {ordem.id} de {ordem.lado.value.lower()} de {ordem.ticker} {texto}"
                    f" ({ordem.quantidade_executada}/{ordem.quantidade})"
                    + (f": {transicao.motivo}" if transicao.motivo else "."))
        chave = f"ordem:{ordem.id}:{transicao.novo.value}:{ordem.quantidade_executada}"
        uow.notificacoes.criar(conta.usuario_id, ordem.id, chave, tipo, mensagem[:200], transicao.data_hora)


class PublicadorEventosOrdem:
    def __init__(self, observadores: list[ObservadorOrdem]) -> None:
        self._observadores = list(observadores)

    def publicar(self, uow, ordem: Ordem, ator: str) -> None:
        for transicao in ordem.coletar_eventos():
            for observador in self._observadores:
                observador.ao_mudar_estado(uow, ordem, transicao, ator)
