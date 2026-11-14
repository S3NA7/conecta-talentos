"""Fixtures compartilhadas pelos testes de serviço."""
import pytest

from app.config import carregar_config, enderecos_sao_locais
from app.servicos.mongo_service import MongoService
from app.servicos.neo4j_service import Neo4jService
from app.servicos.redis_service import RedisService


@pytest.fixture(scope="session")
def cfg():
    c = carregar_config()
    if not enderecos_sao_locais(c):
        pytest.exit("Testes só rodam contra bancos locais")
    return c


@pytest.fixture(scope="module")
def mongo(cfg):
    servico = MongoService(cfg.MONGO_URI, cfg.MONGO_DB)
    yield servico
    servico.close()


@pytest.fixture(scope="module")
def redis_svc(cfg):
    servico = RedisService(cfg.REDIS_URL)
    yield servico
    servico.close()


class _Relogio:
    """Relógio falso: os testes ajustam `.agora` para simular a passagem do tempo."""
    agora = 0.0


@pytest.fixture
def relogio():
    return _Relogio()


@pytest.fixture(scope="module")
def neo4j_svc(cfg):
    servico = Neo4jService(cfg.NEO4J_URI, cfg.NEO4J_USERNAME, cfg.NEO4J_PASSWORD, cfg.NEO4J_DATABASE)
    yield servico
    servico.close()


@pytest.fixture(scope="module")
def dados_carregados(cfg):
    """Recarrega os dados de exemplo nos três bancos antes dos testes do módulo."""
    from scripts.carga_inicial import carregar_tudo
    carregar_tudo(cfg)


@pytest.fixture(scope="session", autouse=True)
def recarregar_dados_no_fim(cfg):
    """Ao fim da sessão, deixa os bancos com os dados de exemplo limpos (a demo roda sobre eles)."""
    yield
    from scripts.carga_inicial import carregar_tudo
    carregar_tudo(cfg)
