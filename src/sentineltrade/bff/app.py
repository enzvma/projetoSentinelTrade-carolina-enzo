"""BFF (Backend for Frontend): a camada entre a interface web e a API.

O navegador fala só com o BFF, e o BFF fala com a API. Isso traz três ganhos:
- o token de acesso nunca chega ao navegador: fica na sessão do servidor, e o navegador
  guarda apenas um cookie HttpOnly e SameSite=Strict (protege contra XSS e CSRF);
- cada tela recebe, numa chamada, tudo de que precisa (agregação de várias rotas da API);
- códigos técnicos (estados, motivos de rejeição, erros) viram mensagens em português.

Execução: sentineltrade bff (porta 8001; a API precisa estar rodando na porta 8000).
"""

import logging
import re
import secrets
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal

import httpx
from fastapi import Depends, FastAPI, Header, Path as PathParam, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..api import esquemas as E
from ..api.protecoes import ProtecaoHttp
from ..config import Configuracao, obter_configuracao
from ..logs import configurar_logs, correlation_id

log = logging.getLogger(__name__)
ESTATICOS = Path(__file__).parent / "static"
COOKIE = "st_sessao"
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; "
       "font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; "
       "base-uri 'none'; form-action 'self'; frame-ancestors 'none'")

ESTADOS = {
    "CRIADA": "Criada", "VALIDADA": "Validada", "ENVIADA": "Na corretora",
    "PARCIALMENTE_EXECUTADA": "Executada em parte", "EXECUTADA": "Executada",
    "REJEITADA": "Rejeitada", "CANCELADA": "Cancelada",
}
MOTIVOS = {
    "MERCADO_FECHADO": "O pregão está fechado.",
    "ATIVO_INDISPONIVEL": "Este ativo não está disponível para negociação.",
    "COTACAO_INDISPONIVEL": "Não há cotação recente para este ativo.",
    "PRECO_FORA_DA_FAIXA": "O preço está fora da faixa permitida em relação à cotação atual.",
    "LIMITE_RISCO_EXCEDIDO": "A ordem ultrapassa o limite de risco da conta.",
    "SALDO_INSUFICIENTE": "Saldo disponível insuficiente.",
    "POSICAO_INSUFICIENTE": "Quantidade do ativo insuficiente na carteira.",
    "CONTA_INATIVA": "A conta está inativa.",
    "REJEITADA_PELA_CORRETORA": "A corretora recusou a ordem.",
    "ORDEM_ORIGINAL_EXECUTADA": "A ordem original foi executada antes da alteração.",
    "ALTERADA": "Substituída por uma ordem alterada.",
}
ORIGENS = {"USUARIO": "você", "SISTEMA": "sistema", "CORRETORA": "corretora"}
CAMPOS = {"ticker": "ativo", "quantidade": "quantidade", "preco": "preço", "email": "e-mail", "senha": "senha",
          "codigo": "código", "nome": "nome", "valor": "valor", "saldo_inicial": "saldo inicial",
          "valor_maximo_ordem": "valor máximo por ordem", "exposicao_maxima": "exposição máxima",
          "preco_referencia": "preço de referência", "chave_idempotencia": "identificador da ordem"}
CANCELAVEIS = {"CRIADA", "VALIDADA", "ENVIADA", "PARCIALMENTE_EXECUTADA"}
ALTERAVEIS = {"VALIDADA", "ENVIADA", "PARCIALMENTE_EXECUTADA"}
_CORRELACAO_RE = re.compile(r"^[A-Za-z0-9-]{8,64}$")


class ErroBff(Exception):
    def __init__(self, status: int, mensagem: str) -> None:
        super().__init__(mensagem)
        self.status, self.mensagem = status, mensagem


# ---- sessões no servidor --------------------------------------------------------------------
@dataclass
class Sessao:
    csrf: str
    expira: float
    token_mfa: str | None = None
    token: str | None = None
    nome: str = ""
    perfil: str = ""


