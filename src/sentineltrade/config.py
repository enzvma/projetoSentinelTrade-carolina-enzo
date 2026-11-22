"""Configuração lida de variáveis de ambiente ou do arquivo .env (RNF-09).

Os segredos não têm valor padrão: sem eles a aplicação se recusa a iniciar.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from cryptography.fernet import Fernet
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracao(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    database_url: str = "sqlite:///./sentineltrade.db"

    jwt_secret: SecretStr
    data_encryption_key: SecretStr

    mfa_issuer: str = Field(default="SentinelTrade", min_length=1, max_length=40)
    mfa_code_ttl_seconds: int = Field(default=300, ge=60, le=900)
    access_token_minutes: int = Field(default=15, ge=1, le=60)
    login_max_failures: int = Field(default=5, ge=1, le=20)
    login_lock_minutes: int = Field(default=15, ge=1, le=1440)

    rate_limit_login_per_min: int = Field(default=5, ge=1, le=1000)
    rate_limit_orders_per_min: int = Field(default=30, ge=1, le=10000)
    max_body_bytes: int = Field(default=16_384, ge=1024, le=1_048_576)

    # Proxies cujo X-Forwarded-For a API aceita (o BFF roda na mesma máquina). Sem isso, todo
    # login feito pelo BFF contaria como um único IP no limite de tentativas.
    trusted_proxies: list[str] = Field(default=["127.0.0.1"], max_length=10)
    api_url: str = Field(default="http://127.0.0.1:8000", pattern=r"^https?://[A-Za-z0-9.-]+(:[0-9]{1,5})?$")

    integration_timeout_ms: int = Field(default=3000, ge=100, le=60_000)
    integration_max_retries: int = Field(default=3, ge=1, le=10)

    @field_validator("jwt_secret")
    @classmethod
    def _segredo_forte(cls, v: SecretStr) -> SecretStr:
        if len(v.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET deve ter pelo menos 32 caracteres (use: sentineltrade gerar-segredos)")
        return v

    @field_validator("data_encryption_key")
    @classmethod
    def _chave_fernet(cls, v: SecretStr) -> SecretStr:
        try:
            Fernet(v.get_secret_value().encode())
        except (ValueError, TypeError) as exc:
            raise ValueError("DATA_ENCRYPTION_KEY inválida (use: sentineltrade gerar-segredos)") from exc
        return v

    @property
    def producao(self) -> bool:
        return self.app_env == "production"


@lru_cache
def obter_configuracao() -> Configuracao:
    return Configuracao()  # type: ignore[call-arg]
