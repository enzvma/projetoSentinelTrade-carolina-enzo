# SentinelTrade
Trabalho Semestral - Projeto de Software

> **Aviso:** o SentinelTrade opera exclusivamente com dados e operações **simulados**. Não há integração com bolsa real, dinheiro real nem dados reais de investidores.

## Integrantes e Participação

| Integrante | R.A. | GitHub | Participação |
|---|---|---|---|
| Carolina Yamada | 10741647 | ychbr | Contexto e visão no README; documento de requisitos (RF e RNF) e revisões; diagrama e tabela de casos de uso; organização das pastas; matriz de rastreabilidade; dados iniciais do banco (`seed.sql`). |
| Enzo Vasconcellos | 10736817 | enzvma | Criação do repositório; `.gitignore` e `.env.example`; correções dos requisitos; regras de negócio; descrição dos casos de uso críticos; estrutura do banco (`schema.sql`); tecnologias e instruções no README. |

O detalhe de cada contribuição está no histórico de commits.

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
| Banco de dados | SQLite (relacional), estrutura em `database/schema.sql` e acesso com SQL parametrizado (`sqlite3`) |
| API e validação de entradas | FastAPI, Pydantic e Uvicorn |
| Segurança | argon2-cffi (hash de senha), pyotp (segundo fator TOTP), PyJWT (tokens), cryptography (cifra em repouso) |
| Fuso horário do pregão | tzdata |
| Testes | pytest e httpx |
| Análise de segurança | bandit (código), pip-audit (dependências) e gitleaks (segredos), na esteira do GitHub Actions |
| Documentação e diagramas | Markdown e UML |

As versões mínimas estão em `pyproject.toml`.

## Arquitetura

O código fica em `src/sentineltrade/`, separado em camadas:

| Camada | Pasta | Responsabilidade |
|---|---|---|
| Interface | `api/` | Rotas HTTP, autenticação, autorização por perfil, validação das entradas e erros sem detalhes internos |
| Regras de negócio | `dominio/`, `regras/` | Entidades (Ordem com máquina de estados, Conta, Posição, Limite, Ativo) e regras de validação, uma classe por regra |
| Casos de uso | `servicos/` | Envio, alteração e cancelamento de ordens, transmissão à corretora, autenticação, auditoria e administração |
| Persistência | `persistencia/` | Repositórios (interfaces e implementação SQLite) e transações |
| Integrações externas | `integracoes/` | Corretora, cotações e notificações simuladas, com tempo limite, retentativa e validação das respostas |

Dois processos trabalham juntos: a **API** recebe as requisições e coloca as ordens válidas numa fila no banco; o **processador** lê a fila, fala com a corretora simulada, aplica execuções e envia as notificações.

## Instruções de Execução

Pré-requisitos: Git e Python 3.12 ou superior. Os comandos abaixo são para o terminal (no Windows, PowerShell ou Git Bash), dentro da pasta do projeto.

**1. Instalar**

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows (no Linux/macOS: source .venv/bin/activate)
pip install -e ".[dev]"
```

**2. Configurar**

```bash
cp .env.example .env
sentineltrade gerar-segredos    # copie as duas linhas exibidas para dentro do .env
```

**3. Criar o banco e os usuários**

```bash
sentineltrade criar-banco
sentineltrade criar-usuario --nome "Admin Demo" --email admin@demo.com --perfil ADMINISTRADOR
sentineltrade criar-usuario --nome "Investidor Demo" --email investidor@demo.com --saldo 10000
```

A senha é pedida no terminal. O comando mostra uma URI `otpauth://` para cadastrar o segundo fator num aplicativo autenticador. No ambiente simulado, o código atual também pode ser obtido com `sentineltrade codigo-mfa --email investidor@demo.com`.

**4. Subir o sistema** (dois terminais)

```bash
sentineltrade processar         # terminal 1: cotações, fila de ordens e notificações
sentineltrade api               # terminal 2: API em http://127.0.0.1:8000
```

A documentação interativa da API fica em http://127.0.0.1:8000/docs. O fluxo é: `POST /auth/login` → `POST /auth/mfa` → usar o `access_token` (botão *Authorize*) nas demais rotas.

> Pela RN-01, ordens só são aceitas em dias úteis, das 10h às 17h55. Para demonstrar fora desse horário, o Administrador pode ajustar os parâmetros `PREGAO_DIAS` (`TODOS`), `PREGAO_ABERTURA` e `PREGAO_FECHAMENTO` em `PUT /admin/parametros/{chave}`; a alteração fica registrada na auditoria.

**5. Testes e análise de segurança**

```bash
pytest                          # testes automatizados
bandit -r src                   # análise estática de segurança
pip-audit --skip-editable       # vulnerabilidades conhecidas nas dependências
```

Os resultados mais recentes estão em `docs/evidencias/`.

## Organização das Pastas

```
SentinelTrade/
├── README.md
├── pyproject.toml                    # dependências e configuração do projeto
├── .gitignore
├── .env.example                      # só nomes de variáveis, sem segredos
├── .github/workflows/ci.yml          # esteira: testes, bandit, pip-audit e gitleaks
├── docs/
│   ├── requisitos/
│   │   ├── requisitos.md             # visão, atores, RF, RNF e restrições
│   │   ├── regras-de-negocio.md
│   │   └── matriz-rastreabilidade.md
│   ├── uml/
│   │   └── casos-de-uso/
│   │       ├── casos-de-uso.md       # diagrama, atores e casos de uso
│   │       ├── casos-de-uso.png
│   │       ├── casos-de-uso.py       # fonte editável do diagrama
│   │       └── descricoes-casos-criticos.md
│   └── evidencias/                   # resultados de testes e análises
├── src/sentineltrade/
│   ├── api/                          # interface HTTP
│   ├── dominio/                      # entidades e erros
│   ├── regras/                       # regras de validação de ordens
│   ├── servicos/                     # casos de uso
│   ├── persistencia/                 # banco de dados
│   ├── integracoes/                  # corretora, cotações e notificação simuladas
│   └── cli.py                        # linha de comando
├── tests/                            # testes automatizados (pytest)
├── database/
│   ├── schema.sql                    # estrutura do banco
│   └── seed.sql                      # dados iniciais simulados
└── diagrams/                         # demais diagramas UML
```

## Segurança do Repositório

Não são versionados senhas, tokens, chaves, arquivos `.env` reais nem dados pessoais. O `.env.example` traz apenas os nomes das variáveis necessárias.
