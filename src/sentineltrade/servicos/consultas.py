"""Consultas de saldo, carteira e cotações, e recepção de cotações (UC-06 a UC-09, RF-14)."""
from __future__ import annotations

import logging

from ..dominio.dinheiro import Dinheiro
from ..dominio.enums import Perfil
from ..dominio.erros import AcessoNegado, NaoEncontrado
from ..dominio.mercado import Cotacao
from ..integracoes.cotacoes import ProvedorCotacoes, interpretar_cotacao
from ..relogio import Relogio
from .comum import carregar_parametros, exigir_perfil

log = logging.getLogger(__name__)
SALTO_MAXIMO_BPS = 2000           # cotação que varia mais de 20% de uma vez é descartada


class ServicoConsultas:
    def __init__(self, fabrica_uow, relogio: Relogio) -> None:
        self._uow = fabrica_uow
        self._relogio = relogio

    def _conta(self, uow, usuario):
        exigir_perfil(usuario, Perfil.INVESTIDOR)
        conta = uow.contas.buscar_por_usuario(usuario.id)
        if conta is None:
            raise AcessoNegado()
        return conta

    def saldo(self, usuario) -> dict:
        with self._uow(somente_leitura=True) as uow:
            conta = self._conta(uow, usuario)
        return {"disponivel": conta.saldo_disponivel, "bloqueado": conta.saldo_bloqueado,
                "total": conta.saldo_disponivel + conta.saldo_bloqueado}

    def carteira(self, usuario) -> list[dict]:
        agora = self._relogio.agora()
        with self._uow(somente_leitura=True) as uow:
            conta = self._conta(uow, usuario)
            idade = carregar_parametros(uow).cotacao_idade_max_s
            itens = []
            for p in uow.contas.listar_posicoes(conta.id):
                if p.quantidade_total == 0:
                    continue
                ativo = uow.ativos.buscar_por_id(p.ativo_id)
                cot = uow.ativos.ultima_cotacao(p.ativo_id)
                preco = cot.preco if cot else None
                itens.append({"ticker": ativo.ticker, "nome": ativo.nome, "quantidade_disponivel": p.quantidade_disponivel,
                              "quantidade_bloqueada": p.quantidade_bloqueada, "preco_medio": p.preco_medio,
                              "preco_atual": preco,
                              "valor_estimado": preco.vezes(p.quantidade_total) if preco else None,
                              "cotacao_desatualizada": cot is None or not cot.esta_valida(agora, idade)})
            return itens

    def cotacoes(self, ticker: str | None = None) -> list[dict]:
        agora = self._relogio.agora()
        with self._uow(somente_leitura=True) as uow:
            idade = carregar_parametros(uow).cotacao_idade_max_s
            ativos = uow.ativos.listar()
            if ticker is not None:
                ativos = [a for a in ativos if a.ticker == ticker]
                if not ativos:
                    raise NaoEncontrado("Ativo não encontrado.")
            saida = []
            for a in ativos:
                cot = uow.ativos.ultima_cotacao(a.id)
                saida.append({"ticker": a.ticker, "nome": a.nome, "tipo": a.tipo.value, "negociavel": a.negociavel,
                              "preco": cot.preco if cot else None, "variacao_bps": cot.variacao_bps if cot else None,
                              "data_hora": cot.data_hora if cot else None,
                              "desatualizada": cot is None or not cot.esta_valida(agora, idade)})
            return saida

    def ingerir_cotacoes(self, provedor: ProvedorCotacoes) -> int:
        """Grava as cotações recebidas; dados malformados, do futuro ou com salto absurdo são descartados."""
        agora = self._relogio.agora()
        with self._uow(somente_leitura=True) as uow:
            tickers = [a.ticker for a in uow.ativos.listar()]
        try:
            brutos = provedor.obter(tickers)
        except Exception:  # noqa: BLE001 - provedor fora: mantém a última cotação (fica desatualizada)
            log.warning("provedor de cotações indisponível")
            return 0
        gravadas = 0
        with self._uow() as uow:
            for bruto in brutos if isinstance(brutos, list) else []:
                c = interpretar_cotacao(bruto)
                if c is None or c.data_hora.tzinfo is None or (c.data_hora - agora).total_seconds() > 5:
                    log.warning("cotação descartada: formato ou horário inválido")
                    continue
                ativo = uow.ativos.buscar_por_ticker(c.ticker)
                if ativo is None:
                    continue
                ultima = uow.ativos.ultima_cotacao(ativo.id)
                variacao = 0
                if ultima is not None:
                    variacao = (c.preco_centavos - ultima.preco.centavos) * 10_000 // ultima.preco.centavos
                    if abs(variacao) > SALTO_MAXIMO_BPS:
                        log.warning("cotação descartada: variação acima do limite",
                                    extra={"dados": {"ticker": c.ticker}})
                        continue
                uow.ativos.inserir_cotacao(Cotacao(ativo.id, Dinheiro(c.preco_centavos), variacao, c.data_hora))
                gravadas += 1
            uow.confirmar()
        return gravadas
