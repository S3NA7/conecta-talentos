"""Tela 3 — Rede de Conexões & Busca de Mentores (Neo4j).

É a tela que mostra o que só um banco de grafos faz bem: caminhos entre pessoas, graus de
separação, "amigos de amigos" e recomendações que levam em conta a posição de cada um na rede.
"""
import streamlit as st

from app import estado
from app.componentes import grafo
from app.componentes.cartoes import cartao_pessoa, texto_seguro
from app.servicos.erros import BancoIndisponivel

AVISO_NEO4J = "A rede de conexões está indisponível no momento (Neo4j fora do ar)."
CHAVE_RECADO = "rede_recado"  # mensagem guardada para mostrar depois do st.rerun()


# ---------- textos ----------

def _primeiro_nome(nome: str) -> str:
    partes = (nome or "").split()
    return partes[0] if partes else nome


def _graus(n: int) -> str:
    return "1 grau" if n == 1 else f"{n} graus"


def _juntar(itens: list[str]) -> str:
    """["A"] → "A"; ["A", "B"] → "A e B"; ["A", "B", "C"] → "A, B e C"."""
    if len(itens) <= 1:
        return "".join(itens)
    return ", ".join(itens[:-1]) + " e " + itens[-1]


def texto_caminho(caminho: dict) -> str:
    """"Você → Camila → Kleber → Patrícia → Sabrina: 4 graus"."""
    nomes = ["Você"] + [_primeiro_nome(p["nome"]) for p in caminho["pessoas"][1:]]
    return f"{' → '.join(nomes)}: {_graus(caminho['graus'])}"


def porque_do_mentor(mentor: dict) -> str:
    """O motivo da recomendação, em frases, a partir do que o grafo devolveu."""
    dominios = [f"{h['nome']} (nível {h['nivel']})"
                for h in sorted(mentor["habilidades"], key=lambda h: (-h["nivel"], h["nome"]))]
    frases = [f"Domina {_juntar(dominios)}."]
    graus = mentor.get("graus")
    if graus is None:
        frases.append("Fora da sua rede.")
    elif graus == 1:
        frases.append("Já é sua conexão direta.")
    elif mentor.get("via"):
        frases.append(f"Está a {_graus(graus)} de você, via {_primeiro_nome(mentor['via'])}.")
    else:
        frases.append(f"Está a {_graus(graus)} de você.")
    em_comum = mentor.get("em_comum") or 0
    if em_comum == 1:
        frases.append("1 conexão em comum.")
    elif em_comum > 1:
        frases.append(f"{em_comum} conexões em comum.")
    return " ".join(frases)


# ---------- ações (botões) ----------

def _recado_depois(sucesso: str, avisos: list[str]) -> None:
    """Guarda a confirmação e os avisos e recarrega a tela para as listas se atualizarem."""
    st.session_state[CHAVE_RECADO] = {"sucesso": sucesso, "avisos": avisos}
    st.rerun()


def _mostrar_recado() -> None:
    recado = st.session_state.pop(CHAVE_RECADO, None)
    if recado:
        st.toast(recado["sucesso"], icon="✅")
        estado.mostrar_avisos(recado["avisos"])


def _botao_conectar(srv, eu: str, pessoa: dict, chave: str, onde=st) -> None:
    if onde.button("Conectar", key=chave, icon="🤝", width="stretch"):
        resultado = estado.tentar(srv.orq.conectar, eu, pessoa["id"])
        if resultado is not None:
            nome = texto_seguro(_primeiro_nome(pessoa["nome"]))  # o aviso (st.toast) aceita Markdown
            if resultado["criada"]:
                sucesso = f"Agora você e {nome} estão conectados."
            else:
                sucesso = f"Você e {nome} já estavam conectados."
            _recado_depois(sucesso, resultado["avisos"])


def _botao_mentoria(srv, eu: str, pessoa: dict, onde=st) -> None:
    if onde.button("Pedir mentoria", key=f"mentoria_{pessoa['id']}", icon="🎓", width="stretch"):
        resultado = estado.tentar(srv.orq.pedir_mentoria, eu, pessoa["id"])
        if resultado is not None:
            _recado_depois(f"Pedido de mentoria enviado para {texto_seguro(_primeiro_nome(pessoa['nome']))}.",
                           resultado["avisos"])


# ---------- aba 1: graus de separação ----------

