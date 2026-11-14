"""Testes do Disjuntor: depois de uma falha de conexão, o serviço fica um tempo sem tentar de novo.

O relógio é falso (fixture `relogio`): nenhum teste espera de verdade.
"""
import pymongo.errors
import pytest
import redis
from neo4j.exceptions import ServiceUnavailable

from app.config import PAUSA_APOS_FALHA_SEGUNDOS
from app.servicos.disjuntor import Disjuntor
from app.servicos.erros import BancoIndisponivel
from app.servicos.mongo_service import MongoService
from app.servicos.neo4j_service import Neo4jService
from app.servicos.redis_service import RedisService


def test_pausa_padrao_e_10_segundos():
    assert PAUSA_APOS_FALHA_SEGUNDOS == 10 and Disjuntor("Redis").pausa == 10


def test_sem_falha_nao_bloqueia(relogio):
    Disjuntor("Redis", relogio=lambda: relogio.agora).conferir()  # não levanta nada


def test_depois_da_falha_bloqueia_ate_a_pausa_acabar(relogio):
    d = Disjuntor("Neo4j", relogio=lambda: relogio.agora)
    relogio.agora = 100.0; d.falhou()
    relogio.agora = 109.9
    with pytest.raises(BancoIndisponivel) as erro: d.conferir()
    assert erro.value.banco == "Neo4j"
    relogio.agora = 110.0; d.conferir()  # passou a pausa: pode tentar de verdade


def test_sucesso_limpa_a_pausa(relogio):
    d = Disjuntor("MongoDB", relogio=lambda: relogio.agora)
    d.falhou(); d.funcionou(); d.conferir()


# ---------- nos três serviços ----------

class _Contador:
    """Finge o driver: conta as chamadas e levanta o erro de conexão do banco."""

    def __init__(self, erro):
        self.erro = erro
        self.chamadas = 0

    def __call__(self, *args, **kwargs):
        self.chamadas += 1
        raise self.erro


class _BancoMongoFalso:
    """Faz o papel de MongoService.db: db.usuarios.find chama o contador."""

    def __init__(self, contador):
        self.usuarios = type("Colecao", (), {"find": staticmethod(contador)})()


def _neo4j_quebrado(cfg, monkeypatch):
    srv = Neo4jService(cfg.NEO4J_URI, cfg.NEO4J_USERNAME, cfg.NEO4J_PASSWORD, cfg.NEO4J_DATABASE)
    contador = _Contador(ServiceUnavailable("fora"))
    monkeypatch.setattr(srv.driver, "session", contador)
    return srv, contador, lambda: srv.ids_conexoes("u001")


def _redis_quebrado(cfg, monkeypatch):
    srv = RedisService(cfg.REDIS_URL)
    contador = _Contador(redis.exceptions.ConnectionError("fora"))
    monkeypatch.setattr(srv.r, "get", contador)
    monkeypatch.setattr(srv.r, "ping", contador)
    return srv, contador, lambda: srv.nao_lidas("u001")


def _mongo_quebrado(cfg, monkeypatch):
    srv = MongoService(cfg.MONGO_URI, cfg.MONGO_DB)
    contador = _Contador(pymongo.errors.ServerSelectionTimeoutError("fora"))
    srv.db = _BancoMongoFalso(contador)
    return srv, contador, srv.listar_usuarios


@pytest.mark.parametrize("montar,banco", [(_neo4j_quebrado, "Neo4j"), (_redis_quebrado, "Redis"),
                                          (_mongo_quebrado, "MongoDB")])
def test_servico_nao_insiste_durante_a_pausa(cfg, monkeypatch, relogio, montar, banco):
    srv, contador, consulta = montar(cfg, monkeypatch)
    srv.disjuntor = Disjuntor(banco, relogio=lambda: relogio.agora)
    try:
        relogio.agora = 1000.0
        with pytest.raises(BancoIndisponivel): consulta()        # 1ª falha: tentou de verdade
        assert contador.chamadas == 1
        relogio.agora = 1005.0
        with pytest.raises(BancoIndisponivel): consulta()        # durante a pausa: nem tenta
        assert srv.ping() is False and contador.chamadas == 1
        relogio.agora = 1010.0
        with pytest.raises(BancoIndisponivel): consulta()        # pausa acabou: tenta de novo
        assert contador.chamadas == 2
    finally:
        srv.close()
