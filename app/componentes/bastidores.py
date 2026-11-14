"""Painel "Bastidores": o que cada banco executou nas últimas ações, com o comando e o tempo."""
from html import escape

import streamlit as st

from app import estado

MAX_ACOES = 8
# caracteres visíveis; o texto inteiro aparece ao passar o mouse. 110 cabe o começo das
# consultas Cypher até o que importa (o shortestPath do caminho, o CREATE do conectar)
MAX_COMANDO = 110
MARCA_FALHA = " ✗ falhou"  # o sufixo que Registro.medir põe no comando que falhou

# uma cor fixa por banco, a mesma em toda a aplicação
CORES = {"MongoDB": "#00684A", "Redis": "#C6302B", "Neo4j": "#0B5CAD"}


def painel() -> None:
    registro = estado.servicos().registro
    with st.expander("🔎 Bastidores — o que cada banco fez"):
        esquerda, direita = st.columns([4, 1])
        incluir_leituras = esquerda.checkbox("mostrar também as leituras da tela", key="bastidores_leituras")
        if direita.button("limpar", key="bastidores_limpar", width="stretch"):
            registro.limpar()

        grupos = registro.grupos(incluir_leituras=incluir_leituras)[:MAX_ACOES]
        if not grupos:
            st.caption("Nenhuma ação registrada ainda. Faça algo na tela (publicar, conectar, "
                       "curtir…) e veja aqui os comandos enviados a cada banco.")
            return
        st.caption("A ação mais recente aparece primeiro; dentro dela, os comandos na ordem em que rodaram.")
        for grupo in grupos:
            st.html(_html_grupo(grupo))


def _html_grupo(grupo: dict) -> str:
    operacoes = grupo["operacoes"]
    hora = operacoes[0]["quando"].astimezone().strftime("%H:%M:%S")
    total = sum(o["ms"] for o in operacoes)
    linhas = "".join(_html_operacao(o) for o in operacoes)
    # etiqueta discreta: separa as leituras da tela das ações que o usuário fez
    etiqueta = ('<span style="font-weight:400;font-size:0.75rem;color:#5b6573;border:1px solid #c9ced6;'
                'border-radius:4px;padding:0 5px;margin-left:6px;vertical-align:middle;">leitura</span>'
                if grupo.get("leitura") else "")
    return (
        '<div style="margin:0 0 14px 0;">'
        f'<div style="font-size:1.05rem;font-weight:700;margin-bottom:4px;">{escape(grupo["acao"])}{etiqueta}'
        f'<span style="font-weight:400;color:#5b6573;font-size:0.9rem;"> · {hora} · '
        f'{len(operacoes)} comando(s) · {total:.0f} ms no total</span></div>'
        f'<table style="border-collapse:collapse;width:100%;">{linhas}</table></div>'
    )


def encurtar(comando: str) -> str:
    """Corta o comando em MAX_COMANDO caracteres (com "…"); a marca de falha nunca é cortada."""
    marca = MARCA_FALHA if comando.endswith(MARCA_FALHA) else ""
    base = comando[:len(comando) - len(marca)]
    if len(base) > MAX_COMANDO:
        base = base[:MAX_COMANDO - 1] + "…"
    return base + marca


def _html_operacao(op: dict) -> str:
    cor = CORES.get(op["banco"], "#555555")
    comando = op["comando"]
    curto = encurtar(comando)
    return (
        '<tr style="border-top:1px solid #e6e9ee;">'
        f'<td style="padding:5px 8px 5px 0;width:88px;"><span style="display:inline-block;min-width:76px;'
        f'text-align:center;background:{cor};color:#fff;border-radius:4px;padding:2px 6px;'
        f'font-weight:700;font-size:0.85rem;">{escape(op["banco"])}</span></td>'
        f'<td title="{escape(comando)}" style="padding:5px 8px;font-family:ui-monospace,Consolas,monospace;'
        f'font-size:0.95rem;overflow-wrap:anywhere;">{escape(curto)}</td>'
        f'<td style="padding:5px 0;text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums;'
        f'color:#3d4550;">{op["ms"]:.1f} ms</td></tr>'
    )
