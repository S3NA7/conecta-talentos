"""Testes do Neo4jService. Rodam na ordem do arquivo e compartilham o mesmo mini-grafo,
montado uma única vez em setup_module:

    t1 - t2 - t3 - t4        t1 - t5 - t3        t6 (isolada)
    mentores: t3 e t4 | habilidades: t3 Neo4j 5; t4 Neo4j 4, Redis 5; t2 Neo4j 5; t5 Redis 3
"""
from unittest.mock import ANY

import pytest
from neo4j.exceptions import TransientError

from app.config import carregar_config, enderecos_sao_locais
from app.servicos.erros import BancoIndisponivel
from app.servicos.neo4j_service import Neo4jService


def setup_module(module):
    cfg = carregar_config()
    if not enderecos_sao_locais(cfg):
        pytest.exit("Testes só rodam contra bancos locais")
    servico = Neo4jService(cfg.NEO4J_URI, cfg.NEO4J_USERNAME, cfg.NEO4J_PASSWORD, cfg.NEO4J_DATABASE)
    try:
        servico.apagar_tudo()
        servico.criar_esquema()
        for numero in range(1, 7):
            servico.criar_pessoa(f"t{numero}", f"T{numero}", "Analista", mentor=numero in (3, 4))
        for nome in ("Neo4j", "Redis"):
            servico.criar_habilidade(nome, "Bancos de dados")
        for a, b in [("t1", "t2"), ("t2", "t3"), ("t3", "t4"), ("t1", "t5"), ("t5", "t3")]:
            servico.conectar(a, b)
        for pessoa, habilidade, nivel in [("t3", "Neo4j", 5), ("t4", "Neo4j", 4), ("t4", "Redis", 5),
                                          ("t2", "Neo4j", 5), ("t5", "Redis", 3)]:
            servico.definir_habilidade(pessoa, habilidade, nivel)
    finally:
        servico.close()


def test_esquema_cria_constraints(neo4j_svc):
    nomes = [r["name"] for r in neo4j_svc._executar("SHOW CONSTRAINTS YIELD name RETURN name")]
    assert len(nomes) >= 3

def test_conectar_e_idempotente_e_sem_direcao(neo4j_svc):
    assert neo4j_svc.conectar("t2", "t1") is False            # já existe t1-t2
    assert neo4j_svc.estao_conectados("t2", "t1")
    total = neo4j_svc._executar("MATCH (:Pessoa {id:'t1'})-[r:CONECTADO_COM]-(:Pessoa {id:'t2'}) RETURN count(r) AS n")[0]["n"]
    assert total == 1
    with pytest.raises(ValueError): neo4j_svc.conectar("t1", "t1")

def test_menor_caminho(neo4j_svc):
    c = neo4j_svc.menor_caminho("t1", "t4")
    assert c["graus"] == 3 and [p["id"] for p in c["pessoas"]][0] == "t1" and c["pessoas"][-1]["id"] == "t4"

def test_menor_caminho_para_si_mesmo(neo4j_svc):                 # Review Focus 1
    assert neo4j_svc.menor_caminho("t1", "t1") == {"pessoas": [{"id": "t1", "nome": "T1", "titulo": ANY}], "graus": 0}

def test_painel_registra_o_cypher_inteiro_numa_linha(neo4j_svc):
    neo4j_svc.registro.limpar(); neo4j_svc.menor_caminho("t1", "t4")
    comando = neo4j_svc.registro.itens()[-1]["comando"]
    assert "shortestPath" in comando and "\n" not in comando and "  " not in comando

def test_sem_caminho_e_pessoa_inexistente(neo4j_svc):
    assert neo4j_svc.menor_caminho("t1", "t6") is None and neo4j_svc.menor_caminho("t1", "nao-existe") is None

def test_rede_por_grau(neo4j_svc):
    assert [(p["id"], p["grau"]) for p in neo4j_svc.rede_por_grau("t1")] == [("t2", 1), ("t5", 1), ("t3", 2), ("t4", 3)]
    assert neo4j_svc.rede_por_grau("t6") == []

