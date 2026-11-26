"""Primitivas de segurança: hash de senha (Argon2id), MFA por TOTP, tokens JWT e cifra em repouso."""
from __future__ import annotations

import hmac
import re
from datetime import datetime, timedelta

import jwt
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

from .dominio.erros import CredenciaisInvalidas, DadosInvalidos

_hasher = PasswordHasher()           # Argon2id com os parâmetros recomendados pela biblioteca (RNF-01)
HASH_FICTICIO = _hasher.hash("senha-ficticia-usada-para-igualar-o-tempo-de-resposta-0")
EMISSOR = "sentineltrade"
AUDIENCIA = "sentineltrade-api"
FINALIDADE_MFA = "mfa"
FINALIDADE_ACESSO = "acesso"


# ---- senha ------------------------------------------------------------------------------------
def validar_politica_senha(senha: str) -> None:
    """RN-13: 12 a 128 caracteres, com letras e números."""
    if (not isinstance(senha, str) or not 12 <= len(senha) <= 128
            or not re.search(r"[A-Za-z]", senha) or not re.search(r"[0-9]", senha)):
        raise DadosInvalidos("A senha deve ter de 12 a 128 caracteres, com letras e números.")


def gerar_hash_senha(senha: str) -> str:
    validar_politica_senha(senha)
    return _hasher.hash(senha)


def verificar_senha(senha: str, hash_armazenado: str) -> bool:
    try:
        return _hasher.verify(hash_armazenado, senha)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


# ---- cifra em repouso (segredo do MFA) - RNF-10 ---------------------------------------------
class Cifrador:
    def __init__(self, chave: str) -> None:
        self._fernet = Fernet(chave.encode())

    def cifrar(self, texto: str) -> str:
        return self._fernet.encrypt(texto.encode()).decode()

    def decifrar(self, cifrado: str) -> str:
        try:
            return self._fernet.decrypt(cifrado.encode()).decode()
        except InvalidToken as exc:
            raise CredenciaisInvalidas() from exc

    @staticmethod
    def gerar_chave() -> str:
        return Fernet.generate_key().decode()


# ---- segundo fator: TOTP de uso único - RNF-02 ----------------------------------------------
def gerar_segredo_mfa() -> str:
    return pyotp.random_base32()


def uri_mfa(segredo: str, email: str, emissor: str) -> str:
    return pyotp.TOTP(segredo).provisioning_uri(name=email, issuer_name=emissor)


def codigo_atual(segredo: str, agora: datetime) -> str:
    return pyotp.TOTP(segredo).at(agora)


def verificar_totp(segredo: str, codigo: str, ultimo_passo: int, agora: datetime) -> int | None:
    """Devolve o passo de tempo aceito, ou None. Códigos de passos já usados são recusados."""
    if not isinstance(codigo, str) or not re.fullmatch(r"[0-9]{6}", codigo):
        return None
    totp = pyotp.TOTP(segredo)
    atual = totp.timecode(agora)
    for passo in (atual - 1, atual, atual + 1):
        if passo > ultimo_passo and hmac.compare_digest(totp.generate_otp(passo), codigo):
            return passo
    return None


# ---- tokens ---------------------------------------------------------------------------------
def emitir_token(segredo: str, usuario_id: int, finalidade: str, validade: timedelta, agora: datetime) -> str:
    claims = {"sub": str(usuario_id), "fin": finalidade, "iss": EMISSOR, "aud": AUDIENCIA,
              "iat": int(agora.timestamp()), "exp": int((agora + validade).timestamp())}
    return jwt.encode(claims, segredo, algorithm="HS256")


def ler_token(segredo: str, token: str, finalidade: str, agora: datetime) -> int:
    try:
        claims = jwt.decode(token, segredo, algorithms=["HS256"], audience=AUDIENCIA, issuer=EMISSOR,
                            options={"require": ["exp", "iat", "sub", "iss", "aud"],
                                     "verify_exp": False, "verify_iat": False})
    except jwt.PyJWTError as exc:
        raise CredenciaisInvalidas() from exc
    # expiração conferida com o relógio da aplicação (permite testar sem esperar)
    if claims.get("fin") != finalidade or int(claims["exp"]) <= int(agora.timestamp()):
        raise CredenciaisInvalidas()
    try:
        return int(claims["sub"])
    except (TypeError, ValueError) as exc:
        raise CredenciaisInvalidas() from exc
