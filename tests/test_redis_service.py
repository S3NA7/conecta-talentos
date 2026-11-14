"""Testes do RedisService (rodam contra o Redis local; FLUSHDB antes de cada teste)."""
import time

import pytest

from app.servicos.erros import BancoIndisponivel
from app.servicos.redis_service import RedisService


@pytest.fixture(autouse=True)
def _banco_limpo(redis_svc):
    redis_svc.apagar_tudo()


def test_sessao_criada_com_ttl_e_presenca(redis_svc):
    t = redis_svc.criar_sessao("u001", "Ana")
    assert redis_svc.validar_sessao(t)["usuario_id"] == "u001"
    assert 1790 <= redis_svc.listar_sessoes("u001")[0]["ttl"] <= 1800
    assert redis_svc.esta_online("u001")


def test_sessao_invalida_ou_vazia(redis_svc):
    assert redis_svc.validar_sessao("nao-existe") is None and redis_svc.validar_sessao("") is None


def test_sessao_expira_e_some_da_lista(cfg):
    r = RedisService(cfg.REDIS_URL, sessao_ttl=1); t = r.criar_sessao("u001", "Ana"); time.sleep(1.5)
    assert r.validar_sessao(t) is None and r.listar_sessoes("u001") == []
    r.close()


def test_validar_renova_ttl(redis_svc):
    t = redis_svc.criar_sessao("u001", "Ana"); redis_svc.r.expire(f"sessao:{t}", 100)
    redis_svc.validar_sessao(t); assert redis_svc.r.ttl(f"sessao:{t}") > 1700


def test_encerrar_ultima_sessao_marca_offline(redis_svc):
    t1 = redis_svc.criar_sessao("u001", "Ana"); t2 = redis_svc.criar_sessao("u001", "Ana")
    redis_svc.encerrar_sessao(t1); assert redis_svc.esta_online("u001")
    redis_svc.encerrar_sessao(t2); assert not redis_svc.esta_online("u001")


def test_presenca_expira_pela_janela(cfg, relogio):
    r = RedisService(cfg.REDIS_URL, relogio=lambda: relogio.agora)
    relogio.agora = 1000.0; r.sinal_de_presenca("u001"); r.sinal_de_presenca("u002")
    relogio.agora = 1060.0; r.sinal_de_presenca("u002")
    relogio.agora = 1095.0
    assert r.usuarios_online() == ["u002"] and r.contar_online() == 1
    p = r.presenca_de(["u001", "u002", "u999"])
    assert p["u001"] == {"online": False, "visto": 1000.0} and p["u002"]["online"] and p["u999"] == {"online": False, "visto": None}
    r.close()


def test_notificacoes_contador_e_lista_limitada(redis_svc):
    for i in range(25): n = redis_svc.notificar("u001", {"texto": f"n{i}"})
    assert n == 25 and redis_svc.nao_lidas("u001") == 25
    rec = redis_svc.notificacoes_recentes("u001")
    assert len(rec) == 20 and rec[0]["texto"] == "n24"
    redis_svc.marcar_lidas("u001"); assert redis_svc.nao_lidas("u001") == 0 and redis_svc.nao_lidas("u404") == 0


def test_notificar_varios(redis_svc):
    redis_svc.notificar_varios(["u002", "u003"], {"texto": "oi"})
    assert redis_svc.nao_lidas("u002") == 1 and redis_svc.nao_lidas("u003") == 1


def test_cache_ida_volta_ttl_e_lixo(redis_svc):
    redis_svc.cache_gravar("cache:perfil:u001", {"nome": "Ana"}, 300)
    assert redis_svc.cache_ler("cache:perfil:u001") == {"nome": "Ana"} and 290 <= redis_svc.r.ttl("cache:perfil:u001") <= 300
    redis_svc.r.set("cache:x", "{isso não é json"); assert redis_svc.cache_ler("cache:x") is None
    redis_svc.cache_apagar("cache:perfil:u001"); assert redis_svc.cache_ler("cache:perfil:u001") is None


def test_redis_fora_do_ar_vira_BancoIndisponivel():
    fora = RedisService("redis://127.0.0.1:1/0"); assert fora.ping() is False
    with pytest.raises(BancoIndisponivel): fora.nao_lidas("u001")
