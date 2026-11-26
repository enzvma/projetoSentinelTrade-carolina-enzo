"""Implementação SQLite dos repositórios e da unidade de trabalho.

Regras desta camada:
- toda consulta usa parâmetros (?); nenhum dado de entrada é concatenado ao SQL (RNF-07);
- trechos dinâmicos de WHERE vêm de listas fixas no código, nunca do usuário;
- valores monetários são gravados em centavos e datas em UTC (RT-05).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from ..dominio.conta import Conta, LimiteRisco, Posicao
from ..dominio.dinheiro import Dinheiro
from ..dominio.enums import EstadoOrdem, Lado, Perfil, TipoAtivo, TipoOrdem
from ..dominio.mercado import Ativo, Cotacao
from ..dominio.ordem import Ordem, TransicaoOrdem
from ..dominio.usuario import Usuario
from .banco import conectar
from .repositorios import (ItemFila, NotificacaoPendente, RegistroAuditoria, RepositorioAtivos,
                           RepositorioAuditoria, RepositorioContas, RepositorioEstadoSistema, RepositorioFila,
                           RepositorioNotificacoes, RepositorioOrdens, RepositorioParametros, RepositorioUsuarios)

ESTADOS_ABERTOS = (EstadoOrdem.CRIADA.value, EstadoOrdem.VALIDADA.value, EstadoOrdem.ENVIADA.value,
                   EstadoOrdem.PARCIALMENTE_EXECUTADA.value)


def para_texto(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        raise ValueError("datetime sem fuso horário")
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def de_texto(texto: str | None) -> datetime | None:
    if texto is None:
        return None
    return datetime.fromisoformat(texto.replace("Z", "+00:00")).astimezone(timezone.utc)


class _Repo:
    def __init__(self, conexao: sqlite3.Connection) -> None:
        self._c = conexao


class UsuariosSQLite(_Repo, RepositorioUsuarios):
    _POR_EMAIL = ("SELECT id, nome, email, senha_hash, mfa_segredo_cifrado, mfa_ultimo_passo, perfil, ativo, "
                  "tentativas_falhas, bloqueado_ate FROM usuarios WHERE email = ?")
    _POR_ID = ("SELECT id, nome, email, senha_hash, mfa_segredo_cifrado, mfa_ultimo_passo, perfil, ativo, "
               "tentativas_falhas, bloqueado_ate FROM usuarios WHERE id = ?")

    @staticmethod
    def _montar(l: sqlite3.Row | None) -> Usuario | None:
        if l is None:
            return None
        return Usuario(id=l["id"], nome=l["nome"], email=l["email"], senha_hash=l["senha_hash"],
                       mfa_segredo_cifrado=l["mfa_segredo_cifrado"], perfil=Perfil(l["perfil"]),
                       ativo=bool(l["ativo"]), mfa_ultimo_passo=l["mfa_ultimo_passo"],
                       tentativas_falhas=l["tentativas_falhas"], bloqueado_ate=de_texto(l["bloqueado_ate"]))

    def buscar_por_email(self, email):
        return self._montar(self._c.execute(self._POR_EMAIL, (email,)).fetchone())

    def buscar_por_id(self, usuario_id):
        return self._montar(self._c.execute(self._POR_ID, (usuario_id,)).fetchone())

    def inserir(self, usuario, agora):
        senha_hash, segredo = usuario.credenciais()
        cur = self._c.execute(
            "INSERT INTO usuarios (nome, email, senha_hash, mfa_segredo_cifrado, perfil, ativo, criado_em) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (usuario.nome, usuario.email, senha_hash, segredo, usuario.perfil.value, int(usuario.ativo),
             para_texto(agora)))
        usuario.definir_id(cur.lastrowid)
        return cur.lastrowid

    def atualizar_seguranca(self, usuario):
        self._c.execute(
            "UPDATE usuarios SET ativo = ?, tentativas_falhas = ?, bloqueado_ate = ?, mfa_ultimo_passo = ? "
            "WHERE id = ?",
            (int(usuario.ativo), usuario.tentativas_falhas, para_texto(usuario.bloqueado_ate),
             usuario.mfa_ultimo_passo, usuario.id))


class ContasSQLite(_Repo, RepositorioContas):
    @staticmethod
    def _montar(l):
        if l is None:
            return None
        return Conta(id=l["id"], usuario_id=l["usuario_id"],
                     saldo_disponivel=Dinheiro(l["saldo_disponivel_centavos"]),
                     saldo_bloqueado=Dinheiro(l["saldo_bloqueado_centavos"]), ativa=l["situacao"] == "ATIVA")

    def buscar(self, conta_id):
        return self._montar(self._c.execute("SELECT * FROM contas WHERE id = ?", (conta_id,)).fetchone())

    def buscar_por_usuario(self, usuario_id):
        return self._montar(self._c.execute("SELECT * FROM contas WHERE usuario_id = ?", (usuario_id,)).fetchone())

    def inserir(self, usuario_id, agora):
        cur = self._c.execute("INSERT INTO contas (usuario_id, criada_em) VALUES (?, ?)",
                              (usuario_id, para_texto(agora)))
        return self.buscar(cur.lastrowid)

    def atualizar_saldos(self, conta):
        self._c.execute(
            "UPDATE contas SET saldo_disponivel_centavos = ?, saldo_bloqueado_centavos = ?, situacao = ? "
            "WHERE id = ?",
            (conta.saldo_disponivel.centavos, conta.saldo_bloqueado.centavos,
             "ATIVA" if conta.ativa else "INATIVA", conta.id))

    def buscar_limite(self, conta_id):
        l = self._c.execute("SELECT * FROM limites_risco WHERE conta_id = ?", (conta_id,)).fetchone()
        if l is None:
            return None
        return LimiteRisco(conta_id=l["conta_id"], valor_maximo_ordem=Dinheiro(l["valor_maximo_ordem_centavos"]),
                           exposicao_maxima=Dinheiro(l["exposicao_maxima_centavos"]))

    def salvar_limite(self, limite, por_usuario_id, agora):
        self._c.execute(
            "INSERT INTO limites_risco (conta_id, valor_maximo_ordem_centavos, exposicao_maxima_centavos, "
            "atualizado_em, atualizado_por) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(conta_id) DO UPDATE SET valor_maximo_ordem_centavos = excluded.valor_maximo_ordem_centavos, "
            "exposicao_maxima_centavos = excluded.exposicao_maxima_centavos, "
            "atualizado_em = excluded.atualizado_em, atualizado_por = excluded.atualizado_por",
            (limite.conta_id, limite.valor_maximo_ordem.centavos, limite.exposicao_maxima.centavos,
             para_texto(agora), por_usuario_id))

    @staticmethod
    def _posicao(l):
        return Posicao(conta_id=l["conta_id"], ativo_id=l["ativo_id"],
                       quantidade_disponivel=l["quantidade_disponivel"],
                       quantidade_bloqueada=l["quantidade_bloqueada"],
                       preco_medio=Dinheiro(l["preco_medio_centavos"]))

    def buscar_posicao(self, conta_id, ativo_id):
        l = self._c.execute("SELECT * FROM posicoes WHERE conta_id = ? AND ativo_id = ?",
                            (conta_id, ativo_id)).fetchone()
        return self._posicao(l) if l else None

    def listar_posicoes(self, conta_id):
        return [self._posicao(l) for l in self._c.execute(
            "SELECT * FROM posicoes WHERE conta_id = ? ORDER BY ativo_id", (conta_id,))]

    def salvar_posicao(self, posicao):
        self._c.execute(
            "INSERT INTO posicoes (conta_id, ativo_id, quantidade_disponivel, quantidade_bloqueada, "
            "preco_medio_centavos) VALUES (?, ?, ?, ?, ?) ON CONFLICT(conta_id, ativo_id) DO UPDATE SET "
            "quantidade_disponivel = excluded.quantidade_disponivel, "
            "quantidade_bloqueada = excluded.quantidade_bloqueada, preco_medio_centavos = excluded.preco_medio_centavos",
            (posicao.conta_id, posicao.ativo_id, posicao.quantidade_disponivel, posicao.quantidade_bloqueada,
             posicao.preco_medio.centavos))

    def exposicao_compras_abertas(self, conta_id):
        marcadores = ",".join("?" * len(ESTADOS_ABERTOS))
        total = self._c.execute(
            f"SELECT COALESCE(SUM(valor_bloqueado_centavos), 0) FROM ordens "  # nosec B608 - só marcadores ?
            f"WHERE conta_id = ? AND lado = 'COMPRA' AND estado IN ({marcadores})",
            (conta_id, *ESTADOS_ABERTOS)).fetchone()[0]
        return Dinheiro(int(total))


class AtivosSQLite(_Repo, RepositorioAtivos):
    @staticmethod
    def _montar(l):
        if l is None:
            return None
        return Ativo(id=l["id"], ticker=l["ticker"], nome=l["nome"], tipo=TipoAtivo(l["tipo"]),
                     lote_minimo=l["lote_minimo"], negociavel=bool(l["negociavel"]))

    def buscar_por_ticker(self, ticker):
        return self._montar(self._c.execute("SELECT * FROM ativos WHERE ticker = ?", (ticker,)).fetchone())

    def buscar_por_id(self, ativo_id):
        return self._montar(self._c.execute("SELECT * FROM ativos WHERE id = ?", (ativo_id,)).fetchone())

    def listar(self):
        return [self._montar(l) for l in self._c.execute("SELECT * FROM ativos ORDER BY ticker")]

    def inserir(self, ativo):
        cur = self._c.execute("INSERT INTO ativos (ticker, nome, tipo, lote_minimo, negociavel) VALUES (?, ?, ?, ?, ?)",
                              (ativo.ticker, ativo.nome, ativo.tipo.value, ativo.lote_minimo, int(ativo.negociavel)))
        return cur.lastrowid

    def atualizar(self, ativo):
        self._c.execute("UPDATE ativos SET nome = ?, negociavel = ? WHERE id = ?",
                        (ativo.nome, int(ativo.negociavel), ativo.id))

    def ultima_cotacao(self, ativo_id):
        l = self._c.execute("SELECT * FROM cotacoes WHERE ativo_id = ? ORDER BY data_hora DESC, id DESC LIMIT 1",
                            (ativo_id,)).fetchone()
        if l is None:
            return None
        return Cotacao(ativo_id=l["ativo_id"], preco=Dinheiro(l["preco_centavos"]),
                       variacao_bps=l["variacao_bps"], data_hora=de_texto(l["data_hora"]))

    def inserir_cotacao(self, cotacao):
        self._c.execute("INSERT INTO cotacoes (ativo_id, preco_centavos, variacao_bps, data_hora) VALUES (?, ?, ?, ?)",
                        (cotacao.ativo_id, cotacao.preco.centavos, cotacao.variacao_bps, para_texto(cotacao.data_hora)))


class OrdensSQLite(_Repo, RepositorioOrdens):
    _SELECT = "SELECT o.*, a.ticker FROM ordens o JOIN ativos a ON a.id = o.ativo_id"

    @staticmethod
    def _montar(l):
        if l is None:
            return None
        preco = l["preco_centavos"]
        return Ordem(id=l["id"], conta_id=l["conta_id"], ativo_id=l["ativo_id"], ticker=l["ticker"],
                     chave_idempotencia=l["chave_idempotencia"], lado=Lado(l["lado"]), tipo=TipoOrdem(l["tipo"]),
                     quantidade=l["quantidade"], preco=Dinheiro(preco) if preco is not None else None,
                     estado=EstadoOrdem(l["estado"]), quantidade_executada=l["quantidade_executada"],
                     valor_bloqueado=Dinheiro(l["valor_bloqueado_centavos"]), motivo=l["motivo"],
                     ordem_origem_id=l["ordem_origem_id"], criada_em=de_texto(l["criada_em"]),
                     atualizada_em=de_texto(l["atualizada_em"]))

    def inserir(self, ordem):
        cur = self._c.execute(
            "INSERT INTO ordens (conta_id, ativo_id, ordem_origem_id, chave_idempotencia, lado, tipo, quantidade, "
            "preco_centavos, quantidade_executada, valor_bloqueado_centavos, estado, motivo, criada_em, atualizada_em) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ordem.conta_id, ordem.ativo_id, ordem.ordem_origem_id, ordem.chave_idempotencia, ordem.lado.value,
             ordem.tipo.value, ordem.quantidade, ordem.preco.centavos if ordem.preco else None,
             ordem.quantidade_executada, ordem.valor_bloqueado.centavos, ordem.estado.value, ordem.motivo,
             para_texto(ordem.criada_em), para_texto(ordem.atualizada_em)))
        ordem.definir_id(cur.lastrowid)
        return cur.lastrowid

    def atualizar(self, ordem):
        self._c.execute(
            "UPDATE ordens SET estado = ?, quantidade_executada = ?, valor_bloqueado_centavos = ?, motivo = ?, "
            "atualizada_em = ? WHERE id = ?",
            (ordem.estado.value, ordem.quantidade_executada, ordem.valor_bloqueado.centavos, ordem.motivo,
             para_texto(ordem.atualizada_em), ordem.id))

    def buscar(self, ordem_id):
        return self._montar(self._c.execute(f"{self._SELECT} WHERE o.id = ?", (ordem_id,)).fetchone())

    def buscar_por_chave(self, conta_id, chave):
        return self._montar(self._c.execute(f"{self._SELECT} WHERE o.conta_id = ? AND o.chave_idempotencia = ?",
                                            (conta_id, chave)).fetchone())

    def listar(self, *, conta_id, estado, ticker, limite, deslocamento):
        condicoes, parametros = [], []
        if conta_id is not None:
            condicoes.append("o.conta_id = ?"); parametros.append(conta_id)
        if estado is not None:
            condicoes.append("o.estado = ?"); parametros.append(EstadoOrdem(estado).value)
        if ticker is not None:
            condicoes.append("a.ticker = ?"); parametros.append(ticker)
        where = (" WHERE " + " AND ".join(condicoes)) if condicoes else ""
        sql = f"{self._SELECT}{where} ORDER BY o.criada_em DESC, o.id DESC LIMIT ? OFFSET ?"  # nosec B608
        return [self._montar(l) for l in self._c.execute(sql, (*parametros, limite, deslocamento))]

    def derivadas_aguardando(self, ordem_origem_id):
        return [self._montar(l) for l in self._c.execute(
            f"{self._SELECT} WHERE o.ordem_origem_id = ? AND o.estado = 'CRIADA' ORDER BY o.id", (ordem_origem_id,))]

    def registrar_transicao(self, ordem_id, transicao):
        self._c.execute(
            "INSERT INTO transicoes_ordem (ordem_id, estado_anterior, estado_novo, origem, data_hora) "
            "VALUES (?, ?, ?, ?, ?)",
            (ordem_id, transicao.anterior.value if transicao.anterior else None, transicao.novo.value,
             transicao.origem.value, para_texto(transicao.data_hora)))

    def listar_transicoes(self, ordem_id):
        return [{"estado_anterior": l["estado_anterior"], "estado_novo": l["estado_novo"], "origem": l["origem"],
                 "data_hora": de_texto(l["data_hora"])}
                for l in self._c.execute("SELECT * FROM transicoes_ordem WHERE ordem_id = ? ORDER BY id", (ordem_id,))]

    def execucao_registrada(self, id_execucao_corretora):
        return self._c.execute("SELECT 1 FROM execucoes WHERE id_execucao_corretora = ?",
                               (id_execucao_corretora,)).fetchone() is not None

    def registrar_execucao(self, ordem_id, id_execucao_corretora, quantidade, preco, agora):
        self._c.execute(
            "INSERT INTO execucoes (ordem_id, id_execucao_corretora, quantidade, preco_centavos, data_hora) "
            "VALUES (?, ?, ?, ?, ?)", (ordem_id, id_execucao_corretora, quantidade, preco.centavos, para_texto(agora)))


class FilaSQLite(_Repo, RepositorioFila):
    def enfileirar(self, ordem_id, operacao, agora):
        self._c.execute("INSERT INTO fila_ordens (ordem_id, operacao, criada_em) VALUES (?, ?, ?) "
                        "ON CONFLICT(ordem_id, operacao) DO NOTHING", (ordem_id, operacao, para_texto(agora)))

    def existe(self, ordem_id, operacao):
        return self._c.execute("SELECT 1 FROM fila_ordens WHERE ordem_id = ? AND operacao = ?",
                               (ordem_id, operacao)).fetchone() is not None

    def proximos(self, agora, limite):
        return [ItemFila(l["id"], l["ordem_id"], l["operacao"], l["situacao"], l["tentativas"])
                for l in self._c.execute(
                    "SELECT * FROM fila_ordens WHERE situacao = 'PENDENTE' "
                    "AND (proxima_tentativa_em IS NULL OR proxima_tentativa_em <= ?) ORDER BY id LIMIT ?",
                    (para_texto(agora), limite))]

    def atualizar(self, item_id, situacao, tentativas, proxima):
        self._c.execute("UPDATE fila_ordens SET situacao = ?, tentativas = ?, proxima_tentativa_em = ? WHERE id = ?",
                        (situacao, tentativas, para_texto(proxima), item_id))

    def concluir_pendentes_da_ordem(self, ordem_id, operacao):
        self._c.execute("UPDATE fila_ordens SET situacao = 'CONCLUIDA' WHERE ordem_id = ? AND operacao = ? "
                        "AND situacao IN ('PENDENTE', 'FALHA')", (ordem_id, operacao))

    def reabrir_falhas(self, agora):
        cur = self._c.execute("UPDATE fila_ordens SET situacao = 'PENDENTE', tentativas = 0, "
                              "proxima_tentativa_em = ? WHERE situacao = 'FALHA'", (para_texto(agora),))
        return cur.rowcount


class NotificacoesSQLite(_Repo, RepositorioNotificacoes):
    def criar(self, usuario_id, ordem_id, chave_evento, tipo, mensagem, agora):
        self._c.execute(
            "INSERT INTO notificacoes (usuario_id, ordem_id, chave_evento, tipo, mensagem, criada_em) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(chave_evento) DO NOTHING",
            (usuario_id, ordem_id, chave_evento, tipo, mensagem, para_texto(agora)))

    def pendentes(self, limite):
        return [NotificacaoPendente(l["id"], l["usuario_id"], l["ordem_id"], l["tipo"], l["mensagem"], l["tentativas"])
                for l in self._c.execute("SELECT * FROM notificacoes WHERE situacao_envio = 'PENDENTE' "
                                         "ORDER BY id LIMIT ?", (limite,))]

    def marcar(self, notificacao_id, situacao, tentativas):
        self._c.execute("UPDATE notificacoes SET situacao_envio = ?, tentativas = ? WHERE id = ?",
                        (situacao, tentativas, notificacao_id))


class AuditoriaSQLite(_Repo, RepositorioAuditoria):
    @staticmethod
    def _montar(l):
        return RegistroAuditoria(l["id"], de_texto(l["data_hora"]), l["ator"], l["acao"], l["entidade"],
                                 l["entidade_id"], l["resultado"], l["detalhes"], l["correlation_id"],
                                 l["hash_anterior"], l["hash"])

    def ultimo_hash(self):
        l = self._c.execute("SELECT hash FROM log_auditoria ORDER BY id DESC LIMIT 1").fetchone()
        return l["hash"] if l else None

    def inserir(self, r):
        self._c.execute(
            "INSERT INTO log_auditoria (data_hora, ator, acao, entidade, entidade_id, resultado, detalhes, "
            "correlation_id, hash_anterior, hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (para_texto(r.data_hora), r.ator, r.acao, r.entidade, r.entidade_id, r.resultado, r.detalhes,
             r.correlation_id, r.hash_anterior, r.hash))

    def listar(self, *, entidade, entidade_id, limite, deslocamento):
        condicoes, parametros = [], []
        if entidade is not None:
            condicoes.append("entidade = ?"); parametros.append(entidade)
        if entidade_id is not None:
            condicoes.append("entidade_id = ?"); parametros.append(entidade_id)
        where = (" WHERE " + " AND ".join(condicoes)) if condicoes else ""
        sql = f"SELECT * FROM log_auditoria{where} ORDER BY id DESC LIMIT ? OFFSET ?"  # nosec B608
        return [self._montar(l) for l in self._c.execute(sql, (*parametros, limite, deslocamento))]

    def todos_em_ordem(self):
        return [self._montar(l) for l in self._c.execute("SELECT * FROM log_auditoria ORDER BY id")]


class ParametrosSQLite(_Repo, RepositorioParametros):
    def obter_todos(self):
        return {l["chave"]: l["valor"] for l in self._c.execute("SELECT chave, valor FROM parametros")}

    def atualizar(self, chave, valor, por_usuario_id, agora):
        self._c.execute(
            "INSERT INTO parametros (chave, valor, atualizado_em, atualizado_por) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor, atualizado_em = excluded.atualizado_em, "
            "atualizado_por = excluded.atualizado_por", (chave, valor, para_texto(agora), por_usuario_id))


class EstadoSistemaSQLite(_Repo, RepositorioEstadoSistema):
    def modo_restrito(self):
        l = self._c.execute("SELECT modo_restrito, motivo FROM estado_sistema WHERE id = 1").fetchone()
        return (bool(l["modo_restrito"]), l["motivo"]) if l else (False, None)

    def definir(self, restrito, motivo, agora):
        self._c.execute("UPDATE estado_sistema SET modo_restrito = ?, motivo = ?, atualizado_em = ? WHERE id = 1",
                        (int(restrito), motivo, para_texto(agora)))


class UnidadeDeTrabalho:
    """Uma transação: tudo o que é feito dentro dela é gravado junto ou desfeito junto (RNF-18).

    Uso:
        with fabrica() as uow:
            ...
            uow.confirmar()
    Sem `confirmar()`, a transação é desfeita ao sair do bloco.
    """

    def __init__(self, caminho: str, somente_leitura: bool = False) -> None:
        self._caminho = caminho
        self._somente_leitura = somente_leitura
        self._conexao: sqlite3.Connection | None = None
        self._confirmada = False

    def __enter__(self) -> "UnidadeDeTrabalho":
        self._conexao = conectar(self._caminho)
        self._conexao.execute("BEGIN" if self._somente_leitura else "BEGIN IMMEDIATE")
        c = self._conexao
        self.usuarios = UsuariosSQLite(c)
        self.contas = ContasSQLite(c)
        self.ativos = AtivosSQLite(c)
        self.ordens = OrdensSQLite(c)
        self.fila = FilaSQLite(c)
        self.notificacoes = NotificacoesSQLite(c)
        self.auditoria = AuditoriaSQLite(c)
        self.parametros = ParametrosSQLite(c)
        self.estado_sistema = EstadoSistemaSQLite(c)
        return self

    def confirmar(self) -> None:
        self._conexao.execute("COMMIT")
        self._confirmada = True

    def __exit__(self, tipo, valor, rastreio) -> None:
        try:
            if not self._confirmada:
                self._conexao.execute("ROLLBACK")
        finally:
            self._conexao.close()


class FabricaUnidade:
    def __init__(self, caminho: str) -> None:
        self._caminho = caminho

    def __call__(self, somente_leitura: bool = False) -> UnidadeDeTrabalho:
        return UnidadeDeTrabalho(self._caminho, somente_leitura)
