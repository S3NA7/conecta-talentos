"""Testes do Orquestrador: cada ação de negócio sobre os três bancos reais (dados de exemplo)."""
import io
import time

import pytest
from PIL import Image

from app.config import carregar_config
from app.servicos.erros import BancoIndisponivel, EmailJaCadastrado, ErroDeNegocio
from app.servicos.mongo_service import MongoService
from app.servicos.neo4j_service import Neo4jService
from app.servicos.orquestrador import Orquestrador
from app.servicos.redis_service import RedisService
from app.servicos.registro import Registro
from scripts.carga_inicial import carregar_tudo

SENHA = carregar_config().SENHA_DEMO


def _png_minusculo() -> bytes:
    """Uma imagem PNG de verdade, 2x2, gerada com o Pillow."""
    saida = io.BytesIO()
    Image.new("RGB", (2, 2), (0, 104, 74)).save(saida, format="PNG")
    return saida.getvalue()


class ForaDoAr:
    """Finge um banco fora do ar: qualquer método chamado levanta BancoIndisponivel."""

    def __init__(self, banco):
        self.banco = banco

    def __getattr__(self, nome):
        def falhar(*args, **kwargs):
            raise BancoIndisponivel(self.banco)
        return falhar


@pytest.fixture
def orq(cfg):
    carregar_tudo(cfg)  # cada teste começa com os dados de exemplo limpos
    registro = Registro()
    mongo = MongoService(cfg.MONGO_URI, cfg.MONGO_DB, registro)
    redis_svc = RedisService(cfg.REDIS_URL, registro)
    neo4j_svc = Neo4jService(cfg.NEO4J_URI, cfg.NEO4J_USERNAME, cfg.NEO4J_PASSWORD,
                             cfg.NEO4J_DATABASE, registro)
    yield Orquestrador(mongo, redis_svc, neo4j_svc, registro, cfg)
    mongo.close()
    redis_svc.close()
    neo4j_svc.close()


def test_login_cria_sessao_e_presenca(orq):
    r = orq.fazer_login("  ANA@exemplo.com ", SENHA)
    assert r["usuario"]["id"] == "u001" and orq.redis.validar_sessao(r["token"])["usuario_id"] == "u001"
    assert orq.redis.esta_online("u001")
    orq.sair(r["token"]); assert orq.validar_sessao(r["token"]) is None and not orq.redis.esta_online("u001")

@pytest.mark.parametrize("email,senha", [("ana@exemplo.com", "errada"), ("ninguem@exemplo.com", "x")])
def test_login_invalido(orq, email, senha):
    with pytest.raises(ErroDeNegocio): orq.fazer_login(email, senha)

def test_feed_so_tem_conexoes_e_eu(orq):
    f = orq.montar_feed("u001")
    assert {p["autor_id"] for p in f["posts"]} == {"u001", "u002", "u003", "u005"} and f["avisos"] == []
    assert all("autor_online" in p for p in f["posts"])

def test_feed_de_quem_nao_tem_conexoes_nem_posts(orq):
    assert orq.montar_feed("u030") == {"posts": [], "avisos": []}

def test_publicar_normaliza_tags_e_notifica_conexoes(orq):
    antes = orq.redis.nao_lidas("u002")
    r = orq.publicar_post("u001", "  Olá, rede!  ", ["#Dados", "dados", " Carreira ", ""])
    p = orq.mongo.buscar_post(r["post_id"])
    assert p["texto"] == "Olá, rede!" and p["tags"] == ["dados", "carreira"] and r["notificados"] == 3
    assert orq.redis.nao_lidas("u002") == antes + 1 and orq.redis.nao_lidas("u001") == 3
    assert orq.mongo.listar_notificacoes("u002")[0]["tipo"] == "post"

