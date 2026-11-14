"""Desenho da rede de conexões como grafo interativo (pyvis, que gera uma página com vis-network)."""
import json
import re

import streamlit as st
from pyvis.network import Network

# cores do grafo: "você" na cor de destaque do tema (.streamlit/config.toml), os graus em tons
# suaves bem diferentes entre si e o caminho numa cor forte que salta aos olhos no projetor
COR_VOCE = "#2457A6"
COR_GRAU = {1: "#9CC3F0", 2: "#B7E1C7"}
COR_LONGE = "#D9DEE5"  # 3º grau em diante (só aparece quando faz parte de um caminho)
COR_CAMINHO = "#E8590C"
COR_CAMINHO_BORDA = "#A93F06"
COR_ARESTA = "#B8C2CF"
COR_TEXTO = "#1C2430"

# Opções do vis-network. A física fica ligada (os nós se acomodam sozinhos e dá para arrastar),
# mas "stabilization" calcula o desenho antes de mostrar e o "damping" alto freia o movimento:
# assim os nós param em vez de ficarem flutuando para sempre.
# Atenção: o pyvis apaga os espaços deste texto, então nenhum valor pode ter espaço.
OPCOES = {
    "nodes": {"shape": "dot", "font": {"size": 18, "color": COR_TEXTO}, "borderWidth": 2},
    "edges": {"color": {"color": COR_ARESTA}, "width": 1.5, "smooth": False},
    "physics": {
        "barnesHut": {"gravitationalConstant": -6000, "springLength": 130, "springConstant": 0.04,
                      "damping": 0.4, "avoidOverlap": 0.2},
        "minVelocity": 0.75,
        "stabilization": {"enabled": True, "iterations": 300},
    },
    "interaction": {"hover": True, "tooltipDelay": 100},
}

# o pyvis aponta para o Bootstrap num CDN (não usamos nada dele); sem internet, essas duas tags
# só deixariam a página esperando. O <h1> vazio do título ocuparia espaço à toa.
_CDN = re.compile(r"<link[^>]*cdn\.jsdelivr\.net[^>]*>|<script[^>]*cdn\.jsdelivr\.net[^>]*>\s*</script>")
_TITULO_VAZIO = re.compile(r"<center>\s*<h1>\s*</h1>\s*</center>")
# linhas onde o pyvis grava os nós e as arestas em JSON (com os acentos como ã)
_DADOS = re.compile(r"(?:nodes|edges) = new vis\.DataSet\(.*?\);")
_ESCAPE_UNICODE = re.compile(r"\\u([0-9a-fA-F]{4})")
_CSS_EXTRA = ("<style>body{margin:0;}#mynetwork{border:none!important;}"
              ".vis-tooltip{font-family:sans-serif!important;font-size:15px!important;}</style>")


def _primeiro_nome(nome: str) -> str:
    partes = (nome or "").split()
    return partes[0] if partes else "?"


def _letra(achado: re.Match) -> str:
    # só letras não-ASCII (ã, é, ç...) voltam a ser o próprio caractere; < (<), & (&)
    # e afins continuam escapados, que é o que impede um nome de virar HTML/JS na página
    codigo = int(achado.group(1), 16)
    if codigo < 0x80 or 0xD800 <= codigo <= 0xDFFF or codigo in (0x2028, 0x2029):
        return achado.group(0)
    return chr(codigo)


def _acentos_legiveis(html: str) -> str:
    """Deixa os nomes com acento legíveis no HTML (só nas linhas de dados, não no código do vis)."""
    return _DADOS.sub(lambda m: _ESCAPE_UNICODE.sub(_letra, m.group(0)), html)


