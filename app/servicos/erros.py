"""Exceções compartilhadas pelos serviços e pelas páginas."""


class BancoIndisponivel(Exception):
    """Um dos bancos não respondeu; `banco` diz qual (mongo, redis ou neo4j)."""

    def __init__(self, banco: str, mensagem: str = ""):
        super().__init__(mensagem or f"O banco {banco} está indisponível.")
        self.banco = banco


class ErroDeNegocio(Exception):
    """Erro com mensagem pronta para mostrar na tela."""


class EmailJaCadastrado(ErroDeNegocio):
    pass
