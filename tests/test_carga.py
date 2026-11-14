"""Testes da carga de dados de exemplo (usam os três bancos locais)."""
from dataclasses import replace

import pytest

from app.servicos.seguranca import conferir_senha
from scripts.carga_inicial import carregar_tudo


def test_contagens(dados_carregados, mongo, neo4j_svc):
    assert mongo.db.usuarios.count_documents({}) == 30 and mongo.db.posts.count_documents({}) == 40
    assert mongo.db["fs.files"].count_documents({}) == 3
    c = lambda q: neo4j_svc._executar(q)[0]["n"]
    assert c("MATCH (n:Pessoa) RETURN count(n) AS n") == 30 and c("MATCH (n:Habilidade) RETURN count(n) AS n") == 25
    assert c("MATCH (n:Empresa) RETURN count(n) AS n") == 12 and c("MATCH ()-[r:CONECTADO_COM]->() RETURN count(r) AS n") == 53


def test_ids_iguais_nos_dois_bancos(dados_carregados, mongo, neo4j_svc):
    assert {u["_id"] for u in mongo.listar_usuarios()} == {r["id"] for r in neo4j_svc._executar("MATCH (p:Pessoa) RETURN p.id AS id")}


def test_caminhos_conhecidos(dados_carregados, neo4j_svc):
    ids = lambda c: [p["id"] for p in c["pessoas"]]
    assert ids(neo4j_svc.menor_caminho("u001", "u007")) == ["u001", "u005", "u007"]
    assert ids(neo4j_svc.menor_caminho("u001", "u019")) == ["u001", "u003", "u012", "u017", "u019"]
    assert neo4j_svc.menor_caminho("u001", "u029")["graus"] == 5 and neo4j_svc.menor_caminho("u001", "u030") is None


def test_rede_da_ana(dados_carregados, neo4j_svc):
    por_grau = {}
    for p in neo4j_svc.rede_por_grau("u001", 3): por_grau.setdefault(p["grau"], set()).add(p["id"])
    assert por_grau == {1: {"u002", "u003", "u005"}, 2: {"u004", "u007", "u012"},
                        3: {"u006", "u008", "u009", "u010", "u013", "u014", "u017", "u025"}}


def test_mentores_da_ana(dados_carregados, neo4j_svc):
    m = neo4j_svc.recomendar_mentores("u001")
    assert [x["id"] for x in m] == ["u003", "u004", "u007", "u006", "u024", "u027"]
    assert [x["pontuacao"] for x in m] == [9.0, 8.0, 6.0, 4.0, 4.0, 3.0] and m[2]["via"] == "Eduarda Monteiro"


def test_mentores_de_quem_nao_tem_conexoes(dados_carregados, neo4j_svc):
    m = neo4j_svc.recomendar_mentores("u030")
    assert [(x["id"], x["pontuacao"], x["graus"]) for x in m] == [("u003", 5.0, None), ("u006", 4.5, None), ("u007", 2.0, None)]


def test_sugestoes_da_ana(dados_carregados, neo4j_svc):
    s = neo4j_svc.sugerir_conexoes("u001")
    assert (s[0]["id"], s[0]["em_comum"]) == ("u004", 2) and {x["id"] for x in s[1:]} == {"u007", "u012"}


def test_login_e_notificacoes_iniciais(dados_carregados, cfg, mongo, redis_svc):
    assert conferir_senha(cfg.SENHA_DEMO, mongo.buscar_usuario_por_email("ana@exemplo.com")["senha_hash"])
    assert redis_svc.nao_lidas("u001") == 3 and len(mongo.listar_notificacoes("u001")) == 3
    assert redis_svc.contar_online() == 0


def test_notificacao_da_curtida_bate_com_o_post(dados_carregados, mongo):
    # a 1ª notificação da Ana diz que o Bruno curtiu o post dela sobre o dashboard
    post = mongo.db.posts.find_one({"autor_id": "u001", "texto": {"$regex": "^Terminei meu primeiro dashboard"}})
    assert post["curtidas"] == ["u002"]


def test_experiencias_batem_com_o_grafo(dados_carregados, mongo, neo4j_svc):
    no_mongo = {(e["empresa"], e["cargo"]) for e in mongo.buscar_usuario("u007")["experiencias"]}
    no_grafo = {(t["empresa"], t["cargo"]) for t in neo4j_svc.trabalhos_de("u007")}
    assert no_mongo == no_grafo and len(no_grafo) == 2


def test_carga_pode_repetir(dados_carregados, cfg, mongo):
    carregar_tudo(cfg); assert mongo.db.usuarios.count_documents({}) == 30


def test_se_vazio_nao_apaga(dados_carregados, cfg, mongo):
    mongo.db.posts.delete_one({}); carregar_tudo(cfg, se_vazio=True)
    assert mongo.db.posts.count_documents({}) == 39


def test_trava_contra_banco_remoto(cfg):
    with pytest.raises(SystemExit): carregar_tudo(replace(cfg, NEO4J_URI="neo4j+s://abc.databases.neo4j.io"))
