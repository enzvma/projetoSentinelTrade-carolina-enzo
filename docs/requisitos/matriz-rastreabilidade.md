# SentinelTrade: Matriz de Rastreabilidade

Liga cada requisito ao caso de uso, ao diagrama, ao controle técnico, à implementação e ao teste. Casos de uso em [casos-de-uso.md](../uml/casos-de-uso/casos-de-uso.md); regras em [regras-de-negocio.md](regras-de-negocio.md).

Os caminhos de **Implementação** são relativos a `src/sentineltrade/` e os de **Teste**, a `tests/`.

## Requisitos funcionais

| Requisito | Caso de uso | Diagrama (atual → futuro) | Controle técnico | Implementação | Teste |
|---|---|---|---|---|---|
| RF-01 Gestão de usuários e investidores | UC-03 | Casos de uso → classes | Validação de dados obrigatórios; acesso só do Administrador; auditoria | `servicos/administracao.py`, `servicos/autenticacao.py` | `test_autenticacao.py` (política de senha), `test_api.py` (perfis) |
| RF-02 Autenticação com MFA | UC-01, UC-02 | Casos de uso → sequência | Hash Argon2id, TOTP de uso único, bloqueio após 5 falhas | `servicos/autenticacao.py`, `seguranca.py` | `test_autenticacao.py` |
| RF-03 Saldo e carteira | UC-06, UC-07 | Casos de uso → classes | Acesso só do titular | `servicos/consultas.py` | `test_api.py::test_fluxo_de_ordem_pela_api`, `test_transmissao.py` |
| RF-04 Consulta de cotações | UC-08 | Casos de uso | Sinalização de cotação com mais de 5 s | `servicos/consultas.py`, `dominio/mercado.py` | `test_servico_ordens.py::test_ativo_suspenso_e_cotacao_desatualizada` |
| RF-05 Envio de ordem de compra e venda | UC-10, UC-11 | Casos de uso → atividade, sequência e estados | Validação de saldo, posição, limite e idempotência | `servicos/ordens.py`, `dominio/ordem.py` | `test_servico_ordens.py` |
| RF-06 Cancelamento | UC-13 | Casos de uso → estados | Só estados canceláveis; liberação do bloqueio | `servicos/ordens.py`, `servicos/transmissao.py` | `test_transmissao.py` (testes de cancelamento) |
| RF-07 Validação de ordem | UC-14, UC-15 | Casos de uso → atividade e sequência | Regras de negócio e de risco aplicadas antes da transmissão | `regras/` | `test_regras.py` |
| RF-08 Status da ordem | UC-20 | Casos de uso → estados | Máquina de estados sem retorno de estados finais | `dominio/ordem.py`, `servicos/eventos.py` | `test_ordem_estados.py`, `test_servico_ordens.py::test_historico_registra_cada_transicao` |
| RF-09 Notificações | UC-18 | Casos de uso → sequência | Reenvio sem duplicar; falha não desfaz a operação | `servicos/eventos.py`, `servicos/notificacoes.py`, `integracoes/notificacao.py` | `test_transmissao.py::test_corretora_fora_preserva_ordem_ativa_modo_restrito_e_recupera` |
| RF-10 Histórico | UC-21 | Casos de uso | Filtros validados; só ordens do titular | `servicos/ordens.py`, `persistencia/sqlite.py` | `test_servico_ordens.py::test_investidor_nao_ve_ordem_de_outro` |
| RF-11 Auditoria | UC-19, UC-22 | Casos de uso → classes, componentes e implantação | Log persistente, só inclusão, com hash encadeado | `servicos/auditoria.py`, `database/schema.sql` (gatilhos) | `test_auditoria.py` |
| RF-12 Integração com a corretora | UC-16, UC-17 | Casos de uso → sequência, estados e implantação | Tempo limite, retentativa controlada e consulta de estado antes de reenviar | `integracoes/corretora.py`, `servicos/transmissao.py` | `test_transmissao.py` |
| RF-13 Posição financeira | UC-16 | Casos de uso → sequência | Atualização de saldo e carteira na mesma transação | `servicos/transmissao.py`, `dominio/conta.py` | `test_transmissao.py` (execução total, parcial e venda) |
| RF-14 Recepção de cotações | UC-09 | Casos de uso | Cotação externa tratada como não confiável e validada | `integracoes/cotacoes.py`, `servicos/consultas.py` | Teste de ponta a ponta com o processador (`docs/evidencias/`) |
| RF-15 Gestão de ativos e parâmetros | UC-04 | Casos de uso | Acesso só do Administrador; auditoria | `servicos/administracao.py` | `test_api.py::test_administrador_e_auditor` |
| RF-16 Gestão de limites de risco | UC-05 | Casos de uso | Acesso do Analista de Risco e do Administrador; auditoria com valor anterior e novo | `servicos/administracao.py` | `test_servico_ordens.py::test_limite_de_risco_por_ordem` |
| RF-17 Alteração de ordem | UC-12 | Casos de uso → estados | Cancelamento do restante e nova ordem revalidada | `servicos/ordens.py`, `servicos/transmissao.py` | `test_transmissao.py::test_alterar_ordem_cancela_original_e_valida_a_nova` |

