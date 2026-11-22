# SentinelTrade: Regras de Negócio

Regras aplicadas pelo sistema. Cada regra é referenciada nos [requisitos](requisitos.md), nos [casos de uso](../uml/casos-de-uso/casos-de-uso.md) e na [matriz de rastreabilidade](matriz-rastreabilidade.md).

## Mercado e ativos

| ID | Regra |
|----|-------|
| RN-01 | Ordens só são aceitas com o mercado aberto: dias úteis, das 10h às 17h55 (horário de Brasília). Dias e horário são parâmetros do Administrador (`PREGAO_DIAS`, `PREGAO_ABERTURA`, `PREGAO_FECHAMENTO`). |
| RN-02 | Só ativos cadastrados e em situação ativa podem ser negociados. |
| RN-06 | O preço de uma ordem limitada deve estar a no máximo 10% da última cotação válida. |
| RN-07 | Uma cotação é válida por até 5 segundos; sem cotação válida, novas ordens daquele ativo são bloqueadas. |

## Saldo, posição e risco

| ID | Regra |
|----|-------|
| RN-03 | Uma ordem de compra exige saldo disponível para quantidade × preço, mais taxas; esse valor fica bloqueado até a execução ou o cancelamento. |
| RN-04 | Uma ordem de venda exige posição disponível do ativo na carteira; venda a descoberto é proibida e a quantidade fica bloqueada até a execução ou o cancelamento. |
| RN-05 | Cada investidor tem limites de risco (valor máximo por ordem e exposição total); ordem acima do limite é rejeitada. |

## Ciclo de vida da ordem

| ID | Regra |
|----|-------|
| RN-09 | A ordem segue o ciclo criada → validada → enviada → parcialmente executada → executada. Uma ordem executada, rejeitada ou cancelada não pode retornar ao estado inicial nem mudar de estado. |
| RN-10 | O cancelamento é permitido antes da execução total; em ordem parcialmente executada, cancela-se só o restante. Se a bolsa executar antes de confirmar o cancelamento, vale a execução. |
| RN-11 | Se a bolsa não responder, a ordem não é reenviada às cegas: seu estado é consultado antes de qualquer nova tentativa. |
| RN-12 | Cada ordem exige uma chave de idempotência. A mesma ordem não pode ser processada ou executada duas vezes; repetir a chave devolve a ordem original. |
| RN-16 | Toda mudança de estado da ordem gera um registro de auditoria. |
| RN-18 | Uma indisponibilidade da corretora simulada não pode apagar a ordem nem alterar a carteira; saldo e posição bloqueados só são liberados depois de confirmado o estado da ordem. |
| RN-19 | Alterar uma ordem significa cancelar o restante da original e criar uma nova ordem vinculada, que passa por validação completa. Ordens executadas, rejeitadas ou canceladas não podem ser alteradas. |

## Acesso e segurança

| ID | Regra |
|----|-------|
| RN-08 | O investidor somente pode consultar e operar as suas próprias informações e ordens. |
| RN-13 | A senha tem no mínimo 12 caracteres, com letras e números; 5 falhas seguidas de login bloqueiam a conta por 15 minutos. |
| RN-17 | O acesso administrativo (usuários, ativos e parâmetros) é restrito ao perfil Administrador; a alteração de limites é restrita aos perfis Analista de Risco e Administrador. |

## Auditoria e notificações

| ID | Regra |
|----|-------|
| RN-14 | Todo evento de auditoria guarda ator, ação, data/hora, resultado e identificador de rastreio. Se o registro não puder ser gravado, a operação é cancelada. |
| RN-15 | A falha no envio de uma notificação não desfaz a operação; a mensagem é reenviada depois, sem duplicar. |
| RN-20 | O investidor é notificado na execução (total ou parcial), na rejeição, no cancelamento e na falha de suas ordens. |