@pytest.mark.parametrize("texto,arquivo", [
    ("   ", None), ("x" * 1001, None),
    ("ok", ("v.exe", "application/x-msdownload", b"MZ")),
    ("ok", ("g.png", "image/png", b"0" * (5 * 1024 * 1024 + 1))),
    ("ok", ("lixo.png", "image/png", b"isto nao e uma imagem")),
    ("ok", ("falso.jpg", "image/jpeg", _png_minusculo())),  # PNG de verdade declarado como JPEG
    ("ok", ("g.pdf", "application/pdf", _png_minusculo())),
])
def test_publicar_recusa_entradas_invalidas(orq, texto, arquivo):                  # Review Focus 5
    with pytest.raises(ErroDeNegocio): orq.publicar_post("u001", texto, [], arquivo)
    assert orq.mongo.db.posts.count_documents({}) == 40

def test_publicar_com_anexo(orq):
    png = _png_minusculo()
    r = orq.publicar_post("u001", "com imagem", [], ("g.png", "image/png", png))
    a = orq.mongo.buscar_post(r["post_id"])["anexos"][0]
    assert a["nome"] == "g.png" and orq.mongo.ler_anexo(a["arquivo_id"]) == png

def test_publicar_foto_de_celular_mpo(orq):
    # celulares gravam JPEG com mais de uma imagem dentro (formato MPO); continua sendo image/jpeg
    saida = io.BytesIO()
    Image.new("RGB", (2, 2)).save(saida, format="MPO", save_all=True, append_images=[Image.new("RGB", (2, 2))])
    r = orq.publicar_post("u001", "foto do celular", [], ("foto.jpg", "image/jpeg", saida.getvalue()))
    assert orq.mongo.buscar_post(r["post_id"])["anexos"][0]["tipo"] == "image/jpeg"

def test_publicar_com_pdf(orq):
    pdf = b"%PDF-1.4\n%fim\n"
    r = orq.publicar_post("u001", "com pdf", [], ("d.pdf", "application/pdf", pdf))
    assert orq.mongo.buscar_post(r["post_id"])["anexos"][0]["tipo"] == "application/pdf"

def test_conectar_notifica_uma_vez_so(orq):                                         # Review Focus 3
    assert orq.conectar("u001", "u004")["criada"] is True and orq.redis.nao_lidas("u004") == 1
    assert orq.conectar("u004", "u001")["criada"] is False and orq.redis.nao_lidas("u004") == 1
    with pytest.raises(ErroDeNegocio): orq.conectar("u001", "u001")

def test_curtir_notifica_so_ao_curtir_post_alheio(orq):
    pid = orq.mongo.listar_posts(["u002"])[0]["_id"]
    assert orq.curtir_post("u001", pid) == {"curtido": True, "avisos": []} and orq.redis.nao_lidas("u002") == 1
    assert orq.curtir_post("u001", pid) == {"curtido": False, "avisos": []} and orq.redis.nao_lidas("u002") == 1

def test_cadastro_grava_nos_dois_bancos(orq):
    novo = orq.cadastrar_usuario("Zé Teste", "  NOVO@Exemplo.com ", "segredo1", "Desenvolvedor")
    assert novo == "u031" and orq.neo4j.buscar_pessoa("u031")["nome"] == "Zé Teste"
    assert orq.fazer_login("novo@exemplo.com", "segredo1")["usuario"]["id"] == "u031"

def test_cadastro_com_email_repetido_nao_deixa_no_orfao(orq):                       # Review Focus 4
    with pytest.raises(EmailJaCadastrado): orq.cadastrar_usuario("Outra Ana", " Ana@EXEMPLO.com", "segredo1", "Dev")
    assert orq.neo4j._executar("MATCH (p:Pessoa) RETURN count(p) AS n")[0]["n"] == 30

def test_cadastro_desfaz_mongo_se_neo4j_falhar(orq):
    quebrado = Orquestrador(orq.mongo, orq.redis, ForaDoAr("Neo4j"), orq.registro, orq.cfg)
    with pytest.raises(BancoIndisponivel): quebrado.cadastrar_usuario("Zé Teste", "ze@exemplo.com", "segredo1", "Dev")
    assert orq.mongo.buscar_usuario_por_email("ze@exemplo.com") is None

