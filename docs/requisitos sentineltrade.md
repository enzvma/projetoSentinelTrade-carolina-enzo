# SentinelTrade — Requisitos do Sistema

## 1. Requisitos Funcionais (RF)

| ID | RF | Descrição |
|----|----|-----------|
| RF-01 | Cadastro e Gestão de Investidores | Cadastrar, editar e consultar os dados dos investidores (perfil, conta, documentos). |
| RF-02 | Autenticação com MFA | O investidor entra com login e senha e confirma a identidade com um segundo fator (MFA). |
| RF-03 | Consulta de Carteira | Mostrar quais ativos o investidor tem e qual a posição atual de cada um. |
| RF-04 | Consulta de Cotações | Mostrar o preço atualizado dos ativos disponíveis para negociação. |
| RF-05 | Envio de Ordem de Compra e Venda | Permitir que o investidor crie uma ordem para comprar ou vender um ativo. |
| RF-06 | Cancelamento de Ordem | Permitir cancelar uma ordem que ainda não foi executada. |
| RF-07 | Validação de Saldo, Posição e Limites | Antes de enviar a ordem, checar se o investidor tem saldo, ativos suficientes e está dentro do limite de risco. |
| RF-08 | Acompanhamento do Status da Ordem | Mostrar em que etapa a ordem está: criada, enviada, executada, parcialmente executada, rejeitada ou cancelada. |
| RF-09 | Notificações | Avisar o investidor quando algo relevante acontece com a ordem (execução, rejeição, cancelamento, falha). |
| RF-10 | Consulta de Histórico | Permitir ver todas as operações já realizadas pelo investidor. |
| RF-11 | Auditoria | Registrar quem fez o quê e quando, para consulta e conferência futura. |
| RF-12 | Integração com Bolsa/Corretora Simulada | Enviar as ordens validadas para a bolsa simulada e receber o retorno da execução. |
| RF-13 | Cálculo de Posição Financeira | Atualizar automaticamente o saldo e a carteira do investidor após cada operação. |

## 2. Requisitos Não-Funcionais (RNF)

### 2.1 Segurança

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

### 2.2 Resiliência

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

### 2.3 Qualidade

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
