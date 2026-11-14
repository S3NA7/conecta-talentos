"""Testes da tela Presença & Notificações (Redis) com o AppTest do Streamlit."""
from tests.apoio import abrir_pagina


def test_indicadores_da_ana(dados_carregados):
    at = abrir_pagina("presenca_notificacoes", "ana@exemplo.com")
    valores = {m.label: m.value for m in at.metric}
    assert not at.exception and valores["Online agora"] == "1" and valores["Notificações não lidas"] == "3"
    assert valores["Minhas sessões ativas"] == "1"


def test_marcar_como_lidas(dados_carregados):
    at = abrir_pagina("presenca_notificacoes", "ana@exemplo.com"); at.button(key="notif_marcar_lidas").click().run()
    assert at.session_state["servicos"].redis.nao_lidas("u001") == 0


def test_simulador_poe_gente_online(dados_carregados):
    at = abrir_pagina("presenca_notificacoes", "ana@exemplo.com"); at.button(key="simular").click().run()
    assert {m.label: m.value for m in at.metric}["Online agora"] == "7"


def test_encerrar_outra_sessao_pelo_token(dados_carregados):
    at = abrir_pagina("presenca_notificacoes", "ana@exemplo.com")
    sv = at.session_state["servicos"]
    # os dados são recarregados uma vez por módulo: os logins dos testes anteriores ainda estão
    # no Redis; encerrá-los deixa só a sessão desta página
    for s in sv.redis.listar_sessoes("u001"):
        if s["token"] != at.session_state["token"]:
            sv.redis.encerrar_sessao(s["token"])
    outro = sv.redis.criar_sessao("u001", "Ana Beatriz Lima")
    at.run()
    botoes = [b for b in at.button if b.label == "Encerrar"]
    assert len(botoes) == 1 and botoes[0].key.endswith(outro[:8])
    botoes[0].click().run()
    assert not at.exception
    assert sv.redis.validar_sessao(outro) is None
    assert sv.redis.validar_sessao(at.session_state["token"]) is not None


def test_pagina_abre_sem_notificacoes(dados_carregados):
    assert not abrir_pagina("presenca_notificacoes", "jose@exemplo.com").exception