def _aba_graus(srv, eu: str, rede: dict) -> None:
    st.markdown("Escolha alguém e veja **por quem** a sua rede chega até essa pessoa.")
    pessoas = {u["_id"]: u["nome"] for u in srv.mongo.listar_usuarios() if u["_id"] != eu}
    destino = st.selectbox("Pessoa", options=list(pessoas), format_func=lambda i: pessoas.get(i, i),
                           index=None, placeholder="Digite ou escolha um nome…", key="sep_destino")
    if destino is None:
        return

    # grupo próprio no Bastidores (com as leituras à mostra): o shortestPath não se perde no
    # meio das leituras das outras abas
    with srv.registro.acao("Graus de separação", leitura=True):
        caminho = srv.neo4j.menor_caminho(eu, destino)
    if caminho is None:
        st.info("Não há caminho entre vocês em até 6 conexões.")
        return

    st.markdown(f"#### {texto_seguro(texto_caminho(caminho))}")

    # o caminho é desenhado por cima da minha rede de 2 graus; quem está além do 2º grau
    # entra no desenho só por fazer parte do caminho (com o grau = posição no caminho)
    ids_caminho = [p["id"] for p in caminho["pessoas"]]
    nos = list(rede["nos"])
    presentes = {no["id"] for no in nos}
    for posicao, p in enumerate(caminho["pessoas"]):
        if p["id"] not in presentes:
            nos.append({**p, "grau": posicao})
    arestas = list(rede["arestas"]) + [list(par) for par in zip(ids_caminho, ids_caminho[1:])]
    grafo.desenhar(nos, arestas, destaque=ids_caminho)

    linhas = []
    for posicao, p in enumerate(caminho["pessoas"]):
        quem = "Você" if posicao == 0 else texto_seguro(p["nome"])
        titulo = f" — {texto_seguro(p['titulo'])}" if p.get("titulo") else ""
        linhas.append(f"{posicao + 1}. **{quem}**{titulo}")
    st.markdown("\n".join(linhas))


# ---------- aba 2: minha rede ----------

def _aba_minha_rede(srv, eu: str, rede: dict) -> None:
    por_grau = srv.neo4j.rede_por_grau(eu, 3)
    contagem = {g: sum(1 for p in por_grau if p["grau"] == g) for g in (1, 2, 3)}
    c1, c2, c3 = st.columns(3)
    c1.metric("1º grau", contagem[1], help="Suas conexões diretas.", border=True)
    c2.metric("2º grau", contagem[2], help="Conexões das suas conexões.", border=True)
    c3.metric("3º grau", contagem[3], help="Um passo além do 2º grau.", border=True)

    if contagem[1] == 0:
        st.info("Você ainda não tem conexões. Encontre alguém em **Buscar mentores** ou entre os "
                "colegas de empresa abaixo; a partir da primeira conexão, a aba "
                "**Talvez você conheça** passa a sugerir pessoas para você.")
    else:
        grafo.desenhar(rede["nos"], rede["arestas"])
        for grau, titulo in ((1, "1º grau — conexões diretas"), (2, "2º grau — conexões das suas conexões")):
            pessoas = [p for p in por_grau if p["grau"] == grau]
            with st.expander(f"{titulo} ({len(pessoas)})", expanded=(grau == 1)):
                if not pessoas:
                    st.caption("Ninguém neste grau.")
                for p in pessoas:
                    titulo_p = f" — {texto_seguro(p['titulo'])}" if p.get("titulo") else ""
                    st.markdown(f"- **{texto_seguro(p['nome'])}**{titulo_p}")

    st.subheader("Colegas e ex-colegas de empresa")
    colegas = {}
    for c in srv.neo4j.colegas_de_empresa(eu):  # uma linha por pessoa e empresa
        colegas.setdefault(c["id"], {**c, "empresas": []})["empresas"].append(c["empresa"])
    if not colegas:
        st.caption("Ninguém do seu histórico profissional está na plataforma ainda.")
    for c in colegas.values():
        titulo_c = f" — {texto_seguro(c['titulo'])}" if c.get("titulo") else ""
        st.markdown(f"- **{texto_seguro(c['nome'])}**{titulo_c} · "
                    f"{texto_seguro(_juntar(c['empresas']))}")


# ---------- aba 3: buscar mentores ----------

