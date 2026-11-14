"""Tela 1 — Feed & Perfil (MongoDB, com apoio do Redis e do Neo4j).

O feed e o perfil são documentos do MongoDB (posts com curtidas e comentários embutidos, anexos
no GridFS, perfil com experiências, formação e certificações). O Neo4j diz de quem são os posts
do feed e guarda habilidades e conexões; o Redis dá a bolinha de presença e o cache.
"""
import re

import streamlit as st

from app import estado
from app.componentes.cartoes import cartao_pessoa, tempo_relativo, texto_livre, texto_seguro
from app.servicos.erros import BancoIndisponivel

CHAVE_RECADO = "feed_recado"  # mensagem guardada para mostrar depois do st.rerun()
CHAVE_TAG = "feed_tag"        # tag escolhida em "Tags em alta" (None = feed completo)
AVISO_NEO4J_EDICAO = "Habilidades e mentoria estão indisponíveis agora (Neo4j fora do ar)."
NIVEIS_FORMACAO = ["Técnico", "Graduação", "Especialização", "MBA", "Mestrado", "Doutorado", "Curso livre"]
FORMATO_MES = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")  # "2021-03": o mesmo texto ISO usado no grafo


# ---------- textos ----------

def _mes(valor) -> str:
    """"2021-03" → "03/2021"; vazio/None → "atual"."""
    if not valor:
        return "atual"
    ano, _, mes = str(valor).partition("-")
    return f"{mes}/{ano}" if mes else ano


def _periodo_anos(inicio, fim) -> str:
    if inicio and fim:
        return f"{inicio}–{fim}"
    if inicio:
        return f"desde {inicio}"
    return ""


# ---------- confirmação depois do st.rerun() ----------

def _recado_depois(sucesso: str | None, avisos: list[str]) -> None:
    """Guarda a confirmação e os avisos e recarrega a tela para os dados se atualizarem."""
    st.session_state[CHAVE_RECADO] = {"sucesso": sucesso, "avisos": avisos}
    st.rerun()


def _mostrar_recado() -> None:
    recado = st.session_state.pop(CHAVE_RECADO, None)
    if recado:
        if recado["sucesso"]:
            st.toast(recado["sucesso"], icon="✅")
        estado.mostrar_avisos(recado["avisos"])


# ---------- aba 1: feed ----------

def _filtrar_tag(tag: str | None) -> None:
    # usado como on_click: roda antes da tela ser redesenhada, então não precisa de st.rerun()
    st.session_state[CHAVE_TAG] = tag


def _formulario_publicar(srv, eu: str) -> None:
    # clear_on_submit: depois de publicar, o formulário volta vazio
    with st.form("form_publicar", clear_on_submit=True, border=True):
        texto = st.text_area("Publicar", placeholder="O que você quer compartilhar com a sua rede?",
                             max_chars=1000, height=100, key="post_texto")
        tags_col, arquivo_col = st.columns(2)
        tags = tags_col.text_input("Tags (separadas por vírgula)", placeholder="nosql, carreira",
                                   key="post_tags")
        arquivo = arquivo_col.file_uploader("Anexo (imagem PNG/JPG ou PDF, até 5 MB)",
                                            type=["png", "jpg", "jpeg", "pdf"], key="post_arquivo")
        enviar = st.form_submit_button("Publicar", type="primary", icon="📤", key="post_publicar")
    if enviar:
        anexo = (arquivo.name, arquivo.type, arquivo.getvalue()) if arquivo is not None else None
        resultado = estado.tentar(srv.orq.publicar_post, eu, texto, tags.split(","), anexo)
        if resultado is not None:
            n = resultado["notificados"]
            if n == 0:
                sucesso = "Post publicado."
            else:
                sucesso = f"Post publicado. {'1 conexão foi notificada' if n == 1 else f'{n} conexões foram notificadas'}."
            _recado_depois(sucesso, resultado["avisos"])


