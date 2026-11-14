"""Carga inicial dos três bancos: python scripts/carga_inicial.py [--confirmar-remoto] [--se-vazio]"""
import argparse
import sys
from pathlib import Path

RAIZ = str(Path(__file__).resolve().parent.parent)
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from app.config import carregar_config, enderecos_sao_locais  # noqa: E402
from app.servicos.mongo_service import MongoService  # noqa: E402
from app.servicos.neo4j_service import Neo4jService  # noqa: E402
from app.servicos.redis_service import RedisService  # noqa: E402
from scripts import carga_mongo, carga_neo4j, carga_redis  # noqa: E402


def carregar_tudo(cfg, *, confirmar_remoto: bool = False, se_vazio: bool = False) -> dict:
    """Apaga e recarrega os três bancos com os dados de exemplo; devolve as contagens de cada um."""
    # a trava vem antes de qualquer conexão: a carga apaga dados
    if not enderecos_sao_locais(cfg) and not confirmar_remoto:
        raise SystemExit("Algum banco não está em endereço local. A carga apaga os dados; "
                         "para continuar mesmo assim, use --confirmar-remoto.")
    mongo = MongoService(cfg.MONGO_URI, cfg.MONGO_DB)
    redis_svc = RedisService(cfg.REDIS_URL)
    neo4j_svc = Neo4jService(cfg.NEO4J_URI, cfg.NEO4J_USERNAME, cfg.NEO4J_PASSWORD, cfg.NEO4J_DATABASE)
    try:
        if se_vazio and mongo.db.usuarios.count_documents({}) > 0:
            return {"ignorada": "o banco já tem dados"}
        return {"mongo": carga_mongo.carregar(mongo, cfg.SENHA_DEMO),
                "redis": carga_redis.carregar(redis_svc),
                "neo4j": carga_neo4j.carregar(neo4j_svc)}
    finally:
        mongo.close()
        redis_svc.close()
        neo4j_svc.close()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Carrega os dados de exemplo no MongoDB, Redis e Neo4j.")
    parser.add_argument("--confirmar-remoto", action="store_true",
                        help="permite apagar e carregar bancos que não são locais")
    parser.add_argument("--se-vazio", action="store_true",
                        help="não faz nada se o MongoDB já tiver usuários")
    argumentos = parser.parse_args()
    resumo = carregar_tudo(carregar_config(), confirmar_remoto=argumentos.confirmar_remoto,
                           se_vazio=argumentos.se_vazio)
    if "ignorada" in resumo:
        print(f"Carga ignorada: {resumo['ignorada']}.")
        return
    for banco, contagens in resumo.items():
        print(f"{banco}: " + ", ".join(f"{n} {k}" for k, n in contagens.items()))


if __name__ == "__main__":
    main()
