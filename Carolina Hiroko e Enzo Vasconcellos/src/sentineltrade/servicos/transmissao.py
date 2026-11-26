"""Processamento da fila e transmissão à corretora simulada (UC-16, UC-17).

Garantias:
- antes de enviar, a corretora é sempre consultada: uma ordem nunca é reenviada às cegas (RN-11);
- o identificador enviado à corretora é fixo por ordem, então reenvios não duplicam (RNF-08);
- cada execução tem identificador único e só é aplicada uma vez;
- a chamada externa acontece fora da transação; o resultado é aplicado numa transação atômica (RNF-18);
- após 3 rodadas sem resposta, o item fica em FALHA, o sistema entra em modo restrito e o investidor
  é avisado; a ordem e os bloqueios são preservados (RN-18, RNF-16).
"""
from __future__ import annotations

import logging
import uuid
from datetime import timedelta

from ..dominio.conta import Posicao
from ..dominio.dinheiro import Dinheiro
from ..dominio.enums import EstadoOrdem, Lado, MotivoRejeicao, OrigemTransicao, TipoOrdem
from ..dominio.erros import FalhaIntegracao
from ..dominio.ordem import Ordem
from ..integracoes.corretora import CorretoraGateway, PedidoCorretora, RespostaCorretora
from ..logs import correlation_id
from ..relogio import Relogio
from .auditoria import ServicoAuditoria
from .comum import carregar_parametros
from .eventos import PublicadorEventosOrdem
from .ordens import ServicoOrdens

log = logging.getLogger(__name__)

MAX_RODADAS = 3
ATOR = "sistema"


