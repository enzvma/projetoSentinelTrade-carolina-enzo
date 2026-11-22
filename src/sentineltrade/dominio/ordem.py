"""Entidade Ordem e sua máquina de estados (RF-08, RN-09).

O estado só muda pelos métodos da própria entidade, que conferem se a transição é
permitida. Cada mudança gera um evento (`TransicaoOrdem`) que os serviços publicam
para os observadores (auditoria, histórico de estados e notificações).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .dinheiro import Dinheiro
from .enums import EstadoOrdem, Lado, MotivoRejeicao, OrigemTransicao, TipoOrdem
from .erros import DadosInvalidos, OperacaoNaoPermitida, TransicaoInvalida

E = EstadoOrdem

# Transições permitidas: estados finais não têm saída e nenhum estado volta a CRIADA.
TRANSICOES: dict[EstadoOrdem, frozenset[EstadoOrdem]] = {
    E.CRIADA: frozenset({E.VALIDADA, E.REJEITADA, E.CANCELADA}),
    E.VALIDADA: frozenset({E.ENVIADA, E.REJEITADA, E.CANCELADA}),
    E.ENVIADA: frozenset({E.PARCIALMENTE_EXECUTADA, E.EXECUTADA, E.REJEITADA, E.CANCELADA}),
    E.PARCIALMENTE_EXECUTADA: frozenset({E.PARCIALMENTE_EXECUTADA, E.EXECUTADA, E.CANCELADA}),
    E.EXECUTADA: frozenset(),
    E.REJEITADA: frozenset(),
    E.CANCELADA: frozenset(),
}

ESTADOS_CANCELAVEIS = frozenset({E.CRIADA, E.VALIDADA, E.ENVIADA, E.PARCIALMENTE_EXECUTADA})
QUANTIDADE_MAXIMA = 1_000_000


@dataclass(frozen=True)
class TransicaoOrdem:
    anterior: EstadoOrdem | None
    novo: EstadoOrdem
    origem: OrigemTransicao
    data_hora: datetime
    motivo: str | None = None


class Ordem:
    """Ordem de compra ou venda. Atributos privados; leitura apenas por propriedades."""

    def __init__(self, *, id: int | None, conta_id: int, ativo_id: int, ticker: str,
                 chave_idempotencia: str, lado: Lado, tipo: TipoOrdem, quantidade: int,
                 preco: Dinheiro | None, estado: EstadoOrdem, quantidade_executada: int,
                 valor_bloqueado: Dinheiro, motivo: str | None, ordem_origem_id: int | None,
                 criada_em: datetime, atualizada_em: datetime) -> None:
        self._id = id
        self._conta_id = conta_id
        self._ativo_id = ativo_id
        self._ticker = ticker
        self._chave = chave_idempotencia
        self._lado = Lado(lado)
        self._tipo = TipoOrdem(tipo)
        self._quantidade = quantidade
        self._preco = preco
        self._estado = EstadoOrdem(estado)
        self._quantidade_executada = quantidade_executada
        self._valor_bloqueado = valor_bloqueado
        self._motivo = motivo
        self._ordem_origem_id = ordem_origem_id
        self._criada_em = criada_em
        self._atualizada_em = atualizada_em
        self._eventos: list[TransicaoOrdem] = []
        self._validar_invariantes()

    # ---- criação ----------------------------------------------------------------------
    @classmethod
    def nova(cls, *, conta_id: int, ativo_id: int, ticker: str, chave_idempotencia: str, lado: Lado,
             tipo: TipoOrdem, quantidade: int, preco: Dinheiro | None, agora: datetime,
             ordem_origem_id: int | None = None) -> "Ordem":
        ordem = cls(id=None, conta_id=conta_id, ativo_id=ativo_id, ticker=ticker,
                    chave_idempotencia=chave_idempotencia, lado=lado, tipo=tipo, quantidade=quantidade,
                    preco=preco, estado=E.CRIADA, quantidade_executada=0, valor_bloqueado=Dinheiro.zero(),
                    motivo=None, ordem_origem_id=ordem_origem_id, criada_em=agora, atualizada_em=agora)
        ordem._eventos.append(TransicaoOrdem(None, E.CRIADA, OrigemTransicao.USUARIO, agora))
        return ordem

    def _validar_invariantes(self) -> None:
        if isinstance(self._quantidade, bool) or not isinstance(self._quantidade, int):
            raise DadosInvalidos("Quantidade inválida.")
        if not 1 <= self._quantidade <= QUANTIDADE_MAXIMA:
            raise DadosInvalidos("Quantidade fora do intervalo permitido.")
        if self._tipo is TipoOrdem.LIMITADA and (self._preco is None or self._preco.centavos <= 0):
            raise DadosInvalidos("Ordem limitada exige preço positivo.")
        if self._tipo is TipoOrdem.MERCADO and self._preco is not None:
            raise DadosInvalidos("Ordem a mercado não aceita preço.")
        if not 0 <= self._quantidade_executada <= self._quantidade:
            raise DadosInvalidos("Quantidade executada inconsistente.")
        if self._valor_bloqueado.e_negativo():
            raise DadosInvalidos("Valor bloqueado inconsistente.")

    # ---- leitura ----------------------------------------------------------------------
    id = property(lambda self: self._id)
    conta_id = property(lambda self: self._conta_id)
    ativo_id = property(lambda self: self._ativo_id)
    ticker = property(lambda self: self._ticker)
    chave_idempotencia = property(lambda self: self._chave)
    lado = property(lambda self: self._lado)
    tipo = property(lambda self: self._tipo)
    quantidade = property(lambda self: self._quantidade)
    preco = property(lambda self: self._preco)
    estado = property(lambda self: self._estado)
    quantidade_executada = property(lambda self: self._quantidade_executada)
    valor_bloqueado = property(lambda self: self._valor_bloqueado)
    motivo = property(lambda self: self._motivo)
    ordem_origem_id = property(lambda self: self._ordem_origem_id)
    criada_em = property(lambda self: self._criada_em)
    atualizada_em = property(lambda self: self._atualizada_em)

    @property
    def quantidade_restante(self) -> int:
        return self._quantidade - self._quantidade_executada

    @property
    def cancelavel(self) -> bool:
        return self._estado in ESTADOS_CANCELAVEIS

    @property
    def id_corretora(self) -> str:
        """Identificador enviado à corretora; o mesmo em todo reenvio (idempotência)."""
        if self._id is None:
            raise OperacaoNaoPermitida("Ordem ainda não persistida.")
        return f"ST-{self._id}"

    def definir_id(self, novo_id: int) -> None:
        if self._id is not None:
            raise OperacaoNaoPermitida("Identificador da ordem já definido.")
        self._id = novo_id

    def mesmo_conteudo(self, *, ativo_id: int, lado: Lado, tipo: TipoOrdem, quantidade: int,
                       preco: Dinheiro | None) -> bool:
        """Usado na idempotência: mesma chave com conteúdo diferente é conflito."""
        return (self._ativo_id, self._lado, self._tipo, self._quantidade, self._preco) == (
            ativo_id, Lado(lado), TipoOrdem(tipo), quantidade, preco)

    # ---- transições -------------------------------------------------------------------
    def _transitar(self, novo: EstadoOrdem, origem: OrigemTransicao, agora: datetime,
                   motivo: str | None = None) -> None:
        if novo not in TRANSICOES[self._estado]:
            raise TransicaoInvalida()
        anterior = self._estado
        self._estado = novo
        self._atualizada_em = agora
        if motivo is not None:
            self._motivo = motivo
        self._eventos.append(TransicaoOrdem(anterior, novo, origem, agora, motivo))

    def marcar_validada(self, valor_bloqueado: Dinheiro, agora: datetime) -> None:
        self._transitar(E.VALIDADA, OrigemTransicao.SISTEMA, agora)
        self._valor_bloqueado = valor_bloqueado

    def marcar_enviada(self, agora: datetime) -> None:
        self._transitar(E.ENVIADA, OrigemTransicao.SISTEMA, agora)

    def rejeitar(self, motivo: MotivoRejeicao, origem: OrigemTransicao, agora: datetime) -> None:
        self._transitar(E.REJEITADA, origem, agora, motivo.value)

    def cancelar(self, origem: OrigemTransicao, agora: datetime, motivo: str | None = None) -> None:
        if not self.cancelavel:
            raise OperacaoNaoPermitida("Ordem executada, rejeitada ou cancelada não pode ser cancelada.")
        self._transitar(E.CANCELADA, origem, agora, motivo)

    def registrar_execucao(self, quantidade: int, agora: datetime) -> None:
        """Aplica uma execução (total ou parcial) informada pela corretora."""
        if isinstance(quantidade, bool) or not isinstance(quantidade, int) or quantidade <= 0:
            raise DadosInvalidos("Quantidade executada inválida.")
        if quantidade > self.quantidade_restante:
            raise DadosInvalidos("Execução acima da quantidade restante.")
        novo = E.EXECUTADA if quantidade == self.quantidade_restante else E.PARCIALMENTE_EXECUTADA
        self._transitar(novo, OrigemTransicao.CORRETORA, agora)
        self._quantidade_executada += quantidade

    # ---- bloqueio de saldo da ordem de compra -----------------------------------------
    def consumir_bloqueio(self, valor: Dinheiro) -> Dinheiro:
        """Reduz o valor bloqueado da ordem e devolve quanto foi efetivamente consumido."""
        consumido = valor if valor <= self._valor_bloqueado else self._valor_bloqueado
        self._valor_bloqueado = self._valor_bloqueado - consumido
        return consumido

    def liberar_bloqueio_restante(self) -> Dinheiro:
        restante = self._valor_bloqueado
        self._valor_bloqueado = Dinheiro.zero()
        return restante

    # ---- eventos ----------------------------------------------------------------------
    def coletar_eventos(self) -> list[TransicaoOrdem]:
        eventos, self._eventos = self._eventos, []
        return eventos
