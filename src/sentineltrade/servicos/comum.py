"""Funções compartilhadas pelos serviços."""
from __future__ import annotations

from ..dominio.enums import Perfil
from ..dominio.erros import AcessoNegado
from ..dominio.mercado import ParametrosOperacionais
from ..dominio.usuario import Usuario


def exigir_perfil(usuario: Usuario, *perfis: Perfil) -> None:
    """Autorização verificada no servidor (RNF-03); negação por padrão."""
    if usuario is None or not usuario.ativo or usuario.perfil not in perfis:
        raise AcessoNegado()


def ator_de(usuario: Usuario | None) -> str:
    return f"usuario:{usuario.id}" if usuario is not None else "anonimo"


def carregar_parametros(uow) -> ParametrosOperacionais:
    return ParametrosOperacionais.de_dicionario(uow.parametros.obter_todos())
