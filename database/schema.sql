-- ============================================================
-- SentinelTrade - estrutura do banco de dados (SQLite)
-- Dados exclusivamente simulados.
--
-- Convenções:
--   * valores monetários em centavos (INTEGER), nunca ponto flutuante (RT-05);
--   * datas em texto ISO-8601, sempre em UTC (RT-05);
--   * regras críticas protegidas também no banco (restrições e gatilhos).
--
-- Uso: sqlite3 sentineltrade.db < database/schema.sql
-- ============================================================

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------
-- Usuários, contas e limites
-- ------------------------------------------------------------
CREATE TABLE usuarios (
    id                    INTEGER PRIMARY KEY,
    nome                  TEXT    NOT NULL CHECK (length(nome) BETWEEN 2 AND 100),
    email                 TEXT    NOT NULL UNIQUE CHECK (length(email) <= 254 AND email LIKE '%_@_%._%'),
    senha_hash            TEXT    NOT NULL,                 -- Argon2id (RNF-01)
    mfa_segredo_cifrado   TEXT    NOT NULL,                 -- segredo TOTP cifrado (RNF-10)
    mfa_ultimo_passo      INTEGER NOT NULL DEFAULT 0,       -- impede reutilizar o mesmo código (RNF-02)
    perfil                TEXT    NOT NULL CHECK (perfil IN ('INVESTIDOR', 'ADMINISTRADOR', 'ANALISTA_RISCO', 'AUDITOR')),
    ativo                 INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
    tentativas_falhas     INTEGER NOT NULL DEFAULT 0 CHECK (tentativas_falhas >= 0),
    bloqueado_ate         TEXT,                             -- RN-13
    criado_em             TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE contas (
    id                        INTEGER PRIMARY KEY,
    usuario_id                INTEGER NOT NULL UNIQUE REFERENCES usuarios (id),
    saldo_disponivel_centavos INTEGER NOT NULL DEFAULT 0 CHECK (saldo_disponivel_centavos >= 0),
    saldo_bloqueado_centavos  INTEGER NOT NULL DEFAULT 0 CHECK (saldo_bloqueado_centavos >= 0),
    situacao                  TEXT    NOT NULL DEFAULT 'ATIVA' CHECK (situacao IN ('ATIVA', 'INATIVA')),
    criada_em                 TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE limites_risco (
    conta_id                    INTEGER PRIMARY KEY REFERENCES contas (id),
    valor_maximo_ordem_centavos INTEGER NOT NULL CHECK (valor_maximo_ordem_centavos > 0),
    exposicao_maxima_centavos   INTEGER NOT NULL CHECK (exposicao_maxima_centavos > 0),
    atualizado_em               TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    atualizado_por              INTEGER REFERENCES usuarios (id)
);

-- ------------------------------------------------------------
-- Ativos, cotações e parâmetros
-- ------------------------------------------------------------
CREATE TABLE ativos (
    id          INTEGER PRIMARY KEY,
    ticker      TEXT    NOT NULL UNIQUE CHECK (length(ticker) BETWEEN 5 AND 6 AND ticker = upper(ticker)),
    nome        TEXT    NOT NULL CHECK (length(nome) BETWEEN 2 AND 100),
    tipo        TEXT    NOT NULL CHECK (tipo IN ('ACAO', 'ETF', 'FII')),
    lote_minimo INTEGER NOT NULL DEFAULT 1 CHECK (lote_minimo > 0),
    negociavel  INTEGER NOT NULL DEFAULT 1 CHECK (negociavel IN (0, 1))   -- RN-02
);

CREATE TABLE cotacoes (
    id             INTEGER PRIMARY KEY,
    ativo_id       INTEGER NOT NULL REFERENCES ativos (id),
    preco_centavos INTEGER NOT NULL CHECK (preco_centavos > 0),
    variacao_bps   INTEGER NOT NULL DEFAULT 0,             -- variação em centésimos de ponto percentual
    data_hora      TEXT    NOT NULL                          -- horário da cotação (RN-07)
);
CREATE INDEX ix_cotacoes_ativo_data ON cotacoes (ativo_id, data_hora DESC);

CREATE TABLE parametros (
    chave          TEXT    PRIMARY KEY CHECK (chave IN (
                       'PREGAO_ABERTURA', 'PREGAO_FECHAMENTO', 'PREGAO_FUSO', 'PREGAO_DIAS',
                       'COTACAO_IDADE_MAX_S', 'FAIXA_PRECO_PCT', 'TAXA_OPERACAO_BPS')),
    valor          TEXT    NOT NULL CHECK (length(valor) BETWEEN 1 AND 50),
    atualizado_em  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    atualizado_por INTEGER REFERENCES usuarios (id)
);

-- ------------------------------------------------------------
-- Carteira
-- ------------------------------------------------------------
CREATE TABLE posicoes (
    conta_id              INTEGER NOT NULL REFERENCES contas (id),
    ativo_id              INTEGER NOT NULL REFERENCES ativos (id),
    quantidade_disponivel INTEGER NOT NULL DEFAULT 0 CHECK (quantidade_disponivel >= 0),   -- RN-04
    quantidade_bloqueada  INTEGER NOT NULL DEFAULT 0 CHECK (quantidade_bloqueada >= 0),
    preco_medio_centavos  INTEGER NOT NULL DEFAULT 0 CHECK (preco_medio_centavos >= 0),
    PRIMARY KEY (conta_id, ativo_id)
);

-- ------------------------------------------------------------
-- Ordens e execuções
-- ------------------------------------------------------------
CREATE TABLE ordens (
    id                       INTEGER PRIMARY KEY,
    conta_id                 INTEGER NOT NULL REFERENCES contas (id),
    ativo_id                 INTEGER NOT NULL REFERENCES ativos (id),
    ordem_origem_id          INTEGER REFERENCES ordens (id),           -- preenchido na alteração (RN-19)
    chave_idempotencia       TEXT    NOT NULL CHECK (length(chave_idempotencia) BETWEEN 16 AND 64),
    lado                     TEXT    NOT NULL CHECK (lado IN ('COMPRA', 'VENDA')),
    tipo                     TEXT    NOT NULL CHECK (tipo IN ('MERCADO', 'LIMITADA')),
    quantidade               INTEGER NOT NULL CHECK (quantidade > 0),
    preco_centavos           INTEGER CHECK (preco_centavos IS NULL OR preco_centavos > 0),
    quantidade_executada     INTEGER NOT NULL DEFAULT 0 CHECK (quantidade_executada >= 0),
    valor_bloqueado_centavos INTEGER NOT NULL DEFAULT 0 CHECK (valor_bloqueado_centavos >= 0),
    estado                   TEXT    NOT NULL DEFAULT 'CRIADA' CHECK (estado IN (
                                 'CRIADA', 'VALIDADA', 'ENVIADA', 'PARCIALMENTE_EXECUTADA',
                                 'EXECUTADA', 'REJEITADA', 'CANCELADA')),
    motivo                   TEXT    CHECK (motivo IS NULL OR length(motivo) <= 100),
    criada_em                TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    atualizada_em            TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE (conta_id, chave_idempotencia),                                  -- RN-12
    CHECK (quantidade_executada <= quantidade),
    CHECK ((tipo = 'LIMITADA' AND preco_centavos IS NOT NULL) OR (tipo = 'MERCADO' AND preco_centavos IS NULL))
);
CREATE INDEX ix_ordens_conta_data ON ordens (conta_id, criada_em DESC);

-- Histórico de estados de cada ordem (RF-08)
CREATE TABLE transicoes_ordem (
    id              INTEGER PRIMARY KEY,
    ordem_id        INTEGER NOT NULL REFERENCES ordens (id),
    estado_anterior TEXT,
    estado_novo     TEXT    NOT NULL,
    origem          TEXT    NOT NULL CHECK (origem IN ('USUARIO', 'SISTEMA', 'CORRETORA')),
    data_hora       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX ix_transicoes_ordem ON transicoes_ordem (ordem_id, id);

CREATE TABLE execucoes (
    id                      INTEGER PRIMARY KEY,
    ordem_id                INTEGER NOT NULL REFERENCES ordens (id),
    id_execucao_corretora   TEXT    NOT NULL UNIQUE,      -- a mesma execução não é aplicada duas vezes
    quantidade              INTEGER NOT NULL CHECK (quantidade > 0),
    preco_centavos          INTEGER NOT NULL CHECK (preco_centavos > 0),
    data_hora               TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Estados finais não mudam e nenhuma ordem volta ao estado inicial (RN-09)
CREATE TRIGGER tg_ordem_estado_final
BEFORE UPDATE OF estado ON ordens
WHEN OLD.estado IN ('EXECUTADA', 'REJEITADA', 'CANCELADA') AND NEW.estado <> OLD.estado
BEGIN
    SELECT RAISE(ABORT, 'ordem em estado final não pode mudar de estado');
END;

CREATE TRIGGER tg_ordem_sem_volta_inicial
BEFORE UPDATE OF estado ON ordens
WHEN NEW.estado = 'CRIADA' AND OLD.estado <> 'CRIADA'
BEGIN
    SELECT RAISE(ABORT, 'ordem não pode voltar ao estado inicial');
END;

-- Ordens nunca são apagadas, nem em falha da corretora (RN-18)
CREATE TRIGGER tg_ordem_sem_delete
BEFORE DELETE ON ordens
BEGIN
    SELECT RAISE(ABORT, 'ordens não podem ser apagadas');
END;

-- ------------------------------------------------------------
-- Fila persistente de transmissão (RNF-15, RT-03)
-- ------------------------------------------------------------
CREATE TABLE fila_ordens (
    id                  INTEGER PRIMARY KEY,
    ordem_id            INTEGER NOT NULL REFERENCES ordens (id),
    operacao            TEXT    NOT NULL CHECK (operacao IN ('ENVIAR', 'CANCELAR')),
    situacao            TEXT    NOT NULL DEFAULT 'PENDENTE' CHECK (situacao IN ('PENDENTE', 'PROCESSANDO', 'CONCLUIDA', 'FALHA')),
    tentativas          INTEGER NOT NULL DEFAULT 0 CHECK (tentativas BETWEEN 0 AND 3),   -- RNF-13
    proxima_tentativa_em TEXT,
    criada_em           TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE (ordem_id, operacao)                                                 -- sem processamento duplicado
);
CREATE INDEX ix_fila_pendentes ON fila_ordens (situacao, proxima_tentativa_em);

-- ------------------------------------------------------------
-- Notificações
-- ------------------------------------------------------------
CREATE TABLE notificacoes (
    id             INTEGER PRIMARY KEY,
    usuario_id     INTEGER NOT NULL REFERENCES usuarios (id),
    ordem_id       INTEGER REFERENCES ordens (id),
    chave_evento   TEXT    NOT NULL UNIQUE,              -- impede notificação duplicada (RN-15)
    tipo           TEXT    NOT NULL CHECK (tipo IN ('EXECUCAO', 'EXECUCAO_PARCIAL', 'REJEICAO', 'CANCELAMENTO', 'FALHA')),
    mensagem       TEXT    NOT NULL CHECK (length(mensagem) <= 200),
    situacao_envio TEXT    NOT NULL DEFAULT 'PENDENTE' CHECK (situacao_envio IN ('PENDENTE', 'ENVIADA', 'FALHA')),
    tentativas     INTEGER NOT NULL DEFAULT 0 CHECK (tentativas >= 0),
    criada_em      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- ------------------------------------------------------------
-- Auditoria (só inclusão, com hash encadeado) - RF-11, RNF-22
-- ------------------------------------------------------------
CREATE TABLE log_auditoria (
    id             INTEGER PRIMARY KEY,
    data_hora      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    ator           TEXT    NOT NULL CHECK (length(ator) <= 64),
    acao           TEXT    NOT NULL CHECK (length(acao) <= 64),
    entidade       TEXT    NOT NULL CHECK (length(entidade) <= 32),
    entidade_id    TEXT,
    resultado      TEXT    NOT NULL CHECK (length(resultado) <= 64),
    detalhes       TEXT    CHECK (detalhes IS NULL OR length(detalhes) <= 500),
    correlation_id TEXT    NOT NULL CHECK (length(correlation_id) <= 64),   -- RNF-25
    hash_anterior  TEXT    NOT NULL UNIQUE,
    hash           TEXT    NOT NULL UNIQUE
);
CREATE INDEX ix_auditoria_entidade ON log_auditoria (entidade, entidade_id);

CREATE TRIGGER tg_auditoria_sem_update
BEFORE UPDATE ON log_auditoria
BEGIN
    SELECT RAISE(ABORT, 'log de auditoria é imutável');
END;

CREATE TRIGGER tg_auditoria_sem_delete
BEFORE DELETE ON log_auditoria
BEGIN
    SELECT RAISE(ABORT, 'log de auditoria é imutável');
END;

-- ------------------------------------------------------------
-- Estado do sistema: modo restrito (RNF-16), compartilhado entre API e processador da fila
-- ------------------------------------------------------------
CREATE TABLE estado_sistema (
    id            INTEGER PRIMARY KEY CHECK (id = 1),
    modo_restrito INTEGER NOT NULL DEFAULT 0 CHECK (modo_restrito IN (0, 1)),
    motivo        TEXT    CHECK (motivo IS NULL OR length(motivo) <= 100),
    atualizado_em TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
INSERT INTO estado_sistema (id, modo_restrito) VALUES (1, 0);
