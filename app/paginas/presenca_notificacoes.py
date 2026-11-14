"""Tela 2 — Presença & Notificações (Redis).

Tudo aqui é estado quente e de vida curta: quem está online (ZSET com o horário do último
sinal), o contador de não lidas, as notificações recentes (LIST) e as sessões com TTL.
O histórico durável das notificações vem do MongoDB; os nomes e títulos também.
"""
import math
from datetime import datetime

import streamlit as st

from app import estado
from app.componentes.cartoes import cartao_pessoa, tempo_relativo, texto_livre
from app.config import PRESENCA_JANELA_SEGUNDOS
from app.servicos.erros import BancoIndisponivel

CHAVE_RECADO = "presenca_recado"  # mensagem guardada para mostrar depois do st.rerun()
AVISO_REDIS = "Presença e notificações indisponíveis no momento (Redis fora do ar)."
ICONES = {"conexao": "🤝", "post": "📝", "curtida": "👍", "mentoria": "🎓", "comentario": "💬"}
ICONE_NEUTRO = "🔔"  # tipo desconhecido: aparece com um ícone neutro, sem quebrar a tela


# ---------- textos ----------

def _icone(tipo) -> str:
    return ICONES.get(tipo, ICONE_NEUTRO)


def _hora(segundos: float) -> str:
    """Segundos desde a época → "14:05" (horário local)."""
    return datetime.fromtimestamp(segundos).strftime("%H:%M")


def _tempo_restante(ttl) -> str:
    """TTL do Redis em segundos → minutos inteiros (-1 = sem prazo, -2 = já expirou)."""
    if ttl is None or ttl == -1:
        return "sem prazo"
    if ttl <= 0:
        return "expirando"
    return f"expira em {math.ceil(ttl / 60)} min"


# ---------- confirmação depois do st.rerun() ----------

def _recado_depois(sucesso: str, avisos: list[str]) -> None:
    """Guarda a confirmação e recarrega a página inteira (inclusive o 🔔 da barra lateral).

    st.rerun() sem argumentos recarrega o app todo, e não só o fragmento onde o botão está.
    """
    st.session_state[CHAVE_RECADO] = {"sucesso": sucesso, "avisos": avisos}
    st.rerun()


def _mostrar_recado() -> None:
    recado = st.session_state.pop(CHAVE_RECADO, None)
    if recado:
        st.toast(recado["sucesso"], icon="✅")
        estado.mostrar_avisos(recado["avisos"])


# ---------- blocos do painel ----------

def _indicadores(presenca: dict, notif: dict, sessoes: list[dict]) -> None:
    c1, c2, c3 = st.columns(3)
    c1.metric("Online agora", presenca["total_online"], border=True)
    c2.metric("Notificações não lidas", notif["nao_lidas"], border=True)
    c3.metric("Minhas sessões ativas", len(sessoes), border=True)


def _pessoas(presenca: dict, eu: str) -> None:
    st.subheader("👥 Profissionais")
    st.caption(f"online = sinal de presença nos últimos {PRESENCA_JANELA_SEGUNDOS} segundos "
               "(enquanto a aba está aberta, o sinal é renovado sozinho)")
    col_on, col_off = st.columns(2, gap="medium")
    with col_on:
        st.markdown(f"**🟢 Online** · {len(presenca['online'])}")
        with st.container(height=420, border=True):
            if not presenca["online"]:
                st.caption("Ninguém online agora.")
            for p in presenca["online"]:
                pessoa = dict(p, nome=f"{p['nome']} (você)" if p["id"] == eu else p["nome"])
                cartao_pessoa(pessoa, online=True)
    with col_off:
        st.markdown(f"**⚪ Offline** · {len(presenca['offline'])}")
        with st.container(height=420, border=True):
            if not presenca["offline"]:
                st.caption("Todo mundo está online.")
            for p in presenca["offline"]:
                cartao_pessoa(p)
                visto = p.get("visto")
                st.caption(f"visto por último {tempo_relativo(visto)}" if visto else "nunca entrou")


def _linha_notificacao(tipo, texto, quando, nova: bool = False) -> None:
    detalhes = tempo_relativo(quando) if quando is not None else ""
    if nova:
        detalhes = " · ".join(x for x in ("**não lida**", detalhes) if x)
    st.markdown(f"{_icone(tipo)} &nbsp;{texto_livre(texto or '')}")
    if detalhes:
        st.caption(detalhes)


def _notificacoes(srv, eu: str, notif: dict) -> None:
    st.subheader("🔔 Notificações")
    # olha os dois bancos: o botão também serve para acertar o histórico se o contador já zerou
    ha_nao_lidas = notif["nao_lidas"] > 0 or any(not n.get("lida") for n in notif["historico"])
    # numa linha só dele, para o rótulo inteiro caber mesmo com a coluna estreita
    if st.button("Marcar todas como lidas", key="notif_marcar_lidas", icon="✔️", width="stretch",
                    disabled=not ha_nao_lidas):
        if estado.tentar(lambda: srv.orq.marcar_notificacoes_lidas(eu) or True):
            _recado_depois("Notificações marcadas como lidas.", [])

    aba_recentes, aba_historico = st.tabs([f"Recentes · Redis ({len(notif['recentes'])})",
                                           f"Histórico · MongoDB ({len(notif['historico'])})"])
    with aba_recentes:
        st.caption("As últimas 20, guardadas numa LIST do Redis para abrir na hora.")
        with st.container(height=360, border=False):
            if not notif["recentes"]:
                st.caption("Nenhuma notificação recente.")
            for n in notif["recentes"]:
                _linha_notificacao(n.get("tipo"), n.get("texto"), n.get("quando"))
    with aba_historico:
        st.caption("O registro durável, na coleção notificacoes do MongoDB.")
        with st.container(height=360, border=False):
            if not notif["historico"]:
                st.caption("Nenhuma notificação ainda.")
            for n in notif["historico"]:
                _linha_notificacao(n.get("tipo"), n.get("texto"), n.get("criado_em"), nova=not n.get("lida"))


