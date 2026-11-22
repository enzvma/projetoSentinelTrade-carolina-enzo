"""Aplicação FastAPI: rotas, autenticação, autorização por perfil e tratamento seguro de erros.

Execução: uvicorn sentineltrade.api.app:criar_app --factory
"""

import logging
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..config import Configuracao, obter_configuracao
from ..dominio import erros
from ..dominio.enums import EstadoOrdem, Lado, Perfil, TipoAtivo, TipoOrdem
from ..dominio.usuario import Usuario
from ..logs import configurar_logs, correlation_id
from ..servicos.aplicacao import Aplicacao
from ..servicos.comum import exigir_perfil
from ..servicos.ordens import DadosAlteracao, DadosOrdem
from . import esquemas as E
from .protecoes import LimitadorJanela, ProtecaoHttp

log = logging.getLogger(__name__)

STATUS_ERRO = {
    erros.DadosInvalidos: 422, erros.NaoEncontrado: 404, erros.AcessoNegado: 403,
    erros.CredenciaisInvalidas: 401, erros.ConflitoIdempotencia: 409, erros.TransicaoInvalida: 409,
    erros.OperacaoNaoPermitida: 409, erros.ServicoIndisponivel: 503, erros.LimiteRequisicoes: 429,
    erros.FalhaIntegracao: 503,
}

OrdemId = Annotated[int, Path(ge=1, le=2_147_483_647)]
TickerPath = Annotated[str, Path(pattern=E.TICKER)]
ChaveParametro = Literal["PREGAO_ABERTURA", "PREGAO_FECHAMENTO", "PREGAO_FUSO", "PREGAO_DIAS", "COTACAO_IDADE_MAX_S",
                         "FAIXA_PRECO_PCT", "TAXA_OPERACAO_BPS"]
_bearer = HTTPBearer(auto_error=False)


def _erro(status: int, codigo: str, mensagem: str, **extra) -> JSONResponse:
    headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
    return JSONResponse(status_code=status, headers=headers,
                        content={"erro": codigo, "mensagem": mensagem, "correlation_id": correlation_id.get(), **extra})


