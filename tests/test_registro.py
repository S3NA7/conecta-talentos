import pytest

from app.servicos.erros import BancoIndisponivel
from app.servicos.registro import Registro


def test_operacao_fora_de_acao_e_leitura_da_tela():
    r = Registro(); r.registrar("Redis", "GET x", 0.4)
    assert r.itens()[0]["acao"] == "Leitura da tela"


def test_acao_agrupa_e_mais_recente_vem_primeiro():
    r = Registro()
    with r.acao("Login"): r.registrar("MongoDB", "find", 1); r.registrar("Redis", "HSET", 1)
    with r.acao("Publicar post"): r.registrar("MongoDB", "insert_one", 1)
    g = r.grupos()
    assert [x["acao"] for x in g] == ["Publicar post", "Login"]
    assert len(g[1]["operacoes"]) == 2


def test_grupos_esconde_leituras_por_padrao():
    r = Registro(); r.registrar("Redis", "GET x", 1)
    assert r.grupos() == [] and len(r.grupos(incluir_leituras=True)) == 1


def test_pausado_nao_registra():
    r = Registro()
    with r.pausado(): r.registrar("Redis", "ZADD", 1)
    assert r.itens() == []


def test_medir_converte_erro_de_conexao():
    r = Registro()
    with pytest.raises(BancoIndisponivel) as e:
        with r.medir("Neo4j", "MATCH (n)", erros_conexao=(ConnectionError,)): raise ConnectionError()
    assert e.value.banco == "Neo4j" and r.itens()[0]["comando"].endswith("✗ falhou")


def test_acao_de_leitura_fica_escondida_por_padrao():
    r = Registro()
    with r.acao("Publicar post"): r.registrar("MongoDB", "insert_one", 1)
    with r.acao("Abrir perfil", leitura=True): r.registrar("Redis", "GET cache", 1)
    assert [g["acao"] for g in r.grupos()] == ["Publicar post"]
    todos = r.grupos(incluir_leituras=True)
    assert todos[0]["acao"] == "Abrir perfil" and todos[0]["leitura"] is True
    assert r.itens()[-1]["leitura"] is True


def test_leitura_dentro_de_escrita_faz_parte_da_escrita():
    r = Registro()
    with r.acao("Editar perfil"):
        with r.acao("Abrir perfil", leitura=True): r.registrar("MongoDB", "find_one", 1)
    item = r.itens()[0]
    assert item["acao"] == "Editar perfil" and item["leitura"] is False
    assert [g["acao"] for g in r.grupos()] == ["Editar perfil"]


def test_grupo_de_escrita_tem_leitura_falso():
    r = Registro()
    with r.acao("Curtir"): r.registrar("MongoDB", "update_one", 1)
    r.registrar("Redis", "GET x", 1)  # fora de ação: leitura da tela
    assert r.grupos()[0]["leitura"] is False and r.itens()[-1]["leitura"] is True


def test_limite_descarta_os_mais_antigos():
    r = Registro(limite=3)
    for i in range(5): r.registrar("Redis", f"c{i}", 1)
    assert [i["comando"] for i in r.itens()] == ["c2", "c3", "c4"]


def test_duas_acoes_seguidas_com_o_mesmo_nome_sao_dois_grupos():
    r = Registro()
    with r.acao("Curtir"): r.registrar("MongoDB", "curtiu", 1)
    with r.acao("Curtir"): r.registrar("MongoDB", "descurtiu", 1); r.registrar("Redis", "INCR", 1)
    g = r.grupos()
    assert [x["acao"] for x in g] == ["Curtir", "Curtir"]
    assert [o["comando"] for o in g[0]["operacoes"]] == ["descurtiu", "INCR"]   # a mais recente primeiro
    assert [o["comando"] for o in g[1]["operacoes"]] == ["curtiu"]