def test_subgrafo(neo4j_svc):
    s = neo4j_svc.subgrafo_da_rede("t1", max_grau=2)
    assert {n["id"] for n in s["nos"]} == {"t1", "t2", "t5", "t3"} and len(s["arestas"]) == 4

def test_sugerir_conexoes(neo4j_svc):
    s = neo4j_svc.sugerir_conexoes("t1")
    assert s[0]["id"] == "t3" and s[0]["em_comum"] == 2 and sorted(s[0]["amigos"]) == ["T2", "T5"]

def test_mentores_pontuacao_e_ordem(neo4j_svc):
    m = neo4j_svc.recomendar_mentores("t1", ["Neo4j", "Redis"])
    assert [x["id"] for x in m] == ["t3", "t4"]                 # t2 domina mas não é mentor
    assert m[0]["pontuacao"] == 8.0 and m[0]["graus"] == 2 and m[0]["em_comum"] == 2      # 3*1 + 5 + 2 - 2
    assert m[1]["pontuacao"] == 7.5 and m[1]["graus"] == 3 and m[1]["via"] in ("T2", "T5") # 3*2 + 4.5 + 0 - 3

def test_mentores_sem_conexoes_e_sem_interesses(neo4j_svc):
    m = neo4j_svc.recomendar_mentores("t6", ["Neo4j"])
    assert [x["id"] for x in m] == ["t3", "t4"] and m[0]["graus"] is None and m[0]["pontuacao"] == 2.0
    assert neo4j_svc.recomendar_mentores("t6") == []            # t6 não tem QUER_APRENDER

def test_interesses_sao_substituidos(neo4j_svc):
    neo4j_svc.definir_interesses("t1", ["Neo4j", "Redis"]); neo4j_svc.definir_interesses("t1", ["Redis"])
    assert neo4j_svc.interesses_de("t1") == ["Redis"]
    assert [x["id"] for x in neo4j_svc.recomendar_mentores("t1")] == ["t4"]

def test_habilidade_com_aspas_usa_parametros(neo4j_svc):
    nome = "C++ \"avançado\" 'e' {x}"
    neo4j_svc.definir_habilidade("t5", nome, 4)
    assert nome in [h["nome"] for h in neo4j_svc.habilidades_de("t5")]
    with pytest.raises(ValueError): neo4j_svc.definir_habilidade("t5", "Redis", 9)

def test_trabalho_e_colegas(neo4j_svc):
    neo4j_svc.registrar_trabalho("t1", "Empresa X", "Analista", "2021-03"); neo4j_svc.registrar_trabalho("t2", "Empresa X", "Dev", "2018-01", "2020-12")
    assert neo4j_svc.trabalhos_de("t1")[0] == {"empresa": "Empresa X", "setor": "Não informado", "cargo": "Analista", "desde": "2021-03", "ate": None}
    assert [c["id"] for c in neo4j_svc.colegas_de_empresa("t1")] == ["t2"]
    neo4j_svc.remover_trabalho("t1", "Empresa X", "Analista", "2021-03"); assert neo4j_svc.trabalhos_de("t1") == []

def test_neo4j_fora_do_ar_vira_BancoIndisponivel():
    fora = Neo4jService("bolt://127.0.0.1:1", "neo4j", "x")
    try:
        assert fora.ping() is False
        with pytest.raises(BancoIndisponivel): fora.ids_conexoes("t1")
    finally:
        fora.close()

def test_neo4j_iniciando_ou_parando_vira_BancoIndisponivel(cfg, monkeypatch):
    # enquanto o Neo4j sobe ou desce, o servidor responde DatabaseUnavailable (um TransientError)
    servico = Neo4jService(cfg.NEO4J_URI, cfg.NEO4J_USERNAME, cfg.NEO4J_PASSWORD, cfg.NEO4J_DATABASE)
    def sessao_indisponivel(**kwargs):
        raise TransientError("Database is unavailable")
    monkeypatch.setattr(servico.driver, "session", sessao_indisponivel)
    try:
        with pytest.raises(BancoIndisponivel) as erro: servico.ids_conexoes("t1")
        assert erro.value.banco == "Neo4j"
    finally:
        servico.close()
