"""Administração: usuários, ativos, parâmetros, saldo simulado e limites de risco (UC-03 a UC-05, RF-15, RF-16)."""
from __future__ import annotations

from decimal import Decimal

from ..dominio.conta import LimiteRisco
from ..dominio.dinheiro import Dinheiro
from ..dominio.enums import Perfil, TipoAtivo
from ..dominio.erros import DadosInvalidos, NaoEncontrado
from ..dominio.mercado import Ativo, Cotacao, ParametrosOperacionais
from ..relogio import Relogio
from .auditoria import ServicoAuditoria
from .autenticacao import ServicoAutenticacao
from .comum import ator_de, exigir_perfil

LIMITE_ORDEM_PADRAO = Dinheiro.de_decimal("50000.00")
EXPOSICAO_PADRAO = Dinheiro.de_decimal("200000.00")


class ServicoAdministracao:
    def __init__(self, fabrica_uow, relogio: Relogio, auditoria: ServicoAuditoria,
                 autenticacao: ServicoAutenticacao) -> None:
        self._uow = fabrica_uow
        self._relogio = relogio
        self._auditoria = auditoria
        self._autenticacao = autenticacao

    # ---- usuários e contas (UC-03) ----------------------------------------------------------
    def criar_usuario(self, admin, *, nome: str, email: str, senha: str, perfil: Perfil,
                      saldo_inicial: Decimal = Decimal("0")) -> tuple[int, str]:
        """Cria o usuário (e, se investidor, a conta com limites padrão). Devolve o id e a URI do MFA."""
        if admin is not None:
            exigir_perfil(admin, Perfil.ADMINISTRADOR)
        agora = self._relogio.agora()
        with self._uow() as uow:
            usuario, uri = self._autenticacao.novo_usuario(uow, nome=nome, email=email, senha=senha, perfil=perfil)
            if perfil is Perfil.INVESTIDOR:
                conta = uow.contas.inserir(usuario.id, agora)
                uow.contas.salvar_limite(LimiteRisco(conta_id=conta.id, valor_maximo_ordem=LIMITE_ORDEM_PADRAO,
                                                     exposicao_maxima=EXPOSICAO_PADRAO), None, agora)
                saldo = Dinheiro.de_decimal(saldo_inicial)
                if saldo.centavos > 0:
                    conta.creditar(saldo)
                    uow.contas.atualizar_saldos(conta)
            self._auditoria.registrar(uow, ator=ator_de(admin) if admin else "linha-de-comando", acao="USUARIO_CRIADO",
                                      entidade="usuario", entidade_id=usuario.id, resultado="SUCESSO",
                                      detalhes={"perfil": perfil.value})
            uow.confirmar()
        return usuario.id, uri

    def definir_situacao_usuario(self, admin, usuario_id: int, ativo: bool) -> None:
        exigir_perfil(admin, Perfil.ADMINISTRADOR)
        with self._uow() as uow:
            usuario = uow.usuarios.buscar_por_id(usuario_id)
            if usuario is None:
                raise NaoEncontrado("Usuário não encontrado.")
            usuario.definir_ativo(ativo)
            uow.usuarios.atualizar_seguranca(usuario)
            self._auditoria.registrar(uow, ator=ator_de(admin), acao="USUARIO_SITUACAO", entidade="usuario",
                                      entidade_id=usuario_id, resultado="SUCESSO", detalhes={"ativo": ativo})
            uow.confirmar()

    def creditar_saldo(self, admin, conta_id: int, valor: Decimal) -> None:
        """Crédito simulado (não há dinheiro real)."""
        exigir_perfil(admin, Perfil.ADMINISTRADOR)
        quantia = Dinheiro.de_decimal(valor)
        if quantia.centavos <= 0:
            raise DadosInvalidos("O valor deve ser positivo.")
        with self._uow() as uow:
            conta = uow.contas.buscar(conta_id)
            if conta is None:
                raise NaoEncontrado("Conta não encontrada.")
            conta.creditar(quantia)
            uow.contas.atualizar_saldos(conta)
            self._auditoria.registrar(uow, ator=ator_de(admin), acao="SALDO_CREDITADO", entidade="conta",
                                      entidade_id=conta_id, resultado="SUCESSO", detalhes={"valor": str(quantia)})
            uow.confirmar()

    # ---- ativos e parâmetros (UC-04, RF-15) --------------------------------------------------
    def criar_ativo(self, admin, *, ticker: str, nome: str, tipo: TipoAtivo, preco_referencia: Decimal) -> int:
        exigir_perfil(admin, Perfil.ADMINISTRADOR)
        agora = self._relogio.agora()
        with self._uow() as uow:
            if uow.ativos.buscar_por_ticker(ticker) is not None:
                raise DadosInvalidos("Ativo já cadastrado.")
            ativo = Ativo(id=None, ticker=ticker, nome=nome, tipo=tipo)
            ativo_id = uow.ativos.inserir(ativo)
            uow.ativos.inserir_cotacao(Cotacao(ativo_id, Dinheiro.de_decimal(preco_referencia), 0, agora))
            self._auditoria.registrar(uow, ator=ator_de(admin), acao="ATIVO_CRIADO", entidade="ativo",
                                      entidade_id=ticker, resultado="SUCESSO")
            uow.confirmar()
            return ativo_id

    def definir_negociavel(self, admin, ticker: str, negociavel: bool) -> None:
        exigir_perfil(admin, Perfil.ADMINISTRADOR)
        with self._uow() as uow:
            ativo = uow.ativos.buscar_por_ticker(ticker)
            if ativo is None:
                raise NaoEncontrado("Ativo não encontrado.")
            ativo.definir_negociavel(negociavel)
            uow.ativos.atualizar(ativo)
            self._auditoria.registrar(uow, ator=ator_de(admin), acao="ATIVO_SITUACAO", entidade="ativo",
                                      entidade_id=ticker, resultado="SUCESSO", detalhes={"negociavel": negociavel})
            uow.confirmar()

    def atualizar_parametro(self, admin, chave: str, valor: str) -> None:
        exigir_perfil(admin, Perfil.ADMINISTRADOR)
        ParametrosOperacionais.validar_valor(chave, valor)
        agora = self._relogio.agora()
        with self._uow() as uow:
            anterior = uow.parametros.obter_todos().get(chave)
            uow.parametros.atualizar(chave, valor, admin.id, agora)
            ParametrosOperacionais.de_dicionario(uow.parametros.obter_todos())   # conjunto continua coerente
            self._auditoria.registrar(uow, ator=ator_de(admin), acao="PARAMETRO_ALTERADO", entidade="parametro",
                                      entidade_id=chave, resultado="SUCESSO",
                                      detalhes={"anterior": anterior, "novo": valor})
            uow.confirmar()

    # ---- limites de risco (UC-05, RF-16) -----------------------------------------------------
    def definir_limite(self, usuario, conta_id: int, valor_maximo_ordem: Decimal, exposicao_maxima: Decimal) -> None:
        exigir_perfil(usuario, Perfil.ANALISTA_RISCO, Perfil.ADMINISTRADOR)
        agora = self._relogio.agora()
        novo = None
        with self._uow() as uow:
            if uow.contas.buscar(conta_id) is None:
                raise NaoEncontrado("Conta não encontrada.")
            anterior = uow.contas.buscar_limite(conta_id)
            novo = LimiteRisco(conta_id=conta_id, valor_maximo_ordem=Dinheiro.de_decimal(valor_maximo_ordem),
                               exposicao_maxima=Dinheiro.de_decimal(exposicao_maxima))
            uow.contas.salvar_limite(novo, usuario.id, agora)
            self._auditoria.registrar(
                uow, ator=ator_de(usuario), acao="LIMITE_ALTERADO", entidade="conta", entidade_id=conta_id,
                resultado="SUCESSO",
                detalhes={"anterior": None if anterior is None else
                          {"ordem": str(anterior.valor_maximo_ordem), "exposicao": str(anterior.exposicao_maxima)},
                          "novo": {"ordem": str(novo.valor_maximo_ordem), "exposicao": str(novo.exposicao_maxima)}})
            uow.confirmar()
