"""Usuário do sistema e controle de bloqueio por tentativas de login (RN-13)."""
from __future__ import annotations

from datetime import datetime, timedelta

from .enums import Perfil


class Usuario:
    def __init__(self, *, id: int | None, nome: str, email: str, senha_hash: str, mfa_segredo_cifrado: str,
                 perfil: Perfil, ativo: bool = True, mfa_ultimo_passo: int = 0, tentativas_falhas: int = 0,
                 bloqueado_ate: datetime | None = None) -> None:
        self._id = id
        self._nome = nome
        self._email = email
        self.__senha_hash = senha_hash                 # nunca exposto fora do serviço de autenticação
        self.__mfa_segredo_cifrado = mfa_segredo_cifrado
        self._perfil = Perfil(perfil)
        self._ativo = ativo
        self._mfa_ultimo_passo = mfa_ultimo_passo
        self._tentativas_falhas = tentativas_falhas
        self._bloqueado_ate = bloqueado_ate

    id = property(lambda self: self._id)
    nome = property(lambda self: self._nome)
    email = property(lambda self: self._email)
    perfil = property(lambda self: self._perfil)
    ativo = property(lambda self: self._ativo)
    mfa_ultimo_passo = property(lambda self: self._mfa_ultimo_passo)
    tentativas_falhas = property(lambda self: self._tentativas_falhas)
    bloqueado_ate = property(lambda self: self._bloqueado_ate)

    def credenciais(self) -> tuple[str, str]:
        """Hash da senha e segredo cifrado do MFA (uso exclusivo da autenticação e da persistência)."""
        return self.__senha_hash, self.__mfa_segredo_cifrado

    def __repr__(self) -> str:  # nunca inclui credenciais
        return f"Usuario(id={self._id}, perfil={self._perfil.value})"

    def definir_id(self, novo_id: int) -> None:
        self._id = novo_id

    def esta_bloqueado(self, agora: datetime) -> bool:
        return self._bloqueado_ate is not None and agora < self._bloqueado_ate

    def registrar_falha(self, agora: datetime, maximo: int, minutos_bloqueio: int) -> None:
        self._tentativas_falhas += 1
        if self._tentativas_falhas >= maximo:
            self._bloqueado_ate = agora + timedelta(minutes=minutos_bloqueio)
            self._tentativas_falhas = 0

    def registrar_sucesso(self, passo_mfa: int) -> None:
        self._tentativas_falhas = 0
        self._bloqueado_ate = None
        self._mfa_ultimo_passo = passo_mfa

    def definir_ativo(self, valor: bool) -> None:
        self._ativo = bool(valor)
