"""Hash e conferência de senha (PBKDF2 da biblioteca padrão, sem dependências)."""
import hashlib
import hmac
import os

ITERACOES = 100_000


def _derivar(senha: str, sal: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), sal, ITERACOES)


def gerar_hash(senha: str) -> str:
    """Devolve `pbkdf2$<sal_hex>$<hash_hex>`; o sal aleatório faz a mesma senha gerar hashes diferentes."""
    sal = os.urandom(16)
    return f"pbkdf2${sal.hex()}${_derivar(senha, sal).hex()}"


def conferir_senha(senha: str, senha_hash: str) -> bool:
    try:
        formato, sal_hex, hash_hex = senha_hash.split("$")
        if formato != "pbkdf2":
            return False
        esperado = bytes.fromhex(hash_hex)
        sal = bytes.fromhex(sal_hex)
    except (ValueError, AttributeError):
        return False
    # compare_digest evita vazar, pelo tempo de resposta, onde a comparação divergiu
    return hmac.compare_digest(_derivar(senha, sal), esperado)
