"""Configuração central: lê o .env e guarda as constantes da aplicação."""
import os
from dataclasses import dataclass
from urllib.parse import urlsplit

from dotenv import load_dotenv

NOME_APP = "Conecta Talentos"
SESSAO_TTL_SEGUNDOS = 1800
PRESENCA_JANELA_SEGUNDOS = 90
CACHE_PERFIL_TTL = 300
CACHE_TAGS_TTL = 60
NOTIF_RECENTES_MAX = 20
MAX_SALTOS = 6
PAUSA_APOS_FALHA_SEGUNDOS = 10  # depois de uma falha de conexão, tempo sem tentar de novo
ANEXO_MAX_BYTES = 5 * 1024 * 1024
ANEXO_TIPOS = ("image/png", "image/jpeg", "application/pdf")

# Hosts considerados locais (máquina do aluno ou containers do docker compose).
HOSTS_LOCAIS = ("localhost", "127.0.0.1", "::1", "mongo", "redis", "neo4j")


@dataclass
class Config:
    # Os padrões apontam para os bancos do docker compose.
    # 127.0.0.1 e não localhost: no Windows, localhost tenta IPv6 primeiro e cada primeira conexão esperava 2 s
    MONGO_URI: str = "mongodb://127.0.0.1:27017"
    MONGO_DB: str = "conecta_talentos"
    REDIS_URL: str = "redis://127.0.0.1:6379/0"
    NEO4J_URI: str = "bolt://127.0.0.1:7687"
    NEO4J_USERNAME: str = "neo4j"
    NEO4J_PASSWORD: str = ""
    NEO4J_DATABASE: str = "neo4j"
    MODO_DEMO: bool = True
    SENHA_DEMO: str = ""


def carregar_config() -> Config:
    """Lê o arquivo .env (se existir) e monta a Config; variáveis ausentes usam o padrão."""
    load_dotenv()
    padrao = Config()
    return Config(
        MONGO_URI=os.getenv("MONGO_URI", padrao.MONGO_URI),
        MONGO_DB=os.getenv("MONGO_DB", padrao.MONGO_DB),
        REDIS_URL=os.getenv("REDIS_URL", padrao.REDIS_URL),
        NEO4J_URI=os.getenv("NEO4J_URI", padrao.NEO4J_URI),
        NEO4J_USERNAME=os.getenv("NEO4J_USERNAME", padrao.NEO4J_USERNAME),
        NEO4J_PASSWORD=os.getenv("NEO4J_PASSWORD", padrao.NEO4J_PASSWORD),
        NEO4J_DATABASE=os.getenv("NEO4J_DATABASE", padrao.NEO4J_DATABASE),
        MODO_DEMO=os.getenv("MODO_DEMO", "1") == "1",
        SENHA_DEMO=os.getenv("SENHA_DEMO", padrao.SENHA_DEMO),
    )


def enderecos_sao_locais(cfg: Config) -> bool:
    """True só se os três bancos estiverem em hosts locais (trava de segurança da carga e dos testes)."""
    urls = (cfg.MONGO_URI, cfg.REDIS_URL, cfg.NEO4J_URI)
    return all(urlsplit(u).hostname in HOSTS_LOCAIS for u in urls)