class ServicoTransmissao:
    def __init__(self, fabrica_uow, corretora: CorretoraGateway, relogio: Relogio,
                 publicador: PublicadorEventosOrdem, auditoria: ServicoAuditoria, ordens: ServicoOrdens) -> None:
        self._uow = fabrica_uow
        self._corretora = corretora
        self._relogio = relogio
        self._publicador = publicador
        self._auditoria = auditoria
        self._ordens = ordens

    # ---- ciclo completo ---------------------------------------------------------------------
    def ciclo(self) -> None:
        correlation_id.set(f"worker-{uuid.uuid4().hex[:12]}")
        self.verificar_saude()
        self.processar_fila()
        self.acompanhar_abertas()

    def verificar_saude(self) -> bool:
        disponivel = self._corretora.saude()
        agora = self._relogio.agora()
        with self._uow() as uow:
            restrito, _ = uow.estado_sistema.modo_restrito()
            if disponivel and restrito:
                uow.estado_sistema.definir(False, None, agora)
                reabertos = uow.fila.reabrir_falhas(agora)
                self._auditoria.registrar(uow, ator=ATOR, acao="MODO_RESTRITO_DESATIVADO", entidade="sistema",
                                          entidade_id=None, resultado="SUCESSO", detalhes={"itens_reabertos": reabertos})
            elif not disponivel and not restrito:
                self._ativar_modo_restrito(uow, agora)
            uow.confirmar()
        return disponivel

    def _ativar_modo_restrito(self, uow, agora) -> None:
        uow.estado_sistema.definir(True, "CORRETORA_INDISPONIVEL", agora)
        self._auditoria.registrar(uow, ator=ATOR, acao="MODO_RESTRITO_ATIVADO", entidade="sistema", entidade_id=None,
                                  resultado="SUCESSO", detalhes={"motivo": "CORRETORA_INDISPONIVEL"})
        log.warning("modo restrito ativado: corretora indisponível")

    # ---- fila ---------------------------------------------------------------------------------
    def processar_fila(self, limite: int = 50) -> int:
        with self._uow(somente_leitura=True) as uow:
            itens = uow.fila.proximos(self._relogio.agora(), limite)
        for item in itens:
            try:
                if item.operacao == "ENVIAR":
                    self._processar_envio(item)
                else:
                    self._processar_cancelamento(item)
            except FalhaIntegracao:
                self._registrar_falha(item)
            except Exception:  # noqa: BLE001 - um item com problema não pode parar o processamento dos demais
                log.exception("erro inesperado ao processar item da fila", extra={"dados": {"item_id": item.id}})
                self._registrar_falha(item)
        return len(itens)

    def _carregar(self, ordem_id: int) -> Ordem:
        with self._uow(somente_leitura=True) as uow:
            return uow.ordens.buscar(ordem_id)

    def _concluir(self, item_id: int) -> None:
        with self._uow() as uow:
            uow.fila.atualizar(item_id, "CONCLUIDA", 0, None)
            uow.confirmar()

    def _pedido(self, ordem: Ordem) -> PedidoCorretora:
        return PedidoCorretora(ordem.id_corretora, ordem.ticker, ordem.lado, ordem.tipo, ordem.quantidade, ordem.preco)

    def _processar_envio(self, item) -> None:
        ordem = self._carregar(item.ordem_id)
        with self._uow(somente_leitura=True) as uow:
            cancelamento_pedido = uow.fila.existe(ordem.id, "CANCELAR")
        if ordem.estado is not EstadoOrdem.VALIDADA or cancelamento_pedido:
            self._concluir(item.id)          # já resolvida, ou o cancelamento cuidará dela
            return
        resposta = self._corretora.consultar(ordem.id_corretora)     # RN-11: consulta antes de (re)enviar
        if resposta.status == "NAO_ENCONTRADA":
            resposta = self._corretora.enviar(self._pedido(ordem))
        self._aplicar(item.ordem_id, resposta, item_id=item.id)

    def _processar_cancelamento(self, item) -> None:
        ordem = self._carregar(item.ordem_id)
        if ordem.estado.final:
            self._resolver_derivadas(ordem.id)
            self._concluir(item.id)
            return
        resposta = self._corretora.consultar(ordem.id_corretora)
        if resposta.status in ("ACEITA", "PARCIAL"):
            resposta = self._corretora.cancelar(ordem.id_corretora)
        if resposta.status == "NAO_ENCONTRADA":
            self._cancelar_localmente(item)
        else:
            self._aplicar(item.ordem_id, resposta, item_id=item.id)
        self._resolver_derivadas(ordem.id)

    def _cancelar_localmente(self, item) -> None:
        """A ordem nunca chegou à corretora: cancela aqui e impede o envio pendente."""
        agora = self._relogio.agora()
        with self._uow() as uow:
            ordem = uow.ordens.buscar(item.ordem_id)
            if ordem.cancelavel:
                ordem.cancelar(OrigemTransicao.SISTEMA, agora)
                self._liberar_restante(uow, ordem)
                uow.ordens.atualizar(ordem)
                self._publicador.publicar(uow, ordem, ATOR)
            uow.fila.concluir_pendentes_da_ordem(ordem.id, "ENVIAR")
            uow.fila.atualizar(item.id, "CONCLUIDA", item.tentativas, None)
            uow.confirmar()

    def _resolver_derivadas(self, ordem_origem_id: int) -> None:
        """Depois do cancelamento da original, valida a ordem criada pela alteração (RN-19)."""
        agora = self._relogio.agora()
        with self._uow() as uow:
            original = uow.ordens.buscar(ordem_origem_id)
            if not original.estado.final:
                return
            for derivada in uow.ordens.derivadas_aguardando(ordem_origem_id):
                if original.estado is EstadoOrdem.CANCELADA:
                    self._ordens.validar_e_reservar(uow, derivada, agora)
                else:
                    derivada.rejeitar(MotivoRejeicao.ORDEM_ORIGINAL_EXECUTADA, OrigemTransicao.SISTEMA, agora)
                    uow.ordens.atualizar(derivada)
                self._publicador.publicar(uow, derivada, ATOR)
            uow.confirmar()

    # ---- ordens abertas na corretora ----------------------------------------------------------
    def acompanhar_abertas(self, limite: int = 100) -> None:
        with self._uow(somente_leitura=True) as uow:
            abertas = (uow.ordens.listar(conta_id=None, estado=EstadoOrdem.ENVIADA, ticker=None, limite=limite,
                                         deslocamento=0)
                       + uow.ordens.listar(conta_id=None, estado=EstadoOrdem.PARCIALMENTE_EXECUTADA, ticker=None,
                                           limite=limite, deslocamento=0))
        for ordem in abertas:
            try:
                resposta = self._corretora.consultar(ordem.id_corretora)
                if resposta.status == "NAO_ENCONTRADA":      # a corretora perdeu a ordem: reenvia com o mesmo id
                    resposta = self._corretora.enviar(self._pedido(ordem))
                self._aplicar(ordem.id, resposta)
            except FalhaIntegracao:
                log.warning("não foi possível acompanhar ordem aberta", extra={"dados": {"ordem_id": ordem.id}})

    # ---- aplicação da resposta (transação única) --------------------------------------------
    def _validar_resposta(self, ordem: Ordem, resposta: RespostaCorretora) -> None:
        """A resposta é tratada como não confiável: execuções precisam ser coerentes com a ordem."""
        total = sum(e.quantidade for e in resposta.execucoes)
        if total > ordem.quantidade:
            raise FalhaIntegracao("Execuções acima da quantidade da ordem.")
        if ordem.tipo is TipoOrdem.LIMITADA:
            for e in resposta.execucoes:
                if (ordem.lado is Lado.COMPRA and e.preco > ordem.preco) or (
                        ordem.lado is Lado.VENDA and e.preco < ordem.preco):
                    raise FalhaIntegracao("Execução fora do preço limite.")

    def _aplicar(self, ordem_id: int, resposta: RespostaCorretora, item_id: int | None = None) -> None:
        agora = self._relogio.agora()
        with self._uow() as uow:
            ordem = uow.ordens.buscar(ordem_id)
            self._validar_resposta(ordem, resposta)
            conta = uow.contas.buscar(ordem.conta_id)
            posicao = (uow.contas.buscar_posicao(conta.id, ordem.ativo_id)
                       or Posicao(conta_id=conta.id, ativo_id=ordem.ativo_id))
            taxa_bps = carregar_parametros(uow).taxa_operacao_bps

            if ordem.estado is EstadoOrdem.VALIDADA:
                if resposta.status == "REJEITADA":
                    ordem.rejeitar(MotivoRejeicao.REJEITADA_PELA_CORRETORA, OrigemTransicao.CORRETORA, agora)
                    self._liberar(conta, posicao, ordem)
                else:
                    ordem.marcar_enviada(agora)

            for execucao in resposta.execucoes:
                if ordem.estado.final or uow.ordens.execucao_registrada(execucao.id_execucao):
                    continue
                self._aplicar_execucao(uow, ordem, conta, posicao, execucao.quantidade, execucao.preco, taxa_bps, agora)
                uow.ordens.registrar_execucao(ordem.id, execucao.id_execucao, execucao.quantidade, execucao.preco, agora)

            if resposta.status == "CANCELADA" and ordem.cancelavel:
                ordem.cancelar(OrigemTransicao.CORRETORA, agora)
                self._liberar(conta, posicao, ordem)
            if ordem.estado is EstadoOrdem.EXECUTADA and ordem.lado is Lado.COMPRA:
                conta.liberar(ordem.liberar_bloqueio_restante())     # sobra da margem e da taxa estimada

            uow.contas.atualizar_saldos(conta)
            uow.contas.salvar_posicao(posicao)
            uow.ordens.atualizar(ordem)
            self._publicador.publicar(uow, ordem, ATOR)
            if item_id is not None:
                uow.fila.atualizar(item_id, "CONCLUIDA", 0, None)
            uow.confirmar()

    @staticmethod
    def _aplicar_execucao(uow, ordem: Ordem, conta, posicao: Posicao, quantidade: int, preco: Dinheiro,
                          taxa_bps: int, agora) -> None:
        bruto = preco.vezes(quantidade)
        taxa = bruto.percentual(taxa_bps, arredondar_para_cima=True)
        ordem.registrar_execucao(quantidade, agora)
        if ordem.lado is Lado.COMPRA:
            custo = bruto + taxa
            consumido = ordem.consumir_bloqueio(custo)
            conta.consumir_bloqueado(consumido)
            if consumido < custo:                      # preço acima da margem reservada
                conta.debitar_disponivel(custo - consumido)
            posicao.adicionar(quantidade, preco)
        else:
            posicao.consumir_bloqueada(quantidade)
            conta.creditar(bruto - taxa)

    @staticmethod
    def _liberar(conta, posicao: Posicao, ordem: Ordem) -> None:
        if ordem.lado is Lado.COMPRA:
            conta.liberar(ordem.liberar_bloqueio_restante())
        else:
            posicao.liberar(ordem.quantidade_restante)

    def _liberar_restante(self, uow, ordem: Ordem) -> None:
        conta = uow.contas.buscar(ordem.conta_id)
        if ordem.lado is Lado.COMPRA:
            conta.liberar(ordem.liberar_bloqueio_restante())
            uow.contas.atualizar_saldos(conta)
        else:
            posicao = uow.contas.buscar_posicao(conta.id, ordem.ativo_id)
            if posicao is not None:
                posicao.liberar(ordem.quantidade_restante)
                uow.contas.salvar_posicao(posicao)

    # ---- falhas -------------------------------------------------------------------------------
    def _registrar_falha(self, item) -> None:
        agora = self._relogio.agora()
        rodadas = item.tentativas + 1
        with self._uow() as uow:
            if rodadas >= MAX_RODADAS:
                uow.fila.atualizar(item.id, "FALHA", MAX_RODADAS, None)
                if not uow.estado_sistema.modo_restrito()[0]:
                    self._ativar_modo_restrito(uow, agora)
                ordem = uow.ordens.buscar(item.ordem_id)
                conta = uow.contas.buscar(ordem.conta_id)
                uow.notificacoes.criar(conta.usuario_id, ordem.id, f"ordem:{ordem.id}:FALHA:{item.operacao}", "FALHA",
                                       f"Ordem {ordem.id}: falha de comunicação com a corretora. A ordem foi "
                                       "preservada e será processada quando o serviço voltar.", agora)
                self._auditoria.registrar(uow, ator=ATOR, acao=f"TRANSMISSAO_{item.operacao}", entidade="ordem",
                                          entidade_id=ordem.id, resultado="FALHA", detalhes={"rodadas": rodadas})
            else:
                uow.fila.atualizar(item.id, "PENDENTE", rodadas, agora + timedelta(seconds=2 ** rodadas))
            uow.confirmar()
