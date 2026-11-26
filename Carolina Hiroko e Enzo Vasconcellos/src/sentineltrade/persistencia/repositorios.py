"""Interfaces dos repositórios (classes abstratas). A implementação SQLite está em sqlite.py.

Os serviços dependem só destas interfaces, o que permite trocar o banco ou usar dublês nos testes.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from ..dominio.conta import Conta, LimiteRisco, Posicao
from ..dominio.dinheiro import Dinheiro
from ..dominio.enums import EstadoOrdem
from ..dominio.mercado import Ativo, Cotacao
from ..dominio.ordem import Ordem, TransicaoOrdem
from ..dominio.usuario import Usuario


@dataclass(frozen=True)
class ItemFila:
    id: int
    ordem_id: int
    operacao: str
    situacao: str
    tentativas: int


@dataclass(frozen=True)
class RegistroAuditoria:
    id: int | None
    data_hora: datetime
    ator: str
    acao: str
    entidade: str
    entidade_id: str | None
    resultado: str
    detalhes: str | None
    correlation_id: str
    hash_anterior: str
    hash: str


@dataclass(frozen=True)
class NotificacaoPendente:
    id: int
    usuario_id: int
    ordem_id: int | None
    tipo: str
    mensagem: str
    tentativas: int


class RepositorioUsuarios(ABC):
    @abstractmethod
    def buscar_por_email(self, email: str) -> Usuario | None: ...
    @abstractmethod
    def buscar_por_id(self, usuario_id: int) -> Usuario | None: ...
    @abstractmethod
    def inserir(self, usuario: Usuario, agora: datetime) -> int: ...
    @abstractmethod
    def atualizar_seguranca(self, usuario: Usuario) -> None: ...


class RepositorioContas(ABC):
    @abstractmethod
    def buscar(self, conta_id: int) -> Conta | None: ...
    @abstractmethod
    def buscar_por_usuario(self, usuario_id: int) -> Conta | None: ...
    @abstractmethod
    def inserir(self, usuario_id: int, agora: datetime) -> Conta: ...
    @abstractmethod
    def atualizar_saldos(self, conta: Conta) -> None: ...
    @abstractmethod
    def buscar_limite(self, conta_id: int) -> LimiteRisco | None: ...
    @abstractmethod
    def salvar_limite(self, limite: LimiteRisco, por_usuario_id: int | None, agora: datetime) -> None: ...
    @abstractmethod
    def buscar_posicao(self, conta_id: int, ativo_id: int) -> Posicao | None: ...
    @abstractmethod
    def listar_posicoes(self, conta_id: int) -> list[Posicao]: ...
    @abstractmethod
    def salvar_posicao(self, posicao: Posicao) -> None: ...
    @abstractmethod
    def exposicao_compras_abertas(self, conta_id: int) -> Dinheiro: ...


class RepositorioAtivos(ABC):
    @abstractmethod
    def buscar_por_ticker(self, ticker: str) -> Ativo | None: ...
    @abstractmethod
    def buscar_por_id(self, ativo_id: int) -> Ativo | None: ...
    @abstractmethod
    def listar(self) -> list[Ativo]: ...
    @abstractmethod
    def inserir(self, ativo: Ativo) -> int: ...
    @abstractmethod
    def atualizar(self, ativo: Ativo) -> None: ...
    @abstractmethod
    def ultima_cotacao(self, ativo_id: int) -> Cotacao | None: ...
    @abstractmethod
    def inserir_cotacao(self, cotacao: Cotacao) -> None: ...


class RepositorioOrdens(ABC):
    @abstractmethod
    def inserir(self, ordem: Ordem) -> int: ...
    @abstractmethod
    def atualizar(self, ordem: Ordem) -> None: ...
    @abstractmethod
    def buscar(self, ordem_id: int) -> Ordem | None: ...
    @abstractmethod
    def buscar_por_chave(self, conta_id: int, chave: str) -> Ordem | None: ...
    @abstractmethod
    def listar(self, *, conta_id: int | None, estado: EstadoOrdem | None, ticker: str | None,
               limite: int, deslocamento: int) -> list[Ordem]: ...
    @abstractmethod
    def derivadas_aguardando(self, ordem_origem_id: int) -> list[Ordem]: ...
    @abstractmethod
    def registrar_transicao(self, ordem_id: int, transicao: TransicaoOrdem) -> None: ...
    @abstractmethod
    def listar_transicoes(self, ordem_id: int) -> list[dict]: ...
    @abstractmethod
    def execucao_registrada(self, id_execucao_corretora: str) -> bool: ...
    @abstractmethod
    def registrar_execucao(self, ordem_id: int, id_execucao_corretora: str, quantidade: int,
                           preco: Dinheiro, agora: datetime) -> None: ...


class RepositorioFila(ABC):
    @abstractmethod
    def enfileirar(self, ordem_id: int, operacao: str, agora: datetime) -> None: ...
    @abstractmethod
    def existe(self, ordem_id: int, operacao: str) -> bool: ...
    @abstractmethod
    def proximos(self, agora: datetime, limite: int) -> list[ItemFila]: ...
    @abstractmethod
    def atualizar(self, item_id: int, situacao: str, tentativas: int, proxima: datetime | None) -> None: ...
    @abstractmethod
    def concluir_pendentes_da_ordem(self, ordem_id: int, operacao: str) -> None: ...
    @abstractmethod
    def reabrir_falhas(self, agora: datetime) -> int: ...


class RepositorioNotificacoes(ABC):
    @abstractmethod
    def criar(self, usuario_id: int, ordem_id: int | None, chave_evento: str, tipo: str,
              mensagem: str, agora: datetime) -> None: ...
    @abstractmethod
    def pendentes(self, limite: int) -> list[NotificacaoPendente]: ...
    @abstractmethod
    def marcar(self, notificacao_id: int, situacao: str, tentativas: int) -> None: ...


class RepositorioAuditoria(ABC):
    @abstractmethod
    def ultimo_hash(self) -> str | None: ...
    @abstractmethod
    def inserir(self, registro: RegistroAuditoria) -> None: ...
    @abstractmethod
    def listar(self, *, entidade: str | None, entidade_id: str | None, limite: int,
               deslocamento: int) -> list[RegistroAuditoria]: ...
    @abstractmethod
    def todos_em_ordem(self) -> list[RegistroAuditoria]: ...


class RepositorioParametros(ABC):
    @abstractmethod
    def obter_todos(self) -> dict[str, str]: ...
    @abstractmethod
    def atualizar(self, chave: str, valor: str, por_usuario_id: int, agora: datetime) -> None: ...


class RepositorioEstadoSistema(ABC):
    @abstractmethod
    def modo_restrito(self) -> tuple[bool, str | None]: ...
    @abstractmethod
    def definir(self, restrito: bool, motivo: str | None, agora: datetime) -> None: ...
