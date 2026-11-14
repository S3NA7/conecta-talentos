"""Apoio aos testes de tela: abre uma página sozinha, já logada, no AppTest do Streamlit."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

RAIZ = str(Path(__file__).resolve().parents[1])


def _roteiro(nome_modulo: str, email: str, raiz: str) -> None:
    # O AppTest roda o corpo desta função como um script à parte: ela não enxerga __file__
    # nem as variáveis deste módulo. Por isso a raiz chega como argumento e tudo é importado aqui.
    import importlib
    import sys

    if raiz not in sys.path:
        sys.path.insert(0, raiz)

    import streamlit as st

    from app import estado

    if "token" not in st.session_state:
        srv = estado.servicos()
        resposta = srv.orq.fazer_login(email, srv.cfg.SENHA_DEMO)
        estado.entrar(resposta["token"])  # igual à tela de entrada
    importlib.import_module(f"app.paginas.{nome_modulo}").pagina()


def abrir_pagina(nome_modulo: str, email: str) -> AppTest:
    """AppTest da página `app.paginas.<nome_modulo>`, logado como `email`, já executado."""
    at = AppTest.from_function(_roteiro, args=(nome_modulo, email, RAIZ), default_timeout=30)
    return at.run()
