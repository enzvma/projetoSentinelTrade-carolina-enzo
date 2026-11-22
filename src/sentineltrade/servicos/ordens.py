"""Casos de uso de ordens: enviar (compra e venda), consultar, alterar e cancelar (UC-10 a UC-14, UC-20, UC-21)."""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from ..dominio.conta import Conta
from ..dominio.dinheiro import Dinheiro
from ..dominio.enums import EstadoOrdem, Lado, MotivoRejeicao, OrigemTransicao, Perfil, TipoOrdem
from ..dominio.erros import (AcessoNegado, ConflitoIdempotencia, DadosInvalidos, NaoEncontrado,
                             OperacaoNaoPermitida, RegraViolada, ServicoIndisponivel)
from ..dominio.ordem import Ordem
from ..dominio.usuario import Usuario
from ..regras import ContextoValidacao, ValidadorOrdem, calcular_valores
from ..relogio import Relogio
from .auditoria import ServicoAuditoria
from .comum import ator_de, carregar_parametros, exigir_perfil
from .eventos import PublicadorEventosOrdem

log = logging.getLogger(__name__)

ESTADOS_ALTERAVEIS = (EstadoOrdem.VALIDADA, EstadoOrdem.ENVIADA, EstadoOrdem.PARCIALMENTE_EXECUTADA)
PERFIS_GESTAO = (Perfil.ANALISTA_RISCO, Perfil.ADMINISTRADOR)


@dataclass(frozen=True)
class DadosOrdem:
    ticker: str
    lado: Lado
    tipo: TipoOrdem
    quantidade: int
    preco: Decimal | None
    chave_idempotencia: str


@dataclass(frozen=True)
class DadosAlteracao:
    quantidade: int | None
    preco: Decimal | None
    chave_idempotencia: str