## Requisitos não funcionais

| Requisito | Caso de uso | Diagrama (atual → futuro) | Controle técnico | Implementação | Teste |
|---|---|---|---|---|---|
| RNF-01, RNF-02 Senha com hash e MFA | UC-01, UC-02 | Casos de uso → componentes e implantação | Argon2id e TOTP de uso único | `seguranca.py`, `servicos/autenticacao.py` | `test_autenticacao.py` |
| RNF-03, RNF-21 Acesso por perfil e confidencialidade | Todos | Casos de uso → componentes | Autorização verificada no servidor, negação por padrão | `api/app.py`, `servicos/comum.py` | `test_api.py` (acesso por perfil e a dados de outro investidor) |
| RNF-04, RNF-06 Encapsulamento e exceções | — | Classes | Atributos privados; erro genérico com código de rastreio | `dominio/` (atributos privados), `api/app.py`, `api/protecoes.py` | `test_api.py::test_erro_interno_nao_revela_detalhes` |
| RNF-05, RNF-07 Validação de entradas e injeção | UC-10, UC-11, UC-12 | Classes | Lista de valores permitidos e consultas parametrizadas | `api/esquemas.py`, `persistencia/sqlite.py` | `test_api.py::test_entradas_invalidas_sao_rejeitadas` |
| RNF-08, RNF-14 Duplicidade e idempotência | UC-10, UC-11, UC-16 | Sequência, estados e implantação | Chave de idempotência única por investidor | `servicos/ordens.py`, `database/schema.sql` (restrições únicas) | `test_servico_ordens.py` (mesma chave e envios simultâneos), `test_transmissao.py` (reenvio) |
| RNF-09 Segredos fora do repositório | — | — | `.gitignore`, `.env.example` só com nomes de variáveis | `.gitignore`, `.env.example`, `config.py` | gitleaks na esteira (`.github/workflows/ci.yml`) |
| RNF-10 Criptografia | Todos | Implantação | TLS e segredo do MFA cifrado no banco | `seguranca.py` (segredo do MFA cifrado) | `test_autenticacao.py::test_senha_guardada_so_como_hash` |
| RNF-11 Limite de requisições | UC-01, UC-10, UC-11 | Componentes | 5 logins e 30 ordens por minuto | `api/protecoes.py`, `servicos/autenticacao.py` | `test_api.py::test_limite_de_tentativas_de_login`, `test_autenticacao.py::test_cinco_falhas_bloqueiam_a_conta` |
| RNF-12, RNF-13 Tempo limite e retentativa | UC-16 | Sequência | 3 s e até 3 tentativas | `integracoes/corretora.py` (`CorretoraResiliente`) | `test_transmissao.py::test_corretora_fora_preserva_ordem_ativa_modo_restrito_e_recupera` |
| RNF-15, RNF-17, RNF-18 Fila, recuperação e consistência | UC-16, UC-17 | Sequência e implantação | Fila persistente e transações atômicas | `servicos/transmissao.py`, `persistencia/sqlite.py` (transações) | `test_transmissao.py`, `test_auditoria.py::test_falha_ao_gravar_auditoria_desfaz_a_operacao` |
| RNF-16 Modo restrito | UC-17 | Estados | Bloqueio de novas ordens com dependência fora | `servicos/transmissao.py`, `servicos/ordens.py` | `test_servico_ordens.py::test_modo_restrito_bloqueia_novas_ordens` |
| RNF-19 Backup | — | Implantação | Cópia diária do banco | Cópia do arquivo do banco (SQLite) | Restauração manual de uma cópia |
| RNF-20, RNF-22, RNF-25 Auditoria, integridade e rastreabilidade | UC-19, UC-22 | Classes e componentes | Log só de inclusão com hash encadeado e identificador de rastreio | `servicos/auditoria.py`, `logs.py` | `test_auditoria.py` |
| RNF-23, RNF-24, RNF-27 Disponibilidade, desempenho e observabilidade | — | Implantação | Logs estruturados e medição de tempo de resposta | `logs.py` (logs estruturados) | Teste de ponta a ponta (`docs/evidencias/`) |
| RNF-26 Manutenibilidade | — | Classes e componentes | Camadas separadas e testes das regras críticas | Estrutura em camadas de `src/sentineltrade/` | Suíte completa (`pytest`) e `bandit` |
