"""SentinelTrade: plataforma simulada de negociação de ativos (projeto acadêmico).

Camadas:
    dominio       entidades e regras do negócio (sem dependência de banco ou web)
    regras        regras de validação de ordens (padrão Strategy)
    persistencia  acesso ao banco SQLite com SQL parametrizado
    integracoes   corretora, cotações e notificações simuladas
    servicos      casos de uso (coordenam domínio, persistência e integrações)
    api           interface HTTP (FastAPI)
"""

__version__ = "0.1.0"
