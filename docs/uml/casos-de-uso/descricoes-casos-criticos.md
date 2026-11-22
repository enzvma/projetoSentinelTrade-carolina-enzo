# SentinelTrade - Descrição dos Casos de Uso Críticos

Descrições textuais dos três casos de uso críticos do [diagrama de casos de uso](casos-de-uso.md). As regras citadas estão em [regras-de-negocio.md](../../requisitos/regras-de-negocio.md) e os requisitos em [requisitos.md](../../requisitos/requisitos.md).

Estados da ordem: Criada → Validada → Enviada → Parcialmente executada → Executada; estados finais alternativos: Rejeitada e Cancelada.

---

## UC-10 Enviar ordem de compra

**Nome:** Enviar ordem de compra

**Ator principal:** Investidor

**Objetivo:** Comprar uma quantidade de um ativo, a mercado ou a um preço limite, com a garantia de que a ordem é válida e não será duplicada.

**Pré-condições:**
- O investidor está autenticado com MFA (UC-01) e sua conta está ativa.
- Existe cotação recente do ativo no sistema.

**Fluxo principal:**
1. O investidor informa o ativo, a quantidade, o tipo (a mercado ou limitada), o preço (se limitada) e a chave de idempotência.
2. O sistema confere o formato e os limites de cada campo.
3. O sistema verifica que a chave de idempotência ainda não foi usada.
4. O sistema cria a ordem no estado **Criada** e registra a auditoria (UC-19).
5. O sistema valida a ordem (UC-14): mercado aberto, ativo negociável, cotação válida, preço dentro da faixa e limite de risco.
6. O sistema verifica o saldo (UC-15) e bloqueia o valor da ordem mais as taxas.
7. A ordem passa a **Validada**, é registrada em auditoria e entra na fila de transmissão.
8. O sistema transmite a ordem à corretora simulada (UC-16) e a ordem passa a **Enviada**.
9. A corretora devolve a execução; o sistema registra a execução, consome o saldo bloqueado, acrescenta a quantidade à carteira e recalcula o preço médio.
10. A ordem passa a **Executada**, a mudança é auditada e o investidor é notificado (UC-18).

**Fluxos alternativos:**
- **FA1 – Chave repetida:** no passo 3, se a chave já existe, o sistema devolve a ordem original e não cria outra.
- **FA2 – Dados inválidos:** no passo 2, se um campo é inválido (quantidade menor ou igual a zero, ativo com formato inválido, ordem limitada sem preço), a requisição é recusada com o motivo e nenhuma ordem é criada.
- **FA3 – Ativo indisponível:** no passo 5, se o ativo não existe, está suspenso ou não tem cotação válida, a ordem passa a **Rejeitada** com o motivo; o investidor é notificado.
- **FA4 – Mercado fechado ou preço fora da faixa:** no passo 5, a ordem passa a **Rejeitada** com o motivo.
- **FA5 – Limite excedido:** no passo 5, se o valor ultrapassa o limite de risco, a ordem passa a **Rejeitada** com o motivo "limite de risco excedido".
- **FA6 – Saldo insuficiente:** no passo 6, a ordem passa a **Rejeitada** com o motivo "saldo insuficiente"; nada é bloqueado.
- **FA7 – Execução parcial:** no passo 9, a ordem passa a **Parcialmente executada**; saldo e carteira refletem só a parte executada e o restante continua ativo.
- **FA8 – Rejeição pela corretora:** no passo 9, a ordem passa a **Rejeitada**, o saldo bloqueado é liberado e o investidor é notificado.
- **FA9 – Falha de comunicação:** no passo 8, o sistema tenta até 3 vezes, com tempo limite de 3 s. Persistindo a falha, a ordem não é apagada nem reenviada às cegas: continua registrada, o saldo segue bloqueado e o estado é consultado na corretora antes de nova tentativa. O modo restrito (UC-17) bloqueia novas ordens e o investidor é notificado da falha.

**Pós-condições:**
- Sucesso: ordem **Executada** (ou **Parcialmente executada**), execução registrada, saldo debitado, carteira atualizada, cada mudança de estado auditada e investidor notificado.
- Falha: ordem **Rejeitada** com motivo (ou não criada, no FA2), nenhum saldo bloqueado, auditoria e notificação registradas.

**Regras de negócio:** RN-01, RN-02, RN-03, RN-05, RN-06, RN-07, RN-08, RN-09, RN-11, RN-12, RN-14, RN-16, RN-18, RN-20

**Requisitos relacionados:** RF-05, RF-07, RF-08, RF-09, RF-11, RF-12, RF-13 · RNF-05, RNF-08, RNF-12, RNF-13, RNF-14, RNF-16, RNF-18

---

## UC-11 Enviar ordem de venda

**Nome:** Enviar ordem de venda

**Ator principal:** Investidor

**Objetivo:** Vender uma quantidade de um ativo da carteira, a mercado ou a um preço limite, sem vender o que não possui.

**Pré-condições:**
- O investidor está autenticado com MFA (UC-01) e sua conta está ativa.
- O investidor possui o ativo na carteira.
- Existe cotação recente do ativo no sistema.