def _mostrar_anexo(srv, post_id: str, posicao: int, anexo: dict) -> None:
    dados = srv.mongo.ler_anexo(anexo["arquivo_id"])  # MongoDB: GridFS
    nome = texto_seguro(anexo.get("nome") or "anexo")  # a legenda e o rótulo aceitam Markdown
    if dados is None:
        st.caption("📎 anexo indisponível")
    elif anexo.get("tipo", "").startswith("image/"):
        try:
            st.image(dados, width=420, caption=nome)
        except Exception:
            # bytes que não formam uma imagem (gravados sem passar pela validação do
            # orquestrador) não podem derrubar a tela de quem tem o post no feed
            st.caption("📎 anexo indisponível")
    else:
        st.download_button(f"Baixar {nome}", data=dados,
                           file_name=anexo.get("nome") or "anexo.pdf",
                           mime=anexo.get("tipo") or "application/octet-stream",
                           icon="📄", key=f"baixar_{post_id}_{posicao}")


def _post(srv, eu: str, post: dict) -> None:
    pid = post["_id"]
    with st.container(border=True):
        autor, quando = st.columns([4, 1])
        with autor:
            cartao_pessoa({"nome": post["autor"]["nome"], "titulo": post["autor"].get("titulo")},
                          online=post.get("autor_online", False))
        quando.caption(tempo_relativo(post.get("criado_em")))

        st.markdown(texto_livre(post["texto"]))
        if post.get("tags"):
            st.caption(" ".join(texto_seguro(f"#{t}") for t in post["tags"]))
        for posicao, anexo in enumerate(post.get("anexos", [])):
            _mostrar_anexo(srv, pid, posicao, anexo)

        curtidas = post.get("curtidas", [])
        eu_curti = eu in curtidas
        if st.button(f"👍 {len(curtidas)}", key=f"curtir_{pid}", type="primary" if eu_curti else "secondary",
                     help="Descurtir" if eu_curti else "Curtir"):
            resultado = estado.tentar(srv.orq.curtir_post, eu, pid)
            if resultado is not None:
                _recado_depois(None, resultado["avisos"])

        comentarios = post.get("comentarios", [])
        rotulo = "1 comentário" if len(comentarios) == 1 else f"{len(comentarios)} comentários"
        with st.expander(f"💬 {rotulo}"):
            for c in comentarios:
                st.markdown(f"**{texto_seguro(c.get('autor_nome'))}** · {tempo_relativo(c.get('criado_em'))}  \n"
                            f"{texto_livre(c.get('texto'))}")
            with st.form(f"form_coment_{pid}", clear_on_submit=True, border=False):
                texto = st.text_input("Comentar", placeholder="Escreva um comentário…", max_chars=500,
                                      key=f"coment_{pid}", label_visibility="collapsed")
                enviar = st.form_submit_button("Comentar", key=f"coment_enviar_{pid}")
            if enviar:
                resultado = estado.tentar(srv.orq.comentar_post, eu, pid, texto)
                if resultado is not None:
                    _recado_depois("Comentário publicado.", resultado["avisos"])


def _tags_em_alta(srv) -> None:
    st.subheader("🔥 Tags em alta")
    resultado = srv.orq.tags_em_alta()
    if not resultado["tags"]:
        st.caption("Nenhuma tag ainda.")
    escolhida = st.session_state.get(CHAVE_TAG)
    for item in resultado["tags"]:
        tag = item["tag"]
        st.button(f"{texto_seguro('#' + tag)} · {item['total']}", key=f"tag_{tag}", width="stretch",
                  type="primary" if tag == escolhida else "secondary",
                  on_click=_filtrar_tag, args=(tag,))
    if resultado["do_cache"]:
        st.caption("cache HIT: lista lida do Redis")
    else:
        st.caption("cache MISS: calculada agora no MongoDB e guardada no Redis por 60 s")


