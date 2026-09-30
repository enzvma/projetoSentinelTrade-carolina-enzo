# SentinelTrade — Requisitos do Sistema

## 1. Atores

| Ator | Tipo | Papel |
|---|---|---|
| Investidor | Humano | Consulta cotações e carteira, envia e cancela ordens, acompanha status e histórico |
| Administrador/Gestor | Humano | Administra usuários, contas e limites financeiros |
| Auditor | Humano | Consulta a trilha de auditoria (somente leitura) |
| Provedor de Cotações | Sistema externo | Envia cotações em tempo quase real |
| Bolsa/Corretora Simulada | Sistema externo | Recebe ordens e devolve execução, rejeição e cancelamento |
| Serviço de Notificação | Sistema externo | Entrega as notificações ao investidor |
| Serviço de Autenticação/MFA | Sistema externo | Valida o segundo fator de autenticação |

## 2. Requisitos Funcionais (RF)

Definem as funcionalidades específicas que o sistema deve realizar.

| ID | RF | Descrição | Critério de aceitação |
|----|----|-----------|-----------------------|
| RF-01 | Cadastro e Gestão de Investidores | Cadastrar, editar e consultar os dados dos investidores (perfil, conta, documentos), dos ativos e dos limites financeiros. | Cadastro só é concluído com dados obrigatórios válidos; toda alteração fica registrada. |
| RF-02 | Autenticação com MFA | O investidor entra com login e senha e confirma a identidade com um segundo fator (MFA). | Sem MFA válido não há sessão; falha gera log de auditoria. |
| RF-03 | Consulta de Carteira | Mostrar quais ativos o investidor tem e qual a posição atual de cada um. | O investidor só vê a própria carteira, com valores atualizados. |
| RF-04 | Consulta de Cotações | Mostrar o preço atualizado dos ativos disponíveis para negociação. | Cotação com mais de 5 s é marcada como desatualizada. |
| RF-05 | Envio de Ordem de Compra e Venda | Permitir que o investidor crie uma ordem para comprar ou vender um ativo. | Ordem só é aceita após a validação do RF-07; caso contrário é rejeitada com motivo. |
| RF-06 | Cancelamento de Ordem | Permitir cancelar uma ordem que ainda não foi executada. | Só cancela ordem em estado cancelável; se já executada, informa o estado real. |
| RF-07 | Validação de Saldo, Posição, Limites e Mercado | Antes de enviar a ordem, checar se o investidor tem saldo, ativos suficientes, está dentro do limite de risco e se o mercado está aberto. | Nenhuma ordem chega à bolsa sem validação completa. |
| RF-08 | Acompanhamento do Status da Ordem | Mostrar em que etapa a ordem está: criada, validada, enviada, executada, parcialmente executada, rejeitada ou cancelada. | Toda mudança de estado é registrada com data/hora e origem. |
| RF-09 | Notificações | Avisar o investidor quando algo relevante acontece com a ordem (execução, rejeição, cancelamento, falha). | Se o envio falhar, a notificação é reenviada sem duplicar. |
| RF-10 | Consulta de Histórico | Permitir ver todas as operações já realizadas pelo investidor. | Histórico mostra só as ordens do investidor e bate com a auditoria. |
| RF-11 | Auditoria | Registrar, de forma imutável, quem fez o quê e quando, para consulta e conferência futura. | Ninguém altera ou apaga registros; cada registro traz ator, ação, data e resultado. |
| RF-12 | Integração com Bolsa/Corretora Simulada | Enviar as ordens validadas para a bolsa simulada e receber o retorno da execução. | Toda comunicação é registrada; resposta inesperada é tratada sem quebrar o fluxo. |
| RF-13 | Cálculo de Posição Financeira | Atualizar automaticamente o saldo e a carteira do investidor após cada operação. | Após execução (inclusive parcial), saldo e carteira refletem exatamente o executado. |
| RF-14 | Recepção de Cotações | Receber e armazenar as cotações do provedor externo em tempo quase real. | Cotação inválida é descartada; se o provedor cair, mantém-se a última cotação marcada como desatualizada. |

## 3. Requisitos Não-Funcionais (RNF)

Estabelecem restrições e critérios de qualidade, desempenho e segurança para o sistema.

### 3.1 Segurança

