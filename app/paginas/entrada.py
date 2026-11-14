"""Tela de entrada: login, cadastro e (no modo demonstração) troca rápida de usuário."""
import streamlit as st

from app import estado
from app.componentes.cartoes import texto_seguro
from app.config import NOME_APP
from app.servicos.erros import ErroDeNegocio

# Por que cada banco é indispensável para entrar (design, seção 9)
MOTIVOS = {
    "MongoDB": "É onde ficam os cadastros e as senhas: sem ele não dá para conferir quem está entrando.",
    "Redis": "É onde fica a sessão de quem está conectado: sem ele não dá para manter você logado.",
}


def pagina() -> None:
    srv = estado.servicos()
    _, centro, _ = st.columns([1, 2, 1])
    with centro:
        st.title(f"🤝 {NOME_APP}")
        st.caption("A rede profissional para encontrar colegas, conexões e mentores.")

        aviso = st.session_state.pop("aviso_entrada", None)
        if aviso:
            st.warning(aviso)

        bancos = srv.orq.estado_dos_bancos()
        fora = [b for b in ("MongoDB", "Redis") if not bancos[b]]
        if fora:
            _mostrar_indisponivel(fora)
            return
        if not bancos["Neo4j"]:
            st.info("A rede de conexões está indisponível agora (Neo4j fora do ar). "
                    "Você pode entrar normalmente; essa parte volta sozinha.")

        aba_entrar, aba_criar = st.tabs(["Entrar", "Criar conta"])
        with aba_entrar:
            _formulario_login(srv)
            if srv.cfg.MODO_DEMO:
                _entrar_como(srv)
        with aba_criar:
            _formulario_cadastro(srv)


def _mostrar_indisponivel(fora: list[str]) -> None:
    for banco in fora:
        st.error(f"**{banco} fora do ar.** {MOTIVOS[banco]}")
    if "Redis" in fora and st.session_state.get("token"):
        # quem já estava logado: o token continua guardado nesta aba (ver estado.usuario_atual)
        st.info("Você já tinha entrado: a sua sessão está guardada no Redis, que está fora do ar. "
                "Assim que ele voltar, clique em \"Tentar de novo\" para continuar de onde parou.")
    else:
        st.info("Por isso não é possível entrar agora. Assim que o banco voltar, clique em "
                "\"Tentar de novo\".")
    st.button("Tentar de novo", key="tentar_de_novo")  # o clique já recarrega a tela


def _formulario_login(srv) -> None:
    with st.form("form_login"):
        email = st.text_input("E-mail", key="login_email", placeholder="voce@exemplo.com")
        senha = st.text_input("Senha", type="password", key="login_senha")
        if st.form_submit_button("Entrar", key="login_entrar", type="primary", width="stretch"):
            resultado = estado.tentar(srv.orq.fazer_login, email, senha)
            if resultado:
                estado.entrar(resultado["token"])
                st.rerun()


def _entrar_como(srv) -> None:
    """Modo demonstração: troca de usuário sem digitar, usando a senha comum dos dados de exemplo.

    Passa pelo mesmo fazer_login do formulário; não existe atalho que pule a senha.
    """
    with st.container(border=True):
        st.markdown("**Modo demonstração**")
        st.caption("Escolha uma pessoa dos dados de exemplo para entrar sem digitar a senha.")
        usuarios = estado.tentar(srv.mongo.listar_usuarios)
        if not usuarios:
            return
        escolhido = st.selectbox(
            "Entrar como…", usuarios, key="demo_usuario",
            format_func=lambda u: f"{u['nome']} — {u.get('titulo', '')}")
        if st.button("Entrar como esta pessoa", key="demo_entrar", width="stretch"):
            resultado = estado.tentar(_login_demo, srv, escolhido)
            if resultado:
                estado.entrar(resultado["token"])
                st.rerun()


def _login_demo(srv, usuario: dict) -> dict:
    # tudo sob a ação "Login": o Bastidores mostra a busca do e-mail junto com o login
    with srv.registro.acao("Login"):
        perfil = srv.mongo.buscar_usuario(usuario["_id"])  # MongoDB: o e-mail da pessoa escolhida
        if perfil is None:
            raise ErroDeNegocio("Essa pessoa não está mais cadastrada.")
        try:
            return srv.orq.fazer_login(perfil["email"], srv.cfg.SENHA_DEMO)
        except ErroDeNegocio:
            # quem criou a conta pela tela tem senha própria, diferente da senha da demo
            # a mensagem vai para st.error, que aceita Markdown: o nome passa por texto_seguro
            raise ErroDeNegocio(f"Não é possível entrar como {texto_seguro(perfil['nome'])} por aqui: essa conta "
                                "tem senha própria. Use o formulário acima.") from None


def _formulario_cadastro(srv) -> None:
    with st.form("form_cadastro"):
        nome = st.text_input("Nome completo", key="cad_nome")
        email = st.text_input("E-mail", key="cad_email", placeholder="voce@exemplo.com")
        titulo = st.text_input("Título profissional", key="cad_titulo",
                               placeholder="Ex.: Desenvolvedora Back-end")
        senha = st.text_input("Senha", type="password", key="cad_senha",
                              help="Pelo menos 6 caracteres.")
        if st.form_submit_button("Criar conta", key="cad_criar", type="primary", width="stretch"):
            if estado.tentar(srv.orq.cadastrar_usuario, nome, email, senha, titulo) is None:
                return
            # conta criada: entra direto, sem pedir os dados de novo
            resultado = estado.tentar(srv.orq.fazer_login, email, senha)
            if resultado:
                estado.entrar(resultado["token"])
                st.rerun()