def _aba_feed(srv, eu: str) -> None:
    coluna_feed, coluna_tags = st.columns([3, 1], gap="large")
    with coluna_tags:
        _tags_em_alta(srv)
    with coluna_feed:
        _formulario_publicar(srv, eu)
        tag = st.session_state.get(CHAVE_TAG)
        if tag:
            filtro, limpar = st.columns([3, 1], vertical_alignment="center")
            filtro.markdown(f"Mostrando só os posts com **{texto_seguro('#' + tag)}**")
            limpar.button("Limpar filtro", key="feed_limpar_tag", icon="✖️", width="stretch",
                          on_click=_filtrar_tag, args=(None,))

        feed = srv.orq.montar_feed(eu, tag=tag)
        estado.mostrar_avisos(feed["avisos"])
        if not feed["posts"]:
            if tag:
                st.info("Nenhum post da sua rede com essa tag.")
            else:
                st.info("Seu feed ainda está vazio. Publique algo acima ou conecte-se a outras "
                        "pessoas na tela **Rede & Mentores** para ver os posts delas aqui.")
        for post in feed["posts"]:
            _post(srv, eu, post)


# ---------- aba 2: perfil ----------

def _bloco_experiencias(perfil: dict) -> None:
    st.markdown("#### Experiência")
    experiencias = sorted(perfil.get("experiencias", []), key=lambda e: e.get("inicio") or "", reverse=True)
    if not experiencias:
        st.caption("Nenhuma experiência cadastrada.")
    for e in experiencias:
        st.markdown(f"**{texto_seguro(e.get('cargo'))}** · {texto_seguro(e.get('empresa'))}  \n"
                    f"{_mes(e.get('inicio'))} – {_mes(e.get('fim'))}")
        if e.get("descricao"):
            st.caption(texto_livre(e["descricao"]))


def _bloco_formacao(perfil: dict) -> None:
    st.markdown("#### Formação")
    if not perfil.get("formacao"):
        st.caption("Nenhuma formação cadastrada.")
    for f in perfil.get("formacao", []):
        detalhes = " · ".join(x for x in (texto_seguro(f.get("nivel")), _periodo_anos(f.get("inicio"), f.get("fim"))) if x)
        st.markdown(f"**{texto_seguro(f.get('curso'))}** — {texto_seguro(f.get('instituicao'))}  \n{detalhes}")


def _bloco_certificacoes(perfil: dict) -> None:
    st.markdown("#### Certificações")
    if not perfil.get("certificacoes"):
        st.caption("Nenhuma certificação cadastrada.")
    for c in perfil.get("certificacoes", []):
        ano = f" ({c['ano']})" if c.get("ano") else ""
        st.markdown(f"**{texto_seguro(c.get('nome'))}** — {texto_seguro(c.get('emissor'))}{ano}")


def _periodo_grafo(trabalho: dict) -> str:
    """Período como está no grafo: "desde 2021-03" (emprego atual) ou "2016-02 a 2020-12"."""
    if trabalho.get("ate"):
        return f"{trabalho['desde']} a {trabalho['ate']}"
    return f"desde {trabalho['desde']}"


def _bloco_grafo(dados: dict) -> None:
    """Habilidades, empresas e interesses: vêm ao vivo do Neo4j."""
    st.markdown("#### Habilidades")
    if not dados["habilidades"]:
        st.caption("Nenhuma habilidade cadastrada.")
    for h in dados["habilidades"]:
        st.progress(h["nivel"] / 5, text=f"{texto_seguro(h['nome'])} · nível {h['nivel']} de 5")
    st.markdown("#### Empresas (grafo)")
    if not dados["trabalhos"]:
        st.caption("Nenhuma empresa no histórico.")
    for t in dados["trabalhos"]:
        st.markdown(f"**{texto_seguro(t['empresa'])}** · {texto_seguro(t.get('setor'))} · "
                    f"{texto_seguro(t.get('cargo'))} · {_periodo_grafo(t)}")
    st.caption("TRABALHA_EM: Neo4j")
    st.markdown("#### Quer aprender")
    if dados["interesses"]:
        st.markdown(" · ".join(texto_seguro(i) for i in dados["interesses"]))
    else:
        st.caption("Nenhum interesse cadastrado.")
    st.caption("habilidades e conexões: Neo4j")


