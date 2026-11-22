"""Montagem da aplicação: cria e liga todos os serviços (injeção de dependências)."""
from __future__ import annotations

from ..config import Configuracao
from ..dominio.dinheiro import Dinheiro
from ..integracoes.corretora import CorretoraGateway, CorretoraResiliente, CorretoraSimulada
from ..integracoes.cotacoes import ProvedorCotacoes, ProvedorCotacoesSimulado
from ..integracoes.notificacao import Notificador, NotificadorSimulado
from ..persistencia.banco import caminho_do_banco
from ..persistencia.sqlite import FabricaUnidade
from ..regras import ValidadorOrdem
from ..relogio import Relogio, RelogioSistema
from ..seguranca import Cifrador
from .administracao import ServicoAdministracao
from .auditoria import ServicoAuditoria
from .autenticacao import ServicoAutenticacao
from .consultas import ServicoConsultas
from .eventos import AuditoriaDeOrdem, HistoricoEstados, NotificacaoDeOrdem, PublicadorEventosOrdem
from .notificacoes import ServicoNotificacoes
from .ordens import ServicoOrdens
from .transmissao import ServicoTransmissao


class Aplicacao:
    def __init__(self, config: Configuracao, *, relogio: Relogio | None = None,
                 corretora: CorretoraGateway | None = None, provedor: ProvedorCotacoes | None = None,
                 notificador: Notificador | None = None, dormir=None) -> None:
        self.config = config
        self.relogio = relogio or RelogioSistema()
        self.uow = FabricaUnidade(caminho_do_banco(config.database_url))
        cifrador = Cifrador(config.data_encryption_key.get_secret_value())

        self.auditoria = ServicoAuditoria(self.uow, self.relogio)
        publicador = PublicadorEventosOrdem([HistoricoEstados(), AuditoriaDeOrdem(self.auditoria), NotificacaoDeOrdem()])
        self.autenticacao = ServicoAutenticacao(self.uow, config, self.relogio, self.auditoria, cifrador)
        self.ordens = ServicoOrdens(self.uow, self.relogio, ValidadorOrdem(), publicador, self.auditoria)
        self.consultas = ServicoConsultas(self.uow, self.relogio)
        self.administracao = ServicoAdministracao(self.uow, self.relogio, self.auditoria, self.autenticacao)

        self.provedor = provedor or ProvedorCotacoesSimulado(self.relogio, self._precos_iniciais())
        self.corretora_externa = corretora or CorretoraSimulada(self._preco_atual)
        extras = {"dormir": dormir} if dormir else {}
        corretora_resiliente = CorretoraResiliente(self.corretora_externa, timeout_s=config.integration_timeout_ms / 1000,
                                                   tentativas=config.integration_max_retries, **extras)
        self.transmissao = ServicoTransmissao(self.uow, corretora_resiliente, self.relogio, publicador,
                                              self.auditoria, self.ordens)
        self.notificador = notificador or NotificadorSimulado()
        self.notificacoes = ServicoNotificacoes(self.uow, self.notificador)

    def _precos_iniciais(self) -> dict[str, Dinheiro]:
        precos = {}
        with self.uow(somente_leitura=True) as uow:
            for ativo in uow.ativos.listar():
                cotacao = uow.ativos.ultima_cotacao(ativo.id)
                if cotacao is not None:
                    precos[ativo.ticker] = cotacao.preco
        return precos

    def _preco_atual(self, ticker: str) -> Dinheiro | None:
        """Preço usado pela corretora simulada: a última cotação gravada."""
        with self.uow(somente_leitura=True) as uow:
            ativo = uow.ativos.buscar_por_ticker(ticker)
            cotacao = uow.ativos.ultima_cotacao(ativo.id) if ativo else None
        return cotacao.preco if cotacao else None

    def ciclo_processamento(self) -> None:
        """Uma rodada do processador: cotações, fila, ordens abertas e notificações."""
        self.consultas.ingerir_cotacoes(self.provedor)
        self.transmissao.ciclo()
        self.notificacoes.despachar()