class Sessoes:
    """Sessões em memória, com validade e número máximo (um processo, adequado à demonstração)."""

    def __init__(self, duracao_s: int, maximo: int = 5000, relogio=time.monotonic) -> None:
        self._duracao, self._maximo, self._relogio = duracao_s, maximo, relogio
        self._dados: dict[str, Sessao] = {}
        self._lock = threading.Lock()

    def criar(self) -> tuple[str, Sessao]:
        with self._lock:
            agora = self._relogio()
            for sid in [s for s, v in self._dados.items() if v.expira <= agora]:
                del self._dados[sid]
            if len(self._dados) >= self._maximo:
                del self._dados[min(self._dados, key=lambda s: self._dados[s].expira)]
            sid = secrets.token_urlsafe(32)
            self._dados[sid] = sessao = Sessao(csrf=secrets.token_urlsafe(32), expira=agora + self._duracao)
            return sid, sessao

    def obter(self, sid: str | None) -> Sessao | None:
        if not sid or len(sid) > 64:
            return None
        with self._lock:
            sessao = self._dados.get(sid)
            if sessao is None or sessao.expira <= self._relogio():
                self._dados.pop(sid, None)
                return None
            return sessao

    def remover(self, sid: str | None) -> None:
        with self._lock:
            self._dados.pop(sid or "", None)


# ---- entradas próprias do BFF ---------------------------------------------------------------
class CodigoEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    codigo: str = Field(pattern=r"^[0-9]{6}$", repr=False)


# ---- tradução das respostas da API ----------------------------------------------------------
def _ordem(o: dict) -> dict:
    return {**o, "estado_texto": ESTADOS.get(o["estado"], o["estado"]),
            "motivo_texto": MOTIVOS.get(o.get("motivo") or "", None),
            "pode_cancelar": o["estado"] in CANCELAVEIS, "pode_alterar": o["estado"] in ALTERAVEIS}


def _mensagem_erro(status: int, corpo: Any) -> str:
    if not isinstance(corpo, dict):
        return "Não foi possível concluir a operação."
    if corpo.get("erro") == "DADOS_INVALIDOS" and corpo.get("campos"):
        nomes = sorted({CAMPOS.get(c.get("campo", "").split(".")[-1], "dados") for c in corpo["campos"]})
        return "Confira " + ", ".join(nomes) + "."
    if status == 401 and corpo.get("erro") == "CREDENCIAIS_INVALIDAS":
        return "E-mail, senha ou código incorretos, ou conta bloqueada temporariamente."
    mensagem = corpo.get("mensagem")
    return mensagem if isinstance(mensagem, str) and len(mensagem) <= 200 else "Não foi possível concluir a operação."


