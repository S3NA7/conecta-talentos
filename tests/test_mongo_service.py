"""Testes do MongoService. Rodam na ordem do arquivo e compartilham o mesmo banco,
limpo uma única vez em setup_module."""
import pymongo.errors
import pytest

from app.config import carregar_config, enderecos_sao_locais
from app.servicos.erros import BancoIndisponivel, EmailJaCadastrado
from app.servicos.mongo_service import MongoService


def setup_module(module):
    cfg = carregar_config()
    if not enderecos_sao_locais(cfg):
        pytest.exit("Testes só rodam contra bancos locais")
    servico = MongoService(cfg.MONGO_URI, cfg.MONGO_DB)
    servico.apagar_tudo()
    servico.criar_esquema()
    servico.close()


def _usuario(id, email):
    return {"_id": id, "nome": "Usuário " + id, "email": email,
            "titulo": "Analista", "senha_hash": "pbkdf2$abc"}


def test_ping(mongo): assert mongo.ping() is True

def test_usuario_sem_campos_obrigatorios_e_recusado(mongo):
    with pytest.raises(pymongo.errors.WriteError): mongo.inserir_usuario({"_id": "u900", "nome": "Sem título", "email": "a@b.c"})

def test_email_duplicado_ignora_maiusculas_e_espacos(mongo):
    mongo.inserir_usuario(_usuario("u001", "ana@exemplo.com"))
    with pytest.raises(EmailJaCadastrado): mongo.inserir_usuario(_usuario("u002", "  ANA@Exemplo.com "))

def test_buscar_usuario_nao_devolve_senha(mongo):
    assert "senha_hash" not in mongo.buscar_usuario("u001")
    assert "senha_hash" in mongo.buscar_usuario_por_email(" Ana@EXEMPLO.com")

def test_proximo_id(mongo): assert mongo.proximo_id_usuario() == "u002"

def test_perfil_flexivel_push_e_pull(mongo):
    exp = {"empresa": "DataNorte", "cargo": "Analista", "inicio": "2021-03", "fim": None}
    mongo.adicionar_item("u001", "experiencias", exp)
    assert mongo.buscar_usuario("u001")["experiencias"] == [exp]
    assert mongo.remover_item("u001", "experiencias", exp) == 1
    assert mongo.buscar_usuario("u001")["experiencias"] == []
    assert mongo.remover_item("u001", "experiencias", exp) == 0
    with pytest.raises(ValueError): mongo.adicionar_item("u001", "senha_hash", {})

def test_posts_ordem_filtro_por_autor_e_tag(mongo):
    a = {"id": "u001", "nome": "Ana", "titulo": "Analista"}; b = {"id": "u002", "nome": "Bia", "titulo": "Dev"}
    p1 = mongo.criar_post(a, "primeiro", ["dados"], []); p2 = mongo.criar_post(b, "segundo", ["web"], [])
    p3 = mongo.criar_post(a, "terceiro", ["dados", "carreira"], [])
    assert [p["_id"] for p in mongo.listar_posts(["u001"])] == [p3, p1]
    assert [p["_id"] for p in mongo.listar_posts(["u001", "u002"], tag="web")] == [p2]
    assert isinstance(p1, str) and mongo.listar_posts([]) == []

def test_curtir_alterna_e_comentar(mongo):
    pid = mongo.criar_post({"id": "u001", "nome": "Ana", "titulo": "A"}, "x", [], [])
    assert mongo.curtir(pid, "u002") is True and mongo.curtir(pid, "u002") is False
    mongo.curtir(pid, "u002"); mongo.comentar(pid, {"id": "u002", "nome": "Bia"}, "boa!")
    p = mongo.buscar_post(pid)
    assert p["curtidas"] == ["u002"] and p["comentarios"][0]["texto"] == "boa!"

def test_tags_em_alta(mongo):            # após os posts dos testes acima: dados=2, carreira=1, web=1
    assert mongo.tags_em_alta()[0] == {"tag": "dados", "total": 2}

def test_titulo_propagado_aos_posts(mongo):
    assert mongo.atualizar_titulo_nos_posts("u001", "Analista Sênior") >= 2
    assert mongo.listar_posts(["u001"])[0]["autor"]["titulo"] == "Analista Sênior"

def test_anexo_gridfs_ida_e_volta(mongo):
    ref = mongo.salvar_anexo("a.png", "image/png", b"\x89PNG" + b"0" * 300_000)
    assert ref["tamanho"] == 300_004 and mongo.ler_anexo(ref["arquivo_id"])[:4] == b"\x89PNG"
    assert mongo.ler_anexo("000000000000000000000000") is None

def test_buscar_post_com_id_malformado(mongo):
    assert mongo.buscar_post("isto-nao-e-um-id") is None

def test_notificacoes(mongo):
    assert mongo.criar_notificacoes([]) == 0
    mongo.criar_notificacoes([{"usuario_id": "u001", "tipo": "post", "de": {"id": "u002", "nome": "Bia"}, "texto": "t"} for _ in range(2)])
    assert len(mongo.listar_notificacoes("u001")) == 2 and mongo.marcar_notificacoes_lidas("u001") == 2
    assert all(n["lida"] for n in mongo.listar_notificacoes("u001"))

def test_indices_criados(mongo):
    idx = mongo.db.notificacoes.index_information()
    assert any(i.get("expireAfterSeconds") == 2592000 for i in idx.values())
    assert any(i.get("unique") for i in mongo.db.usuarios.index_information().values())

def test_banco_fora_do_ar_vira_BancoIndisponivel():
    fora = MongoService("mongodb://localhost:1", "x")
    assert fora.ping() is False
    with pytest.raises(BancoIndisponivel): fora.listar_usuarios()
