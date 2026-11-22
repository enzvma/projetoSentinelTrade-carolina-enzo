"""Transmissão à corretora, execuções, falhas, cancelamento e alteração (RF-06, RF-12, RF-13, RF-17, RN-10, RN-11, RN-18)."""
from decimal import Decimal

from conftest import dar_posicao, definir_cotacao, posicao, saldo
from sentineltrade.dominio.dinheiro import Dinheiro
from sentineltrade.dominio.enums import EstadoOrdem as E, Lado, TipoOrdem
from sentineltrade.servicos.ordens import DadosAlteracao, DadosOrdem

R = Dinheiro.de_decimal


def ordem(app, usuario, lado=Lado.COMPRA, quantidade=10, preco="38.50", chave="chave-transmissao-01",
          tipo=TipoOrdem.LIMITADA):
    o, _ = app.ordens.criar(usuario, DadosOrdem("PETR4", lado, tipo, quantidade,
                                                Decimal(preco) if preco else None, chave))
    return o


def estado(app, usuario, ordem_id):
    return app.ordens.consultar(usuario, ordem_id)[0]


def test_compra_executada_atualiza_saldo_carteira_e_preco_medio(app, investidor):
    usuario, conta_id = investidor
    dar_posicao(app, conta_id, "PETR4", 10, "30.00")
    o = ordem(app, usuario)
    app.transmissao.processar_fila()
    o = estado(app, usuario, o.id)
    assert o.estado is E.EXECUTADA and o.quantidade_executada == 10
    assert saldo(app, conta_id) == (R("10000.00") - R("385.20"), Dinheiro.zero())   # 385,00 + taxa 0,20
    p = posicao(app, conta_id, "PETR4")
    assert p.quantidade_disponivel == 20 and p.preco_medio == R("34.25")


def test_compra_a_mercado_devolve_a_margem_nao_usada(app, investidor):
    usuario, conta_id = investidor
    o = ordem(app, usuario, tipo=TipoOrdem.MERCADO, preco=None)
    assert saldo(app, conta_id)[1] == R("423.72")                    # 385 + 10% + taxa, bloqueado
    app.transmissao.processar_fila()
    assert estado(app, usuario, o.id).estado is E.EXECUTADA
    assert saldo(app, conta_id) == (R("10000.00") - R("385.20"), Dinheiro.zero())


def test_venda_executada_credita_saldo(app, investidor):
    usuario, conta_id = investidor
    dar_posicao(app, conta_id, "PETR4", 10, "30.00")
    o = ordem(app, usuario, lado=Lado.VENDA)
    app.transmissao.processar_fila()
    assert estado(app, usuario, o.id).estado is E.EXECUTADA
    assert saldo(app, conta_id)[0] == R("10000.00") + R("384.80")     # 385,00 - taxa 0,20
    p = posicao(app, conta_id, "PETR4")
    assert (p.quantidade_disponivel, p.quantidade_bloqueada) == (0, 0)


def test_execucao_parcial_e_depois_total(app, investidor):
    usuario, conta_id = investidor
    app.corretora_externa._liquidez = 4
    o = ordem(app, usuario)
    app.transmissao.processar_fila()
    assert estado(app, usuario, o.id).estado is E.PARCIALMENTE_EXECUTADA
    assert posicao(app, conta_id, "PETR4").quantidade_disponivel == 4
    app.transmissao.acompanhar_abertas()
    app.transmissao.acompanhar_abertas()
    final = estado(app, usuario, o.id)
    assert final.estado is E.EXECUTADA and final.quantidade_executada == 10
    assert saldo(app, conta_id)[1] == Dinheiro.zero()


def test_mesma_execucao_nao_e_aplicada_duas_vezes(app, investidor):
    usuario, conta_id = investidor
    o = ordem(app, usuario)
    app.transmissao.processar_fila()
    resposta = app.transmissao._corretora.consultar(o.id_corretora)
    app.transmissao._aplicar(o.id, resposta)                       # mesma resposta de novo
    assert posicao(app, conta_id, "PETR4").quantidade_disponivel == 10
    with app.uow(somente_leitura=True) as uow:
        assert uow.ordens.buscar(o.id).quantidade_executada == 10


def test_reenvio_nao_duplica_ordem_na_corretora(app, investidor):
    usuario, _ = investidor
    definir_cotacao(app, "PETR4", "40.00")                         # limitada a 38,50 fica aberta
    o = ordem(app, usuario)
    app.transmissao.processar_fila()
    app.transmissao.acompanhar_abertas()
    app.transmissao.acompanhar_abertas()
    assert app.corretora_externa.chamadas_enviar == 1
    assert len(app.corretora_externa._ordens) == 1
    assert estado(app, usuario, o.id).estado is E.ENVIADA


