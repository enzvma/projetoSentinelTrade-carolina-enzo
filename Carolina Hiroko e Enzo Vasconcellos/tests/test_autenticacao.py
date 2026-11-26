"""Autenticação com senha e segundo fator (RF-02, RNF-01, RNF-02, RN-13)."""
import pytest

from conftest import SENHA, codigo_mfa, criar_usuario
from sentineltrade.dominio.erros import CredenciaisInvalidas, DadosInvalidos
from sentineltrade.seguranca import verificar_senha


def test_login_completo_com_mfa(app, investidor):
    usuario, _ = investidor
    token_mfa = app.autenticacao.login("investidor@exemplo.com", SENHA)
    token, _ = app.autenticacao.confirmar_mfa(token_mfa, codigo_mfa(app, usuario))
    assert app.autenticacao.usuario_do_token(token).id == usuario.id


def test_senha_guardada_so_como_hash(app, investidor):
    usuario, _ = investidor
    senha_hash, segredo = usuario.credenciais()
    assert SENHA not in senha_hash and senha_hash.startswith("$argon2id$")
    assert verificar_senha(SENHA, senha_hash)
    assert app.autenticacao.segredo_mfa(usuario) not in segredo     # segredo do MFA cifrado no banco


def test_senha_errada_e_email_inexistente_tem_a_mesma_resposta(app, investidor):
    for email, senha in (("investidor@exemplo.com", "SenhaErrada1234"), ("ninguem@exemplo.com", SENHA)):
        with pytest.raises(CredenciaisInvalidas) as exc:
            app.autenticacao.login(email, senha)
        assert exc.value.mensagem_publica == "Credenciais inválidas ou conta bloqueada."


def test_sem_mfa_nao_ha_acesso(app, investidor):
    token_mfa = app.autenticacao.login("investidor@exemplo.com", SENHA)
    with pytest.raises(CredenciaisInvalidas):
        app.autenticacao.usuario_do_token(token_mfa)                # token de MFA não serve como acesso
    with pytest.raises(CredenciaisInvalidas):
        app.autenticacao.confirmar_mfa(token_mfa, "000000")


def test_codigo_mfa_nao_pode_ser_reutilizado(app, investidor):
    usuario, _ = investidor
    codigo = codigo_mfa(app, usuario)
    app.autenticacao.confirmar_mfa(app.autenticacao.login("investidor@exemplo.com", SENHA), codigo)
    with pytest.raises(CredenciaisInvalidas):
        app.autenticacao.confirmar_mfa(app.autenticacao.login("investidor@exemplo.com", SENHA), codigo)


def test_cinco_falhas_bloqueiam_a_conta(app, investidor, relogio):
    for _ in range(5):
        with pytest.raises(CredenciaisInvalidas):
            app.autenticacao.login("investidor@exemplo.com", "SenhaErrada1234")
    with pytest.raises(CredenciaisInvalidas):
        app.autenticacao.login("investidor@exemplo.com", SENHA)    # bloqueada mesmo com a senha certa
    relogio.avancar(minutes=16)
    assert app.autenticacao.login("investidor@exemplo.com", SENHA)


def test_token_expirado_e_recusado(app, investidor, relogio):
    usuario, _ = investidor
    token, _ = app.autenticacao.confirmar_mfa(app.autenticacao.login("investidor@exemplo.com", SENHA),
                                              codigo_mfa(app, usuario))
    relogio.avancar(minutes=16)
    with pytest.raises(CredenciaisInvalidas):
        app.autenticacao.usuario_do_token(token)


def test_usuario_inativado_perde_acesso(app, investidor):
    from sentineltrade.dominio.enums import Perfil
    usuario, _ = investidor
    token, _ = app.autenticacao.confirmar_mfa(app.autenticacao.login("investidor@exemplo.com", SENHA),
                                              codigo_mfa(app, usuario))
    admin, _ = criar_usuario(app, "admin@exemplo.com", Perfil.ADMINISTRADOR)
    app.administracao.definir_situacao_usuario(admin, usuario.id, False)
    with pytest.raises(CredenciaisInvalidas):
        app.autenticacao.usuario_do_token(token)


@pytest.mark.parametrize("senha", ["curta1", "semnumerosaquiok", "123456789012"])
def test_politica_de_senha(app, senha):
    from sentineltrade.dominio.enums import Perfil
    with pytest.raises(DadosInvalidos):
        app.administracao.criar_usuario(None, nome="Pessoa", email="nova@exemplo.com", senha=senha,
                                        perfil=Perfil.INVESTIDOR)