def test_perfil_cache_miss_hit_e_invalidacao(orq):
    assert orq.abrir_perfil("u001")["do_cache"] is False and orq.abrir_perfil("u001")["do_cache"] is True
    orq.editar_dados_basicos("u001", titulo="Analista de Dados Pleno", resumo="novo", cidade="Recife", estado="PE")
    p = orq.abrir_perfil("u001")
    assert p["do_cache"] is False and p["perfil"]["titulo"] == "Analista de Dados Pleno" and p["total_conexoes"] == 3
    assert orq.neo4j.buscar_pessoa("u001")["titulo"] == "Analista de Dados Pleno"
    assert orq.mongo.listar_posts(["u001"])[0]["autor"]["titulo"] == "Analista de Dados Pleno"
    assert "senha_hash" not in p["perfil"]

def test_cache_do_perfil_que_nao_e_objeto_conta_como_miss(orq):
    orq.redis.r.set("cache:perfil:u001", '"x"')  # JSON válido, mas não é um perfil
    p = orq.abrir_perfil("u001")
    assert p["do_cache"] is False and p["perfil"]["nome"] == "Ana Beatriz Lima"
    assert orq.redis.cache_ler("cache:perfil:u001")["nome"] == "Ana Beatriz Lima"  # cache refeito

def test_cache_das_tags_que_nao_e_lista_conta_como_miss(orq):
    orq.redis.r.set("cache:tags_em_alta", '{"carreira": 19}')
    t = orq.tags_em_alta()
    assert t["do_cache"] is False and t["tags"][0] == {"tag": "carreira", "total": 19}
    assert orq.tags_em_alta()["do_cache"] is True

def test_titulo_volta_se_neo4j_falhar(orq):
    quebrado = Orquestrador(orq.mongo, orq.redis, ForaDoAr("Neo4j"), orq.registro, orq.cfg)
    with pytest.raises(BancoIndisponivel): quebrado.editar_dados_basicos("u001", titulo="X", resumo="r", cidade="c", estado="PB")
    assert orq.mongo.buscar_usuario("u001")["titulo"] == "Analista de Dados Júnior"

def test_experiencia_vai_para_mongo_e_grafo(orq):
    exp = {"empresa": "Farol Educação", "cargo": "Analista", "inicio": "2019-01", "fim": "2020-06", "descricao": ""}
    orq.adicionar_experiencia("u001", exp)
    assert exp in orq.mongo.buscar_usuario("u001")["experiencias"]
    assert ("Farol Educação", "2020-06") in {(t["empresa"], t["ate"]) for t in orq.neo4j.trabalhos_de("u001")}
    orq.remover_experiencia("u001", exp)
    assert "Farol Educação" not in {t["empresa"] for t in orq.neo4j.trabalhos_de("u001")}

def test_neo4j_fora_feed_mostra_so_meus_posts_com_aviso(orq):
    f = Orquestrador(orq.mongo, orq.redis, ForaDoAr("Neo4j"), orq.registro, orq.cfg).montar_feed("u001")
    assert {p["autor_id"] for p in f["posts"]} == {"u001"} and len(f["avisos"]) == 1

def test_neo4j_fora_post_e_salvo_sem_notificar(orq):
    r = Orquestrador(orq.mongo, orq.redis, ForaDoAr("Neo4j"), orq.registro, orq.cfg).publicar_post("u001", "mesmo assim", [])
    assert orq.mongo.buscar_post(r["post_id"]) and r["notificados"] == 0 and r["avisos"]

def test_redis_fora_conexao_e_mantida_com_aviso(orq):
    r = Orquestrador(orq.mongo, ForaDoAr("Redis"), orq.neo4j, orq.registro, orq.cfg).conectar("u001", "u004")
    assert r["criada"] is True and r["avisos"] and orq.neo4j.estao_conectados("u001", "u004")

