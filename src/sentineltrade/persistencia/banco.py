"""Conexão, criação do banco e unidade de trabalho (transação)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from ..dominio.erros import DadosInvalidos

RAIZ_PROJETO = Path(__file__).resolve().parents[3]
PASTA_SQL = RAIZ_PROJETO / "database"


def caminho_do_banco(database_url: str) -> str:
    """Aceita apenas URLs SQLite (sqlite:///arquivo.db); qualquer outro esquema é recusado."""
    prefixo = "sqlite:///"
    if not database_url.startswith(prefixo) or len(database_url) == len(prefixo):
        raise DadosInvalidos("DATABASE_URL deve ter o formato sqlite:///caminho/arquivo.db")
    return database_url[len(prefixo):]


def conectar(caminho: str) -> sqlite3.Connection:
    conexao = sqlite3.connect(caminho, timeout=10, isolation_level=None, check_same_thread=False)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    conexao.execute("PRAGMA busy_timeout = 10000")
    return conexao


def criar_banco(caminho: str, com_seed: bool = True, pasta_sql: Path = PASTA_SQL) -> None:
    """Cria as tabelas a partir de database/schema.sql e, opcionalmente, carrega database/seed.sql."""
    if Path(caminho).exists() and Path(caminho).stat().st_size > 0:
        raise DadosInvalidos("O banco já existe; apague o arquivo para recriá-lo.")
    conexao = conectar(caminho)
    try:
        conexao.executescript((pasta_sql / "schema.sql").read_text(encoding="utf-8"))
        if com_seed:
            conexao.executescript((pasta_sql / "seed.sql").read_text(encoding="utf-8"))
    finally:
        conexao.close()
