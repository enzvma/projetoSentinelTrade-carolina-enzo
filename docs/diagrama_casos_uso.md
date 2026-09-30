SentinelTrade - Diagrama de Casos de Uso

O Modelo de Casos de Uso (MCU) representa um refinamento dos requisitos funcionais do sistema em desenvolvimento, sendo o diagrama de casos de uso a ferramenta da UML a ser utilizada. A construção desse modelo envolve a definição de diversos componentes: casos de uso, atores e rela­cionamentos entre eles.

## Identificação dos Atores

Na terminologia da UML, qualquer elemento externo ao sistema que interage com o mesmo é, por definição, denominado ator.

| Ator | Tipo | Descrição |
|----|----|-----------|
| **Investidor** | Ator Principal | Usuário que acessa a plataforma para consultar carteira, saldo e cotações, além de enviar, cancelar e acompanhar ordens. |
| **Administrador/Gestor** | Ator Interno | Responsável pela administração de usuários, contas, limites financeiros e acompanhamento operacional. |
| **Auditor** | Ator Interno | Consulta a trilha de auditoria, sem poder de alteração sobre os registros. |
| **Provedor de Cotações** | Sistema Externo | Sistema externo que fornece cotações dos ativos em tempo quase real. |
| **Bolsa/Corretora Simulada** | Sistema Externo | Sistema externo para o qual o SentinelTrade transmite as ordens e do qual recebe informações sobre execução, rejeição ou cancelamento. |
| **Serviço de Notificação** | Sistema Externo | Serviço responsável por enviar notificações ao investidor sobre execução, rejeição, cancelamento ou falha das ordens. |
| **Serviço de Autenticação/MFA** | Sistema Externo | Sistema ou serviço utilizado para autenticar o usuário por meio de múltiplos fatores de autenticação. |

## Casos de Uso

Por definição, é a especificação de uma sequência completa de interações entre um sistema e um ou mais agentes externos a esse sistema.

Relacionamentos `<<include>>` e `<<extend>>` ligam apenas casos de uso entre si; a ligação com os atores é uma associação simples.

| ID | Caso | Categoria | Ator(es) | Relacionamento | Descrição |
|---|---|---|---|---|---|
| UC-01 | **Autenticar usuário** | Segurança | Investidor, Administrador/Gestor, Auditor | Inclui: UC-02 | Permite ao usuário acessar o SentinelTrade por meio de autenticação com múltiplos fatores. |
| UC-02 | **Validar segundo fator** | Segurança | Serviço de Autenticação/MFA | Incluído por: UC-01 | Confirma o segundo fator de autenticação do usuário. |
| UC-03 | **Cadastrar investidor** | Cadastro | Administrador/Gestor | Inclui: UC-15 | Cadastra um novo investidor e sua conta na plataforma. |
| UC-04 | **Gerir contas e limites financeiros** | Cadastro | Administrador/Gestor | Inclui: UC-15 | Mantém contas, saldo e limites financeiros e de risco dos investidores. |
| UC-05 | **Consultar conta e carteira** | Consulta | Investidor, Administrador/Gestor | — | Consultar dados da conta, saldo, carteira, ativos e limites financeiros. |
| UC-06 | **Receber cotações** | Cotações | Provedor de Cotações | — | Recebe e armazena as cotações dos ativos em tempo quase real. |
| UC-07 | **Consultar cotações** | Consulta | Investidor | — | Consultar as cotações dos ativos disponíveis para negociação, obtidas de um provedor externo. |
| UC-08 | **Enviar ordem** | Negociação | Investidor | Inclui: UC-09, UC-10, UC-13, UC-15 | Permite ao investidor enviar uma ordem de compra ou venda de ações, ETFs ou fundos imobiliários. |
| UC-09 | **Validar ordem** | Validação | — | Incluído por: UC-08 | Verificar saldo, posição em carteira, limite de risco e situação do mercado antes da transmissão da ordem. |
| UC-10 | **Transmitir ordem** | Integração | Bolsa/Corretora Simulada | Incluído por: UC-08, UC-11 · Estendido por: UC-14 | Transmitir a ordem (ou o cancelamento) para a Bolsa/Corretora Simulada e receber informações sobre seu processamento. |
| UC-11 | **Cancelar ordem** | Negociação | Investidor | Inclui: UC-10, UC-13, UC-15 | Permite ao investidor solicitar o cancelamento de uma ordem que ainda possa ser cancelada. |
| UC-12 | **Acompanhar ordem e histórico** | Monitoramento | Investidor, Administrador/Gestor | — | Acompanhar o estado e o ciclo de vida da ordem (envio, execução, rejeição, cancelamento ou falha) e consultar o histórico de operações. |
| UC-13 | **Notificar investidor** | Notificação | Serviço de Notificação | Incluído por: UC-08, UC-11 | Notifica o investidor sobre execução, rejeição, cancelamento ou falha da ordem. |
| UC-14 | **Ativar modo restrito** | Resiliência | — | Estende: UC-10 | Ao detectar indisponibilidade de um componente crítico, bloqueia novas ordens e mantém consultas e cancelamentos. |
| UC-15 | **Registrar log de auditoria** | Auditoria | — | Incluído por: UC-03, UC-04, UC-08, UC-11 (e demais ações críticas) | Registro imutável das ações críticas do sistema. |
| UC-16 | **Consultar trilha de auditoria** | Auditoria | Auditor | — | Consulta o histórico de auditoria, sem poder de alteração. |
