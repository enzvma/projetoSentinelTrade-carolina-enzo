"""Contratos da API (Pydantic). Toda entrada é validada por allowlist: formato, tamanho, tipo e intervalo.

`extra="forbid"` rejeita campos não previstos; padrões aceitam só os caracteres esperados.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

TICKER = r"^[A-Z]{4}[0-9]{1,2}$"
CHAVE = r"^[A-Za-z0-9_-]{16,64}$"
Preco = Annotated[Decimal, Field(gt=0, le=Decimal("1000000"), max_digits=12, decimal_places=2, allow_inf_nan=False)]
Quantidade = Annotated[int, Field(ge=1, le=1_000_000, strict=True)]
Valor = Annotated[Decimal, Field(gt=0, le=Decimal("100000000"), max_digits=14, decimal_places=2, allow_inf_nan=False)]

_ENTRADA = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ---- autenticação ---------------------------------------------------------------------------
class LoginEntrada(BaseModel):
    model_config = _ENTRADA
    email: EmailStr = Field(max_length=254)
    senha: str = Field(min_length=1, max_length=128, repr=False)


class MfaEntrada(BaseModel):
    model_config = _ENTRADA
    token_mfa: str = Field(pattern=r"^[A-Za-z0-9_\-.]+$", max_length=2048, repr=False)
    codigo: str = Field(pattern=r"^[0-9]{6}$", repr=False)


class MfaPendenteSaida(BaseModel):
    token_mfa: str
    expira_em_segundos: int


class AcessoSaida(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expira_em_segundos: int


# ---- ordens ---------------------------------------------------------------------------------
class OrdemEntrada(BaseModel):
    model_config = _ENTRADA
    ticker: str = Field(pattern=TICKER)
    lado: Literal["COMPRA", "VENDA"]
    tipo: Literal["MERCADO", "LIMITADA"]
    quantidade: Quantidade
    preco: Preco | None = None
    chave_idempotencia: str = Field(pattern=CHAVE)

    @model_validator(mode="after")
    def _preco_conforme_tipo(self) -> "OrdemEntrada":
        if self.tipo == "LIMITADA" and self.preco is None:
            raise ValueError("ordem limitada exige preço")
        if self.tipo == "MERCADO" and self.preco is not None:
            raise ValueError("ordem a mercado não aceita preço")
        return self


class AlteracaoEntrada(BaseModel):
    model_config = _ENTRADA
    quantidade: Quantidade | None = None
    preco: Preco | None = None
    chave_idempotencia: str = Field(pattern=CHAVE)

    @model_validator(mode="after")
    def _algo_a_alterar(self) -> "AlteracaoEntrada":
        if self.quantidade is None and self.preco is None:
            raise ValueError("informe a nova quantidade ou o novo preço")
        return self


class TransicaoSaida(BaseModel):
    estado_anterior: str | None
    estado_novo: str
    origem: str
    data_hora: datetime


class OrdemSaida(BaseModel):
    id: int
    ticker: str
    lado: str
    tipo: str
    quantidade: int
    quantidade_executada: int
    preco: Decimal | None
    estado: str
    motivo: str | None
    ordem_origem_id: int | None
    criada_em: datetime
    atualizada_em: datetime

    @classmethod
    def de(cls, ordem) -> "OrdemSaida":
        return cls(id=ordem.id, ticker=ordem.ticker, lado=ordem.lado.value, tipo=ordem.tipo.value,
                   quantidade=ordem.quantidade, quantidade_executada=ordem.quantidade_executada,
                   preco=ordem.preco.como_decimal() if ordem.preco else None, estado=ordem.estado.value,
                   motivo=ordem.motivo, ordem_origem_id=ordem.ordem_origem_id, criada_em=ordem.criada_em,
                   atualizada_em=ordem.atualizada_em)


class OrdemDetalheSaida(OrdemSaida):
    historico: list[TransicaoSaida]


class CancelamentoSaida(BaseModel):
    ordem: OrdemSaida
    mensagem: str


# ---- conta e mercado ------------------------------------------------------------------------
class SaldoSaida(BaseModel):
    disponivel: Decimal
    bloqueado: Decimal
    total: Decimal


class PosicaoSaida(BaseModel):
    ticker: str
    nome: str
    quantidade_disponivel: int
    quantidade_bloqueada: int
    preco_medio: Decimal
    preco_atual: Decimal | None
    valor_estimado: Decimal | None
    cotacao_desatualizada: bool


class CotacaoSaida(BaseModel):
    ticker: str
    nome: str
    tipo: str
    negociavel: bool
    preco: Decimal | None
    variacao_percentual: Decimal | None
    data_hora: datetime | None
    desatualizada: bool


# ---- administração, risco e auditoria -------------------------------------------------------
def _nome_valido(valor: str) -> str:
    valor = unicodedata.normalize("NFC", valor.strip())
    if not 2 <= len(valor) <= 100 or not re.fullmatch(r"[^\W\d_]+(?:[ '\-][^\W\d_]+)*", valor):
        raise ValueError("nome deve conter apenas letras, espaços, hífen ou apóstrofo")
    return valor


class UsuarioEntrada(BaseModel):
    model_config = _ENTRADA
    nome: str = Field(max_length=100)
    email: EmailStr = Field(max_length=254)
    senha: str = Field(min_length=12, max_length=128, repr=False)
    perfil: Literal["INVESTIDOR", "ADMINISTRADOR", "ANALISTA_RISCO", "AUDITOR"]
    saldo_inicial: Annotated[Decimal, Field(ge=0, le=Decimal("100000000"), max_digits=14, decimal_places=2)] = Decimal("0")

    @field_validator("nome")
    @classmethod
    def _nome(cls, v: str) -> str:
        return _nome_valido(v)


class UsuarioCriadoSaida(BaseModel):
    id: int
    otpauth_uri: str
    aviso: str = "Guarde a URI do segundo fator agora: ela não será exibida novamente."


class SituacaoEntrada(BaseModel):
    model_config = _ENTRADA
    ativo: bool = Field(strict=True)


class CreditoEntrada(BaseModel):
    model_config = _ENTRADA
    valor: Valor


class AtivoEntrada(BaseModel):
    model_config = _ENTRADA
    ticker: str = Field(pattern=TICKER)
    nome: str = Field(max_length=100)
    tipo: Literal["ACAO", "ETF", "FII"]
    preco_referencia: Preco

    @field_validator("nome")
    @classmethod
    def _nome(cls, v: str) -> str:
        v = unicodedata.normalize("NFC", v.strip())
        if not 2 <= len(v) <= 100 or not re.fullmatch(r"[\w &.'()/-]+", v):
            raise ValueError("nome do ativo contém caracteres não permitidos")
        return v


class NegociavelEntrada(BaseModel):
    model_config = _ENTRADA
    negociavel: bool = Field(strict=True)


class ParametroEntrada(BaseModel):
    model_config = _ENTRADA
    valor: str = Field(pattern=r"^[A-Za-z0-9:_/]{1,50}$")


class LimiteEntrada(BaseModel):
    model_config = _ENTRADA
    valor_maximo_ordem: Valor
    exposicao_maxima: Valor


class AuditoriaSaida(BaseModel):
    id: int
    data_hora: datetime
    ator: str
    acao: str
    entidade: str
    entidade_id: str | None
    resultado: str
    detalhes: str | None
    correlation_id: str
    hash: str


class VerificacaoSaida(BaseModel):
    integra: bool
    registros_verificados: int
    primeiro_registro_invalido: int | None