def _aba_perfil(srv, eu: str) -> None:
    pessoas = {u["_id"]: u["nome"] for u in srv.mongo.listar_usuarios()}
    opcoes = list(pessoas)
    escolhido = st.selectbox("Ver perfil de", options=opcoes, index=opcoes.index(eu) if eu in opcoes else 0,
                             format_func=lambda i: f"{pessoas.get(i, i)} (você)" if i == eu else pessoas.get(i, i),
                             key="perfil_de")
    if escolhido is None:
        return
    dados = estado.tentar(srv.orq.abrir_perfil, escolhido)
    if dados is None:
        return
    perfil = dados["perfil"]
    grafo_ok = dados["habilidades"] is not None

    # selo "Mentor": a disponibilidade para mentoria só existe no grafo
    pessoa_grafo = None
    if grafo_ok:
        try:
            pessoa_grafo = srv.neo4j.buscar_pessoa(escolhido)
        except BancoIndisponivel:
            grafo_ok = False

    with st.container(border=True):
        cabecalho, numeros = st.columns([3, 1], vertical_alignment="center")
        with cabecalho:
            st.markdown(f"### {texto_seguro(perfil.get('nome'))}")
            st.markdown(texto_seguro(perfil.get("titulo")))
            local = perfil.get("localizacao") or {}
            onde = ", ".join(x for x in (local.get("cidade"), local.get("estado")) if x)
            presenca = "🟢 online agora" if dados["online"] else "⚪ offline"
            st.caption(" · ".join(x for x in (texto_seguro(onde) if onde else "", presenca) if x))
            if pessoa_grafo and pessoa_grafo.get("mentor"):
                anos = pessoa_grafo.get("anos_experiencia")
                st.badge(f"Mentor{f' · {anos} anos de experiência' if anos else ''}", icon="🎓", color="green")
        with numeros:
            total = dados["total_conexoes"]
            st.metric("Conexões", total if total is not None else "—", border=True)

    if perfil.get("resumo"):
        st.markdown("#### Resumo")
        st.markdown(texto_livre(perfil["resumo"]))

    esquerda, direita = st.columns([3, 2], gap="large")
    with esquerda:
        _bloco_experiencias(perfil)
        _bloco_formacao(perfil)
        _bloco_certificacoes(perfil)
        origem = "do cache Redis" if dados["do_cache"] else "lido agora"
        st.caption(f"perfil: MongoDB ({origem}) · presença: Redis")
    with direita:
        if grafo_ok:
            _bloco_grafo(dados)
        else:
            st.markdown("#### Habilidades")
            estado.mostrar_avisos(dados["avisos"] or ["Habilidades e conexões estão indisponíveis agora (Neo4j fora do ar)."])


# ---------- aba 3: editar meu perfil ----------

def _editar_dados_basicos(srv, eu: str, perfil: dict) -> None:
    st.markdown("#### Dados básicos")
    st.markdown(f"**{texto_seguro(perfil.get('nome'))}**")
    st.caption("O nome não pode ser alterado aqui: ele é copiado em posts, comentários, "
               "notificações e no grafo.")
    local = perfil.get("localizacao") or {}
    with st.form("form_dados"):
        titulo = st.text_input("Título profissional", value=perfil.get("titulo", ""), max_chars=80, key="ed_titulo")
        resumo = st.text_area("Resumo", value=perfil.get("resumo", ""), max_chars=1000, key="ed_resumo")
        c1, c2 = st.columns([3, 1])
        cidade = c1.text_input("Cidade", value=local.get("cidade", ""), key="ed_cidade")
        uf = c2.text_input("Estado", value=local.get("estado", ""), max_chars=2, key="ed_estado")
        salvar = st.form_submit_button("Salvar dados básicos", type="primary", key="ed_salvar")
    if salvar:
        # editar_dados_basicos não devolve nada; o "or True" faz o tentar() devolver True no sucesso
        if estado.tentar(lambda: srv.orq.editar_dados_basicos(eu, titulo=titulo, resumo=resumo,
                                                              cidade=cidade, estado=uf) or True):
            _recado_depois("Dados básicos salvos.", [])