def test_notificacoes_e_marcar_lidas(orq):
    n = orq.notificacoes("u001"); assert n["nao_lidas"] == 3 and len(n["recentes"]) == 3 and len(n["historico"]) == 3
    orq.marcar_notificacoes_lidas("u001")
    assert orq.notificacoes("u001")["nao_lidas"] == 0 and all(x["lida"] for x in orq.notificacoes("u001")["historico"])

def test_painel_presenca(orq):
    orq.fazer_login("ana@exemplo.com", SENHA); p = orq.painel_presenca()
    assert p["total_online"] == 1 and p["online"][0]["id"] == "u001" and len(p["offline"]) == 29

def test_painel_presenca_limpa_sinal_vencido(orq):
    # sinal de 10 min atrás, gravado direto no ZSET: passou da janela de 90 s
    orq.redis.r.zadd("presenca:online", {"u002": time.time() - 600})
    p = orq.painel_presenca()
    assert "u002" not in {x["id"] for x in p["online"]} and "u002" in {x["id"] for x in p["offline"]}
    assert p["total_online"] == 0 and len(p["offline"]) == 30
    assert orq.redis.r.zscore("presenca:online", "u002") is None  # limpeza preguiçosa por score

def test_tags_em_alta_usa_cache_e_invalida_ao_publicar(orq):
    assert orq.tags_em_alta()["do_cache"] is False and orq.tags_em_alta()["do_cache"] is True
    orq.publicar_post("u001", "novo", ["nosql"]); assert orq.tags_em_alta()["do_cache"] is False

def test_acoes_aparecem_no_registro_com_os_tres_bancos(orq):
    orq.registro.limpar(); orq.publicar_post("u001", "bastidores", ["dados"])
    g = orq.registro.grupos()[0]
    assert g["acao"] == "Publicar post" and {o["banco"] for o in g["operacoes"]} == {"MongoDB", "Redis", "Neo4j"}

def test_leituras_da_tela_nao_escondem_a_ultima_acao(orq):
    orq.registro.limpar(); orq.publicar_post("u001", "a última ação", ["dados"])
    orq.montar_feed("u001"); orq.abrir_perfil("u001")
    assert orq.registro.grupos()[0]["acao"] == "Publicar post"
    todos = orq.registro.grupos(incluir_leituras=True)
    assert todos[0]["acao"] == "Abrir perfil" and todos[0]["leitura"] is True

def test_simulador(orq):
    r = orq.simular_atividade("u001", quantos=6)
    assert len(r["online"]) == 6 and "u001" not in r["online"] and orq.redis.contar_online() == 6
    assert orq.redis.nao_lidas("u001") == 5 and orq.redis.notificacoes_recentes("u001")[0]["texto"].endswith("(simulação)")


# ---------- endurecimentos decididos nesta tarefa ----------

@pytest.mark.parametrize("post_id", ["isto-nao-e-um-id", "000000000000000000000000"])
def test_curtir_e_comentar_post_inexistente(orq, post_id):
    with pytest.raises(ErroDeNegocio, match="Post não encontrado."): orq.curtir_post("u001", post_id)
    with pytest.raises(ErroDeNegocio, match="Post não encontrado."): orq.comentar_post("u001", post_id, "oi")

def test_conectar_e_pedir_mentoria_com_pessoa_inexistente(orq):
    with pytest.raises(ErroDeNegocio, match="Pessoa não encontrada."): orq.conectar("u001", "u999")
    with pytest.raises(ErroDeNegocio, match="Pessoa não encontrada."): orq.pedir_mentoria("u001", "u999")
    assert orq.redis.nao_lidas("u999") == 0

def test_sessao_sem_usuario_id_e_invalida(orq):
    orq.redis.r.hset("sessao:quebrada", "nome", "Ana")  # sobra rara de uma corrida entre expirar e renovar
    assert orq.validar_sessao("quebrada") is None

