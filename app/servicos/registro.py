"""Registro das operações feitas nos bancos, mostrado no painel "Por dentro dos bancos"."""
import time
from collections import deque
from contextlib import contextmanager
from datetime import datetime, timezone

from app.servicos.erros import BancoIndisponivel

ACAO_LEITURA = "Leitura da tela"


class Registro:
    def __init__(self, limite: int = 300):
        # deque com maxlen descarta sozinha as operações mais antigas
        self._itens = deque(maxlen=limite)
        self._acao_atual = None
        self._leitura_atual = False
        self._pausas = 0
        # cada ação de fora ganha um número: duas ações seguidas com o mesmo nome (curtir e
        # descurtir) viram dois grupos no painel, e não um só
        self._total_acoes = 0
        self._numero_atual = None

    def registrar(self, banco: str, comando: str, ms: float) -> None:
        if self._pausas:
            return
        self._itens.append({
            "banco": banco,
            "comando": comando,
            "ms": ms,
            "acao": self._acao_atual or ACAO_LEITURA,
            "numero": self._numero_atual,  # None = fora de qualquer ação
            # fora de qualquer ação também é leitura (o caso "Leitura da tela")
            "leitura": self._leitura_atual if self._acao_atual else True,
            "quando": datetime.now(timezone.utc),
        })

    @contextmanager
    def medir(self, banco: str, comando: str, erros_conexao: tuple = ()):
        """Mede o tempo do bloco e registra; falha de conexão vira BancoIndisponivel."""
        inicio = time.perf_counter()
        try:
            yield
        except erros_conexao as erro:
            self.registrar(banco, comando + " ✗ falhou", (time.perf_counter() - inicio) * 1000)
            raise BancoIndisponivel(banco) from erro
        self.registrar(banco, comando, (time.perf_counter() - inicio) * 1000)

    @contextmanager
    def acao(self, nome: str, leitura: bool = False):
        """Operações feitas dentro levam este nome; numa ação aninhada vale a mais externa.

        leitura=True marca uma ação que só lê para desenhar a tela (montar o feed, abrir um
        perfil): o painel a esconde por padrão, para não encobrir a última ação do usuário.
        Aninhada numa escrita, a leitura faz parte da escrita (vale o nome e a marca da externa).
        """
        anterior, leitura_anterior, numero_anterior = self._acao_atual, self._leitura_atual, self._numero_atual
        if anterior is None:
            self._total_acoes += 1
            self._acao_atual, self._leitura_atual, self._numero_atual = nome, leitura, self._total_acoes
        try:
            yield
        finally:
            self._acao_atual, self._leitura_atual, self._numero_atual = anterior, leitura_anterior, numero_anterior

    @contextmanager
    def pausado(self):
        """Nada é registrado dentro (usado nas atualizações automáticas da tela)."""
        self._pausas += 1
        try:
            yield
        finally:
            self._pausas -= 1

    def itens(self) -> list[dict]:
        return list(self._itens)

    def grupos(self, incluir_leituras: bool = False) -> list[dict]:
        """Um grupo por execução de ação (pelo número); o grupo mais recente vem primeiro.

        Itens fora de qualquer ação (número None) que vêm seguidos ficam num grupo só.
        """
        grupos = []
        for item in self._itens:
            if not incluir_leituras and item["leitura"]:
                continue
            ultimo = grupos[-1] if grupos else None
            if (ultimo and ultimo["numero"] == item["numero"] and ultimo["acao"] == item["acao"]
                    and ultimo["leitura"] == item["leitura"]):
                ultimo["operacoes"].append(item)
            else:
                grupos.append({"acao": item["acao"], "leitura": item["leitura"],
                               "numero": item["numero"], "operacoes": [item]})
        return grupos[::-1]

    def limpar(self) -> None:
        self._itens.clear()