| ID | RNF | Descrição |
|----|-----|-----------|
| RNF-01 | Senha com Hash | Senhas nunca são guardadas em texto puro. Usarão um hash forte. |
| RNF-02 | MFA no Login | O login exige uma segunda etapa de verificação, além da senha. |
| RNF-03 | Controle de Acesso por Perfil | Cada tipo de usuário só acessa o que faz sentido para o seu perfil. |
| RNF-04 | Atributos Privados / Encapsulamento | Dados sensíveis ficam protegidos e não são expostos diretamente no código ou nas respostas do sistema. |
| RNF-05 | Validação de Entradas | Todo dado que entra no sistema é conferido antes de ser usado, para evitar dados inválidos ou maliciosos. |
| RNF-06 | Tratamento Seguro de Exceções | Erros são tratados sem expor detalhes internos para quem está usando o sistema. |
| RNF-07 | Prevenção de Injeção | O sistema se protege contra ataques como SQL Injection e afins. |
| RNF-08 | Proteção contra Reenvio/Duplicidade de Ordem | Evita que a mesma ordem seja enviada ou processada duas vezes por engano ou falha de rede. |
| RNF-09 | Ausência de Segredos no Repositório | Chaves, senhas e tokens de acesso não ficam expostos no código-fonte. |
| RNF-10 | Criptografia em Trânsito e Repouso | Dados sensíveis são criptografados tanto enquanto trafegam quanto enquanto armazenados. |
| RNF-11 | Rate Limiting | O sistema limita tentativas de login e envio de ordens em curto intervalo de tempo, para evitar abuso e ataques automatizados. |

### 3.2 Resiliência

| ID | RNF | Descrição |
|----|-----|-----------|
| RNF-12 | Timeout de Integração | Toda chamada a um serviço externo tem um tempo limite de espera. |
| RNF-13 | Retentativa Controlada | Se uma chamada externa falhar, o sistema tenta de novo algumas vezes, de forma controlada, antes de desistir. |
| RNF-14 | Idempotência | Repetir a mesma operação não gera efeito duplicado. |
| RNF-15 | Fila de Mensagens | Ordens e eventos são processados de forma assíncrona por fila, evitando perda de dados em picos de uso ou falhas. |
| RNF-16 | Modo de Indisponibilidade Segura | Se uma parte crítica cair, o sistema entra em modo restrito em vez de operar de forma arriscada. |
| RNF-17 | Recuperação de Falhas | O sistema volta a funcionar automaticamente após uma falha, sem perder dados. |
| RNF-18 | Consistência de Dados | Saldo, carteira e ordens sempre refletem o estado real, mesmo depois de uma falha. |
| RNF-19 | Backup e Plano de Recuperação de Desastres | Além de se recuperar de falhas pontuais, o sistema tem backup e um plano para voltar do zero em caso de perda grave. |

### 3.3 Qualidade

| ID | RNF | Descrição |
|----|-----|-----------|
| RNF-20 | Auditabilidade | É possível reconstruir o histórico completo de qualquer operação. |
| RNF-21 | Confidencialidade | Dados sensíveis só podem ser vistos por quem tem permissão para isso. |
| RNF-22 | Integridade | Os dados não podem ser alterados de forma indevida ou sem rastro. |
| RNF-23 | Disponibilidade | O sistema deve estar no ar na maior parte do tempo, principalmente durante o horário de pregão. |
| RNF-24 | Desempenho | O sistema responde rápido, mesmo com muitos usuários e ordens acontecendo ao mesmo tempo. |
| RNF-25 | Rastreabilidade | Dá para acompanhar o caminho completo de uma ordem, do início ao fim. |
| RNF-26 | Manutenibilidade | O código é organizado de um jeito que facilita manutenção e evolução no futuro. |
| RNF-27 | Observabilidade | O sistema gera logs estruturados, métricas e alertas, permitindo perceber problemas antes que virem incidente grave. |

## 4. Regras de Negócio

| ID | Regra |
|----|-------|
| RN-01 | Ordens só são aceitas com o mercado aberto (dias úteis, horário de pregão). |
| RN-02 | Só ativos cadastrados e ativos podem ser negociados. |
| RN-03 | Compra exige saldo disponível para o valor da ordem mais taxas; o valor fica bloqueado até a execução ou o cancelamento. |
| RN-04 | Venda exige quantidade disponível em carteira; venda a descoberto é proibida. |
| RN-05 | Cada investidor tem limites de risco (valor por ordem e exposição total); ordem acima do limite é rejeitada. |
| RN-06 | O preço de uma ordem limitada deve estar em até 10% da última cotação válida. |
| RN-07 | Cotação válida tem no máximo 5 segundos; sem cotação válida, novas ordens do ativo são bloqueadas. |
| RN-08 | Só o titular da conta envia, cancela ou consulta suas ordens. |
| RN-09 | A ordem segue o ciclo criada → validada → enviada → (parcialmente) executada; pode ser rejeitada ou cancelada. Estados finais não mudam. |
| RN-10 | O cancelamento é permitido antes da execução total; em ordem parcial, cancela-se só o restante. Se a bolsa executar antes de confirmar o cancelamento, vale a execução. |
| RN-11 | Se a bolsa não responder, a ordem não é reenviada às cegas: seu estado é consultado antes. |
| RN-12 | Cada ordem exige uma chave de idempotência; a mesma chave devolve a ordem original. |
| RN-13 | A senha tem no mínimo 12 caracteres; 5 falhas de login bloqueiam a conta temporariamente. |
| RN-14 | Todo evento de auditoria guarda ator, ação, data/hora, resultado e identificador de rastreio; se não puder ser gravado, a operação é cancelada. |
| RN-15 | Falha na notificação não desfaz a operação; a mensagem é reenviada depois. |

