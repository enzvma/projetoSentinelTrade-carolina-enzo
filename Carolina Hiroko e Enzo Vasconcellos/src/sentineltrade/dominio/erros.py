"""Hierarquia de erros do domínio.

Cada erro tem um `codigo` estável e uma `mensagem_publica` segura para o usuário;
detalhes internos nunca são devolvidos pela API (RNF-06).
"""
from __future__ import annotations


class ErroSentinel(Exception):
    codigo = "ERRO"
    mensagem_publica = "Não foi possível concluir a operação."

    def __init__(self, mensagem_publica: str | None = None) -> None:
        if mensagem_publica:
            self.mensagem_publica = mensagem_publica
        super().__init__(self.mensagem_publica)


class DadosInvalidos(ErroSentinel):
    codigo = "DADOS_INVALIDOS"
    mensagem_publica = "Dados inválidos."


class NaoEncontrado(ErroSentinel):
    codigo = "NAO_ENCONTRADO"
    mensagem_publica = "Recurso não encontrado."


class AcessoNegado(ErroSentinel):
    codigo = "ACESSO_NEGADO"
    mensagem_publica = "Acesso negado."


class CredenciaisInvalidas(ErroSentinel):
    codigo = "CREDENCIAIS_INVALIDAS"
    mensagem_publica = "Credenciais inválidas ou conta bloqueada."


class ConflitoIdempotencia(ErroSentinel):
    codigo = "CHAVE_REUTILIZADA"
    mensagem_publica = "A chave de idempotência já foi usada para uma ordem diferente."


class TransicaoInvalida(ErroSentinel):
    codigo = "TRANSICAO_INVALIDA"
    mensagem_publica = "A ordem não pode passar para esse estado."


class OperacaoNaoPermitida(ErroSentinel):
    codigo = "OPERACAO_NAO_PERMITIDA"
    mensagem_publica = "Operação não permitida no estado atual."


class RegraViolada(ErroSentinel):
    """Violação de regra de negócio na validação de uma ordem."""
    codigo = "REGRA_VIOLADA"

    def __init__(self, motivo) -> None:  # motivo: MotivoRejeicao
        self.motivo = motivo
        super().__init__(f"Ordem rejeitada: {motivo.value}.")


class ServicoIndisponivel(ErroSentinel):
    codigo = "SERVICO_INDISPONIVEL"
    mensagem_publica = "Envio de novas ordens temporariamente indisponível. Consultas e cancelamentos continuam ativos."


class LimiteRequisicoes(ErroSentinel):
    codigo = "LIMITE_REQUISICOES"
    mensagem_publica = "Muitas requisições. Tente novamente em instantes."


class FalhaIntegracao(ErroSentinel):
    """Falha ao falar com um sistema externo (tempo esgotado, conexão ou resposta malformada)."""
    codigo = "FALHA_INTEGRACAO"
    mensagem_publica = "Serviço externo indisponível."