def _aba_mentores(srv, eu: str, conectados: set[str]) -> None:
    catalogo = [h["nome"] for h in srv.neo4j.listar_habilidades()]
    salvos = srv.neo4j.interesses_de(eu)
    escolhidas = st.multiselect("O que você quer aprender?", options=catalogo,
                                default=[h for h in salvos if h in catalogo],
                                placeholder="Escolha uma ou mais habilidades", key="mentor_habilidades")
    if st.button("Salvar e buscar", key="mentor_buscar", type="primary", icon="🔍"):
        # o botão só grava os interesses; a lista abaixo é sempre calculada a partir do que está
        # salvo no grafo, então ela continua a mesma nas próximas interações da tela.
        # definir_interesses não devolve nada; o "or True" faz o tentar() devolver True no
        # sucesso (e None quando a gravação é recusada)
        if estado.tentar(lambda: srv.orq.definir_interesses(eu, escolhidas) or True):
            st.toast("Interesses salvos.", icon="✅")
            salvos = srv.neo4j.interesses_de(eu)

    # recomendação a partir dos interesses salvos (QUER_APRENDER)
    mentores = srv.neo4j.recomendar_mentores(eu, salvos)
    if not salvos:
        st.info("Escolha as habilidades que você quer aprender e clique em **Salvar e buscar**.")
    elif not mentores:
        st.info("Nenhum mentor com nível 4 ou 5 nessas habilidades por enquanto. "
                "Tente outras habilidades.")
    else:
        st.caption("Ordenados pela pontuação: habilidades que a pessoa ensina, nível, "
                   "conexões em comum e proximidade na rede.")
    for m in mentores:
        with st.container(border=True):
            esquerda, direita = st.columns([3, 1], vertical_alignment="center")
            with esquerda:
                cartao_pessoa(m, extra=texto_seguro(porque_do_mentor(m)))
            with direita:
                pontos = f"{m['pontuacao']:.1f}".replace(".", ",")
                st.markdown(f"**Pontuação {pontos}**")
                if m["id"] not in conectados:
                    _botao_conectar(srv, eu, m, f"conectar_{m['id']}")
                _botao_mentoria(srv, eu, m)

    with st.expander("Quem domina uma habilidade?"):
        habilidade = st.selectbox("Habilidade", options=catalogo, index=None,
                                  placeholder="Escolha uma habilidade", key="quem_domina")
        if habilidade:
            pessoas = srv.neo4j.pessoas_com_habilidade(habilidade)
            if not pessoas:
                st.caption("Ninguém cadastrou essa habilidade ainda.")
            for p in pessoas:
                titulo_p = f" — {texto_seguro(p['titulo'])}" if p.get("titulo") else ""
                st.markdown(f"- **{texto_seguro(p['nome'])}**{titulo_p} · nível {p['nivel']}")


# ---------- aba 4: talvez você conheça ----------

def _aba_sugestoes(srv, eu: str) -> None:
    sugestoes = srv.neo4j.sugerir_conexoes(eu)
    if not sugestoes:
        st.info("Ainda não há sugestões: elas vêm das conexões das suas conexões. "
                "Que tal procurar alguém em **Buscar mentores**?")
        return
    st.caption("Pessoas conectadas a quem você já conhece.")
    for s in sugestoes:
        with st.container(border=True):
            esquerda, direita = st.columns([3, 1], vertical_alignment="center")
            em_comum = "1 conexão em comum" if s["em_comum"] == 1 else f"{s['em_comum']} conexões em comum"
            with esquerda:
                cartao_pessoa(s, extra=texto_seguro(f"{em_comum}: {', '.join(s['amigos'])}"))
            # chave diferente da aba de mentores: a mesma pessoa pode aparecer nas duas abas
            # e o Streamlit não aceita dois botões com a mesma chave
            _botao_conectar(srv, eu, s, f"conectar_sugestao_{s['id']}", onde=direita)


# ---------- página ----------

def _protegido(funcao, *args) -> None:
    """Roda uma aba; banco fora do ar vira mensagem na tela em vez de exceção."""
    try:
        funcao(*args)
    except BancoIndisponivel as erro:
        if erro.banco == "Neo4j":
            st.error(AVISO_NEO4J)
        else:
            st.error(f"{erro.banco} está fora do ar. Tente novamente em instantes.")


def pagina() -> None:
    st.title("🕸️ Rede & Mentores")
    st.caption("Sua rede de conexões, os graus de separação e a busca de mentores — tudo vindo do Neo4j.")
    usuario = estado.usuario_atual()
    if usuario is None:
        st.warning(estado.AVISO_SESSAO_EXPIRADA)
        return
    srv = estado.servicos()
    eu = usuario["id"]
    _mostrar_recado()

    # a primeira consulta também confirma que o Neo4j responde; se não, uma mensagem só
    try:
        rede = srv.neo4j.subgrafo_da_rede(eu, 2)
        conectados = set(srv.neo4j.ids_conexoes(eu))
    except BancoIndisponivel:
        st.error(AVISO_NEO4J)
        return

    aba_graus, aba_rede, aba_mentores, aba_sugestoes = st.tabs(
        ["🧭 Graus de separação", "🕸️ Minha rede", "🎓 Buscar mentores", "👋 Talvez você conheça"])
    with aba_graus:
        _protegido(_aba_graus, srv, eu, rede)
    with aba_rede:
        _protegido(_aba_minha_rede, srv, eu, rede)
    with aba_mentores:
        _protegido(_aba_mentores, srv, eu, conectados)
    with aba_sugestoes:
        _protegido(_aba_sugestoes, srv, eu)
