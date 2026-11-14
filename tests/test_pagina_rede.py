"""Testes da tela Rede & Mentores (Neo4j) com o AppTest do Streamlit."""
from tests.apoio import abrir_pagina


def test_pagina_abre_para_ana(dados_carregados):
    at = abrir_pagina("rede_mentores", "ana@exemplo.com")
    assert not at.exception and len(at.tabs) == 4


def test_caminho_ate_sabrina(dados_carregados):
    at = abrir_pagina("rede_mentores", "ana@exemplo.com")
    at.selectbox(key="sep_destino").select("u019").run()
    assert any("4 graus" in m.value for m in at.markdown)
    grupos = at.session_state["servicos"].registro.grupos(incluir_leituras=True)
    caminho = [g for g in grupos if g["acao"] == "Graus de separação"]
    assert caminho and "shortestPath" in caminho[0]["operacoes"][0]["comando"]


def test_sem_caminho_ate_jose(dados_carregados):
    at = abrir_pagina("rede_mentores", "ana@exemplo.com")
    at.selectbox(key="sep_destino").select("u030").run()
    assert any("Não há caminho" in i.value for i in at.info)


def test_mentores_e_conectar(dados_carregados):
    at = abrir_pagina("rede_mentores", "ana@exemplo.com")
    at.button(key="mentor_buscar").click().run()
    assert any("Camila Nóbrega" in m.value for m in at.markdown)
    at.button(key="conectar_u004").click().run()
    assert not at.exception and at.session_state["servicos"].neo4j.estao_conectados("u001", "u004")


def test_pagina_abre_para_quem_nao_tem_conexoes(dados_carregados):
    assert not abrir_pagina("rede_mentores", "jose@exemplo.com").exception
