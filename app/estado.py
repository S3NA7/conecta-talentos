"""Estado de cada sessão do navegador: serviços, usuário logado e mensagens de erro na tela."""
from dataclasses import dataclass

import streamlit as st

from app.config import Config, carregar_config
from app.servicos.erros import BancoIndisponivel, ErroDeNegocio
from app.servicos.mongo_service import MongoService
from app.servicos.neo4j_service import Neo4jService
from app.servicos.orquestrador import Orquestrador
from app.servicos.redis_service import RedisService
from app.servicos.registro import Registro

AVISO_SESSAO_EXPIRADA = "Sua sessão expirou. Entre novamente."


@dataclass
class Servicos:
    cfg: Config
    registro: Registro
    mongo: MongoService
    redis: RedisService
    neo4j: Neo4jService
    orq: Orquestrador


def servicos() -> Servicos:
    """Cria os serviços uma vez por sessão do navegador e guarda em st.session_state.

    Cada aba do navegador tem seus próprios serviços e, portanto, seu próprio Registro:
    o painel Bastidores mostra só o que aquela aba fez. Criar os serviços não conecta
    em nada; a conexão acontece na primeira operação.
    """
    if "servicos" not in st.session_state:
        cfg = carregar_config()
        registro = Registro()
        mongo = MongoService(cfg.MONGO_URI, cfg.MONGO_DB, registro)
        redis = RedisService(cfg.REDIS_URL, registro)
        neo4j = Neo4jService(cfg.NEO4J_URI, cfg.NEO4J_USERNAME, cfg.NEO4J_PASSWORD,
                             cfg.NEO4J_DATABASE, registro)
        orq = Orquestrador(mongo, redis, neo4j, registro, cfg)
        st.session_state["servicos"] = Servicos(cfg, registro, mongo, redis, neo4j, orq)
    return st.session_state["servicos"]


def usuario_atual() -> dict | None:
    """{"id", "nome"} de quem está logado, ou None.

    A sessão vive no Redis: o token guardado na aba é conferido lá a cada interação.
    Token que o Redis não conhece mais (expirou) é apagado e a tela de entrada mostra o aviso.
    """
    token = st.session_state.get("token")
    if not token:
        return None
    try:
        sessao = servicos().orq.validar_sessao(token)
    except BancoIndisponivel:
        # Redis fora do ar: não dá para confirmar a sessão agora. O token fica guardado e,
        # quando o Redis voltar, a pessoa continua logada; a tela de entrada explica o problema
        return None
    if sessao is None:
        del st.session_state["token"]
        st.session_state["aviso_entrada"] = AVISO_SESSAO_EXPIRADA
        return None
    return {"id": sessao["usuario_id"], "nome": sessao["nome"]}


def entrar(token: str) -> None:
    st.session_state["token"] = token


def sair() -> None:
    """Encerra a sessão no Redis e esquece o token nesta aba."""
    token = st.session_state.pop("token", None)
    if token:
        try:
            servicos().orq.sair(token)
        except BancoIndisponivel:
            pass  # com o Redis fora, a sessão expira sozinha pelo TTL


def mostrar_avisos(avisos: list[str]) -> None:
    for aviso in avisos:
        st.warning(aviso)


def tentar(funcao, *args, **kwargs):
    """Executa uma ação; erros esperados viram mensagem na tela em vez de exceção.

    Devolve o resultado da ação, ou None se ela foi recusada.
    """
    try:
        return funcao(*args, **kwargs)
    except ErroDeNegocio as erro:
        st.error(str(erro))
    except BancoIndisponivel as erro:
        st.error(f"{erro.banco} está fora do ar. Tente novamente em instantes.")
    return None