## 5. Restrições Técnicas

| ID | Restrição |
|----|-----------|
| RT-01 | Ativos, contas, cotações e bolsa são simulados; não há dinheiro nem dados reais. |
| RT-02 | Repositório Git privado, sem senhas, tokens, chaves de API ou dados sensíveis. |
| RT-03 | Arquitetura distribuída, com processamento de ordens por fila de mensagens. |
| RT-04 | Integrações externas (cotações, bolsa) por API com contrato definido, possíveis de simular em testes. |
| RT-05 | Valores monetários em tipo decimal (nunca ponto flutuante) e datas em UTC. |
| RT-06 | Equipe de até 3 integrantes; a documentação fica na pasta `docs/`. |

## 6. Matriz de Rastreabilidade

Os casos de uso (UC) estão em [diagrama_casos_uso.md](diagrama_casos_uso.md). Implementação e teste são **planejados** e serão atualizados durante o desenvolvimento.

### Requisitos Funcionais (RF)

| Requisito | Diagrama | Implementação (módulo) | Teste |
|---|---|---|---|
| RF-01 | UC-03, UC-04 | Cadastros | Teste de cadastro e validação de dados |
| RF-02 | UC-01, UC-02 | Autenticação | Teste de login com MFA e bloqueio |
| RF-03 | UC-05 | Carteira | Teste de consulta de carteira |
| RF-04 | UC-07 | Cotações | Teste de cotação atual e desatualizada |
| RF-05 | UC-08 | Ordens | Teste de envio de ordem e de reenvio duplicado |
| RF-06 | UC-11 | Ordens | Teste de cancelamento por estado |
| RF-07 | UC-09 | Validação e risco | Teste de rejeição por saldo, posição, limite e mercado |
| RF-08 | UC-12 | Ordens (máquina de estados) | Teste de transições de estado |
| RF-09 | UC-13 | Notificações | Teste de envio e reenvio |
| RF-10 | UC-12 | Ordens | Teste dos filtros do histórico |
| RF-11 | UC-15, UC-16 | Auditoria | Teste de registro e imutabilidade |
| RF-12 | UC-10, UC-14 | Integração com a bolsa | Teste com bolsa simulada (sucesso, timeout, rejeição) |
| RF-13 | UC-10 | Carteira e saldo | Teste de saldo após execução parcial e total |
| RF-14 | UC-06 | Cotações | Teste de cotação inválida e de provedor fora do ar |

### Requisitos não-funcionais

| Requisito | Diagrama | Implementação (módulo) | Teste |
|---|---|---|---|
| RNF-01, 02 | UC-01, UC-02 | Autenticação | Teste de hash e de MFA |
| RNF-03, 21 | Todos os UCs | Controle de acesso | Teste de acesso por perfil |
| RNF-04, 06 | — | Camada de API (respostas e erros) | Teste de resposta de erro e de exposição de dados |
| RNF-05, 07 | UC-08 | Validação de entrada e acesso a dados | Teste com entradas maliciosas |
| RNF-08, 14 | UC-08, UC-10 | Ordens (idempotência) | Teste de concorrência com a mesma chave |
| RNF-09 | — | `.gitignore`, `.env.example` | Varredura de segredos (ex.: gitleaks) |
| RNF-10 | Todos os UCs | Configuração de TLS e criptografia | Teste de conexão e inspeção do banco |
| RNF-11 | UC-01, UC-08 | Limite de requisições | Teste de excesso de tentativas |
| RNF-12, 13 | UC-10 | Cliente de integração | Teste com bolsa lenta e com falha |
| RNF-15, 17, 18 | UC-10, UC-14 | Fila de mensagens e transações | Teste de queda do consumidor e de consistência |
| RNF-16 | UC-14 | Modo restrito | Teste com bolsa e cotações fora do ar |
| RNF-19 | — | Rotina de backup | Simulado de restauração |
| RNF-20, 22, 25 | UC-15, UC-16 | Auditoria | Teste de reconstrução da trilha e de adulteração |
| RNF-23, 24, 27 | — | Monitoramento | Teste de carga e alerta forçado |
| RNF-26 | — | Estrutura modular | Análise estática e revisão |
