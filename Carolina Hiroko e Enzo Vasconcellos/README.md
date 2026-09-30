# SentinelTrade
Trabalho Semestral - Projeto de Software

## Integrantes
- Carolina Yamada - R.A.: 10741647
- Enzo Vasconcellos - R.A.: 10736817

## Contexto do Problema

A corretora fictícia Orion Capital opera uma plataforma digital de negociação de ações, ETFs e fundos imobiliários. Atualmente, suas operações dependem de sistemas pouco integrados, dificultando a rastreabilidade das ordens, o controle de risco e a auditoria.

## Requisitos do Sistema

A Orion Capital contratou a nossa equipe para especificar e modelar o SentinelTrade, uma plataforma que deverá:

- Autenticar usuários com MFA;
- Manter dados de investidores, contas, carteiras, ativos e limites financeiros;
- Receber cotações em tempo quase real por meio de um provedor externo;
- Permitir ordens de compra, venda, cancelamento e consulta;
- Validar saldo, posição em carteira, limite de risco e situação do mercado antes de transmitir a ordem;
- Integrar-se a uma Bolsa/Corretora simulada;
- Acompanhar o ciclo de vida das ordens;
- Registrar logs de auditoria imutáveis;
- Notificar o investidor sobre execução, rejeição, cancelamento ou falha;
- Operar com mecanismos de recuperação, indisponibilidade controlada e prevenção de duplicidade de ordens.

Observação: Não é necessário integrar com uma bolsa real ou utilizar dinheiro real. O projeto deverá operar com ativos, contas e cotações simuladas.

## Visão do Projeto

O **SentinelTrade** é uma plataforma distribuída, segura e tolerante a falhas para negociação de **ações, ETFs e FIIs**, encomendada pela corretora fictícia **Orion Capital**. Ela substitui sistemas pouco integrados por um fluxo único e auditável:

`cotação → validação (saldo, posição, risco, mercado) → ordem → bolsa simulada → execução → posição → notificação → auditoria`

Principais objetivos: **nenhuma ordem duplicada, nenhuma ordem aceita perdida, nenhuma operação sem rastro auditável**.

### Escopo
Dentro: autenticação com MFA, cadastro de investidores, ativos e limites, cotações, ordens (compra, venda, cancelamento), validações, integração com bolsa simulada, ciclo de vida da ordem, carteira/saldo, histórico, notificações, auditoria imutável.

Fora: bolsa real, dinheiro real, liquidação/custódia real, derivativos e renda fixa, análise gráfica/recomendação de investimentos.

## Tecnologias

Ainda serão decididas.

## Instruções de execução

Não há código para rodar.
