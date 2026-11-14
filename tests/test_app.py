"""Testes da casca da aplicação (tela de entrada, barra lateral, Bastidores) com o AppTest do Streamlit."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

# caminho absoluto: o AppTest resolve caminhos relativos a partir da pasta do teste (tests/)
ARQUIVO = str(Path(__file__).resolve().parents[1] / "app" / "Inicio.py")


def _logado(cfg):
    """Abre a aplicação e entra como Ana pelo formulário."""
    at = AppTest.from_file(ARQUIVO, default_timeout=30).run()
    at.text_input(key="login_email").set_value("ana@exemplo.com")
    at.text_input(key="login_senha").set_value(cfg.SENHA_DEMO)
    at.button(key="login_entrar").click().run()
    return at


def test_sem_login_mostra_entrada(dados_carregados):
    at = AppTest.from_file(ARQUIVO, default_timeout=30).run()
    assert not at.exception and any("Entrar" in t.label for t in at.tabs)


def test_login_pelo_formulario(dados_carregados, cfg):
    at = AppTest.from_file(ARQUIVO, default_timeout=30).run()
    at.text_input(key="login_email").set_value("ana@exemplo.com")
    at.text_input(key="login_senha").set_value(cfg.SENHA_DEMO)
    at.button(key="login_entrar").click().run()
    assert not at.exception and "token" in at.session_state and "Ana Beatriz Lima" in at.sidebar.markdown[0].value


def test_senha_errada_mostra_erro(dados_carregados):
    at = AppTest.from_file(ARQUIVO, default_timeout=30).run()
    at.text_input(key="login_email").set_value("ana@exemplo.com")
    at.text_input(key="login_senha").set_value("errada")
    at.button(key="login_entrar").click().run()
    assert "token" not in at.session_state and at.error[0].value == "E-mail ou senha inválidos."


def test_sessao_expirada_volta_para_entrada_com_aviso(dados_carregados):
    at = AppTest.from_file(ARQUIVO, default_timeout=30)
    at.session_state["token"] = "token-que-nao-existe"
    at.run()
    assert not at.exception and "token" not in at.session_state
    assert any("sessão expirou" in w.value for w in at.warning)


def test_bastidores_mostra_login_nos_dois_bancos(dados_carregados, cfg):
    at = _logado(cfg)
    grupos = at.session_state["servicos"].registro.grupos()
    assert {o["banco"] for g in grupos if g["acao"] == "Login" for o in g["operacoes"]} == {"MongoDB", "Redis"}
