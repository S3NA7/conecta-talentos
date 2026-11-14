"""MongoService: tudo que a aplicação faz no MongoDB (perfis, posts, anexos, notificações)."""
from contextlib import contextmanager
from datetime import datetime, timezone

import gridfs
from bson import ObjectId
from bson.errors import InvalidId
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, DuplicateKeyError

from app.servicos.disjuntor import Disjuntor
from app.servicos.erros import BancoIndisponivel, EmailJaCadastrado
from app.servicos.registro import Registro

CAMPOS_DE_LISTA = ("experiencias", "formacao", "certificacoes")
TTL_NOTIFICACOES_SEGUNDOS = 30 * 24 * 3600  # 2592000 = 30 dias


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _com_id_texto(doc: dict) -> dict:
    """Troca o ObjectId do documento por str (as páginas só veem str)."""
    doc["_id"] = str(doc["_id"])
    return doc


class MongoService:
    def __init__(self, uri: str, banco: str, registro: Registro | None = None):
        self.registro = registro if registro is not None else Registro()
        # tz_aware: datas voltam do Mongo com fuso UTC
        self.client = MongoClient(uri, tz_aware=True, serverSelectionTimeoutMS=2000)
        self.db = self.client[banco]
        self.fs = gridfs.GridFS(self.db)
        self.disjuntor = Disjuntor("MongoDB")

    @contextmanager
    def _op(self, comando: str):
        """Registra a operação no painel; falha de conexão vira BancoIndisponivel.

        Antes, o disjuntor confere se não estamos na pausa depois de uma falha (disjuntor.py).
        """
        self.disjuntor.conferir()
        try:
            with self.registro.medir("MongoDB", comando, erros_conexao=(ConnectionFailure,)):
                yield
        except BancoIndisponivel:
            self.disjuntor.falhou()
            raise
        self.disjuntor.funcionou()

    # ---------- infraestrutura ----------

    def close(self) -> None:
        self.client.close()

    def ping(self) -> bool:
        try:
            with self._op("ping"):
                self.client.admin.command("ping")
            return True
        except Exception:
            return False

    def criar_esquema(self) -> None:
        """Cria coleções com validador e índices; pode rodar várias vezes."""
        validadores = {
            "usuarios": {"$jsonSchema": {
                "bsonType": "object",
                "required": ["nome", "email", "titulo"],
                "properties": {
                    "nome": {"bsonType": "string"},
                    "email": {"bsonType": "string"},
                    "titulo": {"bsonType": "string"},
                },
            }},
            "posts": {"$jsonSchema": {
                "bsonType": "object",
                "required": ["autor_id", "texto", "criado_em"],
            }},
            "notificacoes": None,
        }
        with self._op("criar coleções e índices"):
            existentes = self.db.list_collection_names()
            for nome, validador in validadores.items():
                if nome not in existentes:
                    if validador:
                        self.db.create_collection(nome, validator=validador)
                    else:
                        self.db.create_collection(nome)
                elif validador:
                    self.db.command("collMod", nome, validator=validador)

            self.db.usuarios.create_index("email", unique=True)
            self.db.posts.create_index([("autor_id", 1), ("criado_em", -1)])
            self.db.posts.create_index([("criado_em", -1)])
            self.db.posts.create_index([("tags", 1)])
            self.db.notificacoes.create_index([("usuario_id", 1), ("criado_em", -1)])
            # índice TTL: o próprio Mongo apaga notificações com mais de 30 dias
            self.db.notificacoes.create_index(
                "criado_em", expireAfterSeconds=TTL_NOTIFICACOES_SEGUNDOS)

    def apagar_tudo(self) -> None:
        with self._op("drop_database"):
            self.client.drop_database(self.db.name)

    # ---------- usuários ----------

    def inserir_usuario(self, usuario: dict) -> str:
        doc = dict(usuario)
        doc["email"] = doc["email"].strip().lower()
        doc.setdefault("criado_em", _agora())
        try:
            with self._op("usuarios.insert_one"):
                self.db.usuarios.insert_one(doc)
        except DuplicateKeyError as erro:
            raise EmailJaCadastrado("Este e-mail já está cadastrado.") from erro
        return doc["_id"]

    def remover_usuario(self, usuario_id: str) -> None:
        with self._op("usuarios.delete_one"):
            self.db.usuarios.delete_one({"_id": usuario_id})

    def buscar_usuario(self, usuario_id: str) -> dict | None:
        with self._op("usuarios.find_one"):
            return self.db.usuarios.find_one({"_id": usuario_id}, {"senha_hash": 0})

    def buscar_usuario_por_email(self, email: str) -> dict | None:
        with self._op("usuarios.find_one (por e-mail)"):
            return self.db.usuarios.find_one({"email": email.strip().lower()})

    def listar_usuarios(self) -> list[dict]:
        with self._op("usuarios.find (nome, título)"):
            return list(self.db.usuarios.find({}, {"nome": 1, "titulo": 1}).sort("nome", 1))

    def proximo_id_usuario(self) -> str:
        with self._op("usuarios.find_one (maior _id)"):
            ultimo = self.db.usuarios.find_one({}, {"_id": 1}, sort=[("_id", -1)])
        if ultimo is None:
            return "u001"
        return "u%03d" % (int(ultimo["_id"][1:]) + 1)

    def atualizar_dados_basicos(self, usuario_id: str, *, titulo=None, resumo=None, localizacao=None) -> None:
        campos = {"titulo": titulo, "resumo": resumo, "localizacao": localizacao}
        campos = {k: v for k, v in campos.items() if v is not None}
        if not campos:
            return
        with self._op("usuarios.update_one ($set)"):
            self.db.usuarios.update_one({"_id": usuario_id}, {"$set": campos})

    def atualizar_titulo_nos_posts(self, usuario_id: str, titulo: str) -> int:
        """O post guarda uma cópia do título do autor; quando ele muda, a cópia é atualizada."""
        with self._op("posts.update_many ($set autor.titulo)"):
            return self.db.posts.update_many(
                {"autor_id": usuario_id}, {"$set": {"autor.titulo": titulo}}).matched_count

    def _validar_campo(self, campo: str) -> None:
        if campo not in CAMPOS_DE_LISTA:
            raise ValueError(f"Campo inválido: {campo}")

    def adicionar_item(self, usuario_id: str, campo: str, item: dict) -> None:
        self._validar_campo(campo)
        with self._op(f"usuarios.update_one ($push {campo})"):
            self.db.usuarios.update_one({"_id": usuario_id}, {"$push": {campo: item}})

    def remover_item(self, usuario_id: str, campo: str, item: dict) -> int:
        """Remove o item igual a `item`; devolve 1 se o perfil mudou, 0 se nada casou."""
        self._validar_campo(campo)
        with self._op(f"usuarios.update_one ($pull {campo})"):
            return self.db.usuarios.update_one(
                {"_id": usuario_id}, {"$pull": {campo: item}}).modified_count

    # ---------- posts ----------

    @staticmethod
    def _post_para_texto(post: dict | None) -> dict | None:
        """ObjectId do post e dos anexos viram str."""
        if post is not None:
            _com_id_texto(post)
            for anexo in post.get("anexos", []):
                anexo["arquivo_id"] = str(anexo["arquivo_id"])
        return post

    def criar_post(self, autor: dict, texto: str, tags: list[str], anexos: list[dict]) -> str:
        # arquivo_id chega como str; no documento fica como ObjectId (referência do GridFS)
        anexos_doc = [{**a, "arquivo_id": ObjectId(a["arquivo_id"])} for a in anexos]
        doc = {
            "autor_id": autor["id"],
            "autor": {"nome": autor["nome"], "titulo": autor["titulo"]},
            "texto": texto,
            "tags": tags,
            "anexos": anexos_doc,
            "curtidas": [],
            "comentarios": [],
            "criado_em": _agora(),
        }
        with self._op("posts.insert_one"):
            return str(self.db.posts.insert_one(doc).inserted_id)

    def buscar_post(self, post_id: str) -> dict | None:
        # id malformado é tratado como post inexistente (mesma regra de ler_anexo)
        try:
            oid = ObjectId(post_id)
        except (InvalidId, TypeError):
            return None
        with self._op("posts.find_one"):
            return self._post_para_texto(self.db.posts.find_one({"_id": oid}))

    def listar_posts(self, autores_ids: list[str], limite: int = 30, tag: str | None = None) -> list[dict]:
        if not autores_ids:
            return []
        filtro = {"autor_id": {"$in": autores_ids}}
        if tag:
            filtro["tags"] = tag
        with self._op("posts.find (feed)"):
            # _id desc desempata posts criados no mesmo instante
            posts = self.db.posts.find(filtro).sort([("criado_em", -1), ("_id", -1)]).limit(limite)
            return [self._post_para_texto(p) for p in posts]

    def curtir(self, post_id: str, usuario_id: str) -> bool:
        """Alterna a curtida; devolve True se o post ficou curtido."""
        oid = ObjectId(post_id)
        with self._op("posts.update_one ($pull/$addToSet curtidas)"):
            retirou = self.db.posts.update_one(
                {"_id": oid, "curtidas": usuario_id}, {"$pull": {"curtidas": usuario_id}})
            if retirou.modified_count:
                return False
            self.db.posts.update_one({"_id": oid}, {"$addToSet": {"curtidas": usuario_id}})
            return True

    def comentar(self, post_id: str, autor: dict, texto: str) -> None:
        comentario = {"autor_id": autor["id"], "autor_nome": autor["nome"],
                      "texto": texto, "criado_em": _agora()}
        with self._op("posts.update_one ($push comentarios)"):
            self.db.posts.update_one({"_id": ObjectId(post_id)}, {"$push": {"comentarios": comentario}})

    def tags_em_alta(self, limite: int = 8) -> list[dict]:
        pipeline = [
            {"$unwind": "$tags"},
            {"$group": {"_id": "$tags", "total": {"$sum": 1}}},
            {"$sort": {"total": -1, "_id": 1}},
            {"$limit": limite},
        ]
        with self._op("posts.aggregate (tags em alta)"):
            return [{"tag": r["_id"], "total": r["total"]} for r in self.db.posts.aggregate(pipeline)]

    # ---------- anexos (GridFS) ----------

    def salvar_anexo(self, nome: str, tipo: str, conteudo: bytes) -> dict:
        with self._op("GridFS.put"):
            arquivo_id = self.fs.put(conteudo, filename=nome, content_type=tipo)
        return {"arquivo_id": str(arquivo_id), "nome": nome, "tipo": tipo, "tamanho": len(conteudo)}

    def ler_anexo(self, arquivo_id: str) -> bytes | None:
        try:
            oid = ObjectId(arquivo_id)
        except (InvalidId, TypeError):
            return None
        with self._op("GridFS.get"):
            try:
                return self.fs.get(oid).read()
            except gridfs.NoFile:
                return None

    # ---------- notificações ----------

    def criar_notificacoes(self, notificacoes: list[dict]) -> int:
        if not notificacoes:
            return 0
        # cópias: os dicionários de quem chamou não são alterados
        docs = [{**n, "lida": False, "criado_em": _agora()} for n in notificacoes]
        with self._op("notificacoes.insert_many"):
            return len(self.db.notificacoes.insert_many(docs).inserted_ids)

    def listar_notificacoes(self, usuario_id: str, limite: int = 30) -> list[dict]:
        with self._op("notificacoes.find"):
            cursor = self.db.notificacoes.find({"usuario_id": usuario_id}).sort(
                [("criado_em", -1), ("_id", -1)]).limit(limite)
            return [_com_id_texto(n) for n in cursor]

    def marcar_notificacoes_lidas(self, usuario_id: str) -> int:
        with self._op("notificacoes.update_many ($set lida)"):
            return self.db.notificacoes.update_many(
                {"usuario_id": usuario_id, "lida": False}, {"$set": {"lida": True}}).modified_count