def criar_bff(config: Configuracao | None = None, cliente_api: httpx.Client | None = None) -> FastAPI:
    config = config or obter_configuracao()
    configurar_logs(config.log_level)
    api = cliente_api or httpx.Client(base_url=config.api_url, timeout=5.0)
    sessoes = Sessoes(duracao_s=config.access_token_minutes * 60)

    app = FastAPI(title="SentinelTrade BFF", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(ProtecaoHttp, max_bytes=config.max_body_bytes, csp_documentacao=False, csp=CSP)
    app.mount("/static", StaticFiles(directory=ESTATICOS), name="static")

    def chamar(metodo: str, caminho: str, sessao: Sessao | None = None, ip: str | None = None, **kwargs) -> Any:
        cabecalhos = {}
        if ip:
            cabecalhos["X-Forwarded-For"] = ip                # limite de tentativas por IP real na API
        cid = correlation_id.get()
        if _CORRELACAO_RE.fullmatch(cid):
            cabecalhos["X-Correlation-ID"] = cid          # o mesmo código de rastreio nos logs do BFF e da API
        if sessao is not None and sessao.token:
            cabecalhos["Authorization"] = f"Bearer {sessao.token}"
        try:
            r = api.request(metodo, caminho, headers=cabecalhos, **kwargs)
        except httpx.HTTPError:
            log.warning("API indisponível", extra={"dados": {"rota": caminho}})
            raise ErroBff(503, "A API não respondeu. Confira se ela está em execução (sentineltrade api).") from None
        if r.status_code >= 400:
            try:
                corpo = r.json()
            except ValueError:
                corpo = None
            if r.status_code == 401 and sessao is not None and sessao.token:
                sessao.token = None
                raise ErroBff(401, "Sua sessão expirou. Entre novamente.")
            raise ErroBff(r.status_code, _mensagem_erro(r.status_code, corpo))
        return r.json() if r.content else None

    # ---- erros: sempre JSON curto, sem detalhes internos ------------------------------------
    @app.exception_handler(ErroBff)
    async def _erro_bff(request: Request, exc: ErroBff):
        return JSONResponse(status_code=exc.status, content={"mensagem": exc.mensagem})

    @app.exception_handler(RequestValidationError)
    async def _erro_validacao(request: Request, exc: RequestValidationError):
        nomes = sorted({CAMPOS.get(str(e.get("loc", ("", ""))[-1]), "os dados") for e in exc.errors()[:20]})
        return JSONResponse(status_code=422, content={"mensagem": "Confira " + ", ".join(nomes) + "."})

    @app.exception_handler(StarletteHTTPException)
    async def _erro_http(request: Request, exc: StarletteHTTPException):
        return JSONResponse(status_code=exc.status_code, content={"mensagem": "Página não encontrada."
                                                                  if exc.status_code == 404 else "Requisição inválida."})

    def ip_de(request: Request) -> str | None:
        return request.client.host if request.client else None

    # ---- dependências: sessão, CSRF e perfil ------------------------------------------------
    def sessao_atual(request: Request) -> Sessao | None:
        return sessoes.obter(request.cookies.get(COOKIE))

    def com_csrf(request: Request, x_csrf_token: Annotated[str | None, Header()] = None) -> Sessao:
        sessao = sessao_atual(request)
        if sessao is None:
            raise ErroBff(401, "Sua sessão expirou. Recarregue a página.")
        if not x_csrf_token or not secrets.compare_digest(x_csrf_token, sessao.csrf):
            raise ErroBff(403, "Requisição recusada. Recarregue a página.")
        return sessao

    def logado(request: Request) -> Sessao:
        sessao = sessao_atual(request)
        if sessao is None or not sessao.token:
            raise ErroBff(401, "Sua sessão expirou. Entre novamente.")
        return sessao

    def perfil(*perfis: str, escrita: bool = False):
        def dependencia(request: Request, x_csrf_token: Annotated[str | None, Header()] = None) -> Sessao:
            sessao = com_csrf(request, x_csrf_token) if escrita else logado(request)
            if not sessao.token:
                raise ErroBff(401, "Sua sessão expirou. Entre novamente.")
            if perfis and sessao.perfil not in perfis:
                raise ErroBff(403, "Seu perfil não tem acesso a esta função.")
            return sessao
        return dependencia

    Leitura = Annotated[Sessao, Depends(perfil())]
    Investidor = Annotated[Sessao, Depends(perfil("INVESTIDOR", escrita=True))]
    Admin = Annotated[Sessao, Depends(perfil("ADMINISTRADOR", escrita=True))]
    Gestor = Annotated[Sessao, Depends(perfil("ANALISTA_RISCO", "ADMINISTRADOR", escrita=True))]
    Auditor = Annotated[Sessao, Depends(perfil("AUDITOR"))]
    ComCsrf = Annotated[Sessao, Depends(com_csrf)]
    Id = Annotated[int, PathParam(ge=1, le=2_147_483_647)]

    # ---- página ----------------------------------------------------------------------------
    @app.get("/", include_in_schema=False)
    def pagina():
        return FileResponse(ESTATICOS / "index.html", media_type="text/html; charset=utf-8")

    # ---- sessão e login (UC-01, UC-02) ----------------------------------------------------
    @app.get("/bff/sessao")
    def sessao(request: Request):
        atual = sessao_atual(request)
        resposta_cookie = None
        if atual is None:
            resposta_cookie, atual = sessoes.criar()
        corpo = {"csrf": atual.csrf, "autenticado": bool(atual.token), "nome": atual.nome, "perfil": atual.perfil}
        resposta = JSONResponse(corpo)
        if resposta_cookie:
            resposta.set_cookie(COOKIE, resposta_cookie, httponly=True, samesite="strict", secure=config.producao,
                                path="/", max_age=config.access_token_minutes * 60)
        return resposta

    @app.post("/bff/login")
    def login(dados: E.LoginEntrada, request: Request, sessao: ComCsrf):
        r = chamar("POST", "/auth/login", ip=ip_de(request), json={"email": str(dados.email), "senha": dados.senha})
        sessao.token_mfa, sessao.token = r["token_mfa"], None
        return {"etapa": "mfa", "expira_em_segundos": r["expira_em_segundos"]}

    @app.post("/bff/mfa")
    def mfa(dados: CodigoEntrada, request: Request, sessao: ComCsrf):
        if not sessao.token_mfa:
            raise ErroBff(401, "Informe e-mail e senha novamente.")
        r = chamar("POST", "/auth/mfa", ip=ip_de(request), json={"token_mfa": sessao.token_mfa, "codigo": dados.codigo})
        sessao.token_mfa, sessao.token = None, r["access_token"]
        eu = chamar("GET", "/auth/eu", sessao)
        sessao.nome, sessao.perfil = eu["nome"], eu["perfil"]
        return {"autenticado": True, "nome": sessao.nome, "perfil": sessao.perfil}

    @app.post("/bff/sair")
    def sair(request: Request, sessao: ComCsrf):
        sessoes.remover(request.cookies.get(COOKIE))
        resposta = JSONResponse({"mensagem": "Sessão encerrada."})
        resposta.delete_cookie(COOKIE, path="/")
        return resposta

    # ---- painel: uma chamada traz tudo que a tela do perfil precisa (agregação) -----------
    @app.get("/bff/painel")
    def painel(sessao: Leitura):
        mercado = chamar("GET", "/mercado", sessao)
        dados: dict[str, Any] = {"perfil": sessao.perfil, "nome": sessao.nome, "mercado": mercado}
        if sessao.perfil == "INVESTIDOR":
            dados["saldo"] = chamar("GET", "/conta/saldo", sessao)
            dados["carteira"] = chamar("GET", "/conta/carteira", sessao)
            dados["cotacoes"] = chamar("GET", "/cotacoes", sessao)
            dados["ordens"] = [_ordem(o) for o in chamar("GET", "/ordens", sessao, params={"limite": 30})]
        elif sessao.perfil in ("ADMINISTRADOR", "ANALISTA_RISCO"):
            dados["cotacoes"] = chamar("GET", "/cotacoes", sessao)
            dados["ordens"] = [_ordem(o) for o in chamar("GET", "/ordens", sessao, params={"limite": 50})]
        elif sessao.perfil == "AUDITOR":
            dados["auditoria"] = chamar("GET", "/auditoria", sessao, params={"limite": 100})
        return dados

    # ---- ordens (UC-10 a UC-13) -----------------------------------------------------------
    @app.get("/bff/ordens/{ordem_id}")
    def detalhe_ordem(ordem_id: Id, sessao: Leitura):
        o = chamar("GET", f"/ordens/{ordem_id}", sessao)
        historico = [{**h, "estado_texto": ESTADOS.get(h["estado_novo"], h["estado_novo"]),
                      "origem_texto": ORIGENS.get(h["origem"], h["origem"])} for h in o.pop("historico")]
        return {**_ordem(o), "historico": historico}

    @app.post("/bff/ordens")
    def enviar_ordem(dados: E.OrdemEntrada, sessao: Investidor):
        o = _ordem(chamar("POST", "/ordens", sessao, json=dados.model_dump(mode="json", exclude_none=True)))
        if o["estado"] == "REJEITADA":
            o["mensagem"] = f"Ordem #{o['id']} rejeitada: {o['motivo_texto'] or 'motivo não informado.'}"
        else:
            o["mensagem"] = f"Ordem #{o['id']} validada e na fila para a corretora."
        return o

    @app.post("/bff/ordens/{ordem_id}/cancelar")
    def cancelar_ordem(ordem_id: Id, sessao: Investidor):
        r = chamar("POST", f"/ordens/{ordem_id}/cancelamento", sessao)
        return {"ordem": _ordem(r["ordem"]), "mensagem": r["mensagem"]}

    @app.post("/bff/ordens/{ordem_id}/alterar")
    def alterar_ordem(ordem_id: Id, dados: E.AlteracaoEntrada, sessao: Investidor):
        o = _ordem(chamar("PATCH", f"/ordens/{ordem_id}", sessao, json=dados.model_dump(mode="json", exclude_none=True)))
        o["mensagem"] = f"Alteração registrada: a ordem #{o['id']} substitui a #{ordem_id} após o cancelamento dela."
        return o

    # ---- administração e risco (UC-03 a UC-05) -------------------------------------------
    @app.put("/bff/admin/parametros/{chave}")
    def parametro(chave: Literal["PREGAO_ABERTURA", "PREGAO_FECHAMENTO", "PREGAO_FUSO", "PREGAO_DIAS",
                                 "COTACAO_IDADE_MAX_S", "FAIXA_PRECO_PCT", "TAXA_OPERACAO_BPS"],
                  dados: E.ParametroEntrada, sessao: Admin):
        chamar("PUT", f"/admin/parametros/{chave}", sessao, json=dados.model_dump())
        return {"mensagem": "Parâmetro salvo."}

    @app.post("/bff/admin/ativos/{ticker}")
    def situacao_ativo(ticker: Annotated[str, PathParam(pattern=E.TICKER)], dados: E.NegociavelEntrada, sessao: Admin):
        chamar("PATCH", f"/admin/ativos/{ticker}", sessao, json=dados.model_dump())
        return {"mensagem": f"{ticker} {'liberado' if dados.negociavel else 'suspenso'} para negociação."}

    @app.post("/bff/admin/usuarios")
    def criar_usuario(dados: E.UsuarioEntrada, sessao: Admin):
        r = chamar("POST", "/admin/usuarios", sessao, json=dados.model_dump(mode="json"))
        return {"id": r["id"], "otpauth_uri": r["otpauth_uri"],
                "mensagem": f"Usuário #{r['id']} criado. Cadastre o segundo fator agora: ele não aparece de novo."}

    @app.post("/bff/admin/contas/{conta_id}/creditos")
    def creditar(conta_id: Id, dados: E.CreditoEntrada, sessao: Admin):
        chamar("POST", f"/admin/contas/{conta_id}/creditos", sessao, json=dados.model_dump(mode="json"))
        return {"mensagem": f"Crédito lançado na conta #{conta_id}."}

    @app.put("/bff/risco/contas/{conta_id}/limites")
    def limites(conta_id: Id, dados: E.LimiteEntrada, sessao: Gestor):
        chamar("PUT", f"/risco/contas/{conta_id}/limites", sessao, json=dados.model_dump(mode="json"))
        return {"mensagem": f"Limites da conta #{conta_id} atualizados."}

    # ---- auditoria (UC-22) ----------------------------------------------------------------
    @app.get("/bff/auditoria/verificacao")
    def verificar(sessao: Auditor):
        r = chamar("GET", "/auditoria/verificacao", sessao)
        r["mensagem"] = (f"Trilha íntegra: {r['registros_verificados']} registros conferidos." if r["integra"] else
                         f"Trilha adulterada a partir do registro #{r['primeiro_registro_invalido']}.")
        return r

    return app
