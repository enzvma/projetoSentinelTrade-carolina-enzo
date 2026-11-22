# SentinelTrade: Matriz de Rastreabilidade

Liga cada requisito ao caso de uso, ao diagrama, ao controle técnico, à implementação e ao teste. Casos de uso em [casos-de-uso.md](../uml/casos-de-uso/casos-de-uso.md); regras em [regras-de-negocio.md](regras-de-negocio.md).

As colunas **Implementação** e **Teste** indicam o módulo e o teste **planejados**; serão atualizadas com os caminhos reais durante a fase de código.

## Requisitos funcionais

| Requisito | Caso de uso | Diagrama (atual → futuro) | Controle técnico | Implementação | Teste |
|---|---|---|---|---|---|
| RF-01 Gestão de usuários e investidores | UC-03 | Casos de uso → classes | Validação de dados obrigatórios; acesso só do Administrador; auditoria | Serviço de cadastro | Cadastro válido, dados inválidos e acesso negado |
| RF-02 Autenticação com MFA | UC-01, UC-02 | Casos de uso → sequência | Hash Argon2id, TOTP de uso único, bloqueio após 5 falhas | Serviço de autenticação | Login válido, senha errada, código errado e bloqueio |
| RF-03 Saldo e carteira | UC-06, UC-07 | Casos de uso → classes | Acesso só do titular | Serviço de carteira | Consulta própria e tentativa de ver dados de outro |
| RF-04 Consulta de cotações | UC-08 | Casos de uso | Sinalização de cotação com mais de 5 s | Serviço de cotações | Cotação atual e desatualizada |
| RF-05 Envio de ordem de compra e venda | UC-10, UC-11 | Casos de uso → atividade, sequência e estados | Validação de saldo, posição, limite e idempotência | Serviço de ordens e domínio da ordem | Compra e venda aceitas, rejeitadas e reenvio com a mesma chave |
| RF-06 Cancelamento | UC-13 | Casos de uso → estados | Só estados canceláveis; liberação do bloqueio | Serviço de ordens | Cancelamento por estado e de ordem parcial |
| RF-07 Validação de ordem | UC-14, UC-15 | Casos de uso → atividade e sequência | Regras de negócio e de risco aplicadas antes da transmissão | Validador de ordens (uma regra por classe) | Rejeição por saldo, posição, limite, mercado, preço e cotação |
| RF-08 Status da ordem | UC-20 | Casos de uso → estados | Máquina de estados sem retorno de estados finais | Domínio da ordem | Transições válidas e inválidas |
| RF-09 Notificações | UC-18 | Casos de uso → sequência | Reenvio sem duplicar; falha não desfaz a operação | Serviço de notificação | Notificação gerada e reenvio após falha |
| RF-10 Histórico | UC-21 | Casos de uso | Filtros validados; só ordens do titular | Repositório de ordens | Filtros e acesso a ordens de outro investidor |
| RF-11 Auditoria | UC-19, UC-22 | Casos de uso → classes, componentes e implantação | Log persistente, só inclusão, com hash encadeado | Serviço e repositório de auditoria | Registro de eventos, tentativa de alteração e adulteração |
| RF-12 Integração com a corretora | UC-16, UC-17 | Casos de uso → sequência, estados e implantação | Tempo limite, retentativa controlada e consulta de estado antes de reenviar | Adaptador da corretora simulada | Sucesso, demora, falha e rejeição |
| RF-13 Posição financeira | UC-16 | Casos de uso → sequência | Atualização de saldo e carteira na mesma transação | Serviço de carteira | Saldo após execução total e parcial |
| RF-14 Recepção de cotações | UC-09 | Casos de uso | Cotação externa tratada como não confiável e validada | Adaptador do provedor de cotações | Cotação inválida e provedor indisponível |
| RF-15 Gestão de ativos e parâmetros | UC-04 | Casos de uso | Acesso só do Administrador; auditoria | Serviço de administração | Alteração por Administrador e negada a outros perfis |
| RF-16 Gestão de limites de risco | UC-05 | Casos de uso | Acesso do Analista de Risco e do Administrador; auditoria com valor anterior e novo | Serviço de risco | Ajuste de limite e efeito na próxima ordem |
| RF-17 Alteração de ordem | UC-12 | Casos de uso → estados | Cancelamento do restante e nova ordem revalidada | Serviço de ordens | Alteração de ordem aberta e negada para ordem executada |

## Requisitos não funcionais

| Requisito | Caso de uso | Diagrama (atual → futuro) | Controle técnico | Implementação | Teste |
|---|---|---|---|---|---|
| RNF-01, RNF-02 Senha com hash e MFA | UC-01, UC-02 | Casos de uso → componentes e implantação | Argon2id e TOTP de uso único | Serviço de autenticação | Hash não reversível e código reutilizado |
| RNF-03, RNF-21 Acesso por perfil e confidencialidade | Todos | Casos de uso → componentes | Autorização verificada no servidor, negação por padrão | Camada de interface | Acesso de cada perfil às ações permitidas e negadas |
| RNF-04, RNF-06 Encapsulamento e exceções | — | Classes | Atributos privados; erro genérico com código de rastreio | Domínio e camada de interface | Resposta de erro sem detalhes internos |
| RNF-05, RNF-07 Validação de entradas e injeção | UC-10, UC-11, UC-12 | Classes | Lista de valores permitidos e consultas parametrizadas | Validação de entrada e repositórios | Entradas maliciosas e tentativa de SQL Injection |
| RNF-08, RNF-14 Duplicidade e idempotência | UC-10, UC-11, UC-16 | Sequência, estados e implantação | Chave de idempotência única por investidor | Serviço de ordens e banco (restrição única) | Mesma chave enviada várias vezes |
| RNF-09 Segredos fora do repositório | — | — | `.gitignore`, `.env.example` só com nomes de variáveis | Configuração | Varredura com gitleaks |
| RNF-10 Criptografia | Todos | Implantação | TLS e segredo do MFA cifrado no banco | Configuração e serviço de autenticação | Segredo gravado cifrado |
| RNF-11 Limite de requisições | UC-01, UC-10, UC-11 | Componentes | 5 logins e 30 ordens por minuto | Camada de interface | Excesso de tentativas |
| RNF-12, RNF-13 Tempo limite e retentativa | UC-16 | Sequência | 3 s e até 3 tentativas | Adaptador da corretora simulada | Corretora lenta e com falha |
| RNF-15, RNF-17, RNF-18 Fila, recuperação e consistência | UC-16, UC-17 | Sequência e implantação | Fila persistente e transações atômicas | Fila de ordens e serviço de transmissão | Interrupção no meio do processamento |
| RNF-16 Modo restrito | UC-17 | Estados | Bloqueio de novas ordens com dependência fora | Serviço de transmissão | Corretora e cotações indisponíveis |
| RNF-19 Backup | — | Implantação | Cópia diária do banco | Rotina de backup | Restauração de uma cópia |
| RNF-20, RNF-22, RNF-25 Auditoria, integridade e rastreabilidade | UC-19, UC-22 | Classes e componentes | Log só de inclusão com hash encadeado e identificador de rastreio | Serviço de auditoria | Reconstrução da trilha e detecção de adulteração |
| RNF-23, RNF-24, RNF-27 Disponibilidade, desempenho e observabilidade | — | Implantação | Logs estruturados e medição de tempo de resposta | Configuração de logs | Medição do tempo das consultas e da validação |
| RNF-26 Manutenibilidade | — | Classes e componentes | Camadas separadas e testes das regras críticas | Estrutura de `src/` e `tests/` | Execução da suíte de testes |
