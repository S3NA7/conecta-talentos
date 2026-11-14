from app.servicos.seguranca import conferir_senha, gerar_hash


def test_senha_confere_e_nao_confere():
    h = gerar_hash("segredo1")
    assert h.startswith("pbkdf2$") and conferir_senha("segredo1", h) and not conferir_senha("outra", h)
    assert gerar_hash("segredo1") != h            # sal aleatório
    assert conferir_senha("x", "lixo") is False