def _editar_experiencias(srv, eu: str, perfil: dict) -> None:
    st.markdown("#### Experiências")
    st.caption("Gravadas no MongoDB (a experiência completa) e no Neo4j (TRABALHA_EM).")
    experiencias = sorted(perfil.get("experiencias", []), key=lambda e: e.get("inicio") or "", reverse=True)
    for e in experiencias:
        texto, botao = st.columns([5, 1], vertical_alignment="center")
        texto.markdown(f"**{texto_seguro(e.get('cargo'))}** · {texto_seguro(e.get('empresa'))} · "
                       f"{_mes(e.get('inicio'))} – {_mes(e.get('fim'))}")
        chave = f"exp_remover_{e.get('empresa')}|{e.get('cargo')}|{e.get('inicio')}"
        if botao.button("Remover", key=chave, icon="🗑️", width="stretch"):
            if estado.tentar(lambda: srv.orq.remover_experiencia(eu, e) or True):
                _recado_depois("Experiência removida.", [])
    with st.form("form_exp", clear_on_submit=True):
        st.markdown("**Adicionar experiência**")
        c1, c2 = st.columns(2)
        empresa = c1.text_input("Empresa", key="exp_empresa")
        cargo = c2.text_input("Cargo", key="exp_cargo")
        c3, c4 = st.columns(2)
        inicio = c3.text_input("Início (AAAA-MM)", placeholder="2024-03", key="exp_inicio")
        fim = c4.text_input("Fim (AAAA-MM, vazio se é o emprego atual)", placeholder="", key="exp_fim")
        descricao = st.text_area("Descrição", max_chars=500, key="exp_descricao")
        adicionar = st.form_submit_button("Adicionar experiência", icon="➕", key="exp_adicionar")
    if adicionar:
        inicio, fim = inicio.strip(), fim.strip()
        # início vazio é recusado pelo orquestrador; aqui só se confere o formato do que veio
        if (inicio and not FORMATO_MES.match(inicio)) or (fim and not FORMATO_MES.match(fim)):
            st.error("Use o formato AAAA-MM nas datas, por exemplo 2024-03.")
            return
        exp = {"empresa": empresa, "cargo": cargo, "inicio": inicio, "fim": fim, "descricao": descricao}
        if estado.tentar(lambda: srv.orq.adicionar_experiencia(eu, exp) or True):
            _recado_depois("Experiência adicionada.", [])


