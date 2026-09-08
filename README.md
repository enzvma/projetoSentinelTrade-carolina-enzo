# SentinelTrade
Trabalho Projeto de Software

## Integrantes
- Carolina Yamada - R.A.: 10741647
- Enzo Vasconcellos - R.A.: 10736817

## Contexto do Problema
A corretora fictícia Orion Capital opera uma plataforma digital de negociação de ações, ETFs e fundos imobiliários. Atualmente, suas operações dependem de sistemas pouco integrados, dificultando a rastreabilidade das ordens, o controle de risco e a auditoria.

A Orion Capital contratou sua equipe para especificar e modelar o SentinelTrade, uma plataforma que deverá:
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

Não é necessário integrar com uma bolsa real ou utilizar dinheiro real. O projeto deverá operar com ativos, contas e cotações simuladas.

## Requisitos Funcionais
