"""Testes da tela Feed & Perfil (MongoDB, com apoio do Redis e do Neo4j) com o AppTest do Streamlit."""
from tests.apoio import abrir_pagina


def test_feed_da_ana_abre(dados_carregados):
    at = abrir_pagina("feed_perfil", "ana@exemplo.com")
    assert not at.exception and len(at.tabs) == 3


def test_publicar_pelo_formulario(dados_carregados):
    at = abrir_pagina("feed_perfil", "ana@exemplo.com")
    at.text_area(key="post_texto").set_value("Post do teste de tela")
    at.text_input(key="post_tags").set_value("#NoSQL, dados")
    at.button(key="post_publicar").click().run()
    sv = at.session_state["servicos"]
    p = sv.mongo.listar_posts(["u001"])[0]
    assert not at.exception and p["texto"] == "Post do teste de tela" and p["tags"] == ["nosql", "dados"]


def test_post_vazio_mostra_erro_e_nao_grava(dados_carregados):
    at = abrir_pagina("feed_perfil", "ana@exemplo.com")
    at.button(key="post_publicar").click().run()
    assert at.error and not at.exception


def test_editar_titulo_reflete_nos_dois_bancos(dados_carregados):
    at = abrir_pagina("feed_perfil", "ana@exemplo.com")
    at.text_input(key="ed_titulo").set_value("Analista de Dados Pleno")
    at.button(key="ed_salvar").click().run()
    sv = at.session_state["servicos"]
    assert sv.mongo.buscar_usuario("u001")["titulo"] == sv.neo4j.buscar_pessoa("u001")["titulo"] == "Analista de Dados Pleno"


def test_perfil_de_outra_pessoa(dados_carregados):
    at = abrir_pagina("feed_perfil", "ana@exemplo.com")
    at.selectbox(key="perfil_de").select("u004").run()
    assert not at.exception and any("Diego Farias" in m.value for m in at.markdown)
    # bloco do grafo: o histórico TRABALHA_EM, com o período no formato do grafo
    assert any("DataNorte" in m.value and "2012-01 a 2018-06" in m.value for m in at.markdown)


def test_feed_vazio_para_quem_nao_tem_conexoes(dados_carregados):
    at = abrir_pagina("feed_perfil", "jose@exemplo.com")
    assert not at.exception and at.info


# ---------- testes a mais desta tarefa ----------

def test_anexo_que_nao_e_imagem_nao_derruba_a_tela(dados_carregados):
    at = abrir_pagina("feed_perfil", "ana@exemplo.com")
    sv = at.session_state["servicos"]
    # grava direto no Mongo, sem passar pela validação do orquestrador
    anexo = sv.mongo.salvar_anexo("lixo.png", "image/png", b"isto nao e uma imagem")
    sv.mongo.criar_post({"id": "u001", "nome": "Ana Beatriz Lima", "titulo": "Analista"},
                        "post com anexo quebrado", [], [anexo])
    at.run()
    assert not at.exception
    assert any("anexo indisponível" in c.value for c in at.caption)

def test_bastidores_mostra_publicar_como_ultima_acao(dados_carregados):
    at = abrir_pagina("feed_perfil", "ana@exemplo.com")
    at.text_area(key="post_texto").set_value("Post para os bastidores")
    at.button(key="post_publicar").click().run()
    assert not at.exception
    assert at.session_state["servicos"].registro.grupos()[0]["acao"] == "Publicar post"


def test_curtir_e_comentar(dados_carregados):
    at = abrir_pagina("feed_perfil", "ana@exemplo.com")
    sv = at.session_state["servicos"]
    post_id = sv.mongo.listar_posts(sv.neo4j.ids_conexoes("u001"))[0]["_id"]  # post de uma conexão
    at.button(key=f"curtir_{post_id}").click().run()
    assert not at.exception and "u001" in sv.mongo.buscar_post(post_id)["curtidas"]

    at.text_input(key=f"coment_{post_id}").set_value("Comentário do teste de tela")
    at.button(key=f"coment_enviar_{post_id}").click().run()
    comentarios = sv.mongo.buscar_post(post_id)["comentarios"]
    assert not at.exception and comentarios[-1]["texto"] == "Comentário do teste de tela"


def test_filtrar_por_tag_e_limpar(dados_carregados):
    at = abrir_pagina("feed_perfil", "ana@exemplo.com")
    at.button(key="tag_nosql").click().run()
    assert not at.exception and at.session_state["feed_tag"] == "nosql"
    at.button(key="feed_limpar_tag").click().run()
    assert not at.exception and at.session_state["feed_tag"] is None


def test_adicionar_e_remover_experiencia(dados_carregados):
    at = abrir_pagina("feed_perfil", "ana@exemplo.com")
    at.text_input(key="exp_empresa").set_value("Empresa do Teste")
    at.text_input(key="exp_cargo").set_value("Estagiária")
    at.text_input(key="exp_inicio").set_value("2020-01")
    at.text_input(key="exp_fim").set_value("2020-12")
    at.button(key="exp_adicionar").click().run()
    sv = at.session_state["servicos"]
    assert not at.exception
    assert any(t["empresa"] == "Empresa do Teste" for t in sv.neo4j.trabalhos_de("u001"))

    at.button(key="exp_remover_Empresa do Teste|Estagiária|2020-01").click().run()
    assert not at.exception
    assert not any(t["empresa"] == "Empresa do Teste" for t in sv.neo4j.trabalhos_de("u001"))
    assert not any(e["empresa"] == "Empresa do Teste" for e in sv.mongo.buscar_usuario("u001")["experiencias"])


def test_inicio_de_experiencia_invalido_mostra_erro(dados_carregados):
    at = abrir_pagina("feed_perfil", "ana@exemplo.com")
    at.text_input(key="exp_empresa").set_value("Outra Empresa")
    at.text_input(key="exp_cargo").set_value("Analista")
    at.text_input(key="exp_inicio").set_value("março de 2020")
    at.button(key="exp_adicionar").click().run()
    sv = at.session_state["servicos"]
    assert not at.exception and at.error
    assert not any(t["empresa"] == "Outra Empresa" for t in sv.neo4j.trabalhos_de("u001"))


def test_definir_e_remover_habilidade(dados_carregados):
    at = abrir_pagina("feed_perfil", "ana@exemplo.com")
    at.selectbox(key="hab_nome").select("Neo4j")
    at.slider(key="hab_nivel").set_value(2)
    at.button(key="hab_salvar").click().run()
    sv = at.session_state["servicos"]
    assert not at.exception
    assert {"nome": "Neo4j", "nivel": 2} in [{"nome": h["nome"], "nivel": h["nivel"]} for h in sv.neo4j.habilidades_de("u001")]

    at.button(key="hab_remover_Neo4j").click().run()
    assert not at.exception and "Neo4j" not in [h["nome"] for h in sv.neo4j.habilidades_de("u001")]


def test_adicionar_certificacao(dados_carregados):
    at = abrir_pagina("feed_perfil", "ana@exemplo.com")
    at.text_input(key="cert_nome").set_value("Certificação do Teste")
    at.text_input(key="cert_emissor").set_value("Emissor X")
    at.button(key="cert_adicionar").click().run()
    sv = at.session_state["servicos"]
    assert not at.exception
    assert any(c["nome"] == "Certificação do Teste" for c in sv.mongo.buscar_usuario("u001")["certificacoes"])
