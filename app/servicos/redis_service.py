"""RedisService: sessões, presença, contadores de notificação e cache (dados quentes)."""
import json
import secrets
import time
from contextlib import contextmanager

import redis

from app.config import NOTIF_RECENTES_MAX, PRESENCA_JANELA_SEGUNDOS, SESSAO_TTL_SEGUNDOS
from app.servicos.disjuntor import Disjuntor
from app.servicos.erros import BancoIndisponivel
from app.servicos.registro import Registro

ERROS_DE_CONEXAO = (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError)


class RedisService:
    def __init__(self, url: str, registro: Registro | None = None, *,
                 sessao_ttl: int = SESSAO_TTL_SEGUNDOS,
                 janela_presenca: int = PRESENCA_JANELA_SEGUNDOS,
                 relogio=time.time):
        self.registro = registro if registro is not None else Registro()
        self.r = redis.Redis.from_url(
            url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
        self.sessao_ttl = sessao_ttl
        self.janela_presenca = janela_presenca
        # relogio: os testes trocam por um relógio falso para simular a passagem do tempo
        self.relogio = relogio
        self.disjuntor = Disjuntor("Redis")

    @contextmanager
    def _op(self, comando: str):
        """Registra a operação no painel; falha de conexão vira BancoIndisponivel.

        Antes, o disjuntor confere se não estamos na pausa depois de uma falha (disjuntor.py).
        """
        self.disjuntor.conferir()
        try:
            with self.registro.medir("Redis", comando, erros_conexao=ERROS_DE_CONEXAO):
                yield
        except BancoIndisponivel:
            self.disjuntor.falhou()
            raise
        self.disjuntor.funcionou()

    # ---------- infraestrutura ----------

    def close(self) -> None:
        self.r.close()

    def ping(self) -> bool:
        try:
            with self._op("PING"):
                self.r.ping()
            return True
        except Exception:
            return False

    def apagar_tudo(self) -> None:
        with self._op("FLUSHDB"):
            self.r.flushdb()

    # ---------- sessões ----------

    def criar_sessao(self, usuario_id: str, nome: str) -> str:
        token = secrets.token_urlsafe(24)
        agora = self.relogio()
        with self._op("HSET + EXPIRE + SADD + ZADD + HSET (login)"):
            # pipeline transacional: manda os 5 comandos juntos (MULTI/EXEC), numa só ida
            # ao servidor; eles rodam em sequência, sem comando de outro cliente no meio, e se a
            # conexão cair antes do EXEC nenhum roda. O Redis não tem rollback: se um comando
            # falhasse durante o EXEC, os outros continuariam valendo
            pipe = self.r.pipeline(transaction=True)
            pipe.hset(f"sessao:{token}", mapping={
                "usuario_id": usuario_id, "nome": nome,
                "login_em": agora, "ultimo_acesso": agora})
            pipe.expire(f"sessao:{token}", self.sessao_ttl)
            pipe.sadd(f"usuario:{usuario_id}:sessoes", token)
            pipe.zadd("presenca:online", {usuario_id: agora})
            pipe.hset("presenca:visto", usuario_id, agora)
            pipe.execute()
        return token

    def validar_sessao(self, token: str) -> dict | None:
        if not token:
            return None
        chave = f"sessao:{token}"
        with self._op("HGETALL sessao + EXPIRE"):
            dados = self.r.hgetall(chave)
            if not dados:
                return None
            agora = self.relogio()
            pipe = self.r.pipeline(transaction=True)
            pipe.hset(chave, "ultimo_acesso", agora)
            pipe.expire(chave, self.sessao_ttl)  # cada uso renova os 30 min
            pipe.execute()
        dados["ultimo_acesso"] = str(agora)
        return dados

    def encerrar_sessao(self, token: str) -> None:
        if not token:
            return
        with self._op("DEL sessao + SREM"):
            usuario_id = self.r.hget(f"sessao:{token}", "usuario_id")
            if usuario_id is None:
                return
            pipe = self.r.pipeline(transaction=True)
            pipe.delete(f"sessao:{token}")
            pipe.srem(f"usuario:{usuario_id}:sessoes", token)
            pipe.execute()
            restantes = self.r.scard(f"usuario:{usuario_id}:sessoes")
        if restantes == 0:
            self.marcar_offline(usuario_id)

    def listar_sessoes(self, usuario_id: str) -> list[dict]:
        chave_set = f"usuario:{usuario_id}:sessoes"
        with self._op("SMEMBERS + HGETALL + TTL (sessões)"):
            tokens = sorted(self.r.smembers(chave_set))
            pipe = self.r.pipeline(transaction=False)
            for token in tokens:
                pipe.hgetall(f"sessao:{token}")
                pipe.ttl(f"sessao:{token}")
            resultado = pipe.execute()
            sessoes = []
            for i, token in enumerate(tokens):
                dados, ttl = resultado[2 * i], resultado[2 * i + 1]
                if not dados:
                    # a chave expirou sozinha; o token ficou órfão no SET
                    self.r.srem(chave_set, token)
                    continue
                sessoes.append({"token": token, "login_em": float(dados["login_em"]),
                                "ultimo_acesso": float(dados["ultimo_acesso"]), "ttl": ttl})
        return sessoes

    # ---------- presença ----------

    def sinal_de_presenca(self, usuario_id: str) -> None:
        agora = self.relogio()
        with self._op("ZADD presenca:online + HSET presenca:visto"):
            pipe = self.r.pipeline(transaction=True)
            pipe.zadd("presenca:online", {usuario_id: agora})
            pipe.hset("presenca:visto", usuario_id, agora)
            pipe.execute()

    def marcar_offline(self, usuario_id: str) -> None:
        with self._op("ZREM presenca:online + HSET presenca:visto"):
            pipe = self.r.pipeline(transaction=True)
            pipe.zrem("presenca:online", usuario_id)
            pipe.hset("presenca:visto", usuario_id, self.relogio())
            pipe.execute()

    def usuarios_online(self) -> list[str]:
        corte = self.relogio() - self.janela_presenca
        with self._op("ZREMRANGEBYSCORE + ZRANGEBYSCORE presenca:online"):
            # limpa quem parou de mandar sinal e lista o resto, o mais recente primeiro
            self.r.zremrangebyscore("presenca:online", "-inf", f"({corte}")
            return self.r.zrevrangebyscore("presenca:online", "+inf", corte)

    def contar_online(self) -> int:
        corte = self.relogio() - self.janela_presenca
        with self._op("ZCOUNT presenca:online"):
            return self.r.zcount("presenca:online", f"({corte}", "+inf")

    def esta_online(self, usuario_id: str) -> bool:
        with self._op("ZSCORE presenca:online"):
            score = self.r.zscore("presenca:online", usuario_id)
        return score is not None and score > self.relogio() - self.janela_presenca

    def presenca_de(self, ids: list[str]) -> dict[str, dict]:
        if not ids:
            return {}
        corte = self.relogio() - self.janela_presenca
        with self._op("ZSCORE + HGET (presença de vários)"):
            # pipeline: todas as perguntas vão juntas, em vez de uma ida ao servidor por usuário
            pipe = self.r.pipeline(transaction=False)
            for usuario_id in ids:
                pipe.zscore("presenca:online", usuario_id)
                pipe.hget("presenca:visto", usuario_id)
            resultado = pipe.execute()
        presenca = {}
        for i, usuario_id in enumerate(ids):
            score, visto = resultado[2 * i], resultado[2 * i + 1]
            presenca[usuario_id] = {
                "online": score is not None and score > corte,
                "visto": float(visto) if visto is not None else None}
        return presenca

    # ---------- notificações (contador e lista curta) ----------

    def _empilhar(self, pipe, usuario_id: str, texto_json: str) -> None:
        pipe.incr(f"notif:nao_lidas:{usuario_id}")
        pipe.lpush(f"notif:recentes:{usuario_id}", texto_json)
        pipe.ltrim(f"notif:recentes:{usuario_id}", 0, NOTIF_RECENTES_MAX - 1)

    def notificar(self, usuario_id: str, notificacao: dict) -> int:
        with self._op("INCR + LPUSH + LTRIM (notificação)"):
            # pipeline: os 3 comandos vão juntos, e o contador volta no primeiro resultado
            pipe = self.r.pipeline(transaction=True)
            self._empilhar(pipe, usuario_id, json.dumps(notificacao, ensure_ascii=False))
            return pipe.execute()[0]

    def notificar_varios(self, ids: list[str], notificacao: dict) -> None:
        if not ids:
            return
        texto_json = json.dumps(notificacao, ensure_ascii=False)
        with self._op(f"INCR + LPUSH + LTRIM x{len(ids)} (notificar vários)"):
            # um pipeline só para todos os destinatários
            pipe = self.r.pipeline(transaction=True)
            for usuario_id in ids:
                self._empilhar(pipe, usuario_id, texto_json)
            pipe.execute()

    def nao_lidas(self, usuario_id: str) -> int:
        with self._op("GET notif:nao_lidas"):
            valor = self.r.get(f"notif:nao_lidas:{usuario_id}")
        return int(valor) if valor is not None else 0

    def notificacoes_recentes(self, usuario_id: str) -> list[dict]:
        with self._op("LRANGE notif:recentes"):
            itens = self.r.lrange(f"notif:recentes:{usuario_id}", 0, -1)
        return [json.loads(i) for i in itens]

    def marcar_lidas(self, usuario_id: str) -> None:
        with self._op("SET notif:nao_lidas 0"):
            self.r.set(f"notif:nao_lidas:{usuario_id}", 0)

    # ---------- cache ----------

    def cache_ler(self, chave: str):
        with self._op(f"GET {chave}"):
            texto = self.r.get(chave)
        if texto is None:
            return None
        try:
            return json.loads(texto)
        except json.JSONDecodeError:
            # conteúdo estragado: apaga para a próxima leitura recarregar do banco
            self.cache_apagar(chave)
            return None

    def cache_gravar(self, chave: str, valor, ttl: int) -> None:
        with self._op(f"SET {chave} EX {ttl}"):
            self.r.set(chave, json.dumps(valor, ensure_ascii=False, default=str), ex=ttl)

    def cache_apagar(self, chave: str) -> None:
        with self._op(f"DEL {chave}"):
            self.r.delete(chave)
