"""Testes do encurtamento dos comandos no painel Bastidores (função pura, sem Streamlit rodando)."""
from app.componentes.bastidores import MAX_COMANDO, encurtar

MARCA = " ✗ falhou"


def test_comando_curto_fica_igual():
    assert encurtar("GET x") == "GET x" and encurtar("GET x" + MARCA) == "GET x" + MARCA


def test_comando_longo_e_cortado_com_reticencias():
    curto = encurtar("M" * 300)
    assert len(curto) == MAX_COMANDO and curto.endswith("…")


def test_comando_longo_que_falhou_mantem_a_marca():
    curto = encurtar("MATCH " + "x" * 300 + MARCA)
    assert curto.endswith("…" + MARCA) and len(curto) == MAX_COMANDO + len(MARCA)
