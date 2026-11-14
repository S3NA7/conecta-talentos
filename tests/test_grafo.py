"""Testes dos componentes visuais: HTML do grafo (pyvis) e tempo relativo dos cartões."""
import time

from app.componentes.cartoes import tempo_relativo
from app.componentes.grafo import montar_html

NOS = [{"id": "a", "nome": "Ana Lima", "titulo": "Dev", "grau": 0},
       {"id": "b", "nome": "João Sá", "titulo": "PO", "grau": 1}]


def test_html_funciona_sem_internet():
    h = montar_html(NOS, [["a", "b"]], destaque=["a", "b"])
    assert "jsdelivr" not in h and "cdnjs" not in h and "unpkg" not in h and "vis.Network" in h


def test_html_tem_os_nos_e_aceita_grafo_vazio():
    assert "Ana" in montar_html(NOS, [["a", "b"]]) and "João" in montar_html(NOS, [])
    assert isinstance(montar_html([], []), str)


def test_tempo_relativo():
    agora = time.time()
    assert tempo_relativo(agora - 20) == "agora" and tempo_relativo(agora - 300) == "há 5 min"
    assert tempo_relativo(agora - 3 * 3600) == "há 3 h" and tempo_relativo(agora - 2 * 86400) == "há 2 dias"
