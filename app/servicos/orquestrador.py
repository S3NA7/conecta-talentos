"""Orquestrador: cada método público é uma ação de negócio que usa mais de um banco.

Regra de consistência (design, seção 8), a mesma em todos os métodos:
1. Dado que existe em dois bancos (Mongo e Neo4j) tem de ficar igual nos dois. Grava-se
   primeiro no MongoDB (fonte da verdade); se o Neo4j falhar, a gravação do Mongo é desfeita
   (compensação) e a ação inteira é recusada.
2. Efeito colateral (notificação, contador, presença, cache) nunca desfaz a ação principal:
   se falhar, a ação continua valendo e a tela recebe um aviso em `avisos`.
"""
import io
import random
import time
from datetime import datetime

from PIL import Image

from app.config import (ANEXO_MAX_BYTES, ANEXO_TIPOS, CACHE_PERFIL_TTL, CACHE_TAGS_TTL)
from app.servicos.erros import BancoIndisponivel, ErroDeNegocio
from app.servicos.seguranca import conferir_senha, gerar_hash

CHAVE_TAGS = "cache:tags_em_alta"
CAMPOS_PERFIL_SO_MONGO = ("formacao", "certificacoes")
MAX_TAGS = 5


def _chave_perfil(usuario_id: str) -> str:
    return f"cache:perfil:{usuario_id}"


def _normalizar_tags(tags: list[str]) -> list[str]:
    """Minúsculas, sem # no começo, sem espaços nas pontas, sem vazias nem repetidas; até 5."""
    resultado = []
    for tag in tags:
        tag = tag.strip().lstrip("#").strip().lower()
        if tag and tag not in resultado:
            resultado.append(tag)
    return resultado[:MAX_TAGS]


def _conteudo_confere(tipo: str, conteudo: bytes) -> bool:
    """O tipo vem do navegador de quem enviou; aqui se confere se os bytes são mesmo daquele tipo.

    Imagem: o Pillow abre e verifica o arquivo (verify() lê a estrutura sem decodificar tudo) e
    o formato detectado tem de ser o declarado. MPO é o JPEG com várias imagens dentro que muitos
    celulares gravam: continua sendo image/jpeg. PDF: todo PDF começa com "%PDF-".
    """
    if tipo == "application/pdf":
        return conteudo.startswith(b"%PDF-")
    formatos_aceitos = {"image/png": {"PNG"}, "image/jpeg": {"JPEG", "MPO"}}.get(tipo, set())
    try:
        with Image.open(io.BytesIO(conteudo)) as imagem:
            formato = imagem.format
            imagem.verify()
    except Exception:  # o Pillow levanta erros variados para arquivo corrompido
        return False
    return formato in formatos_aceitos


def _texto_obrigatorio(valor, minimo: int, maximo: int, mensagem: str) -> str:
    """Tira os espaços das pontas e confere o tamanho; fora do limite vira ErroDeNegocio."""
    valor = (valor or "").strip()
    if not minimo <= len(valor) <= maximo:
        raise ErroDeNegocio(mensagem)
    return valor


