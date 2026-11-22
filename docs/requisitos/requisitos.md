# SentinelTrade: Requisitos do Sistema

Documentos relacionados: [regras de negócio](regras-de-negocio.md) · [matriz de rastreabilidade](matriz-rastreabilidade.md) · [casos de uso](../uml/casos-de-uso/casos-de-uso.md)

## 1. Visão do Sistema

O SentinelTrade é uma plataforma simulada de negociação de ativos financeiros (ações, ETFs e fundos imobiliários) da corretora fictícia Orion Capital. Ela permite que investidores autenticados acompanhem sua carteira, consultem cotações e realizem operações de compra e venda, respeitando saldo, posição disponível, limites de risco e regras de segurança.

O sistema deverá garantir que as ordens sejam rastreáveis, que não sejam executadas de forma duplicada e que todos os eventos relevantes sejam registrados em auditoria. Todos os ativos, contas, cotações e a bolsa são simulados.

## 2. Atores Principais

| Ator | Tipo | Responsabilidade |
|---|---|---|
| Investidor | Humano | Consulta cotações, carteira, saldo, status e histórico; envia, altera e cancela ordens. |
| Administrador | Humano | Gerencia usuários, investidores, ativos e parâmetros operacionais. |
| Analista de Risco | Humano | Consulta e ajusta limites de risco; acompanha ordens rejeitadas ou bloqueadas. |
| Auditor | Humano | Consulta a trilha de auditoria, sem poder de alteração. |
| Corretora/Bolsa Simulada | Sistema externo | Recebe ordens válidas e retorna execução, rejeição ou falha. |
| Provedor de Cotações | Sistema externo | Fornece valores atualizados (simulados) dos ativos. |
| Serviço de Notificação | Sistema externo | Informa o investidor sobre eventos relevantes. |
| Serviço de Auditoria | Sistema de apoio | Mantém o registro imutável de ações, decisões e alterações de estado. |

## 3. Requisitos Funcionais (RF)

| ID | RF | Descrição | Critério de aceitação |
|----|----|-----------|-----------------------|
| RF-01 | Cadastro e Gestão de Usuários e Investidores | Cadastrar, editar, consultar e inativar usuários, investidores e suas contas. | Cadastro só é concluído com dados obrigatórios válidos; toda alteração fica registrada em auditoria. |
| RF-02 | Autenticação com MFA | O usuário entra com e-mail e senha e confirma a identidade com um segundo fator simulado (código TOTP). | Usuário inválido é bloqueado; sem segundo fator válido não há sessão; falhas geram log de auditoria. |
| RF-03 | Consulta de Saldo e Carteira | Mostrar saldo disponível e bloqueado, e para cada ativo a quantidade, o preço médio e o valor estimado. | O investidor só vê os próprios dados; os valores batem com as execuções registradas. |
| RF-04 | Consulta de Cotações | Mostrar preço, horário da cotação e variação dos ativos disponíveis para negociação. | Cotação com mais de 5 s é marcada como desatualizada. |
| RF-05 | Envio de Ordem de Compra e Venda | Permitir que o investidor crie uma ordem de compra ou de venda (a mercado ou limitada). | Compra só é aceita com saldo e limite disponíveis; venda só é aceita com quantidade disponível do ativo; caso contrário, a ordem é rejeitada com motivo. |
| RF-06 | Cancelamento de Ordem | Permitir cancelar uma ordem que ainda não foi totalmente executada. | Ordens executadas, rejeitadas ou canceladas não podem ser canceladas; o sistema informa o estado real. |
| RF-07 | Validação de Ordem | Antes de transmitir, verificar dados da ordem, saldo, posição, limite de risco, situação do mercado e faixa de preço. | Dados inválidos, saldo insuficiente ou limite excedido impedem o envio; nenhuma ordem chega à bolsa sem validação completa. |
| RF-08 | Acompanhamento do Status da Ordem | Mostrar a etapa da ordem: criada, validada, enviada, parcialmente executada, executada, rejeitada ou cancelada. | Toda mudança de estado é registrada com data/hora e origem; o usuário vê o status atualizado. |
| RF-09 | Notificações | Avisar o investidor sobre execução, rejeição, cancelamento ou falha da ordem. | A notificação é gerada em cada um desses eventos; se o envio falhar, é reenviada sem duplicar. |
| RF-10 | Consulta de Histórico | Permitir ver as operações já realizadas, com filtro por período, ativo e status. | O histórico mostra só as ordens do investidor e bate com a auditoria. |
| RF-11 | Auditoria | Registrar, de forma imutável, quem fez o quê, quando e com qual resultado. | Cada criação, validação, rejeição, cancelamento ou execução gera log; ninguém altera ou apaga registros. |
| RF-12 | Integração com Bolsa/Corretora Simulada | Enviar as ordens validadas para a bolsa simulada e receber o retorno da execução. | Toda comunicação é registrada; resposta inesperada é tratada sem quebrar o fluxo nem alterar a carteira. |
| RF-13 | Cálculo de Posição Financeira | Atualizar automaticamente o saldo e a carteira após cada execução. | Após execução (inclusive parcial), saldo e carteira refletem exatamente o executado. |
| RF-14 | Recepção de Cotações | Receber e armazenar as cotações do provedor externo. | Cotação inválida é descartada; se o provedor cair, mantém-se a última cotação marcada como desatualizada. |
| RF-15 | Gestão de Ativos e Parâmetros | O administrador cadastra, ativa e suspende ativos e ajusta parâmetros operacionais (horário de pregão, idade máxima da cotação, faixa de preço). | Só o perfil Administrador executa a ação; as alterações ficam registradas e disponíveis para consulta. |
| RF-16 | Gestão de Limites de Risco | O analista de risco consulta e ajusta os limites de cada investidor e acompanha ordens rejeitadas. | O novo limite vale a partir da próxima ordem; a auditoria guarda o valor anterior e o novo. |
| RF-17 | Alteração de Ordem | O investidor altera a quantidade ou o preço de uma ordem ainda não executada. | A alteração cancela o restante da ordem original e cria uma nova ordem vinculada, que passa por validação completa; ordem executada não pode ser alterada. |

