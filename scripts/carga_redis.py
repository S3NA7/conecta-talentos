"""Carga do Redis: contador e lista de notificações não lidas. Ninguém começa online."""
import time

from scripts.dados_exemplo import NOTIFICACOES_INICIAIS


def carregar(redis_svc) -> dict:
    """Esvazia o banco e reflete no Redis as notificações iniciais gravadas no Mongo."""
    redis_svc.apagar_tudo()
    agora = time.time()
    total = len(NOTIFICACOES_INICIAIS)
    # notificar() já faz INCR + LPUSH + LTRIM num pipeline: o mesmo caminho que a aplicação usa
    for i, n in enumerate(NOTIFICACOES_INICIAIS):
        payload = {k: v for k, v in n.items() if k != "usuario_id"}
        # "quando" em segundos desde a época: a 1ª notificação é a mais antiga (15, 10 e 5 min atrás)
        payload["quando"] = agora - 5 * 60 * (total - i)
        redis_svc.notificar(n["usuario_id"], payload)
    return {"notificacoes_nao_lidas": total, "usuarios_online": 0}