def _editar_formacao(srv, eu: str, perfil: dict) -> None:
    st.markdown("#### Formação")
    # formação e certificação não têm chave única no banco (dá para cadastrar a mesma duas
    # vezes); por isso a chave do botão leva a posição na lista, além dos campos do item
    for i, f in enumerate(perfil.get("formacao", [])):
        texto, botao = st.columns([5, 1], vertical_alignment="center")
        periodo = _periodo_anos(f.get("inicio"), f.get("fim"))
        texto.markdown(f"**{texto_seguro(f.get('curso'))}** — {texto_seguro(f.get('instituicao'))}"
                       f"{' · ' + periodo if periodo else ''}")
        chave = f"formacao_remover_{i}_{f.get('instituicao')}|{f.get('curso')}|{f.get('inicio')}"
        if botao.button("Remover", key=chave, icon="🗑️", width="stretch"):
            # f é o item exatamente como está no Mongo, então o $pull acha o mesmo
            if estado.tentar(lambda: srv.orq.remover_item_perfil(eu, "formacao", f) or True):
                _recado_depois("Formação removida.", [])
    with st.form("form_formacao", clear_on_submit=True):
        st.markdown("**Adicionar formação**")
        c1, c2 = st.columns(2)
        instituicao = c1.text_input("Instituição", key="formacao_instituicao")
        curso = c2.text_input("Curso", key="formacao_curso")
        c3, c4, c5 = st.columns(3)
        nivel = c3.selectbox("Nível", NIVEIS_FORMACAO, index=1, key="formacao_nivel")
        inicio = c4.number_input("Ano de início", min_value=1950, max_value=2100, value=None, step=1,
                                 key="formacao_inicio")
        fim = c5.number_input("Ano de conclusão (vazio se em andamento)", min_value=1950, max_value=2100,
                              value=None, step=1, key="formacao_fim")
        adicionar = st.form_submit_button("Adicionar formação", icon="➕", key="formacao_adicionar")
    if adicionar:
        if not instituicao.strip() or not curso.strip():
            st.error("Instituição e curso são obrigatórios.")
            return
        item = {"instituicao": instituicao.strip(), "curso": curso.strip(), "nivel": nivel,
                "inicio": int(inicio) if inicio is not None else None,
                "fim": int(fim) if fim is not None else None}
        if estado.tentar(lambda: srv.orq.adicionar_item_perfil(eu, "formacao", item) or True):
            _recado_depois("Formação adicionada.", [])


def _editar_certificacoes(srv, eu: str, perfil: dict) -> None:
    st.markdown("#### Certificações")
    for i, c in enumerate(perfil.get("certificacoes", [])):
        texto, botao = st.columns([5, 1], vertical_alignment="center")
        ano = f" ({c['ano']})" if c.get("ano") else ""
        texto.markdown(f"**{texto_seguro(c.get('nome'))}** — {texto_seguro(c.get('emissor'))}{ano}")
        chave = f"cert_remover_{i}_{c.get('nome')}|{c.get('emissor')}|{c.get('ano')}"
        if botao.button("Remover", key=chave, icon="🗑️", width="stretch"):
            if estado.tentar(lambda: srv.orq.remover_item_perfil(eu, "certificacoes", c) or True):
                _recado_depois("Certificação removida.", [])
    with st.form("form_cert", clear_on_submit=True):
        st.markdown("**Adicionar certificação**")
        c1, c2, c3 = st.columns([2, 2, 1])
        nome = c1.text_input("Nome", key="cert_nome")
        emissor = c2.text_input("Emissor", key="cert_emissor")
        ano = c3.number_input("Ano", min_value=1950, max_value=2100, value=None, step=1, key="cert_ano")
        adicionar = st.form_submit_button("Adicionar certificação", icon="➕", key="cert_adicionar")
    if adicionar:
        if not nome.strip() or not emissor.strip():
            st.error("Nome e emissor são obrigatórios.")
            return
        item = {"nome": nome.strip(), "emissor": emissor.strip(), "ano": int(ano) if ano is not None else None}
        if estado.tentar(lambda: srv.orq.adicionar_item_perfil(eu, "certificacoes", item) or True):
            _recado_depois("Certificação adicionada.", [])


