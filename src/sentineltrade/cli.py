"""Linha de comando do SentinelTrade.

    sentineltrade gerar-segredos           imprime JWT_SECRET e DATA_ENCRYPTION_KEY novos para o .env
    sentineltrade criar-banco [--sem-seed] cria o banco a partir de database/schema.sql e seed.sql
    sentineltrade criar-usuario ...        cria usuário (a senha é pedida no terminal, sem eco)
    sentineltrade codigo-mfa --email ...   mostra o código atual do segundo fator (só fora de produção)
    sentineltrade processar [--uma-vez]    processa cotações, fila de ordens e notificações
    sentineltrade api [--porta 8000]       inicia a API em 127.0.0.1
    sentineltrade bff [--porta 8001]       inicia a interface web (BFF) em 127.0.0.1
"""
from __future__ import annotations

import argparse
import getpass
import secrets
import sys
import time
from decimal import Decimal, InvalidOperation

from pydantic import ValidationError

from .config import obter_configuracao
from .dominio.enums import Perfil
from .dominio.erros import ErroSentinel
from .logs import configurar_logs
from .persistencia.banco import caminho_do_banco, criar_banco
from .seguranca import Cifrador, codigo_atual


def _gerar_segredos(_args) -> int:
    print(f"JWT_SECRET={secrets.token_urlsafe(48)}")
    print(f"DATA_ENCRYPTION_KEY={Cifrador.gerar_chave()}")
    return 0


def _criar_banco(args) -> int:
    criar_banco(caminho_do_banco(obter_configuracao().database_url), com_seed=not args.sem_seed)
    print("Banco criado.")
    return 0


def _aplicacao():
    from .servicos.aplicacao import Aplicacao
    config = obter_configuracao()
    configurar_logs(config.log_level)
    return Aplicacao(config)


def _criar_usuario(args) -> int:
    senha = getpass.getpass("Senha (mínimo 12 caracteres, com letras e números): ")
    if senha != getpass.getpass("Repita a senha: "):
        print("As senhas não conferem.", file=sys.stderr)
        return 1
    try:
        saldo = Decimal(args.saldo)
    except InvalidOperation:
        print("Saldo inválido.", file=sys.stderr)
        return 1
    app = _aplicacao()
    usuario_id, uri = app.administracao.criar_usuario(None, nome=args.nome, email=args.email, senha=senha,
                                                      perfil=Perfil(args.perfil), saldo_inicial=saldo)
    print(f"Usuário {usuario_id} criado.")
    print("Cadastre o segundo fator num aplicativo autenticador com esta URI (ela não será exibida de novo):")
    print(uri)
    return 0


def _codigo_mfa(args) -> int:
    app = _aplicacao()
    if app.config.producao:
        print("Comando indisponível em produção.", file=sys.stderr)
        return 1
    with app.uow(somente_leitura=True) as uow:
        usuario = uow.usuarios.buscar_por_email(args.email.strip().lower())
    if usuario is None:
        print("Usuário não encontrado.", file=sys.stderr)
        return 1
    print(codigo_atual(app.autenticacao.segredo_mfa(usuario), app.relogio.agora()))
    return 0


def _processar(args) -> int:
    app = _aplicacao()
    while True:
        app.ciclo_processamento()
        if args.uma_vez:
            return 0
        time.sleep(args.intervalo)


def _api(args) -> int:
    import uvicorn
    obter_configuracao()        # falha cedo, com mensagem clara, se o .env estiver incompleto
    uvicorn.run("sentineltrade.api.app:criar_app", factory=True, host="127.0.0.1", port=args.porta)
    return 0


def _bff(args) -> int:
    import uvicorn
    obter_configuracao()
    uvicorn.run("sentineltrade.bff.app:criar_bff", factory=True, host="127.0.0.1", port=args.porta)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sentineltrade", description="SentinelTrade (dados simulados)")
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("gerar-segredos").set_defaults(func=_gerar_segredos)
    p = sub.add_parser("criar-banco"); p.add_argument("--sem-seed", action="store_true"); p.set_defaults(func=_criar_banco)
    p = sub.add_parser("criar-usuario")
    p.add_argument("--nome", required=True); p.add_argument("--email", required=True)
    p.add_argument("--perfil", choices=[x.value for x in Perfil], default="INVESTIDOR")
    p.add_argument("--saldo", default="0"); p.set_defaults(func=_criar_usuario)
    p = sub.add_parser("codigo-mfa"); p.add_argument("--email", required=True); p.set_defaults(func=_codigo_mfa)
    p = sub.add_parser("processar"); p.add_argument("--uma-vez", action="store_true")
    p.add_argument("--intervalo", type=float, default=1.0); p.set_defaults(func=_processar)
    p = sub.add_parser("api"); p.add_argument("--porta", type=int, default=8000); p.set_defaults(func=_api)
    p = sub.add_parser("bff"); p.add_argument("--porta", type=int, default=8001); p.set_defaults(func=_bff)
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ErroSentinel as exc:
        print(exc.mensagem_publica, file=sys.stderr)
        return 1
    except ValidationError as exc:      # configuração inválida no .env: mensagem curta, sem traceback
        print("Configuração inválida no arquivo .env:", file=sys.stderr)
        for erro in exc.errors():
            print(f"  - {erro.get('msg', '').removeprefix('Value error, ')}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