def criar_app(config: Configuracao | None = None, aplicacao: Aplicacao | None = None) -> FastAPI:
    config = config or obter_configuracao()
    configurar_logs(config.log_level)
    aplicacao = aplicacao or Aplicacao(config)
    documentacao = not config.producao
    app = FastAPI(title="SentinelTrade", version="0.1.0", docs_url="/docs" if documentacao else None,
                  redoc_url=None, openapi_url="/openapi.json" if documentacao else None)
    app.state.aplicacao = aplicacao
    app.add_middleware(ProtecaoHttp, max_bytes=config.max_body_bytes, csp_documentacao=documentacao)

    limite_login = LimitadorJanela(config.rate_limit_login_per_min)
    limite_ordens = LimitadorJanela(config.rate_limit_orders_per_min)

    # ---- tratamento de erros (RNF-06): mensagens genéricas, sem detalhes internos --------------
    @app.exception_handler(erros.ErroSentinel)
    async def _erro_dominio(request: Request, exc: erros.ErroSentinel):
        status = next((s for tipo, s in STATUS_ERRO.items() if isinstance(exc, tipo)), 400)
        return _erro(status, exc.codigo, exc.mensagem_publica)

    @app.exception_handler(RequestValidationError)
    async def _erro_validacao(request: Request, exc: RequestValidationError):
        # Não devolve o valor enviado (poderia ser uma senha); só o campo e o tipo do problema.
        campos = [{"campo": ".".join(str(p) for p in e.get("loc", ())[1:]) or "corpo", "problema": e.get("type")}
                  for e in exc.errors()[:20]]
        return _erro(422, "DADOS_INVALIDOS", "Dados inválidos.", campos=campos)

    @app.exception_handler(StarletteHTTPException)
    async def _erro_http(request: Request, exc: StarletteHTTPException):
        mensagens = {404: "Recurso não encontrado.", 405: "Método não permitido."}
        return _erro(exc.status_code, "ERRO_HTTP", mensagens.get(exc.status_code, "Requisição inválida."))

    @app.exception_handler(Exception)
    async def _erro_inesperado(request: Request, exc: Exception):
        log.exception("erro inesperado", extra={"dados": {"rota": request.url.path}})
        return _erro(500, "ERRO_INTERNO", "Erro interno. Informe o código de rastreio ao suporte.")

    # ---- dependências ------------------------------------------------------------------------
    def app_de(request: Request) -> Aplicacao:
        return request.app.state.aplicacao

    def usuario_atual(request: Request,
                      credenciais: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> Usuario:
        if credenciais is None or credenciais.scheme.lower() != "bearer" or len(credenciais.credentials) > 2048:
            raise erros.CredenciaisInvalidas()
        return app_de(request).autenticacao.usuario_do_token(credenciais.credentials)

    def com_perfil(*perfis: Perfil):
        def dependencia(usuario: Usuario = Depends(usuario_atual)) -> Usuario:
            exigir_perfil(usuario, *perfis)
            return usuario
        return dependencia

    Investidor = Annotated[Usuario, Depends(com_perfil(Perfil.INVESTIDOR))]
    Admin = Annotated[Usuario, Depends(com_perfil(Perfil.ADMINISTRADOR))]
    Gestor = Annotated[Usuario, Depends(com_perfil(Perfil.ANALISTA_RISCO, Perfil.ADMINISTRADOR))]
    Auditor = Annotated[Usuario, Depends(com_perfil(Perfil.AUDITOR))]
    Autenticado = Annotated[Usuario, Depends(usuario_atual)]
    App = Annotated[Aplicacao, Depends(app_de)]

    def ip(request: Request) -> str:
        return request.client.host if request.client else "desconhecido"

    # ---- saúde -------------------------------------------------------------------------------
    @app.get("/saude", tags=["sistema"])
    def saude():
        return {"status": "ok"}

    # ---- autenticação (UC-01, UC-02) -------------------------------------------------------
    @app.post("/auth/login", response_model=E.MfaPendenteSaida, tags=["autenticação"])
    def login(dados: E.LoginEntrada, request: Request, a: App):
        if not limite_login.permitir(f"ip:{ip(request)}") or not limite_login.permitir(f"email:{dados.email.lower()}"):
            raise erros.LimiteRequisicoes()
        token = a.autenticacao.login(dados.email, dados.senha)
        return E.MfaPendenteSaida(token_mfa=token, expira_em_segundos=config.mfa_code_ttl_seconds)

    @app.post("/auth/mfa", response_model=E.AcessoSaida, tags=["autenticação"])
    def confirmar_mfa(dados: E.MfaEntrada, request: Request, a: App):
        if not limite_login.permitir(f"mfa:{ip(request)}"):
            raise erros.LimiteRequisicoes()
        token, validade = a.autenticacao.confirmar_mfa(dados.token_mfa, dados.codigo)
        return E.AcessoSaida(access_token=token, expira_em_segundos=validade)

    # ---- cotações, saldo e carteira (UC-06 a UC-08) ----------------------------------------
    def _cotacao(c: dict) -> E.CotacaoSaida:
        return E.CotacaoSaida(ticker=c["ticker"], nome=c["nome"], tipo=c["tipo"], negociavel=c["negociavel"],
                              preco=c["preco"].como_decimal() if c["preco"] else None,
                              variacao_percentual=(None if c["variacao_bps"] is None
                                                   else (Decimal(c["variacao_bps"]) / 100).quantize(Decimal("0.01"))),
                              data_hora=c["data_hora"], desatualizada=c["desatualizada"])

    @app.get("/cotacoes", response_model=list[E.CotacaoSaida], tags=["mercado"])
    def listar_cotacoes(u: Autenticado, a: App):
        return [_cotacao(c) for c in a.consultas.cotacoes()]

    @app.get("/cotacoes/{ticker}", response_model=E.CotacaoSaida, tags=["mercado"])
    def obter_cotacao(ticker: TickerPath, u: Autenticado, a: App):
        return _cotacao(a.consultas.cotacoes(ticker)[0])

    @app.get("/conta/saldo", response_model=E.SaldoSaida, tags=["conta"])
    def saldo(u: Investidor, a: App):
        s = a.consultas.saldo(u)
        return E.SaldoSaida(**{k: v.como_decimal() for k, v in s.items()})

    @app.get("/conta/carteira", response_model=list[E.PosicaoSaida], tags=["conta"])
    def carteira(u: Investidor, a: App):
        return [E.PosicaoSaida(**{k: (v.como_decimal() if hasattr(v, "como_decimal") else v) for k, v in p.items()})
                for p in a.consultas.carteira(u)]

    # ---- ordens (UC-10 a UC-13, UC-20, UC-21) ----------------------------------------------
    @app.post("/ordens", response_model=E.OrdemSaida, status_code=201, tags=["ordens"])
    def enviar_ordem(dados: E.OrdemEntrada, u: Investidor, a: App):
        if not limite_ordens.permitir(f"usuario:{u.id}"):
            raise erros.LimiteRequisicoes()
        ordem, criada = a.ordens.criar(u, DadosOrdem(dados.ticker, Lado(dados.lado), TipoOrdem(dados.tipo),
                                                     dados.quantidade, dados.preco, dados.chave_idempotencia))
        saida = E.OrdemSaida.de(ordem)
        return saida if criada else JSONResponse(status_code=200, content=saida.model_dump(mode="json"))

    @app.get("/ordens", response_model=list[E.OrdemSaida], tags=["ordens"])
    def listar_ordens(u: Autenticado, a: App,
                      estado: Annotated[Literal["CRIADA", "VALIDADA", "ENVIADA", "PARCIALMENTE_EXECUTADA", "EXECUTADA",
                                                "REJEITADA", "CANCELADA"] | None, Query()] = None,
                      ticker: Annotated[str | None, Query(pattern=E.TICKER)] = None,
                      conta_id: Annotated[int | None, Query(ge=1, le=2_147_483_647)] = None,
                      limite: Annotated[int, Query(ge=1, le=100)] = 20,
                      deslocamento: Annotated[int, Query(ge=0, le=100_000)] = 0):
        ordens = a.ordens.listar(u, estado=EstadoOrdem(estado) if estado else None, ticker=ticker,
                                 conta_id=conta_id, limite=limite, deslocamento=deslocamento)
        return [E.OrdemSaida.de(o) for o in ordens]

    @app.get("/ordens/{ordem_id}", response_model=E.OrdemDetalheSaida, tags=["ordens"])
    def consultar_ordem(ordem_id: OrdemId, u: Autenticado, a: App):
        ordem, historico = a.ordens.consultar(u, ordem_id)
        return E.OrdemDetalheSaida(**E.OrdemSaida.de(ordem).model_dump(),
                                   historico=[E.TransicaoSaida(**t) for t in historico])

    @app.patch("/ordens/{ordem_id}", response_model=E.OrdemSaida, status_code=201, tags=["ordens"])
    def alterar_ordem(ordem_id: OrdemId, dados: E.AlteracaoEntrada, u: Investidor, a: App):
        if not limite_ordens.permitir(f"usuario:{u.id}"):
            raise erros.LimiteRequisicoes()
        nova, criada = a.ordens.alterar(u, ordem_id, DadosAlteracao(dados.quantidade, dados.preco,
                                                                    dados.chave_idempotencia))
        saida = E.OrdemSaida.de(nova)
        return saida if criada else JSONResponse(status_code=200, content=saida.model_dump(mode="json"))

    @app.post("/ordens/{ordem_id}/cancelamento", response_model=E.CancelamentoSaida, status_code=202, tags=["ordens"])
    def cancelar_ordem(ordem_id: OrdemId, u: Investidor, a: App):
        ordem = a.ordens.cancelar(u, ordem_id)
        mensagem = ("Ordem cancelada." if ordem.estado is EstadoOrdem.CANCELADA
                    else "Cancelamento solicitado; acompanhe o status da ordem.")
        return E.CancelamentoSaida(ordem=E.OrdemSaida.de(ordem), mensagem=mensagem)

    # ---- administração (UC-03, UC-04) ------------------------------------------------------
    @app.post("/admin/usuarios", response_model=E.UsuarioCriadoSaida, status_code=201, tags=["administração"])
    def criar_usuario(dados: E.UsuarioEntrada, u: Admin, a: App):
        novo_id, uri = a.administracao.criar_usuario(u, nome=dados.nome, email=str(dados.email), senha=dados.senha,
                                                     perfil=Perfil(dados.perfil), saldo_inicial=dados.saldo_inicial)
        return E.UsuarioCriadoSaida(id=novo_id, otpauth_uri=uri)

    @app.patch("/admin/usuarios/{usuario_id}", status_code=204, tags=["administração"])
    def situacao_usuario(usuario_id: OrdemId, dados: E.SituacaoEntrada, u: Admin, a: App):
        a.administracao.definir_situacao_usuario(u, usuario_id, dados.ativo)

    @app.post("/admin/contas/{conta_id}/creditos", status_code=204, tags=["administração"])
    def creditar(conta_id: OrdemId, dados: E.CreditoEntrada, u: Admin, a: App):
        a.administracao.creditar_saldo(u, conta_id, dados.valor)

    @app.post("/admin/ativos", status_code=201, tags=["administração"])
    def criar_ativo(dados: E.AtivoEntrada, u: Admin, a: App):
        ativo_id = a.administracao.criar_ativo(u, ticker=dados.ticker, nome=dados.nome, tipo=TipoAtivo(dados.tipo),
                                               preco_referencia=dados.preco_referencia)
        return {"id": ativo_id}

    @app.patch("/admin/ativos/{ticker}", status_code=204, tags=["administração"])
    def situacao_ativo(ticker: TickerPath, dados: E.NegociavelEntrada, u: Admin, a: App):
        a.administracao.definir_negociavel(u, ticker, dados.negociavel)

    @app.put("/admin/parametros/{chave}", status_code=204, tags=["administração"])
    def parametro(chave: ChaveParametro, dados: E.ParametroEntrada, u: Admin, a: App):
        a.administracao.atualizar_parametro(u, chave, dados.valor)

    # ---- risco (UC-05) -------------------------------------------------------------------
    @app.put("/risco/contas/{conta_id}/limites", status_code=204, tags=["risco"])
    def limites(conta_id: OrdemId, dados: E.LimiteEntrada, u: Gestor, a: App):
        a.administracao.definir_limite(u, conta_id, dados.valor_maximo_ordem, dados.exposicao_maxima)

    # ---- auditoria (UC-22) -----------------------------------------------------------------
    @app.get("/auditoria", response_model=list[E.AuditoriaSaida], tags=["auditoria"])
    def auditoria(u: Auditor, a: App,
                  entidade: Annotated[Literal["ordem", "usuario", "conta", "ativo", "parametro", "sistema"] | None,
                                      Query()] = None,
                  entidade_id: Annotated[str | None, Query(pattern=r"^[A-Za-z0-9_]{1,32}$")] = None,
                  limite: Annotated[int, Query(ge=1, le=200)] = 50,
                  deslocamento: Annotated[int, Query(ge=0, le=1_000_000)] = 0):
        registros = a.auditoria.listar(u, entidade=entidade, entidade_id=entidade_id, limite=limite,
                                       deslocamento=deslocamento)
        return [E.AuditoriaSaida(id=r.id, data_hora=r.data_hora, ator=r.ator, acao=r.acao, entidade=r.entidade,
                                 entidade_id=r.entidade_id, resultado=r.resultado, detalhes=r.detalhes,
                                 correlation_id=r.correlation_id, hash=r.hash) for r in registros]

    @app.get("/auditoria/verificacao", response_model=E.VerificacaoSaida, tags=["auditoria"])
    def verificar_auditoria(u: Auditor, a: App):
        integra, invalido, total = a.auditoria.verificar_cadeia(u)
        return E.VerificacaoSaida(integra=integra, registros_verificados=total, primeiro_registro_invalido=invalido)

    return app