def test_rejeicao_da_corretora_libera_saldo(app, investidor):
    usuario, conta_id = investidor
    app.corretora_externa.rejeitar_tickers.add("PETR4")
    o = ordem(app, usuario)
    app.transmissao.processar_fila()
    final = estado(app, usuario, o.id)
    assert final.estado is E.REJEITADA and final.motivo == "REJEITADA_PELA_CORRETORA"
    assert saldo(app, conta_id) == (R("10000.00"), Dinheiro.zero())


def test_corretora_fora_preserva_ordem_ativa_modo_restrito_e_recupera(app, investidor, relogio):
    usuario, conta_id = investidor
    o = ordem(app, usuario)
    app.corretora_externa.indisponivel = True
    for _ in range(3):                                             # 3 rodadas sem resposta
        app.transmissao.processar_fila()
        relogio.avancar(seconds=10)
    assert estado(app, usuario, o.id).estado is E.VALIDADA          # ordem preservada (RN-18)
    assert saldo(app, conta_id)[1] == R("385.20")                  # bloqueio mantido
    with app.uow(somente_leitura=True) as uow:
        assert uow.estado_sistema.modo_restrito()[0]
        assert any(n.tipo == "FALHA" for n in uow.notificacoes.pendentes(10))
    app.corretora_externa.indisponivel = False
    app.transmissao.ciclo()                                        # saúde ok -> reabre a fila e processa
    assert estado(app, usuario, o.id).estado is E.EXECUTADA
    with app.uow(somente_leitura=True) as uow:
        assert not uow.estado_sistema.modo_restrito()[0]


def test_resposta_malformada_nao_altera_nada(app, investidor):
    usuario, conta_id = investidor
    o = ordem(app, usuario)
    app.corretora_externa.resposta_malformada = True
    app.transmissao.processar_fila()
    assert estado(app, usuario, o.id).estado is E.VALIDADA
    assert posicao(app, conta_id, "PETR4") is None


def test_cancelar_antes_do_envio_cancela_sem_ir_a_corretora(app, investidor):
    usuario, conta_id = investidor
    o = ordem(app, usuario)
    app.ordens.cancelar(usuario, o.id)
    app.transmissao.processar_fila()
    assert estado(app, usuario, o.id).estado is E.CANCELADA
    assert app.corretora_externa.chamadas_enviar == 0
    assert saldo(app, conta_id) == (R("10000.00"), Dinheiro.zero())


def test_cancelar_ordem_aberta_na_corretora(app, investidor):
    usuario, conta_id = investidor
    definir_cotacao(app, "PETR4", "40.00")
    o = ordem(app, usuario)
    app.transmissao.processar_fila()
    app.ordens.cancelar(usuario, o.id)
    app.transmissao.processar_fila()
    assert estado(app, usuario, o.id).estado is E.CANCELADA
    assert saldo(app, conta_id) == (R("10000.00"), Dinheiro.zero())


def test_cancelamento_apos_execucao_vale_a_execucao(app, investidor):
    usuario, _ = investidor
    definir_cotacao(app, "PETR4", "40.00")
    o = ordem(app, usuario)
    app.transmissao.processar_fila()
    app.ordens.cancelar(usuario, o.id)
    definir_cotacao(app, "PETR4", "38.00")                         # executa antes do cancelamento
    app.transmissao.processar_fila()
    assert estado(app, usuario, o.id).estado is E.EXECUTADA         # RN-10


def test_cancelar_ordem_executada_e_negado(app, investidor):
    import pytest
    from sentineltrade.dominio.erros import OperacaoNaoPermitida
    usuario, _ = investidor
    o = ordem(app, usuario)
    app.transmissao.processar_fila()
    with pytest.raises(OperacaoNaoPermitida):
        app.ordens.cancelar(usuario, o.id)


def test_alterar_ordem_cancela_original_e_valida_a_nova(app, investidor):
    usuario, conta_id = investidor
    definir_cotacao(app, "PETR4", "40.00")
    o = ordem(app, usuario)
    app.transmissao.processar_fila()
    nova, criada = app.ordens.alterar(usuario, o.id, DadosAlteracao(None, Decimal("39.00"), "chave-alteracao-001"))
    assert criada and nova.estado is E.CRIADA and nova.ordem_origem_id == o.id
    app.transmissao.processar_fila()                               # cancela original, valida a nova
    assert estado(app, usuario, o.id).estado is E.CANCELADA
    assert estado(app, usuario, nova.id).estado is E.VALIDADA
    assert saldo(app, conta_id)[1] == R("390.20")                  # só o bloqueio da nova ordem
    app.transmissao.processar_fila()                               # próxima rodada envia a nova
    assert estado(app, usuario, nova.id).estado is E.ENVIADA
