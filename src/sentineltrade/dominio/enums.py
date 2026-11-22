"""Enumerações do domínio (valores iguais aos aceitos pelo banco em database/schema.sql)."""
from enum import Enum


class Perfil(str, Enum):
    INVESTIDOR = "INVESTIDOR"
    ADMINISTRADOR = "ADMINISTRADOR"
    ANALISTA_RISCO = "ANALISTA_RISCO"
    AUDITOR = "AUDITOR"


class Lado(str, Enum):
    COMPRA = "COMPRA"
    VENDA = "VENDA"


class TipoOrdem(str, Enum):
    MERCADO = "MERCADO"
    LIMITADA = "LIMITADA"


class EstadoOrdem(str, Enum):
    CRIADA = "CRIADA"
    VALIDADA = "VALIDADA"
    ENVIADA = "ENVIADA"
    PARCIALMENTE_EXECUTADA = "PARCIALMENTE_EXECUTADA"
    EXECUTADA = "EXECUTADA"
    REJEITADA = "REJEITADA"
    CANCELADA = "CANCELADA"

    @property
    def final(self) -> bool:
        return self in (EstadoOrdem.EXECUTADA, EstadoOrdem.REJEITADA, EstadoOrdem.CANCELADA)


class OrigemTransicao(str, Enum):
    USUARIO = "USUARIO"
    SISTEMA = "SISTEMA"
    CORRETORA = "CORRETORA"


class TipoAtivo(str, Enum):
    ACAO = "ACAO"
    ETF = "ETF"
    FII = "FII"


class MotivoRejeicao(str, Enum):
    """Motivos padronizados (texto curto e sem dados internos)."""
    MERCADO_FECHADO = "MERCADO_FECHADO"
    ATIVO_INDISPONIVEL = "ATIVO_INDISPONIVEL"
    COTACAO_INDISPONIVEL = "COTACAO_INDISPONIVEL"
    PRECO_FORA_DA_FAIXA = "PRECO_FORA_DA_FAIXA"
    LIMITE_RISCO_EXCEDIDO = "LIMITE_RISCO_EXCEDIDO"
    SALDO_INSUFICIENTE = "SALDO_INSUFICIENTE"
    POSICAO_INSUFICIENTE = "POSICAO_INSUFICIENTE"
    CONTA_INATIVA = "CONTA_INATIVA"
    REJEITADA_PELA_CORRETORA = "REJEITADA_PELA_CORRETORA"
    ORDEM_ORIGINAL_EXECUTADA = "ORDEM_ORIGINAL_EXECUTADA"
    ALTERADA = "ALTERADA"
