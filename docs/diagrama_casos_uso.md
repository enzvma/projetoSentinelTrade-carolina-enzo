SentinelTrade - Diagrama de Casos de Uso

O Modelo de Casos de Uso (MCU) representa um refinamento dos requisitos funcionais do sistema em desenvolvimento, sendo o diagrama de casos de uso a ferramenta da UML a ser utilizada. A construção desse modelo envolve a definição de diversos componentes: casos de uso, atores e rela­cionamentos entre eles.

## Identificação dos Atores

Na terminologia da UML, qualquer elemento externo ao sistema que interage com 0 mesmo é, por definição, denominado ator.

| Ator | Tipo | Descrição |
|----|----|-----------|
| **Investidor** | Ator Principal | Usuário que acessa a plataforma para consultar carteira, saldo e cotações, além de enviar, cancelar e acompanhar ordens. |
| **Administrador/Gestor** | Ator Interno | Responsável pela administração de usuários, contas, limites financeiros e acompanhamento operacional. |
| **Provedor de Cotações** | Sistema Externo | Sistema externo que fornece cotações dos ativos em tempo quase real. |
| **Bolsa/Corretora Simulada** | Sistema Externo | Sistema externo para o qual o SentinelTrade transmite as ordens e do qual recebe informações sobre execução, rejeição ou cancelamento. |
| **Serviço de Notificação** | Sistema Externo | Serviço responsável por enviar notificações ao investidor sobre execução, rejeição, cancelamento ou falha das ordens. |
| **Serviço de Autenticação/MFA** | Sistema Externo | Sistema ou serviço utilizado para autenticar o usuário por meio de múltiplos fatores de autenticação. |

## Casos de Uso

Por definição, é a especificação de uma se­quência completa de interações entre um sistema e um ou mais agentes externos a esse sistema.

## Casos de Uso

| Caso | Categoria | Ator(es) | Relacionamento | Descrição |
|---|---|---|---|---|
| **Autenticar usuário** | Segurança | Investidor, Administrador/Gestor | Inclui: MFA | Permite ao usuário acessar o SentinelTrade por meio de autenticação com múltiplos fatores. |
| **Consultar conta e carteira** | Consulta | Investidor, Administrador/Gestor | — | Consultar dados da conta, saldo, carteira, ativos e limites financeiros. |
| **Consultar cotações** | Consulta | Investidor | Inclui: Provedor de Cotações | Consultar as cotações dos ativos disponíveis para negociação, obtidas de um provedor externo. |
| **Enviar ordem** | Negociação | Investidor | Inclui: Validar ordem e transmitir ordem | Permite ao investidor enviar uma ordem de compra ou venda de ações, ETFs ou fundos imobiliários. |
| **Validar ordem** | Validação | — | Inclui: Enviar ordem | Verificar saldo, posição em carteira, limite de risco e situação do mercado antes da transmissão da ordem. |
| **Transmitir ordem** | Integração | Bolsa/Corretora Simulada | Inclui: Enviar ordem e cancelar ordem | Transmitir a ordem para a Bolsa/Corretora Simulada e receber informações sobre seu processamento. |
| **Cancelar ordem** | Negociação | Investidor | Inclui: Transmitir ordem | Permite ao investidor solicitar o cancelamento de uma ordem que ainda possa ser cancelada. |
| **Consultar ordem** | Consulta | Investidor, Administrador/Gestor | — | Consultar informações e o estado atual de uma ordem. |
| **Acompanhar ordem** | Monitoramento | Investidor, Administrador/Gestor | Inclui: Bolsa/Corretora Simulada | Acompanhar o ciclo de vida da ordem, incluindo envio, execução, rejeição, cancelamento ou falha. |