def test_comentar_notifica_autor_e_pedir_mentoria_notifica_mentor(orq):
    pid = orq.mongo.listar_posts(["u002"])[0]["_id"]
    assert orq.comentar_post("u001", pid, "  Muito bom!  ") == {"avisos": []}
    assert orq.mongo.buscar_post(pid)["comentarios"][-1]["texto"] == "Muito bom!" and orq.redis.nao_lidas("u002") == 1
    assert orq.pedir_mentoria("u001", "u003", "Quero aprender ML") == {"avisos": []}
    n = orq.redis.notificacoes_recentes("u003")[0]
    assert n["tipo"] == "mentoria" and n["de"] == {"id": "u001", "nome": "Ana Beatriz Lima"} and "quando" in n

def test_redis_fora_curtida_e_mantida_com_aviso(orq):
    pid = orq.mongo.listar_posts(["u002"])[0]["_id"]
    r = Orquestrador(orq.mongo, ForaDoAr("Redis"), orq.neo4j, orq.registro, orq.cfg).curtir_post("u001", pid)
    assert r["curtido"] is True and r["avisos"] and "u001" in orq.mongo.buscar_post(pid)["curtidas"]


# ---------- experiência: a identidade é (empresa, cargo, inicio) nos dois bancos ----------

EXP = {"empresa": "Farol Educação", "cargo": "Analista", "inicio": "2019-01", "fim": None, "descricao": "Dados"}

def _no_mongo(orq):
    return [(e["empresa"], e["cargo"], e["inicio"]) for e in orq.mongo.buscar_usuario("u001")["experiencias"]]

def _no_grafo(orq):
    return [(t["empresa"], t["cargo"], t["desde"]) for t in orq.neo4j.trabalhos_de("u001")]

CHAVE = ("Farol Educação", "Analista", "2019-01")

def test_remover_experiencia_inexistente_nao_mexe_em_nada(orq):
    mongo_antes, grafo_antes = _no_mongo(orq), _no_grafo(orq)
    with pytest.raises(ErroDeNegocio, match="Experiência não encontrada."): orq.remover_experiencia("u001", EXP)
    assert _no_mongo(orq) == mongo_antes and _no_grafo(orq) == grafo_antes

def test_remover_experiencia_pela_chave_mesmo_com_campos_diferentes(orq):
    orq.adicionar_experiencia("u001", EXP)
    orq.remover_experiencia("u001", {"empresa": "Farol Educação", "cargo": "Analista", "inicio": "2019-01", "fim": ""})
    assert CHAVE not in _no_mongo(orq) and CHAVE not in _no_grafo(orq)

def test_remover_experiencia_com_neo4j_fora_mantem_no_mongo(orq):
    orq.adicionar_experiencia("u001", EXP)
    quebrado = Orquestrador(orq.mongo, orq.redis, ForaDoAr("Neo4j"), orq.registro, orq.cfg)
    with pytest.raises(BancoIndisponivel): quebrado.remover_experiencia("u001", EXP)
    assert _no_mongo(orq).count(CHAVE) == 1 and CHAVE in _no_grafo(orq)

def test_adicionar_experiencia_com_neo4j_fora_nao_fica_no_mongo(orq):
    quebrado = Orquestrador(orq.mongo, orq.redis, ForaDoAr("Neo4j"), orq.registro, orq.cfg)
    with pytest.raises(BancoIndisponivel): quebrado.adicionar_experiencia("u001", EXP)
    assert CHAVE not in _no_mongo(orq)

def test_adicionar_experiencia_repetida_e_recusada(orq):
    orq.adicionar_experiencia("u001", EXP)
    with pytest.raises(ErroDeNegocio, match="Essa experiência já está no seu perfil."):
        orq.adicionar_experiencia("u001", {**EXP, "fim": "2020-06", "descricao": "outra"})
    assert _no_mongo(orq).count(CHAVE) == 1 and _no_grafo(orq).count(CHAVE) == 1
