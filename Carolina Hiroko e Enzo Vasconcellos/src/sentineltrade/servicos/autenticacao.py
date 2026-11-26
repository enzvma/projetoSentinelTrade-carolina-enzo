"""Autenticação com senha e segundo fator TOTP (RF-02, RNF-01, RNF-02, RN-13).

Fluxo: login (e-mail e senha) -> token temporário de MFA -> código TOTP -> token de acesso.
Mensagens de erro são sempre as mesmas, para não revelar se o e-mail existe.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from ..config import Configuracao
from ..dominio.enums import Perfil
from ..dominio.erros import CredenciaisInvalidas, DadosInvalidos
from ..dominio.usuario import Usuario
from ..relogio import Relogio
from .. import seguranca
from .auditoria import ServicoAuditoria

log = logging.getLogger(__name__)


class ServicoAutenticacao:
    def __init__(self, fabrica_uow, config: Configuracao, relogio: Relogio, auditoria: ServicoAuditoria,
                 cifrador: seguranca.Cifrador) -> None:
        self._uow = fabrica_uow
        self._config = config
        self._relogio = relogio
        self._auditoria = auditoria
        self._cifrador = cifrador
        self._segredo_jwt = config.jwt_secret.get_secret_value()

    # ---- cadastro (usado pela administração e pela linha de comando) -------------------------
    def novo_usuario(self, uow, *, nome: str, email: str, senha: str, perfil: Perfil) -> tuple[Usuario, str]:
        """Cria o usuário com senha em hash e segredo de MFA cifrado. Devolve o usuário e a URI do MFA."""
        email = email.strip().lower()
        if uow.usuarios.buscar_por_email(email) is not None:
            raise DadosInvalidos("E-mail já cadastrado.")
        segredo = seguranca.gerar_segredo_mfa()
        usuario = Usuario(id=None, nome=nome.strip(), email=email, senha_hash=seguranca.gerar_hash_senha(senha),
                          mfa_segredo_cifrado=self._cifrador.cifrar(segredo), perfil=perfil)
        uow.usuarios.inserir(usuario, self._relogio.agora())
        return usuario, seguranca.uri_mfa(segredo, email, self._config.mfa_issuer)

    def segredo_mfa(self, usuario: Usuario) -> str:
        return self._cifrador.decifrar(usuario.credenciais()[1])

    # ---- primeiro fator ---------------------------------------------------------------------
    def login(self, email: str, senha: str) -> str:
        agora = self._relogio.agora()
        email = email.strip().lower()
        erro = False
        with self._uow() as uow:
            usuario = uow.usuarios.buscar_por_email(email)
            if usuario is None:
                seguranca.verificar_senha(senha, seguranca.HASH_FICTICIO)   # mesmo custo de tempo
                self._auditoria.registrar(uow, ator="anonimo", acao="LOGIN", entidade="usuario", entidade_id=None,
                                          resultado="FALHA_CREDENCIAIS")
                erro = True
            elif not usuario.ativo or usuario.esta_bloqueado(agora):
                seguranca.verificar_senha(senha, seguranca.HASH_FICTICIO)
                self._auditoria.registrar(uow, ator=f"usuario:{usuario.id}", acao="LOGIN", entidade="usuario",
                                          entidade_id=usuario.id, resultado="FALHA_BLOQUEADO")
                erro = True
            elif not seguranca.verificar_senha(senha, usuario.credenciais()[0]):
                usuario.registrar_falha(agora, self._config.login_max_failures, self._config.login_lock_minutes)
                uow.usuarios.atualizar_seguranca(usuario)
                self._auditoria.registrar(uow, ator=f"usuario:{usuario.id}", acao="LOGIN", entidade="usuario",
                                          entidade_id=usuario.id, resultado="FALHA_CREDENCIAIS",
                                          detalhes={"bloqueado": usuario.esta_bloqueado(agora)})
                erro = True
            else:
                self._auditoria.registrar(uow, ator=f"usuario:{usuario.id}", acao="LOGIN_SENHA", entidade="usuario",
                                          entidade_id=usuario.id, resultado="SUCESSO")
            uow.confirmar()
        if erro:
            raise CredenciaisInvalidas()
        return seguranca.emitir_token(self._segredo_jwt, usuario.id, seguranca.FINALIDADE_MFA,
                                      timedelta(seconds=self._config.mfa_code_ttl_seconds), agora)

    # ---- segundo fator ----------------------------------------------------------------------
    def confirmar_mfa(self, token_mfa: str, codigo: str) -> tuple[str, int]:
        agora = self._relogio.agora()
        usuario_id = seguranca.ler_token(self._segredo_jwt, token_mfa, seguranca.FINALIDADE_MFA, agora)
        erro = False
        with self._uow() as uow:
            usuario = uow.usuarios.buscar_por_id(usuario_id)
            if usuario is None or not usuario.ativo or usuario.esta_bloqueado(agora):
                erro = True
            else:
                passo = seguranca.verificar_totp(self.segredo_mfa(usuario), codigo, usuario.mfa_ultimo_passo, agora)
                if passo is None:
                    usuario.registrar_falha(agora, self._config.login_max_failures, self._config.login_lock_minutes)
                    resultado = "FALHA_MFA"
                    erro = True
                else:
                    usuario.registrar_sucesso(passo)
                    resultado = "SUCESSO"
                uow.usuarios.atualizar_seguranca(usuario)
                self._auditoria.registrar(uow, ator=f"usuario:{usuario.id}", acao="LOGIN_MFA", entidade="usuario",
                                          entidade_id=usuario.id, resultado=resultado)
            uow.confirmar()
        if erro:
            raise CredenciaisInvalidas()
        validade = timedelta(minutes=self._config.access_token_minutes)
        token = seguranca.emitir_token(self._segredo_jwt, usuario_id, seguranca.FINALIDADE_ACESSO, validade, agora)
        return token, int(validade.total_seconds())

    # ---- sessão -----------------------------------------------------------------------------
    def usuario_do_token(self, token: str) -> Usuario:
        """Confere o token e recarrega o usuário (um usuário inativado perde o acesso na hora)."""
        agora = self._relogio.agora()
        usuario_id = seguranca.ler_token(self._segredo_jwt, token, seguranca.FINALIDADE_ACESSO, agora)
        with self._uow(somente_leitura=True) as uow:
            usuario = uow.usuarios.buscar_por_id(usuario_id)
        if usuario is None or not usuario.ativo or usuario.esta_bloqueado(agora):
            raise CredenciaisInvalidas()
        return usuario