def _sessoes(srv, sessoes: list[dict], token_atual: str | None) -> None:
    st.subheader("🔑 Minhas sessões")
    st.caption("Cada login é uma chave sessao:{token} no Redis, com TTL de 30 min renovado a cada uso.")
    if not sessoes:
        st.caption("Nenhuma sessão ativa.")
    # mais antiga primeiro; o Redis devolve os tokens sem ordem que faça sentido para a pessoa
    for s in sorted(sessoes, key=lambda x: x["login_em"]):
        with st.container(border=True):
            texto, acao = st.columns([3, 1], vertical_alignment="center")
            atual = s["token"] == token_atual
            detalhes = (f"Iniciada às {_hora(s['login_em'])} · último acesso {tempo_relativo(s['ultimo_acesso'])}"
                        f" · {_tempo_restante(s.get('ttl'))}")
            texto.markdown(f"**Esta sessão** · {detalhes}" if atual else detalhes)
            if atual:
                acao.caption("você está aqui (para encerrar, use Sair)")
            # a chave do botão leva o começo do token (e não a posição na lista): se a lista mudar
            # entre duas atualizações, o clique continua encerrando a sessão que estava na tela
            elif acao.button("Encerrar", key=f"sessao_encerrar_{s['token'][:8]}", icon="🚪", width="stretch"):
                # ação do usuário: aparece no Bastidores com este nome
                with srv.registro.acao("Encerrar sessão"):
                    encerrou = estado.tentar(lambda: srv.redis.encerrar_sessao(s["token"]) or True)
                if encerrou:
                    _recado_depois("Sessão encerrada.", [])


# st.fragment: só esta função roda de novo a cada 5 s, sem recarregar a página inteira.
# É o que faz o painel parecer "vivo": quem entra ou sai aparece sozinho, sem clicar em nada.
@st.fragment(run_every=5)
def _painel_ao_vivo(eu: str, token_atual: str | None) -> None:
    srv = estado.servicos()
    # pausado: a atualização automática não deve encher o Bastidores a cada 5 s
    try:
        with srv.registro.pausado():
            presenca = srv.orq.painel_presenca()   # MongoDB (nomes) + Redis (ZSET de presença)
            notif = srv.orq.notificacoes(eu)       # Redis (contador e recentes) + MongoDB (histórico)
            sessoes = srv.redis.listar_sessoes(eu)  # Redis: SET de tokens + HASH e TTL de cada sessão
    except BancoIndisponivel as erro:
        # mensagem a cada atualização; quando o banco voltar, o próximo ciclo já mostra os dados
        if erro.banco == "Redis":
            st.error(AVISO_REDIS)
        else:
            st.error(f"{erro.banco} está fora do ar. Tente novamente em instantes.")
        return

    _indicadores(presenca, notif, sessoes)
    st.caption(f"🔄 atualizado às {datetime.now().strftime('%H:%M:%S')} · a tela se atualiza sozinha a cada 5 s")
    esquerda, direita = st.columns([3, 2], gap="large")
    with esquerda:
        _pessoas(presenca, eu)
    with direita:
        _notificacoes(srv, eu, notif)
        _sessoes(srv, sessoes, token_atual)


def _simulador(srv, eu: str) -> None:
    """[extra] Para a apresentação: com uma pessoa só logada, o painel ficaria vazio."""
    with st.container(border=True):
        st.markdown("#### 🎬 Simulador (demonstração)")
        st.caption("Gera atividade **fictícia** para a apresentação: coloca 6 pessoas de exemplo online "
                   f"(elas saem sozinhas depois de {PRESENCA_JANELA_SEGUNDOS} s, porque ninguém renova o "
                   "sinal delas) e manda 2 notificações marcadas como simulação para você.")
        if st.button("Simular atividade", key="simular", icon="🎬"):
            resultado = estado.tentar(srv.orq.simular_atividade, eu)
            if resultado is not None:
                _recado_depois(f"Simulação: {len(resultado['online'])} pessoas online e "
                               f"{resultado['notificacoes']} notificações novas.", [])


# ---------- página ----------

def pagina() -> None:
    st.title("🟢 Presença & Notificações")
    st.caption("Quem está online agora, as suas notificações e as suas sessões — estado quente "
               "e de vida curta, guardado no Redis.")
    usuario = estado.usuario_atual()
    if usuario is None:
        st.warning(estado.AVISO_SESSAO_EXPIRADA)
        return
    srv = estado.servicos()
    eu = usuario["id"]
    _mostrar_recado()

    _painel_ao_vivo(eu, st.session_state.get("token"))
    st.divider()
    _simulador(srv, eu)