**Fluxo principal:**
1. O investidor informa o ativo, a quantidade, o tipo (a mercado ou limitada), o preço (se limitada) e a chave de idempotência.
2. O sistema confere o formato e os limites de cada campo.
3. O sistema verifica que a chave de idempotência ainda não foi usada.
4. O sistema cria a ordem no estado **Criada** e registra a auditoria (UC-19).
5. O sistema valida a ordem (UC-14): mercado aberto, ativo negociável, cotação válida, preço dentro da faixa e limite de risco.
6. O sistema verifica a posição disponível do ativo (UC-15) e bloqueia a quantidade da ordem.
7. A ordem passa a **Validada**, é registrada em auditoria e entra na fila de transmissão.
8. O sistema transmite a ordem à corretora simulada (UC-16) e a ordem passa a **Enviada**.
9. A corretora devolve a execução; o sistema registra a execução, retira a quantidade bloqueada da carteira e credita o valor da venda, descontadas as taxas, no saldo disponível.
10. A ordem passa a **Executada**, a mudança é auditada e o investidor é notificado (UC-18).

**Fluxos alternativos:**
- **FA1 – Chave repetida:** no passo 3, o sistema devolve a ordem original e não cria outra.
- **FA2 – Dados inválidos:** no passo 2, a requisição é recusada com o motivo e nenhuma ordem é criada.
- **FA3 – Ativo indisponível:** no passo 5, se o ativo está suspenso ou sem cotação válida, a ordem passa a **Rejeitada** com o motivo.
- **FA4 – Mercado fechado ou preço fora da faixa:** no passo 5, a ordem passa a **Rejeitada** com o motivo.
- **FA5 – Limite excedido:** no passo 5, a ordem passa a **Rejeitada** com o motivo "limite de risco excedido".
- **FA6 – Posição insuficiente:** no passo 6, se a quantidade disponível é menor que a da ordem, a ordem passa a **Rejeitada** com o motivo "posição insuficiente"; venda a descoberto não é permitida.
- **FA7 – Execução parcial:** no passo 9, a ordem passa a **Parcialmente executada**; carteira e saldo refletem só a parte vendida.
- **FA8 – Rejeição pela corretora:** no passo 9, a ordem passa a **Rejeitada**, a quantidade bloqueada volta a ficar disponível e o investidor é notificado.
- **FA9 – Falha de comunicação:** igual ao FA9 de UC-10: a ordem continua registrada, a quantidade segue bloqueada, o estado é consultado antes de nova tentativa e o modo restrito (UC-17) é ativado.

**Pós-condições:**
- Sucesso: ordem **Executada** (ou **Parcialmente executada**), execução registrada, quantidade retirada da carteira, saldo creditado, cada mudança de estado auditada e investidor notificado.
- Falha: ordem **Rejeitada** com motivo (ou não criada, no FA2), carteira inalterada, auditoria e notificação registradas.

**Regras de negócio:** RN-01, RN-02, RN-04, RN-05, RN-06, RN-07, RN-08, RN-09, RN-11, RN-12, RN-14, RN-16, RN-18, RN-20

**Requisitos relacionados:** RF-05, RF-07, RF-08, RF-09, RF-11, RF-12, RF-13 · RNF-05, RNF-08, RNF-12, RNF-13, RNF-14, RNF-16, RNF-18

---

## UC-13 Cancelar ordem

**Nome:** Cancelar ordem

**Ator principal:** Investidor

**Objetivo:** Cancelar uma ordem que ainda não foi totalmente executada e recuperar o saldo ou a posição bloqueados.

**Pré-condições:**
- O investidor está autenticado com MFA (UC-01).
- A ordem pertence ao investidor e está em estado cancelável: **Criada**, **Validada**, **Enviada** ou **Parcialmente executada**.

**Fluxo principal:**
1. O investidor escolhe a ordem e solicita o cancelamento.
2. O sistema confere que a ordem pertence ao investidor e que está em estado cancelável.
3. Se a ordem ainda não foi enviada, o sistema a cancela diretamente; se já foi enviada, transmite o pedido de cancelamento à corretora (UC-16).
4. A corretora confirma o cancelamento.
5. O sistema libera o saldo (compra) ou a quantidade (venda) bloqueados da parte não executada.
6. A ordem passa a **Cancelada**, a mudança é auditada (UC-19) e o investidor é notificado (UC-18).

**Fluxos alternativos:**
- **FA1 – Ordem em estado final:** no passo 2, se a ordem está **Executada**, **Rejeitada** ou **Cancelada**, o cancelamento é negado e o sistema informa o estado real.
- **FA2 – Ordem de outro investidor:** no passo 2, o sistema responde como se a ordem não existisse, sem revelar dados de terceiros, e registra a tentativa em auditoria.
- **FA3 – Ordem parcialmente executada:** no passo 5, só o restante é cancelado; as execuções já feitas permanecem.
- **FA4 – Execução antes da confirmação:** no passo 4, se a corretora executou a ordem antes de confirmar o cancelamento, vale a execução: a ordem fica **Executada** e o investidor é notificado.
- **FA5 – Falha de comunicação:** no passo 3, o pedido de cancelamento fica registrado e é transmitido quando a corretora voltar; o saldo ou a posição continuam bloqueados até a confirmação.

**Pós-condições:**
- Sucesso: ordem **Cancelada** (só o restante, se parcial), saldo ou posição da parte não executada liberados, auditoria e notificação registradas.
- Exceção: ordem inalterada e motivo informado (FA1, FA2) ou ordem **Executada** (FA4).

**Regras de negócio:** RN-08, RN-09, RN-10, RN-11, RN-14, RN-15, RN-16, RN-18, RN-20

**Requisitos relacionados:** RF-06, RF-08, RF-09, RF-11, RF-12 · RNF-03, RNF-14, RNF-18, RNF-21
