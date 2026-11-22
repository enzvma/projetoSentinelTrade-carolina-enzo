"""Auditoria imutável com hash encadeado (RF-11, RNF-22, RN-14, RN-16)."""
import sqlite3
from decimal import Decimal

import pytest

from conftest import criar_usuario
from sentineltrade.dominio.enums import Lado, Perfil, TipoOrdem
from sentineltrade.dominio.erros import AcessoNegado
from sentineltrade.persistencia.banco import caminho_do_banco, conectar
from sentineltrade.servicos.ordens import DadosOrdem


def criar_ordem(app, usuario):
    return app.ordens.criar(usuario, DadosOrdem("PETR4", Lado.COMPRA, TipoOrdem.LIMITADA, 10, Decimal("38.50"),
                                                "chave-auditoria-001"))[0]


def test_toda_transicao_gera_registro(app, investidor):
    usuario, _ = investidor
    o = criar_ordem(app, usuario)
    app.transmissao.processar_fila()
    with app.uow(somente_leitura=True) as uow:
        acoes = [r.acao for r in uow.auditoria.listar(entidade="ordem", entidade_id=str(o.id), limite=50,
                                                       deslocamento=0)]
    assert set(acoes) >= {"ORDEM_CRIADA", "ORDEM_VALIDADA", "ORDEM_ENVIADA", "ORDEM_EXECUTADA"}


def test_cadeia_integra_e_adulteracao_detectada(app, investidor, config):
    usuario, _ = investidor
    criar_ordem(app, usuario)
    auditor, _ = criar_usuario(app, "auditor@exemplo.com", Perfil.AUDITOR)
    assert app.auditoria.verificar_cadeia(auditor)[0] is True
    conexao = conectar(caminho_do_banco(config.database_url))       # simula um ataque direto ao banco
    conexao.execute("DROP TRIGGER tg_auditoria_sem_update")
    conexao.execute("UPDATE log_auditoria SET resultado = 'ADULTERADO' WHERE id = 2")
    conexao.close()
    integra, invalido, _ = app.auditoria.verificar_cadeia(auditor)
    assert integra is False and invalido == 2


def test_banco_impede_alterar_ou_apagar_auditoria(app, investidor, config):
    criar_ordem(app, investidor[0])
    conexao = conectar(caminho_do_banco(config.database_url))
    for sql in ("UPDATE log_auditoria SET ator = 'x'", "DELETE FROM log_auditoria"):
        with pytest.raises(sqlite3.DatabaseError):
            conexao.execute(sql)
    conexao.close()


def test_falha_ao_gravar_auditoria_desfaz_a_operacao(app, investidor, monkeypatch):
    usuario, conta_id = investidor

    def falhar(*args, **kwargs):
        raise sqlite3.OperationalError("disco cheio")
    monkeypatch.setattr(app.auditoria, "registrar", falhar)
    with pytest.raises(sqlite3.OperationalError):
        criar_ordem(app, usuario)
    with app.uow(somente_leitura=True) as uow:
        assert uow.ordens.listar(conta_id=conta_id, estado=None, ticker=None, limite=10, deslocamento=0) == []


def test_so_auditor_consulta_a_trilha(app, investidor):
    with pytest.raises(AcessoNegado):
        app.auditoria.listar(investidor[0], entidade=None, entidade_id=None, limite=10, deslocamento=0)
