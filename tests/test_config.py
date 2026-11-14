from dataclasses import replace

import pytest

from app.config import Config, enderecos_sao_locais


def test_padroes_apontam_para_docker_local(monkeypatch):
    for v in ("MONGO_URI", "REDIS_URL", "NEO4J_URI"):
        monkeypatch.delenv(v, raising=False)
    cfg = Config()  # valores padrão do dataclass
    assert cfg.MONGO_URI == "mongodb://127.0.0.1:27017"
    assert cfg.REDIS_URL == "redis://127.0.0.1:6379/0"
    assert cfg.NEO4J_URI == "bolt://127.0.0.1:7687"
    assert cfg.MONGO_DB == "conecta_talentos"


@pytest.mark.parametrize("campo,valor", [
    ("NEO4J_URI", "neo4j+s://abc123.databases.neo4j.io"),
    ("MONGO_URI", "mongodb+srv://x.mongodb.net"),
    ("REDIS_URL", "rediss://redis-123.cloud.redislabs.com:6379"),
])
def test_endereco_remoto_nao_e_local(campo, valor):
    assert enderecos_sao_locais(replace(Config(), **{campo: valor})) is False


def test_localhost_e_nomes_dos_containers_sao_locais():
    assert enderecos_sao_locais(Config()) is True
    assert enderecos_sao_locais(replace(
        Config(), MONGO_URI="mongodb://mongo:27017",
        REDIS_URL="redis://redis:6379/0", NEO4J_URI="bolt://neo4j:7687")) is True