## 4. Requisitos Não-Funcionais (RNF)

### 4.1 Segurança

| ID | RNF | Descrição |
|----|-----|-----------|
| RNF-01 | Senha com Hash | Senhas nunca são guardadas em texto puro; usam hash Argon2id com salt individual. |
| RNF-02 | MFA no Login | O login exige um segundo fator (código TOTP) além da senha; o código expira e só vale uma vez. |
| RNF-03 | Controle de Acesso por Perfil | Cada perfil (Investidor, Administrador, Analista de Risco, Auditor) só acessa o que lhe cabe; a autorização é verificada no servidor. |
| RNF-04 | Atributos Privados / Encapsulamento | Dados sensíveis ficam encapsulados e não são expostos no código nem nas respostas do sistema. |
| RNF-05 | Validação de Entradas | Toda entrada é conferida no servidor (formato, tamanho, tipo, intervalo e caracteres permitidos) antes de ser usada. |
| RNF-06 | Tratamento Seguro de Exceções | Erros devolvem mensagem genérica e código de rastreio, sem expor detalhes internos. |
| RNF-07 | Prevenção de Injeção | Consultas ao banco são sempre parametrizadas; entradas nunca são concatenadas em comandos SQL. |
| RNF-08 | Proteção contra Reenvio/Duplicidade de Ordem | Cada ordem tem chave de idempotência; reenvios não criam nem executam uma segunda ordem. |
| RNF-09 | Ausência de Segredos no Repositório | Chaves, senhas e tokens ficam só em variáveis de ambiente; o `.env` real não é versionado. |
| RNF-10 | Criptografia em Trânsito e Repouso | Comunicação por TLS 1.2 ou superior; dados sensíveis (como o segredo do MFA) cifrados no banco. |
| RNF-11 | Rate Limiting | Limite de 5 tentativas de login e de 30 ordens por minuto por usuário. |

### 4.2 Resiliência

| ID | RNF | Descrição |
|----|-----|-----------|
| RNF-12 | Timeout de Integração | Toda chamada a serviço externo tem tempo limite de 3 segundos. |
| RNF-13 | Retentativa Controlada | Falhas temporárias são repetidas até 3 vezes, com espera crescente, antes de desistir. |
| RNF-14 | Idempotência | Repetir a mesma operação não gera efeito duplicado. |
| RNF-15 | Fila de Mensagens | Ordens aceitas entram numa fila persistente e são processadas de forma assíncrona, sem perda em picos ou falhas. |
| RNF-16 | Modo de Indisponibilidade Segura | Se a bolsa ou as cotações ficarem indisponíveis, novas ordens são bloqueadas; consultas e cancelamentos continuam. |
| RNF-17 | Recuperação de Falhas | Após uma falha, o sistema retoma o processamento em até 5 minutos, sem perder ordens. |
| RNF-18 | Consistência de Dados | Saldo, carteira e ordens sempre refletem o estado real, mesmo depois de uma falha (transações atômicas). |
| RNF-19 | Backup e Plano de Recuperação de Desastres | Backup diário do banco; perda máxima de 24 horas de dados e retorno em até 1 hora. |

### 4.3 Qualidade

| ID | RNF | Descrição |
|----|-----|-----------|
| RNF-20 | Auditabilidade | É possível reconstruir o histórico completo de qualquer ordem pela trilha de auditoria. |
| RNF-21 | Confidencialidade | Dados do investidor só são acessíveis ao próprio investidor e a perfis autorizados. |
| RNF-22 | Integridade | Os dados não podem ser alterados de forma indevida ou sem rastro; o log de auditoria só admite inclusão. |
| RNF-23 | Disponibilidade | Disponibilidade mínima de 99% durante o horário de pregão no ambiente simulado. |
| RNF-24 | Desempenho | Consultas de carteira e cotações respondem em até 1 segundo, e a validação de uma ordem em até 500 ms, no ambiente simulado. |
| RNF-25 | Rastreabilidade | Um identificador único acompanha a ordem do início ao fim (API, fila, bolsa e auditoria). |
| RNF-26 | Manutenibilidade | Código orientado a objetos, em camadas (interface, regras de negócio, persistência e integrações), com testes das regras críticas. |
| RNF-27 | Observabilidade | Logs estruturados, sem segredos, que permitem perceber falhas de integração e de processamento. |

## 5. Restrições Técnicas

| ID | Restrição |
|----|-----------|
| RT-01 | Ativos, contas, cotações e bolsa são simulados; não há dinheiro nem dados reais. |
| RT-02 | Repositório Git sem senhas, tokens, chaves de API, `.env` real ou dados pessoais. |
| RT-03 | O processamento das ordens é desacoplado por uma fila persistente consumida por um processo separado. |
| RT-04 | Integrações externas (cotações, bolsa, notificação) têm contrato definido e podem ser simuladas em testes. |
| RT-05 | Valores monetários em tipo decimal (nunca ponto flutuante) e datas em UTC. |
| RT-06 | Linguagem Python 3.12 ou superior. |
| RT-07 | Banco de dados relacional SQLite, com estrutura em `database/schema.sql` e dados iniciais em `database/seed.sql`. |
| RT-08 | Equipe de até 3 integrantes; documentação versionada na pasta `docs/`. |
