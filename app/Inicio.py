"""Ponto de entrada: `streamlit run app/Inicio.py`."""
import sys
from pathlib import Path

# o Streamlit roda este arquivo como script: a raiz do projeto entra no caminho para
# os imports `from app...` funcionarem
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

from app import estado  # noqa: E402
from app.componentes import bastidores  # noqa: E402
from app.componentes.cartoes import texto_seguro  # noqa: E402
from app.config import NOME_APP  # noqa: E402
from app.paginas import entrada, feed_perfil, presenca_notificacoes, rede_mentores  # noqa: E402
from app.servicos.erros import BancoIndisponivel  # noqa: E402

st.set_page_config(page_title=NOME_APP, page_icon="🤝", layout="wide")


# st.fragment: só esta função roda de novo a cada 10 s, sem recarregar a página inteira.
# Assim a presença é renovada e o sininho se atualiza enquanto a pessoa só lê a tela.
@st.fragment(run_every=10)
def sininho(usuario_id: str) -> None:
    srv = estado.servicos()
    # pausado: a atualização automática não deve encher o Bastidores a cada 10 s
    with srv.registro.pausado():
        try:
            srv.redis.sinal_de_presenca(usuario_id)  # Redis: "estou online"
            total = srv.redis.nao_lidas(usuario_id)  # Redis: contador do sininho
        except BancoIndisponivel:
            total = None
    if total is None:
        st.markdown("🔔 —")
    elif total == 1:
        st.markdown("🔔 **1** não lida")
    else:
        st.markdown(f"🔔 **{total}** não lidas")


def barra_lateral(usuario: dict) -> None:
    srv = estado.servicos()
    with st.sidebar:
        st.markdown(f"**👤 {texto_seguro(usuario['nome'])}**")  # o primeiro markdown da barra é o nome
        sininho(usuario["id"])
        st.divider()
        st.caption("Bancos de dados")
        for banco, ok in srv.orq.estado_dos_bancos().items():
            st.markdown(f"{'🟢' if ok else '🔴'} {banco} · {'conectado' if ok else 'fora do ar'}")
        st.divider()
        if st.button("Sair", key="sair", width="stretch"):
            estado.sair()
            st.rerun()


estado.servicos()
usuario = estado.usuario_atual()
if usuario is None:
    entrada.pagina()
    st.stop()

barra_lateral(usuario)
st.navigation([
    st.Page(feed_perfil.pagina, title="Feed & Perfil", icon="📰", url_path="feed", default=True),
    st.Page(presenca_notificacoes.pagina, title="Presença & Notificações", icon="🟢", url_path="presenca"),
    st.Page(rede_mentores.pagina, title="Rede & Mentores", icon="🕸️", url_path="rede"),
]).run()
bastidores.painel()
