"""Disjuntor: depois de uma falha de conexão, o serviço passa um tempo sem tentar de novo."""
import time

from app.config import PAUSA_APOS_FALHA_SEGUNDOS
from app.servicos.erros import BancoIndisponivel


class Disjuntor:
    """Depois de uma falha de conexão o serviço fica 10 s sem tentar de novo, para a tela não
    travar esperando o timeout em cada consulta; passado esse tempo, a próxima chamada tenta
    de verdade.

    Cada serviço tem o seu e chama conferir() antes de usar o driver, falhou() quando a
    conexão falha e funcionou() quando a operação dá certo.
    """

    def __init__(self, banco: str, pausa: float = PAUSA_APOS_FALHA_SEGUNDOS, relogio=time.monotonic):
        self.banco = banco
        self.pausa = pausa
        # relogio: os testes trocam por um relógio falso para simular a passagem do tempo
        self.relogio = relogio
        self._fim_da_pausa = None  # None = sem pausa (o banco respondeu da última vez)

    def conferir(self) -> None:
        """Durante a pausa, falha na hora, sem esperar o timeout do driver."""
        if self._fim_da_pausa is not None and self.relogio() < self._fim_da_pausa:
            raise BancoIndisponivel(self.banco)

    def falhou(self) -> None:
        self._fim_da_pausa = self.relogio() + self.pausa

    def funcionou(self) -> None:
        self._fim_da_pausa = None