def _editar_habilidades(srv, eu: str) -> None:
    st.markdown("#### Minhas habilidades")
    st.caption("Gravadas só no Neo4j (POSSUI_HABILIDADE, com o nível no relacionamento).")
    for h in srv.neo4j.habilidades_de(eu):
        texto, botao = st.columns([5, 1], vertical_alignment="center")
        texto.progress(h["nivel"] / 5, text=f"{texto_seguro(h['nome'])} · nível {h['nivel']} de 5")
        if botao.button("Remover", key=f"hab_remover_{h['nome']}", icon="🗑️", width="stretch"):
            if estado.tentar(lambda: srv.orq.remover_habilidade(eu, h["nome"]) or True):
                _recado_depois(f"Habilidade {h['nome']} removida.", [])
    catalogo = [h["nome"] for h in srv.neo4j.listar_habilidades()]
    with st.form("form_hab", clear_on_submit=True):
        st.markdown("**Adicionar ou atualizar habilidade**")
        c1, c2 = st.columns([2, 1])
        nome = c1.selectbox("Habilidade", catalogo, index=None, placeholder="Escolha uma habilidade",
                            key="hab_nome")
        nivel = c2.slider("Nível", min_value=1, max_value=5, value=3, key="hab_nivel")
        salvar = st.form_submit_button("Salvar habilidade", icon="💾", key="hab_salvar")
    if salvar:
        if nome is None:
            st.error("Escolha uma habilidade.")
            return
        if estado.tentar(lambda: srv.orq.definir_habilidade(eu, nome, int(nivel)) or True):
            _recado_depois(f"Habilidade {nome} salva com nível {nivel}.", [])


def _editar_mentoria(srv, eu: str) -> None:
    st.markdown("#### Mentoria")
    pessoa = srv.neo4j.buscar_pessoa(eu) or {}
    with st.form("form_mentoria"):
        mentor = st.checkbox("Disponível para mentoria", value=bool(pessoa.get("mentor")), key="ed_mentor")
        anos = st.number_input("Anos de experiência", min_value=0, max_value=60, step=1,
                               value=min(60, int(pessoa.get("anos_experiencia") or 0)), key="ed_anos")
        salvar = st.form_submit_button("Salvar mentoria", icon="🎓", key="ed_mentoria_salvar")
    if salvar:
        if estado.tentar(lambda: srv.orq.definir_mentoria(eu, mentor, int(anos)) or True):
            _recado_depois("Mentoria atualizada.", [])


def _aba_editar(srv, eu: str) -> None:
    # MongoDB direto (e não o cache): quem edita precisa ver o dado mais recente
    perfil = srv.mongo.buscar_usuario(eu)
    if perfil is None:
        st.error("Perfil não encontrado.")
        return
    esquerda, direita = st.columns(2, gap="large")
    with esquerda:
        _editar_dados_basicos(srv, eu, perfil)
        st.divider()
        _editar_experiencias(srv, eu, perfil)
    with direita:
        try:
            _editar_habilidades(srv, eu)
            st.divider()
            _editar_mentoria(srv, eu)
        except BancoIndisponivel:
            st.warning(AVISO_NEO4J_EDICAO)
        st.divider()
        _editar_formacao(srv, eu, perfil)
        st.divider()
        _editar_certificacoes(srv, eu, perfil)


# ---------- página ----------

def _protegido(funcao, *args) -> None:
    """Roda uma aba; banco fora do ar vira mensagem na tela em vez de exceção."""
    try:
        funcao(*args)
    except BancoIndisponivel as erro:
        st.error(f"{erro.banco} está fora do ar. Tente novamente em instantes.")


def pagina() -> None:
    st.title("📰 Feed & Perfil")
    st.caption("Os posts da sua rede e o seu perfil profissional — documentos do MongoDB, com "
               "a rede vinda do Neo4j e a presença e o cache vindos do Redis.")
    usuario = estado.usuario_atual()
    if usuario is None:
        st.warning(estado.AVISO_SESSAO_EXPIRADA)
        return
    srv = estado.servicos()
    eu = usuario["id"]
    st.session_state.setdefault(CHAVE_TAG, None)
    _mostrar_recado()

    aba_feed, aba_perfil, aba_editar = st.tabs(["📰 Feed", "👤 Perfil", "✏️ Editar meu perfil"])
    with aba_feed:
        _protegido(_aba_feed, srv, eu)
    with aba_perfil:
        _protegido(_aba_perfil, srv, eu)
    with aba_editar:
        _protegido(_aba_editar, srv, eu)