class ServicoOrdens:
    def __init__(self, fabrica_uow, relogio: Relogio, validador: ValidadorOrdem,
                 publicador: PublicadorEventosOrdem, auditoria: ServicoAuditoria) -> None:
        self._uow = fabrica_uow
        self._relogio = relogio
        self._validador = validador
        self._publicador = publicador
        self._auditoria = auditoria

    # ---- auxiliares -------------------------------------------------------------------------
    @staticmethod
    def _conta_do(uow, usuario: Usuario) -> Conta:
        conta = uow.contas.buscar_por_usuario(usuario.id)
        if conta is None:
            raise AcessoNegado()
        return conta

    def _ordem_visivel(self, uow, usuario: Usuario, ordem_id: int, somente_titular: bool) -> Ordem:
        """RN-08: o investidor só enxerga as próprias ordens; ordens de terceiros 'não existem' para ele."""
        ordem = uow.ordens.buscar(ordem_id)
        if usuario.perfil is Perfil.INVESTIDOR:
            conta = uow.contas.buscar_por_usuario(usuario.id)
            if ordem is None or conta is None or ordem.conta_id != conta.id:
                raise NaoEncontrado("Ordem não encontrada.")
            return ordem
        if somente_titular or usuario.perfil not in PERFIS_GESTAO:
            raise AcessoNegado()
        if ordem is None:
            raise NaoEncontrado("Ordem não encontrada.")
        return ordem

    @staticmethod
    def _preco(valor: Decimal | None) -> Dinheiro | None:
        return Dinheiro.de_decimal(valor) if valor is not None else None

    # ---- validação e reserva (UC-14, UC-15) -------------------------------------------------
    def validar_e_reservar(self, uow, ordem: Ordem, agora: datetime) -> None:
        """Aplica as regras; se aprovada, bloqueia saldo ou posição e coloca na fila de envio."""
        conta = uow.contas.buscar(ordem.conta_id)
        ativo = uow.ativos.buscar_por_id(ordem.ativo_id)
        cotacao = uow.ativos.ultima_cotacao(ativo.id)
        posicao = uow.contas.buscar_posicao(conta.id, ativo.id)
        limite = uow.contas.buscar_limite(conta.id)
        parametros = carregar_parametros(uow)
        try:
            if limite is None:                        # conta sem limite definido: nega por padrão
                raise RegraViolada(MotivoRejeicao.LIMITE_RISCO_EXCEDIDO)
            valores = calcular_valores(ordem, cotacao, parametros)
            ctx = ContextoValidacao(
                ordem=ordem, conta=conta, ativo=ativo, cotacao=cotacao, posicao=posicao, limite=limite,
                parametros=parametros, agora=agora, exposicao_atual=uow.contas.exposicao_compras_abertas(conta.id),
                valor_estimado=valores.valor_estimado if valores else None,
                valor_bloqueio=valores.valor_bloqueio if valores else None)
            self._validador.validar(ctx)
            if ordem.lado is Lado.COMPRA:
                conta.bloquear(valores.valor_bloqueio)
                uow.contas.atualizar_saldos(conta)
                ordem.marcar_validada(valores.valor_bloqueio, agora)
            else:
                posicao.bloquear(ordem.quantidade)
                uow.contas.salvar_posicao(posicao)
                ordem.marcar_validada(Dinheiro.zero(), agora)
            uow.fila.enfileirar(ordem.id, "ENVIAR", agora)
        except RegraViolada as violacao:
            ordem.rejeitar(violacao.motivo, OrigemTransicao.SISTEMA, agora)
        uow.ordens.atualizar(ordem)

    # ---- enviar ordem (UC-10, UC-11) --------------------------------------------------------
    def criar(self, usuario: Usuario, dados: DadosOrdem) -> tuple[Ordem, bool]:
        """Devolve (ordem, criada). Repetir a mesma chave devolve a ordem original (RN-12)."""
        exigir_perfil(usuario, Perfil.INVESTIDOR)
        agora = self._relogio.agora()
        preco = self._preco(dados.preco)
        try:
            with self._uow() as uow:
                conta = self._conta_do(uow, usuario)
                ativo = uow.ativos.buscar_por_ticker(dados.ticker)
                if ativo is None:
                    raise DadosInvalidos("Ativo não encontrado.")
                existente = uow.ordens.buscar_por_chave(conta.id, dados.chave_idempotencia)
                if existente is not None:
                    return self._idempotente(existente, ativo.id, dados, preco, None), False
                if uow.estado_sistema.modo_restrito()[0]:
                    raise ServicoIndisponivel()
                ordem = Ordem.nova(conta_id=conta.id, ativo_id=ativo.id, ticker=ativo.ticker,
                                   chave_idempotencia=dados.chave_idempotencia, lado=dados.lado, tipo=dados.tipo,
                                   quantidade=dados.quantidade, preco=preco, agora=agora)
                uow.ordens.inserir(ordem)
                self.validar_e_reservar(uow, ordem, agora)
                self._publicador.publicar(uow, ordem, ator_de(usuario))
                uow.confirmar()
                return ordem, True
        except sqlite3.IntegrityError:
            # Duas requisições simultâneas com a mesma chave: a segunda devolve a primeira.
            with self._uow(somente_leitura=True) as uow:
                conta = self._conta_do(uow, usuario)
                existente = uow.ordens.buscar_por_chave(conta.id, dados.chave_idempotencia)
            if existente is None:
                raise
            return self._idempotente(existente, existente.ativo_id, dados, preco, None), False

    @staticmethod
    def _idempotente(existente: Ordem, ativo_id: int, dados, preco, origem_id) -> Ordem:
        if (existente.ordem_origem_id == origem_id and existente.mesmo_conteudo(
                ativo_id=ativo_id, lado=dados.lado, tipo=dados.tipo, quantidade=dados.quantidade, preco=preco)):
            return existente
        raise ConflitoIdempotencia()

    # ---- consultar (UC-20, UC-21) ------------------------------------------------------------
    def consultar(self, usuario: Usuario, ordem_id: int) -> tuple[Ordem, list[dict]]:
        with self._uow(somente_leitura=True) as uow:
            ordem = self._ordem_visivel(uow, usuario, ordem_id, somente_titular=False)
            return ordem, uow.ordens.listar_transicoes(ordem.id)

    def listar(self, usuario: Usuario, *, estado: EstadoOrdem | None = None, ticker: str | None = None,
               conta_id: int | None = None, limite: int = 20, deslocamento: int = 0) -> list[Ordem]:
        with self._uow(somente_leitura=True) as uow:
            if usuario.perfil is Perfil.INVESTIDOR:
                conta_id = self._conta_do(uow, usuario).id       # ignora qualquer outra conta pedida
            else:
                exigir_perfil(usuario, *PERFIS_GESTAO)
            return uow.ordens.listar(conta_id=conta_id, estado=estado, ticker=ticker, limite=limite,
                                     deslocamento=deslocamento)

    # ---- cancelar (UC-13) --------------------------------------------------------------------
    def cancelar(self, usuario: Usuario, ordem_id: int) -> Ordem:
        """Ordens já na fila ou na corretora são canceladas pelo processador da fila (consulta a corretora antes)."""
        exigir_perfil(usuario, Perfil.INVESTIDOR)
        agora = self._relogio.agora()
        with self._uow() as uow:
            ordem = self._ordem_visivel(uow, usuario, ordem_id, somente_titular=True)
            if not ordem.cancelavel:
                raise OperacaoNaoPermitida("Ordem executada, rejeitada ou cancelada não pode ser cancelada.")
            if ordem.estado is EstadoOrdem.CRIADA:        # ordem derivada de alteração, sem bloqueio nem envio
                ordem.cancelar(OrigemTransicao.USUARIO, agora)
                uow.ordens.atualizar(ordem)
                self._publicador.publicar(uow, ordem, ator_de(usuario))
            elif not uow.fila.existe(ordem.id, "CANCELAR"):
                uow.fila.enfileirar(ordem.id, "CANCELAR", agora)
                self._auditoria.registrar(uow, ator=ator_de(usuario), acao="CANCELAMENTO_SOLICITADO",
                                          entidade="ordem", entidade_id=ordem.id, resultado="SUCESSO")
            uow.confirmar()
            return ordem

    # ---- alterar (RF-17, RN-19) --------------------------------------------------------------
    def alterar(self, usuario: Usuario, ordem_id: int, dados: DadosAlteracao) -> tuple[Ordem, bool]:
        """Cria uma nova ordem vinculada (estado CRIADA) e pede o cancelamento do restante da original.

        A nova ordem só é validada depois que o cancelamento da original for confirmado.
        """
        exigir_perfil(usuario, Perfil.INVESTIDOR)
        agora = self._relogio.agora()
        with self._uow() as uow:
            original = self._ordem_visivel(uow, usuario, ordem_id, somente_titular=True)
            if original.tipo is TipoOrdem.MERCADO and dados.preco is not None:
                raise DadosInvalidos("Ordem a mercado não aceita preço.")
            quantidade = dados.quantidade if dados.quantidade is not None else original.quantidade_restante
            preco = self._preco(dados.preco) if dados.preco is not None else original.preco
            existente = uow.ordens.buscar_por_chave(original.conta_id, dados.chave_idempotencia)
            if existente is not None:
                alvo = DadosOrdem(original.ticker, original.lado, original.tipo, quantidade, None, "")
                return self._idempotente(existente, original.ativo_id, alvo, preco, original.id), False
            if uow.estado_sistema.modo_restrito()[0]:
                raise ServicoIndisponivel()
            if original.estado not in ESTADOS_ALTERAVEIS:
                raise OperacaoNaoPermitida("Só ordens validadas, enviadas ou parcialmente executadas podem ser alteradas.")
            if uow.ordens.derivadas_aguardando(original.id):
                raise OperacaoNaoPermitida("Já existe uma alteração em andamento para esta ordem.")
            if quantidade == original.quantidade_restante and preco == original.preco:
                raise DadosInvalidos("A alteração deve mudar a quantidade ou o preço.")
            nova = Ordem.nova(conta_id=original.conta_id, ativo_id=original.ativo_id, ticker=original.ticker,
                              chave_idempotencia=dados.chave_idempotencia, lado=original.lado, tipo=original.tipo,
                              quantidade=quantidade, preco=preco, agora=agora, ordem_origem_id=original.id)
            uow.ordens.inserir(nova)
            uow.fila.enfileirar(original.id, "CANCELAR", agora)
            self._publicador.publicar(uow, nova, ator_de(usuario))
            self._auditoria.registrar(uow, ator=ator_de(usuario), acao="ALTERACAO_SOLICITADA", entidade="ordem",
                                      entidade_id=original.id, resultado="SUCESSO", detalhes={"nova_ordem": nova.id})
            uow.confirmar()
            return nova, True