def montar_html(nos: list[dict], arestas: list, destaque: list[str] = (), altura: int = 460) -> str:
    """Página HTML completa (vis-network embutido, sem nada da internet) com o grafo.

    nos: [{"id", "nome", "titulo", "grau"}], grau 0 = você. arestas: [[id_a, id_b], ...].
    destaque: ids na ordem do caminho; esses nós e as arestas entre vizinhos do caminho
    ficam na cor de realce e mais grossos.
    """
    rede = Network(height=f"{altura}px", width="100%", bgcolor="#FFFFFF", font_color=COR_TEXTO,
                   cdn_resources="in_line")
    rede.set_options(json.dumps(OPCOES))

    no_caminho = set(destaque)
    ids = set()
    for no in nos:
        grau = no.get("grau")
        if grau == 0:
            fundo, tamanho = COR_VOCE, 30
        else:
            fundo, tamanho = COR_GRAU.get(grau, COR_LONGE), 18
        borda, espessura = fundo, 2
        if no["id"] in no_caminho:
            # você continua na sua cor (com borda de realce); os demais do caminho viram realce
            if grau != 0:
                fundo, tamanho = COR_CAMINHO, 24
            borda, espessura = COR_CAMINHO_BORDA, 4
        dica = no.get("nome") or ""
        if no.get("titulo"):
            dica += f" — {no['titulo']}"
        rede.add_node(no["id"], label=_primeiro_nome(no.get("nome")), title=dica, size=tamanho,
                      borderWidth=espessura,
                      color={"background": fundo, "border": borda,
                             "highlight": {"background": fundo, "border": COR_CAMINHO_BORDA},
                             "hover": {"background": fundo, "border": COR_CAMINHO_BORDA}})
        ids.add(no["id"])

    # pares vizinhos do caminho, sem sentido (a conexão é lida nos dois sentidos)
    trechos = {frozenset(par) for par in zip(destaque, list(destaque)[1:])}
    for a, b in arestas:
        if a not in ids or b not in ids:  # o pyvis recusa aresta para nó que não existe
            continue
        if frozenset((a, b)) in trechos:
            rede.add_edge(a, b, color=COR_CAMINHO, width=5)
        else:
            rede.add_edge(a, b)

    html = rede.generate_html()  # nunca show()/write_html(): gravam arquivo em cp1252 no Windows
    html = _CDN.sub("", html)
    html = _TITULO_VAZIO.sub("", html)
    html = _acentos_legiveis(html)
    return html.replace("</head>", _CSS_EXTRA + "</head>", 1)


def _item_legenda(cor: str, texto: str, linha: bool = False) -> str:
    if linha:
        simbolo = f'<span style="display:inline-block;width:26px;height:5px;background:{cor};' \
                  'border-radius:3px;vertical-align:middle;margin-right:6px;"></span>'
    else:
        simbolo = f'<span style="display:inline-block;width:14px;height:14px;background:{cor};' \
                  'border-radius:50%;vertical-align:middle;margin-right:6px;"></span>'
    return f'<span style="margin-right:18px;white-space:nowrap;">{simbolo}{texto}</span>'


def desenhar(nos: list[dict], arestas: list, destaque: list[str] = (), altura: int = 460) -> None:
    """Mostra o grafo na tela e, logo abaixo, a legenda das cores."""
    st.iframe(montar_html(nos, arestas, destaque, altura), height=altura + 20)
    itens = [_item_legenda(COR_VOCE, "Você"), _item_legenda(COR_GRAU[1], "1º grau (conexão direta)"),
             _item_legenda(COR_GRAU[2], "2º grau (conexão de conexão)")]
    if any(no.get("grau") not in (0, 1, 2) for no in nos):
        itens.append(_item_legenda(COR_LONGE, "3º grau ou mais"))
    if destaque:
        itens.append(_item_legenda(COR_CAMINHO, "caminho até a pessoa escolhida", linha=True))
    st.html('<div style="font-size:0.95rem;color:#3d4550;line-height:2;">'
            + "".join(itens)
            + '<br><span style="color:#5b6573;">Passe o mouse sobre uma pessoa para ver o nome '
              "completo e o cargo; arraste para reorganizar.</span></div>")
