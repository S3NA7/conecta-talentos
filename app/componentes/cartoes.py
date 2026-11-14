"""Cartão de pessoa, "há quanto tempo" e os textos seguros para Markdown, usados nas três telas."""
import re
import time
from datetime import datetime

import streamlit as st

_ESPECIAIS_MARKDOWN = re.compile(r"([\\`*_{}\[\]<>#|~])")


def texto_seguro(texto: str) -> str:
    """Escapa os caracteres que o Markdown interpretaria (um nome com * não vira itálico)."""
    return _ESPECIAIS_MARKDOWN.sub(r"\\\1", texto or "")


def texto_livre(texto: str) -> str:
    """Texto escrito pelo usuário pronto para st.markdown, sem virar formatação.

    Além do que texto_seguro escapa, cuida do que só é especial no começo da linha (listas
    "- " e "1. ", títulos sublinhados com "="), do "$" (o Streamlit desenharia fórmula) e
    das quebras de linha (no Markdown, uma quebra simples sumiria).
    """
    linhas = []
    for linha in (texto or "").split("\n"):
        linha = texto_seguro(linha).replace("$", "\\$")
        linha = re.sub(r"^(\s*)([-+=])", r"\1\\\2", linha)
        linha = re.sub(r"^(\s*\d+)([.)])", r"\1\\\2", linha)
        linhas.append(linha)
    return "  \n".join(linhas)


def tempo_relativo(quando) -> str:
    """"agora", "há 5 min", "há 3 h", "há 2 dias". Aceita datetime ou segundos desde a época."""
    if quando is None:
        return "nunca"
    if isinstance(quando, datetime):
        quando = quando.timestamp()
    segundos = max(0, time.time() - float(quando))
    if segundos < 60:
        return "agora"
    if segundos < 3600:
        return f"há {int(segundos // 60)} min"
    if segundos < 86400:
        return f"há {int(segundos // 3600)} h"
    dias = int(segundos // 86400)
    return "há 1 dia" if dias == 1 else f"há {dias} dias"


def cartao_pessoa(pessoa: dict, *, online: bool | None = None, extra: str = "") -> None:
    """Nome em negrito, bolinha de presença (se informada), título e uma linha extra opcional."""
    nome = f"**{texto_seguro(pessoa.get('nome'))}**"
    if online is True:
        nome += " &nbsp;🟢 online"
    elif online is False:
        nome += " &nbsp;⚪ offline"
    st.markdown(nome)
    if pessoa.get("titulo"):
        st.caption(texto_seguro(pessoa["titulo"]))
    if extra:
        st.markdown(extra)
