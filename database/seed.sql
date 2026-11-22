-- ============================================================
-- SentinelTrade - dados iniciais (SQLite)
-- Todos os valores são SIMULADOS: não representam cotações reais.
--
-- Este arquivo não cria usuários: senhas e segredos de MFA não podem
-- ficar no repositório (RNF-09). Usuários são criados pela aplicação,
-- que gera o hash da senha e o segredo do MFA em tempo de execução.
--
-- Uso (depois do schema): sqlite3 sentineltrade.db < database/seed.sql
-- ============================================================

PRAGMA foreign_keys = ON;

-- Parâmetros operacionais (RF-15, RN-01, RN-06, RN-07)
INSERT INTO parametros (chave, valor) VALUES
    ('PREGAO_ABERTURA',     '10:00'),
    ('PREGAO_FECHAMENTO',   '17:55'),
    ('PREGAO_FUSO',         'America/Sao_Paulo'),
    ('PREGAO_DIAS',         'UTEIS'),
    ('COTACAO_IDADE_MAX_S', '5'),
    ('FAIXA_PRECO_PCT',     '10'),
    ('TAXA_OPERACAO_BPS',   '5');

-- Ativos negociáveis (RN-02); o último está suspenso para testar a rejeição
INSERT INTO ativos (ticker, nome, tipo, lote_minimo, negociavel) VALUES
    ('PETR4',  'Petrobras PN',              'ACAO', 1, 1),
    ('VALE3',  'Vale ON',                   'ACAO', 1, 1),
    ('ITUB4',  'Itaú Unibanco PN',          'ACAO', 1, 1),
    ('BOVA11', 'ETF Ibovespa',              'ETF',  1, 1),
    ('IVVB11', 'ETF S&P 500',               'ETF',  1, 1),
    ('HGLG11', 'FII Logística',             'FII',  1, 1),
    ('MXRF11', 'FII Recebíveis',            'FII',  1, 1),
    ('SUSP3',  'Ativo Suspenso (simulado)', 'ACAO', 1, 0);

-- Cotação inicial simulada de cada ativo (preço em centavos)
INSERT INTO cotacoes (ativo_id, preco_centavos, variacao_bps, data_hora)
SELECT id, preco, variacao, strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
FROM ativos
JOIN (
    SELECT 'PETR4'  AS t, 3850  AS preco,  120 AS variacao UNION ALL
    SELECT 'VALE3',       6120,           -85             UNION ALL
    SELECT 'ITUB4',       3375,            40             UNION ALL
    SELECT 'BOVA11',     12480,            55             UNION ALL
    SELECT 'IVVB11',     35290,           -30             UNION ALL
    SELECT 'HGLG11',     16110,            10             UNION ALL
    SELECT 'MXRF11',      1025,            -5             UNION ALL
    SELECT 'SUSP3',        150,             0
) AS precos ON precos.t = ativos.ticker;
