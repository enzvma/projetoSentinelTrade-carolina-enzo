"""Fixtures compartilhadas: banco temporário, relógio fixo no horário do pregão e usuários de teste."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from cryptography.fernet import Fernet

from sentineltrade.config import Configuracao
from sentineltrade.dominio.conta import Posicao
from sentineltrade.dominio.dinheiro import Dinheiro
from sentineltrade.dominio.enums import Perfil
from sentineltrade.dominio.mercado import Cotacao
from sentineltrade.persistencia.banco import caminho_do_banco, conectar, criar_banco
from sentineltrade.persistencia.sqlite import para_texto
from sentineltrade.relogio import RelogioFixo
from sentineltrade.seguranca import codigo_atual
from sentineltrade.servicos.aplicacao import Aplicacao

PREGAO = datetime(2026, 11, 16, 17, 0, tzinfo=timezone.utc)   # segunda-feira, 14h em Brasília
SENHA = "SenhaDeTeste123"


@pytest.fixture
def config(tmp_path) -> Configuracao:
    return Configuracao(_env_file=None, app_env="test", database_url=f"sqlite:///{tmp_path / 'teste.db'}",
                        jwt_secret="j" * 40, data_encryption_key=Fernet.generate_key().decode(),
                        integration_timeout_ms=300, rate_limit_orders_per_min=1000)


@pytest.fixture
def relogio() -> RelogioFixo:
    return RelogioFixo(PREGAO)


@pytest.fixture
def app(config, relogio) -> Aplicacao:
    caminho = caminho_do_banco(config.database_url)
    criar_banco(caminho)
    conexao = conectar(caminho)     # cotações do seed passam a ter o horário do relógio de teste
    conexao.execute("UPDATE cotacoes SET data_hora = ?", (para_texto(relogio.agora()),))
    conexao.close()
    return Aplicacao(config, relogio=relogio, dormir=lambda s: None)


def criar_usuario(app: Aplicacao, email: str, perfil: Perfil = Perfil.INVESTIDOR, saldo: str = "0"):
    usuario_id, _ = app.administracao.criar_usuario(None, nome="Pessoa Teste", email=email, senha=SENHA,
                                                    perfil=perfil, saldo_inicial=Decimal(saldo))
    with app.uow(somente_leitura=True) as uow:
        usuario = uow.usuarios.buscar_por_id(usuario_id)
        conta = uow.contas.buscar_por_usuario(usuario_id)
    return usuario, (conta.id if conta else None)


def dar_posicao(app: Aplicacao, conta_id: int, ticker: str, quantidade: int, preco: str) -> None:
    with app.uow() as uow:
        ativo = uow.ativos.buscar_por_ticker(ticker)
        uow.contas.salvar_posicao(Posicao(conta_id=conta_id, ativo_id=ativo.id, quantidade_disponivel=quantidade,
                                          preco_medio=Dinheiro.de_decimal(preco)))
        uow.confirmar()


def definir_cotacao(app: Aplicacao, ticker: str, preco: str) -> None:
    with app.uow() as uow:
        ativo = uow.ativos.buscar_por_ticker(ticker)
        uow.ativos.inserir_cotacao(Cotacao(ativo.id, Dinheiro.de_decimal(preco), 0, app.relogio.agora()))
        uow.confirmar()


def codigo_mfa(app: Aplicacao, usuario) -> str:
    return codigo_atual(app.autenticacao.segredo_mfa(usuario), app.relogio.agora())


def saldo(app: Aplicacao, conta_id: int):
    with app.uow(somente_leitura=True) as uow:
        conta = uow.contas.buscar(conta_id)
    return conta.saldo_disponivel, conta.saldo_bloqueado


def posicao(app: Aplicacao, conta_id: int, ticker: str):
    with app.uow(somente_leitura=True) as uow:
        ativo = uow.ativos.buscar_por_ticker(ticker)
        return uow.contas.buscar_posicao(conta_id, ativo.id)


@pytest.fixture
def investidor(app):
    return criar_usuario(app, "investidor@exemplo.com", saldo="10000.00")