class Orquestrador:
    def __init__(self, mongo, redis, neo4j, registro, cfg):
        self.mongo = mongo
        self.redis = redis
        self.neo4j = neo4j
        self.registro = registro
        self.cfg = cfg

    # ---------- apoio interno ----------

    def _notificar(self, destinatarios: list[str], tipo: str, de: dict, texto: str) -> list[str]:
        """Grava a notificação no Mongo (histórico) e no Redis (contador + lista curta).

        As duas gravações são independentes e "melhor esforço": se uma falhar, a outra ainda
        é tentada, e a falha vira um aviso, nunca uma exceção (regra 2).
        """
        # dict.fromkeys tira repetidos mantendo a ordem; ninguém notifica a si mesmo
        destinos = [d for d in dict.fromkeys(destinatarios) if d != de["id"]]
        if not destinos:
            return []
        avisos = []
        try:
            self.mongo.criar_notificacoes([
                {"usuario_id": d, "tipo": tipo, "de": de, "texto": texto} for d in destinos])
        except BancoIndisponivel:
            avisos.append("A notificação não foi guardada no histórico (MongoDB fora do ar).")
        try:
            self.redis.notificar_varios(destinos, {"tipo": tipo, "de": de, "texto": texto,
                                                   "quando": time.time()})
        except BancoIndisponivel:
            avisos.append("A notificação não chegou na hora ao sininho (Redis fora do ar).")
        return avisos

    def _usuario(self, usuario_id: str) -> dict:
        """Perfil do Mongo (sem a senha); usuário inexistente vira ErroDeNegocio."""
        usuario = self.mongo.buscar_usuario(usuario_id)
        if usuario is None:
            raise ErroDeNegocio("Usuário não encontrado.")
        return usuario

    def _pessoa(self, pessoa_id: str) -> dict:
        """Nó :Pessoa do grafo; pessoa inexistente vira ErroDeNegocio."""
        pessoa = self.neo4j.buscar_pessoa(pessoa_id)
        if pessoa is None:
            raise ErroDeNegocio("Pessoa não encontrada.")
        return pessoa

    def _post(self, post_id: str) -> dict:
        post = self.mongo.buscar_post(post_id)
        if post is None:
            raise ErroDeNegocio("Post não encontrado.")
        return post

    def _apagar_cache(self, chave: str) -> None:
        # cache é efeito colateral: se o Redis falhar, a entrada expira sozinha pelo TTL
        try:
            self.redis.cache_apagar(chave)
        except BancoIndisponivel:
            pass

    # ---------- estado, login e sessão ----------

    def estado_dos_bancos(self) -> dict:
        # pausado: a barra lateral pergunta isto a cada tela e não deve poluir o painel
        with self.registro.pausado():
            return {"MongoDB": self.mongo.ping(), "Redis": self.redis.ping(), "Neo4j": self.neo4j.ping()}

    def fazer_login(self, email: str, senha: str) -> dict:
        with self.registro.acao("Login"):
            # MongoDB: fonte da verdade do usuário e do hash da senha
            usuario = self.mongo.buscar_usuario_por_email(email or "")
            # a mesma mensagem nos dois casos: não revela se o e-mail existe
            if usuario is None or not conferir_senha(senha or "", usuario.get("senha_hash")):
                raise ErroDeNegocio("E-mail ou senha inválidos.")
            # Redis: sessão (com TTL) e presença. Sem Redis não há sessão, então a falha
            # aqui recusa o login (BancoIndisponivel sobe para a tela)
            token = self.redis.criar_sessao(usuario["_id"], usuario["nome"])
            return {"token": token,
                    "usuario": {"id": usuario["_id"], "nome": usuario["nome"], "titulo": usuario["titulo"]}}

    def validar_sessao(self, token: str) -> dict | None:
        # pausado: roda a cada interação da tela
        with self.registro.pausado():
            sessao = self.redis.validar_sessao(token)  # Redis: renova o TTL da sessão
            # numa corrida rara (a chave expira enquanto é renovada) o hash volta sem usuario_id
            if not sessao or "usuario_id" not in sessao:
                return None
            self.redis.sinal_de_presenca(sessao["usuario_id"])  # Redis: renova a presença
            return {"usuario_id": sessao["usuario_id"], "nome": sessao.get("nome", "")}

    def sair(self, token: str) -> None:
        with self.registro.acao("Sair"):
            # Redis: apaga a sessão; sem outras sessões abertas, a pessoa fica offline
            self.redis.encerrar_sessao(token)

    def cadastrar_usuario(self, nome: str, email: str, senha: str, titulo: str) -> str:
        with self.registro.acao("Cadastro"):
            nome = _texto_obrigatorio(nome, 3, 80, "O nome deve ter de 3 a 80 caracteres.")
            titulo = _texto_obrigatorio(titulo, 2, 80, "O título deve ter de 2 a 80 caracteres.")
            email = (email or "").strip().lower()
            if "@" not in email:
                raise ErroDeNegocio("Informe um e-mail válido.")
            if len(senha or "") < 6:
                raise ErroDeNegocio("A senha deve ter pelo menos 6 caracteres.")

            # MongoDB primeiro (fonte da verdade). E-mail repetido para aqui com
            # EmailJaCadastrado, antes de tocar o Neo4j: nenhum nó órfão no grafo.
            novo_id = self.mongo.proximo_id_usuario()
            self.mongo.inserir_usuario({
                "_id": novo_id, "nome": nome, "email": email, "senha_hash": gerar_hash(senha),
                "titulo": titulo, "resumo": "", "localizacao": {"cidade": "", "estado": ""},
                "experiencias": [], "formacao": [], "certificacoes": []})
            # Neo4j: cópia mínima (nó :Pessoa). Se falhar, compensação: remove o perfil do
            # Mongo e o cadastro inteiro é recusado (regra 1)
            try:
                self.neo4j.criar_pessoa(novo_id, nome, titulo)
            except Exception:
                self.mongo.remover_usuario(novo_id)
                raise
            return novo_id

    # ---------- perfil ----------

    def abrir_perfil(self, usuario_id: str) -> dict:
        # leitura=True: só lê para desenhar a tela; o painel Bastidores a esconde por padrão
        with self.registro.acao("Abrir perfil", leitura=True):
            avisos = []
            # Redis: cache-aside. Primeiro procura o perfil no cache; cache fora do ar
            # conta como "não achou" e o perfil é lido direto do Mongo
            try:
                perfil = self.redis.cache_ler(_chave_perfil(usuario_id))
            except BancoIndisponivel:
                perfil = None
            # um valor que não é dicionário (alguém gravou outra coisa na chave) também é MISS:
            # o perfil é lido do Mongo e o cache, regravado por cima
            do_cache = isinstance(perfil, dict)
            if not do_cache:
                # MongoDB: fonte da verdade do perfil (já vem sem senha_hash)
                perfil = self._usuario(usuario_id)
                # o cache guarda JSON, onde a data vira texto; aqui também, para a tela
                # receber sempre o mesmo formato, venha do cache ou do banco
                if isinstance(perfil.get("criado_em"), datetime):
                    perfil["criado_em"] = perfil["criado_em"].isoformat()
                try:
                    self.redis.cache_gravar(_chave_perfil(usuario_id), perfil, CACHE_PERFIL_TTL)
                except BancoIndisponivel:
                    pass  # sem cache a próxima abertura só lê o Mongo de novo
            # Neo4j: habilidades, interesses, empregos e nº de conexões vêm ao vivo do grafo.
            # Se cair, o perfil do Mongo continua na tela e o bloco do grafo mostra um aviso
            try:
                habilidades = self.neo4j.habilidades_de(usuario_id)
                interesses = self.neo4j.interesses_de(usuario_id)
                trabalhos = self.neo4j.trabalhos_de(usuario_id)
                total_conexoes = len(self.neo4j.ids_conexoes(usuario_id))
            except BancoIndisponivel:
                habilidades = interesses = trabalhos = total_conexoes = None
                avisos.append("Habilidades e conexões estão indisponíveis agora (Neo4j fora do ar).")
            # Redis: presença (sem Redis, mostra como offline)
            try:
                online = self.redis.esta_online(usuario_id)
            except BancoIndisponivel:
                online = False
            return {"perfil": perfil, "do_cache": do_cache, "habilidades": habilidades,
                    "interesses": interesses, "trabalhos": trabalhos,
                    "total_conexoes": total_conexoes, "online": online, "avisos": avisos}

    def editar_dados_basicos(self, usuario_id: str, *, titulo: str, resumo: str,
                             cidade: str, estado: str) -> None:
        with self.registro.acao("Editar perfil"):
            titulo = _texto_obrigatorio(titulo, 1, 80, "O título deve ter até 80 caracteres e não pode ficar vazio.")
            antes = self._usuario(usuario_id)
            # MongoDB primeiro (fonte da verdade do título, do resumo e da localização)
            self.mongo.atualizar_dados_basicos(
                usuario_id, titulo=titulo, resumo=(resumo or "").strip(),
                localizacao={"cidade": (cidade or "").strip(), "estado": (estado or "").strip()})
            if titulo != antes["titulo"]:
                # Neo4j: o título é copiado em :Pessoa.titulo. Se falhar, compensação: o Mongo
                # volta aos valores antigos e a edição é recusada (regra 1)
                try:
                    self.neo4j.atualizar_pessoa(usuario_id, titulo=titulo)
                except Exception:
                    self.mongo.atualizar_dados_basicos(
                        usuario_id, titulo=antes["titulo"], resumo=antes.get("resumo", ""),
                        localizacao=antes.get("localizacao", {}))
                    raise
                # MongoDB: a cópia do título nos posts (posts.autor.titulo). Usuário e grafo já
                # estão certos; se só isto falhar, os posts antigos mostram o título anterior
                self.mongo.atualizar_titulo_nos_posts(usuario_id, titulo)
            # Redis: o perfil em cache ficou velho
            self._apagar_cache(_chave_perfil(usuario_id))

    @staticmethod
    def _validar_experiencia(exp: dict) -> dict:
        empresa = (exp.get("empresa") or "").strip()
        cargo = (exp.get("cargo") or "").strip()
        inicio = (exp.get("inicio") or "").strip()
        if not (empresa and cargo and inicio):
            raise ErroDeNegocio("Empresa, cargo e início são obrigatórios.")
        return {"empresa": empresa, "cargo": cargo, "inicio": inicio,
                "fim": (exp.get("fim") or "").strip() or None,
                "descricao": (exp.get("descricao") or "").strip()}

    @staticmethod
    def _chave_experiencia(exp: dict) -> tuple:
        """Identidade de uma experiência nos DOIS bancos: (empresa, cargo, inicio).
        No grafo é a chave do MERGE de TRABALHA_EM {cargo, desde} na Empresa."""
        return tuple((exp.get(c) or "").strip() for c in ("empresa", "cargo", "inicio"))

    def _experiencia_guardada(self, usuario: dict, exp: dict) -> dict | None:
        """A experiência do perfil com a mesma chave de `exp` (exatamente como está no Mongo)."""
        chave = self._chave_experiencia(exp)
        for guardada in usuario.get("experiencias", []):
            if self._chave_experiencia(guardada) == chave:
                return guardada
        return None

    def adicionar_experiencia(self, usuario_id: str, exp: dict) -> None:
        with self.registro.acao("Editar experiência"):
            exp = self._validar_experiencia(exp)
            usuario = self._usuario(usuario_id)
            # mesma chave duas vezes: o grafo juntaria as duas num só TRABALHA_EM e os
            # bancos deixariam de bater; por isso a repetida é recusada antes de gravar
            if self._experiencia_guardada(usuario, exp) is not None:
                raise ErroDeNegocio("Essa experiência já está no seu perfil.")
            # MongoDB primeiro: a experiência completa ($push em experiencias)
            self.mongo.adicionar_item(usuario_id, "experiencias", exp)
            # Neo4j: relacionamento TRABALHA_EM {cargo, desde, ate}. Se falhar, compensação:
            # tira a experiência do Mongo e a edição é recusada (regra 1)
            try:
                self.neo4j.registrar_trabalho(usuario_id, exp["empresa"], exp["cargo"],
                                              exp["inicio"], exp["fim"])
            except Exception:
                self.mongo.remover_item(usuario_id, "experiencias", exp)
                raise
            # Redis: o perfil em cache ficou velho
            self._apagar_cache(_chave_perfil(usuario_id))

    def remover_experiencia(self, usuario_id: str, exp: dict) -> None:
        with self.registro.acao("Editar experiência"):
            self._validar_experiencia(exp)
            # a tela pode mandar um dicionário um pouco diferente do guardado (fim "" em vez
            # de None, sem "descricao"...). Por isso a experiência é achada pela chave
            # (empresa, cargo, inicio) e o $pull usa o item exatamente como está no Mongo
            guardada = self._experiencia_guardada(self._usuario(usuario_id), exp)
            if guardada is None:
                raise ErroDeNegocio("Experiência não encontrada.")
            # MongoDB primeiro: $pull em experiencias; 0 = nada saiu, então o grafo não é tocado
            if self.mongo.remover_item(usuario_id, "experiencias", guardada) == 0:
                raise ErroDeNegocio("Experiência não encontrada.")
            # Neo4j: apaga o TRABALHA_EM com a mesma chave. Se falhar, compensação: devolve
            # ao Mongo exatamente o item removido (vai para o fim da lista) e a remoção é
            # recusada (regra 1)
            empresa, cargo, inicio = self._chave_experiencia(guardada)
            try:
                self.neo4j.remover_trabalho(usuario_id, empresa, cargo, inicio)
            except Exception:
                self.mongo.adicionar_item(usuario_id, "experiencias", guardada)
                raise
            # Redis: o perfil em cache ficou velho
            self._apagar_cache(_chave_perfil(usuario_id))

    def adicionar_item_perfil(self, usuario_id: str, campo: str, item: dict) -> None:
        with self.registro.acao("Editar perfil"):
            if campo not in CAMPOS_PERFIL_SO_MONGO:
                raise ErroDeNegocio("Este campo do perfil não pode ser editado aqui.")
            # só MongoDB: formação e certificações não existem no grafo
            self.mongo.adicionar_item(usuario_id, campo, item)
            self._apagar_cache(_chave_perfil(usuario_id))  # Redis: cache do perfil ficou velho

    def remover_item_perfil(self, usuario_id: str, campo: str, item: dict) -> None:
        with self.registro.acao("Editar perfil"):
            if campo not in CAMPOS_PERFIL_SO_MONGO:
                raise ErroDeNegocio("Este campo do perfil não pode ser editado aqui.")
            # só MongoDB
            self.mongo.remover_item(usuario_id, campo, item)
            self._apagar_cache(_chave_perfil(usuario_id))  # Redis: cache do perfil ficou velho

    # ---------- dados que só existem no grafo ----------
    # (o cache do perfil guarda só o documento do Mongo, então não há cache a apagar)

    def definir_habilidade(self, usuario_id: str, habilidade: str, nivel: int) -> None:
        with self.registro.acao("Editar habilidades"):
            habilidade = _texto_obrigatorio(habilidade, 1, 60, "Informe o nome da habilidade.")
            if isinstance(nivel, bool) or not isinstance(nivel, int) or not 1 <= nivel <= 5:
                raise ErroDeNegocio("O nível deve ser de 1 a 5.")
            self.neo4j.definir_habilidade(usuario_id, habilidade, nivel)  # só Neo4j

    def remover_habilidade(self, usuario_id: str, habilidade: str) -> None:
        with self.registro.acao("Editar habilidades"):
            self.neo4j.remover_habilidade(usuario_id, habilidade)  # só Neo4j

    def definir_mentoria(self, usuario_id: str, mentor: bool, anos_experiencia: int) -> None:
        with self.registro.acao("Editar perfil"):
            if isinstance(anos_experiencia, bool) or not isinstance(anos_experiencia, int) \
                    or not 0 <= anos_experiencia <= 60:
                raise ErroDeNegocio("Anos de experiência deve ser um número de 0 a 60.")
            # só Neo4j: disponibilidade para mentoria e anos de experiência
            self.neo4j.atualizar_pessoa(usuario_id, mentor=bool(mentor), anos_experiencia=anos_experiencia)

    def definir_interesses(self, usuario_id: str, habilidades: list[str]) -> None:
        with self.registro.acao("Salvar interesses"):
            nomes = list(dict.fromkeys(h.strip() for h in habilidades if h and h.strip()))
            self.neo4j.definir_interesses(usuario_id, nomes)  # só Neo4j (QUER_APRENDER)

    # ---------- feed e posts ----------

    def montar_feed(self, usuario_id: str, tag: str | None = None) -> dict:
        with self.registro.acao("Montar feed", leitura=True):  # só leitura (ver abrir_perfil)
            avisos = []
            # Neo4j: de quem são os posts do feed (eu + minhas conexões).
            # Fora do ar: o feed mostra só os meus posts, com aviso
            try:
                ids = [usuario_id] + self.neo4j.ids_conexoes(usuario_id)
            except BancoIndisponivel:
                ids = [usuario_id]
                avisos.append("Mostrando só os seus posts: as conexões estão indisponíveis (Neo4j fora do ar).")
            # MongoDB: os posts desses autores
            posts = self.mongo.listar_posts(ids, tag=tag)
            # Redis: a bolinha verde de cada autor (sem Redis, todos aparecem offline)
            try:
                presenca = self.redis.presenca_de(sorted({p["autor_id"] for p in posts}))
            except BancoIndisponivel:
                presenca = {}
            for post in posts:
                post["autor_online"] = presenca.get(post["autor_id"], {}).get("online", False)
            return {"posts": posts, "avisos": avisos}

    def publicar_post(self, usuario_id: str, texto: str, tags: list[str], arquivo=None) -> dict:
        with self.registro.acao("Publicar post"):
            # tudo é validado antes de qualquer gravação
            texto = _texto_obrigatorio(texto, 1, 1000, "O post deve ter de 1 a 1000 caracteres.")
            tags = _normalizar_tags(tags or [])
            if arquivo is not None:
                nome_arquivo, tipo, conteudo = arquivo
                if tipo not in ANEXO_TIPOS:
                    raise ErroDeNegocio("Anexo não aceito: envie uma imagem PNG ou JPEG, ou um PDF.")
                if len(conteudo) > ANEXO_MAX_BYTES:
                    raise ErroDeNegocio("O anexo passa do limite de 5 MB.")
                if not _conteudo_confere(tipo, conteudo):
                    raise ErroDeNegocio("O arquivo anexado não é uma imagem ou um PDF válido.")
            autor = self._usuario(usuario_id)

            # MongoDB: anexo no GridFS e o post (a ação principal). Se o post falhar depois do
            # anexo, sobra um arquivo sem post no GridFS, que ninguém vê
            anexos = []
            if arquivo is not None:
                anexos.append(self.mongo.salvar_anexo(nome_arquivo, tipo, conteudo))
            post_id = self.mongo.criar_post(
                {"id": usuario_id, "nome": autor["nome"], "titulo": autor["titulo"]}, texto, tags, anexos)
            # Redis: as tags em alta mudaram (se falhar, o cache expira sozinho em 60 s)
            self._apagar_cache(CHAVE_TAGS)

            # Neo4j: quem deve ser notificado. Fora do ar: o post continua salvo, com aviso
            avisos = []
            try:
                conexoes = self.neo4j.ids_conexoes(usuario_id)
            except BancoIndisponivel:
                conexoes = []
                avisos.append("Post publicado, mas suas conexões não foram notificadas (Neo4j fora do ar).")
            # MongoDB + Redis: notificações (efeito colateral; falha vira aviso)
            de = {"id": usuario_id, "nome": autor["nome"]}
            avisos_notificacao = self._notificar(conexoes, "post", de, f"{autor['nome']} publicou um post novo.")
            avisos += avisos_notificacao
            # se o histórico (Mongo) e o sininho (Redis) falharam, ninguém foi notificado
            notificados = 0 if len(avisos_notificacao) == 2 else len([c for c in conexoes if c != usuario_id])
            return {"post_id": post_id, "notificados": notificados, "avisos": avisos}

    def curtir_post(self, usuario_id: str, post_id: str) -> dict:
        with self.registro.acao("Curtir"):
            post = self._post(post_id)
            nome = self._usuario(usuario_id)["nome"]
            # MongoDB: alterna a curtida (ação principal)
            curtido = self.mongo.curtir(post_id, usuario_id)
            # MongoDB + Redis: só notifica ao curtir (não ao descurtir) post de outra pessoa.
            # Se a notificação falhar, a curtida continua valendo e a tela mostra o aviso
            avisos = []
            if curtido and post["autor_id"] != usuario_id:
                avisos = self._notificar([post["autor_id"]], "curtida", {"id": usuario_id, "nome": nome},
                                         f"{nome} curtiu o seu post.")
            return {"curtido": curtido, "avisos": avisos}

    def comentar_post(self, usuario_id: str, post_id: str, texto: str) -> dict:
        with self.registro.acao("Comentar"):
            texto = _texto_obrigatorio(texto, 1, 500, "O comentário deve ter de 1 a 500 caracteres.")
            post = self._post(post_id)
            nome = self._usuario(usuario_id)["nome"]
            # MongoDB: o comentário fica embutido no post (ação principal)
            self.mongo.comentar(post_id, {"id": usuario_id, "nome": nome}, texto)
            # MongoDB + Redis: notifica o autor do post, se for outra pessoa (_notificar ignora a
            # própria). Se falhar, o comentário continua valendo e a tela mostra o aviso
            avisos = self._notificar([post["autor_id"]], "comentario", {"id": usuario_id, "nome": nome},
                                     f"{nome} comentou o seu post.")
            return {"avisos": avisos}

    # ---------- conexões e mentoria ----------

    def conectar(self, usuario_id: str, outro_id: str) -> dict:
        with self.registro.acao("Conectar"):
            if usuario_id == outro_id:
                raise ErroDeNegocio("Você não pode se conectar com você mesmo.")
            # Neo4j: as duas pessoas precisam existir (conectar() devolve False tanto para
            # "já conectados" quanto para "pessoa não existe")
            eu = self._pessoa(usuario_id)
            self._pessoa(outro_id)
            # Neo4j: a conexão (ação principal; só existe no grafo)
            criada = self.neo4j.conectar(usuario_id, outro_id)
            avisos = []
            # MongoDB + Redis: notifica só quando a conexão é nova. Se falhar, a conexão
            # é mantida e a tela mostra o aviso (regra 2). O nome vem do grafo (cópia do Mongo)
            if criada:
                falhas = self._notificar([outro_id], "conexao", {"id": usuario_id, "nome": eu["nome"]},
                                         f"{eu['nome']} conectou-se com você.")
                if falhas:
                    avisos.append("Conectado, mas não foi possível notificar a outra pessoa.")
                    avisos += falhas
            return {"criada": criada, "avisos": avisos}

    def pedir_mentoria(self, usuario_id: str, mentor_id: str, mensagem: str = "") -> dict:
        with self.registro.acao("Pedir mentoria"):
            if usuario_id == mentor_id:
                raise ErroDeNegocio("Você não pode pedir mentoria a você mesmo.")
            mensagem = (mensagem or "").strip()
            if len(mensagem) > 500:
                raise ErroDeNegocio("A mensagem deve ter até 500 caracteres.")
            # Neo4j: as duas pessoas precisam existir
            eu = self._pessoa(usuario_id)
            self._pessoa(mentor_id)
            texto = f"{eu['nome']} pediu sua mentoria."
            if mensagem:
                texto += f' Mensagem: "{mensagem}"'
            # MongoDB + Redis: o pedido é a própria notificação (histórico + sininho)
            return {"avisos": self._notificar([mentor_id], "mentoria", {"id": usuario_id, "nome": eu["nome"]}, texto)}

    # ---------- notificações ----------

    def notificacoes(self, usuario_id: str) -> dict:
        with self.registro.acao("Notificações", leitura=True):  # só leitura (ver abrir_perfil)
            # Redis: contador e lista curta (rápidos, para o sininho); MongoDB: histórico durável
            return {"nao_lidas": self.redis.nao_lidas(usuario_id),
                    "recentes": self.redis.notificacoes_recentes(usuario_id),
                    "historico": self.mongo.listar_notificacoes(usuario_id)}

    def marcar_notificacoes_lidas(self, usuario_id: str) -> None:
        with self.registro.acao("Marcar notificações como lidas"):
            # MongoDB primeiro (fonte da verdade): lida = True no histórico
            self.mongo.marcar_notificacoes_lidas(usuario_id)
            # Redis: zera o contador do sininho. Se falhar, o erro sobe e a pessoa tenta de
            # novo; repetir é seguro (o Mongo só muda as que ainda não estavam lidas)
            self.redis.marcar_lidas(usuario_id)

    # ---------- presença e tags ----------

    def painel_presenca(self) -> dict:
        # pausado: o painel se atualiza sozinho a cada poucos segundos
        with self.registro.pausado():
            usuarios = self.mongo.listar_usuarios()  # MongoDB: nomes e títulos
            # Redis: "quem está online" é uma consulta por faixa no ZSET (score = último sinal).
            # usuarios_online também apaga, por score, quem passou da janela de 90 s
            online_ids = set(self.redis.usuarios_online())
            # Redis: o "visto por último" de cada um (HASH presenca:visto, lido em pipeline)
            presenca = self.redis.presenca_de([u["_id"] for u in usuarios])
            online, offline = [], []
            for u in usuarios:
                item = {"id": u["_id"], "nome": u["nome"], "titulo": u["titulo"],
                        "visto": presenca.get(u["_id"], {}).get("visto")}
                (online if u["_id"] in online_ids else offline).append(item)
            # quem foi visto mais recentemente vem primeiro; quem nunca entrou vai para o fim
            offline.sort(key=lambda x: x["visto"] or 0, reverse=True)
            return {"total_online": len(online_ids), "online": online, "offline": offline}

    def tags_em_alta(self) -> dict:
        with self.registro.acao("Tags em alta", leitura=True):  # só leitura (ver abrir_perfil)
            # Redis: cache-aside (cache fora do ar conta como "não achou")
            try:
                tags = self.redis.cache_ler(CHAVE_TAGS)
            except BancoIndisponivel:
                tags = None
            # só uma lista vale como HIT; outra coisa na chave conta como MISS (ver abrir_perfil)
            if isinstance(tags, list):
                return {"tags": tags, "do_cache": True}
            # MongoDB: a agregação ($unwind → $group → $sort), guardada no cache por 60 s
            tags = self.mongo.tags_em_alta()
            try:
                self.redis.cache_gravar(CHAVE_TAGS, tags, CACHE_TAGS_TTL)
            except BancoIndisponivel:
                pass
            return {"tags": tags, "do_cache": False}

    # ---------- demonstração [extra] ----------

    def simular_atividade(self, usuario_id: str, quantos: int = 6) -> dict:
        """Coloca outros usuários online e gera 2 notificações, para o painel não ficar vazio na demo."""
        with self.registro.acao("Simulação (demo)"):
            # MongoDB: quem pode ser sorteado (todos menos eu)
            outros = [u for u in self.mongo.listar_usuarios() if u["_id"] != usuario_id]
            sorteados = random.sample(outros, min(quantos, len(outros)))
            # Redis: um sinal de presença para cada um; como ninguém renova o sinal,
            # eles ficam offline sozinhos depois de 90 s
            for u in sorteados:
                self.redis.sinal_de_presenca(u["_id"])
            # MongoDB + Redis: duas notificações marcadas como simulação
            textos = [("curtida", "curtiu o seu post"), ("post", "publicou um post novo")]
            for (tipo, acao), u in zip(textos, sorteados):
                self._notificar([usuario_id], tipo, {"id": u["_id"], "nome": u["nome"]},
                                f"{u['nome']} {acao} (simulação)")
            return {"online": [u["_id"] for u in sorteados], "notificacoes": min(2, len(sorteados))}
