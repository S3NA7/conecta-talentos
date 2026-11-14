"""Carga do MongoDB: usuários, posts (com imagens no GridFS) e notificações iniciais."""
import io
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from PIL import Image, ImageDraw

from app.servicos.seguranca import gerar_hash
from scripts.dados_exemplo import IMAGENS, NOTIFICACOES_INICIAIS, PESSOAS, TRABALHOS, gerar_posts

# O hash de senha é lento de propósito (100 mil iterações). Como a suíte recarrega os dados
# dezenas de vezes, o hash de cada usuário é calculado uma vez por processo e reaproveitado;
# cada usuário continua com o seu próprio sal aleatório.
_HASHES: dict[tuple[str, str], str] = {}


def _hash_do_usuario(usuario_id: str, senha: str) -> str:
    if (usuario_id, senha) not in _HASHES:
        _HASHES[(usuario_id, senha)] = gerar_hash(senha)
    return _HASHES[(usuario_id, senha)]


def _gerar_png(titulo: str, cor: tuple[int, int, int]) -> bytes:
    """Gráfico de barras simples, sempre igual: serve de anexo de exemplo."""
    imagem = Image.new("RGB", (480, 270), (245, 245, 245))
    desenho = ImageDraw.Draw(imagem)
    desenho.rectangle([0, 0, 480, 48], fill=cor)
    desenho.text((16, 18), titulo, fill=(255, 255, 255))
    for i, altura in enumerate((60, 110, 85, 150, 120)):
        x = 40 + i * 80
        desenho.rectangle([x, 250 - altura, x + 50, 250], fill=cor)
    saida = io.BytesIO()
    imagem.save(saida, format="PNG")
    return saida.getvalue()


def _experiencias_de(pessoa: dict) -> list[dict]:
    """Experiências do perfil, a partir dos mesmos TRABALHOS que vão para o grafo."""
    tecnologias = sorted(pessoa["habilidades"], key=lambda h: -pessoa["habilidades"][h])[:3]
    experiencias = []
    for t in sorted((t for t in TRABALHOS if t["pessoa_id"] == pessoa["id"]), key=lambda t: t["desde"], reverse=True):
        verbo = "Atua" if t["ate"] is None else "Atuou"
        experiencias.append({
            "empresa": t["empresa"], "cargo": t["cargo"], "inicio": t["desde"], "fim": t["ate"],
            "descricao": f"{verbo} como {t['cargo']} na {t['empresa']}, com foco em {', '.join(tecnologias)}.",
            "tecnologias": tecnologias})
    return experiencias


def carregar(mongo, senha_demo: str) -> dict:
    """Apaga o banco, recria o esquema e grava usuários, posts, anexos e notificações."""
    mongo.apagar_tudo()
    mongo.criar_esquema()
    agora = datetime.now(timezone.utc)

    usuarios = []
    for i, p in enumerate(PESSOAS):
        usuarios.append({
            "_id": p["id"], "nome": p["nome"], "email": p["email"],
            "senha_hash": _hash_do_usuario(p["id"], senha_demo),
            "titulo": p["titulo"], "resumo": p["resumo"], "localizacao": p["localizacao"],
            "experiencias": _experiencias_de(p), "formacao": p["formacao"],
            "certificacoes": p["certificacoes"],
            "criado_em": agora - timedelta(days=60 + i)})
    mongo.db.usuarios.insert_many(usuarios)

    # cada imagem vai para o GridFS uma vez; o post guarda só a referência
    anexos = {}
    for chave, (nome, titulo, cor) in IMAGENS.items():
        anexo = mongo.salvar_anexo(nome, "image/png", _gerar_png(titulo, cor))
        # no documento do post a referência é um ObjectId (o serviço devolve em texto)
        anexos[chave] = {**anexo, "arquivo_id": ObjectId(anexo["arquivo_id"])}

    posts = []
    for p in gerar_posts(agora):
        imagem = p.pop("imagem")
        p["anexos"] = [anexos[imagem]] if imagem else []
        posts.append(p)
    mongo.db.posts.insert_many(posts)

    mongo.criar_notificacoes(NOTIFICACOES_INICIAIS)
    return {"usuarios": len(usuarios), "posts": len(posts), "anexos": len(anexos),
            "notificacoes": len(NOTIFICACOES_INICIAIS)}
