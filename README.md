# SentinelTrade
Trabalho Semestral - Projeto de Software

> **Aviso:** o SentinelTrade opera exclusivamente com dados e operações **simulados**. Não há integração com bolsa real, dinheiro real nem dados reais de investidores.

## Integrantes
- Carolina Yamada - R.A.: 10741647
- Enzo Vasconcellos - R.A.: 10736817

## Objetivo

O SentinelTrade é uma plataforma simulada de negociação de ações, ETFs e fundos imobiliários para a corretora fictícia Orion Capital. Investidores autenticados com MFA consultam saldo, carteira e cotações e enviam, alteram e cancelam ordens de compra e venda. Toda ordem é validada (saldo, posição, limite de risco e situação do mercado) antes de ir à corretora simulada, nenhuma ordem é processada em duplicidade e todos os eventos relevantes ficam registrados em auditoria.

## Contexto do Problema

A corretora fictícia Orion Capital opera uma plataforma digital de negociação de ações, ETFs e fundos imobiliários. Atualmente, suas operações dependem de sistemas pouco integrados, dificultando a rastreabilidade das ordens, o controle de risco e a auditoria.

A Orion Capital contratou a nossa equipe para especificar, modelar e implementar o SentinelTrade, uma plataforma que deverá:

- Autenticar usuários com MFA;
- Manter dados de investidores, contas, carteiras, ativos e limites financeiros;
- Receber cotações em tempo quase real por meio de um provedor externo;
- Permitir ordens de compra, venda, alteração, cancelamento e consulta;
- Validar saldo, posição em carteira, limite de risco e situação do mercado antes de transmitir a ordem;
- Integrar-se a uma Bolsa/Corretora simulada;
- Acompanhar o ciclo de vida das ordens;
- Registrar logs de auditoria imutáveis;
- Notificar o investidor sobre execução, rejeição, cancelamento ou falha;
- Operar com mecanismos de recuperação, indisponibilidade controlada e prevenção de duplicidade de ordens.

### Escopo
Dentro: autenticação com MFA, cadastro de usuários e investidores, ativos e limites, cotações, ordens (compra, venda, alteração e cancelamento), validações, integração com corretora simulada, ciclo de vida da ordem, carteira e saldo, histórico, notificações e auditoria imutável.

Fora: bolsa real, dinheiro real, liquidação e custódia reais, derivativos e renda fixa, análise gráfica e recomendação de investimentos.

## Tecnologias e Dependências

| Item | Escolha |
|---|---|
| Linguagem | Python 3.12 ou superior |
| Banco de dados | SQLite (relacional, scripts em `database/`) |
| API e validação de entradas | FastAPI e Pydantic |
| Acesso ao banco | SQLAlchemy (consultas parametrizadas) |
| Segurança | argon2-cffi (hash de senha), pyotp (segundo fator TOTP), cryptography (cifra em repouso) |
| Testes | pytest |
| Análise de segurança | bandit (código) e pip-audit (dependências) |
| Documentação e diagramas | Markdown e UML |

## Instruções de Execução

Pré-requisitos: Git e Python 3.12 ou superior.

```bash
git clone <url-do-repositorio>
cd SentinelTrade
cp .env.example .env    # preencha os segredos localmente; nunca versione o .env
```

Criar o banco de dados com a estrutura e os dados simulados:

```bash
python -c "import sqlite3; c = sqlite3.connect('sentineltrade.db'); [c.executescript(open(f, encoding='utf-8').read()) for f in ('database/schema.sql', 'database/seed.sql')]"
```

A aplicação e os testes estão em desenvolvimento (fase de código); os comandos para executá-los serão adicionados aqui.

## Organização das Pastas

```
SentinelTrade/
├── README.md
├── .gitignore
├── .env.example                      # só nomes de variáveis, sem segredos
├── docs/
│   ├── requisitos/
│   │   ├── requisitos.md             # visão, atores, RF, RNF e restrições
│   │   ├── regras-de-negocio.md
│   │   └── matriz-rastreabilidade.md
│   ├── uml/
│   │   └── casos-de-uso/
│   │       ├── casos-de-uso.md       # diagrama, atores e casos de uso
│   │       ├── casos-de-uso.png
│   │       └── descricoes-casos-criticos.md
│   └── evidencias/                   # prints e relatórios do andamento
├── src/                              # código-fonte (Python)
├── tests/                            # testes automatizados
├── database/
│   ├── schema.sql                    # estrutura do banco
│   └── seed.sql                      # dados iniciais simulados
└── diagrams/                         # demais diagramas UML
```

## Segurança do Repositório

Não são versionados senhas, tokens, chaves, arquivos `.env` reais nem dados pessoais. O `.env.example` traz apenas os nomes das variáveis necessárias.
