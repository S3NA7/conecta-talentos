# Conecta Talentos — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir a aplicação Streamlit "Conecta Talentos" (Estudo de Caso 02) usando MongoDB, Redis e Neo4j em Docker local, com scripts de carga, testes e material de defesa.

**Architecture:** Três camadas: páginas Streamlit (só interface) → `Orquestrador` (um método por ação que cruza bancos) → um serviço por banco (`MongoService`, `RedisService`, `Neo4jService`). O `id` do usuário (`u007`) liga os três bancos. Cada chamada a banco é registrada num `Registro` exibido no painel "Bastidores".

**Tech Stack:** Python 3.11 · Streamlit 1.67 · pymongo 4.20 (+GridFS) · redis-py 8.1 · neo4j driver 6.4 · pyvis 0.3.2 · pytest 9 · Docker Compose (mongo:8.0, redis:8.2-alpine, neo4j:5.26-community).

**Spec:** [docs/design.md](design.md) — quem executa lê os dois.

## Global Constraints

- Versões fixadas em `requirements.txt`: `streamlit==1.67.0`, `pymongo==4.20.0`, `redis==8.1.0`, `neo4j==6.4.1`, `pyvis==0.3.2`, `python-dotenv==1.2.2`, `pillow`, `pytest==9.2.0`.
- Imagens: `mongo:8.0`, `redis:8.2-alpine`, `neo4j:5.26-community`. Portas publicadas só em `127.0.0.1` (27017, 6379, 7474, 7687, 8501).
- Tudo em português (pt-BR): interface, nomes de funções/variáveis, comentários, documentação.
- Rótulos e relacionamentos do grafo exatamente: `Pessoa`, `Habilidade`, `Empresa`, `CONECTADO_COM`, `POSSUI_HABILIDADE`, `TRABALHA_EM`, `QUER_APRENDER`.
- Variáveis do Neo4j com os nomes do enunciado: `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`.
- Serviços no formato do item 3.2 do enunciado: driver criado no construtor, `close()`, um método por consulta, Cypher em texto **sempre com parâmetros** (`$nome`), `driver.session()` + `session.run()`, retorno em listas/dicionários Python.
- Páginas não importam `pymongo`, `redis` nem `neo4j`.
- Código simples: classes e funções diretas. Onde houver `pipeline` do Redis ou `st.fragment`, um comentário explica o que é e por quê.
- Imports sempre a partir da raiz (`from app.servicos...`, `from scripts...`). `app/Inicio.py` e `scripts/carga_inicial.py` inserem a raiz do projeto em `sys.path`; `pytest.ini` usa `pythonpath = .`.
- Datas: no Mongo, `datetime` com fuso UTC (`MongoClient(tz_aware=True)`); no grafo, texto ISO (`"2021-03"`, `"2026-11-13"`); no Redis, segundos desde a época (`time.time()`).
- Os serviços convertem `ObjectId` ↔ `str` nas bordas: orquestrador e páginas só veem `str`.
- **Sem commits.** `git init` na Tarefa 1; commit e envio ao GitHub só quando o grupo pedir. Cada tarefa termina num "ponto de verificação" (testes passando).
- A carga e os testes apagam dados: só rodam contra endereços locais (ver `enderecos_sao_locais`).
- Senhas e segredos só em `.env` / `.env.example`; nunca em mensagens.
- Console do Windows usa cp1252: scripts de linha de comando chamam `sys.stdout.reconfigure(encoding="utf-8")` no início e não imprimem emojis.

**Desvios conscientes em relação ao design**

1. **Ordem:** o design (seção 13) intercala telas e bancos. Aqui os três serviços e a carga vêm antes das telas, porque cada serviço é testado sozinho. A regra de corte continua: o que está marcado **[extra]** é o último passo da sua tarefa e pode ser pulado.
2. **Cache ao conectar:** a tabela da seção 8 diz "invalida cache" em Conectar. O cache de perfil guarda só o documento do Mongo (o nº de conexões vem ao vivo do grafo), então não há o que invalidar; nada é apagado nesse fluxo.
3. **Testes:** rodam sobre os mesmos bancos da demo e recarregam os dados de exemplo no início e no fim da sessão de testes (o Neo4j Community tem um banco só). O `README` avisa: rodar os testes apaga o que foi criado pela aplicação.

## Review Focus

Entradas que o design implica mas não descreve, da mais provável para a menos:

1. **Origem = destino nos graus de separação** — `shortestPath` do Neo4j dá erro com nó inicial igual ao final. Esperado: "é você mesmo, 0 graus". → teste na Tarefa 5.
2. **Sessão expira no meio do uso** (TTL venceu ou o Redis foi limpo). Esperado: volta à tela de entrada com aviso, sem erro. → testes nas Tarefas 4 e 8.
3. **Conectar duas vezes, ou consigo mesmo.** Esperado: um relacionamento só, uma notificação só; consigo mesmo é recusado. → testes nas Tarefas 5 e 7.
4. **E-mail já cadastrado, com maiúsculas/espaços diferentes.** Esperado: recusado com mensagem; nenhum nó órfão no grafo. → testes nas Tarefas 3 e 7.
5. **Post vazio, tags sujas (`#Dados`, repetidas), anexo grande ou de tipo não aceito.** Esperado: recusa com mensagem clara; tags normalizadas. → teste na Tarefa 7.

Também cobertos por teste: usuário sem conexões (`u030`) em feed, rede e mentores; texto com aspas em nome de habilidade (parâmetros Cypher).

---

## Mapa de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `docker-compose.yml`, `Dockerfile`, `.env.example`, `.gitignore`, `requirements.txt`, `pytest.ini` | Infraestrutura |
| `app/config.py` | Ler `.env`; constantes; `enderecos_sao_locais` |
| `app/servicos/erros.py` | `BancoIndisponivel`, `ErroDeNegocio`, `EmailJaCadastrado` |
| `app/servicos/registro.py` | `Registro`: log de operações para o Bastidores |
| `app/servicos/seguranca.py` | Hash e conferência de senha |
| `app/servicos/mongo_service.py` | Tudo que fala com o MongoDB |
| `app/servicos/redis_service.py` | Tudo que fala com o Redis |
| `app/servicos/neo4j_service.py` | Tudo que fala com o Neo4j |
| `app/servicos/orquestrador.py` | Ações de negócio que cruzam bancos |
| `app/estado.py` | Serviços e usuário da sessão do navegador (`st.session_state`) |
| `app/Inicio.py` | Entrada: login, barra lateral, navegação |
| `app/paginas/entrada.py` | Login, cadastro, "entrar como…" |
| `app/paginas/feed_perfil.py`, `presenca_notificacoes.py`, `rede_mentores.py` | As três telas |
| `app/componentes/bastidores.py`, `grafo.py`, `cartoes.py` | Pedaços de tela reutilizados |
| `scripts/dados_exemplo.py` | Dados fictícios (fonte única dos 3 bancos) |
| `scripts/carga_mongo.py`, `carga_redis.py`, `carga_neo4j.py`, `carga_inicial.py` | Carga |
| `tests/…` | Um arquivo de teste por módulo |
| `README.md`, `docs/guia_da_defesa.md` | Documentação |

---

### Task 1: Base do projeto e bancos no Docker

**Files:**
- Create: `docker-compose.yml`, `.env.example`, `.env` (cópia), `.gitignore`, `requirements.txt`, `pytest.ini`, `app/__init__.py`, `app/servicos/__init__.py`, `app/paginas/__init__.py`, `app/componentes/__init__.py`, `scripts/__init__.py`, `tests/__init__.py`, `app/config.py`, `app/servicos/erros.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces:
  - `app.config.Config` (dataclass): `MONGO_URI`, `MONGO_DB`, `REDIS_URL`, `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`, `MODO_DEMO: bool`, `SENHA_DEMO: str`
  - `app.config.carregar_config() -> Config` (lê `.env` com `python-dotenv`)
  - Constantes em `app.config`: `NOME_APP = "Conecta Talentos"`, `SESSAO_TTL_SEGUNDOS = 1800`, `PRESENCA_JANELA_SEGUNDOS = 90`, `CACHE_PERFIL_TTL = 300`, `CACHE_TAGS_TTL = 60`, `NOTIF_RECENTES_MAX = 20`, `MAX_SALTOS = 6`, `ANEXO_MAX_BYTES = 5 * 1024 * 1024`, `ANEXO_TIPOS = ("image/png", "image/jpeg", "application/pdf")`
  - `app.config.enderecos_sao_locais(cfg: Config) -> bool`
  - `app.servicos.erros`: `BancoIndisponivel(Exception)` com atributo `banco: str`; `ErroDeNegocio(Exception)` (mensagem pronta para a tela); `EmailJaCadastrado(ErroDeNegocio)`

- [ ] **Step 1: Testes que falham** — `tests/test_config.py`

```python
def test_padroes_apontam_para_docker_local(monkeypatch):
    for v in ("MONGO_URI", "REDIS_URL", "NEO4J_URI"): monkeypatch.delenv(v, raising=False)
    cfg = Config()                      # valores padrão do dataclass
    assert cfg.MONGO_URI == "mongodb://localhost:27017"
    assert cfg.REDIS_URL == "redis://localhost:6379/0"
    assert cfg.NEO4J_URI == "bolt://localhost:7687"
    assert cfg.MONGO_DB == "conecta_talentos"

@pytest.mark.parametrize("campo,valor", [
    ("NEO4J_URI", "neo4j+s://abc123.databases.neo4j.io"),
    ("MONGO_URI", "mongodb+srv://x.mongodb.net"),
    ("REDIS_URL", "rediss://redis-123.cloud.redislabs.com:6379"),
])
def test_endereco_remoto_nao_e_local(campo, valor):
    assert enderecos_sao_locais(replace(Config(), **{campo: valor})) is False

def test_localhost_e_nomes_dos_containers_sao_locais():
    assert enderecos_sao_locais(Config()) is True
    assert enderecos_sao_locais(replace(Config(), MONGO_URI="mongodb://mongo:27017",
        REDIS_URL="redis://redis:6379/0", NEO4J_URI="bolt://neo4j:7687")) is True
```

- [ ] **Step 2:** `pytest tests/test_config.py -v` → FALHA (módulo não existe).
- [ ] **Step 3: Implementar `app/config.py` e `app/servicos/erros.py`.** "Local" = o host da URL é um de `localhost`, `127.0.0.1`, `::1`, `mongo`, `redis`, `neo4j` (usar `urllib.parse.urlsplit(...).hostname`).
- [ ] **Step 4: Infraestrutura.**
  - `.env.example` com todas as chaves de `Config`; `NEO4J_PASSWORD` com uma senha local de ≥ 8 caracteres; `MODO_DEMO=1`; `SENHA_DEMO` com a senha de demonstração. `.env` = cópia. `.gitignore`: `.env`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `.claude/`.
  - `docker-compose.yml`: serviços `mongo`, `redis`, `neo4j`, cada um com volume nomeado, `restart: unless-stopped` e `healthcheck` (`mongosh --eval "db.adminCommand('ping')"`, `redis-cli ping`, `cypher-shell -u neo4j -p $$NEO4J_PASSWORD "RETURN 1"`). Neo4j: `NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}`, heap máx. 512m, pagecache 256m. (Serviços `app`, `carga` e perfil `ferramentas` entram na Tarefa 12.)
  - `python -m venv .venv` e `pip install -r requirements.txt`; `git init`.
- [ ] **Step 5: Verificar.** `pytest tests/test_config.py -v` → 5 passam. `docker compose up -d` e `docker compose ps` → `mongo`, `redis`, `neo4j` com estado `healthy`.

---

### Task 2: Registro de operações e senha

**Files:**
- Create: `app/servicos/registro.py`, `app/servicos/seguranca.py`
- Test: `tests/test_registro.py`, `tests/test_seguranca.py`

**Interfaces:**
- Consumes: `BancoIndisponivel`
- Produces:
  - `Registro(limite: int = 300)`
    - `registrar(banco: str, comando: str, ms: float) -> None`
    - `medir(banco: str, comando: str, erros_conexao: tuple = ())` — gerenciador de contexto: mede o tempo, registra, e converte qualquer exceção de `erros_conexao` em `BancoIndisponivel(banco)` (registrando o comando com o sufixo `" ✗ falhou"`)
    - `acao(nome: str)` — gerenciador de contexto: operações registradas dentro recebem `acao=nome`; fora de qualquer ação, `acao="Leitura da tela"`; ações aninhadas mantêm o nome da mais externa
    - `pausado()` — gerenciador de contexto: nada é registrado dentro (usado nas atualizações automáticas)
    - `itens() -> list[dict]` — mais antigo primeiro; cada item `{"banco", "comando", "ms", "acao", "quando"}`
    - `grupos(incluir_leituras: bool = False) -> list[dict]` — itens consecutivos da mesma ação agrupados, **mais recente primeiro**: `{"acao", "operacoes": [itens]}`
    - `limpar() -> None`
  - `seguranca.gerar_hash(senha: str) -> str` — formato `pbkdf2$<sal_hex>$<hash_hex>`, `hashlib.pbkdf2_hmac("sha256", …, 100_000)`, sal aleatório de 16 bytes
  - `seguranca.conferir_senha(senha: str, senha_hash: str) -> bool` — comparação com `hmac.compare_digest`; hash malformado → `False`

- [ ] **Step 1: Testes que falham**

```python
def test_operacao_fora_de_acao_e_leitura_da_tela():
    r = Registro(); r.registrar("Redis", "GET x", 0.4)
    assert r.itens()[0]["acao"] == "Leitura da tela"

def test_acao_agrupa_e_mais_recente_vem_primeiro():
    r = Registro()
    with r.acao("Login"): r.registrar("MongoDB", "find", 1); r.registrar("Redis", "HSET", 1)
    with r.acao("Publicar post"): r.registrar("MongoDB", "insert_one", 1)
    g = r.grupos()
    assert [x["acao"] for x in g] == ["Publicar post", "Login"]
    assert len(g[1]["operacoes"]) == 2

def test_grupos_esconde_leituras_por_padrao():
    r = Registro(); r.registrar("Redis", "GET x", 1)
    assert r.grupos() == [] and len(r.grupos(incluir_leituras=True)) == 1

def test_pausado_nao_registra():
    r = Registro()
    with r.pausado(): r.registrar("Redis", "ZADD", 1)
    assert r.itens() == []

def test_medir_converte_erro_de_conexao():
    r = Registro()
    with pytest.raises(BancoIndisponivel) as e:
        with r.medir("Neo4j", "MATCH (n)", erros_conexao=(ConnectionError,)): raise ConnectionError()
    assert e.value.banco == "Neo4j" and r.itens()[0]["comando"].endswith("✗ falhou")

def test_limite_descarta_os_mais_antigos():
    r = Registro(limite=3)
    for i in range(5): r.registrar("Redis", f"c{i}", 1)
    assert [i["comando"] for i in r.itens()] == ["c2", "c3", "c4"]

def test_senha_confere_e_nao_confere():
    h = gerar_hash("segredo1")
    assert h.startswith("pbkdf2$") and conferir_senha("segredo1", h) and not conferir_senha("outra", h)
    assert gerar_hash("segredo1") != h            # sal aleatório
    assert conferir_senha("x", "lixo") is False
```

- [ ] **Step 2:** `pytest tests/test_registro.py tests/test_seguranca.py -v` → FALHA.
- [ ] **Step 3: Implementar** os dois módulos (`collections.deque(maxlen=limite)`, `contextlib.contextmanager`).
- [ ] **Step 4:** mesmos testes → 7 passam.

---

### Task 3: MongoService

**Files:**
- Create: `app/servicos/mongo_service.py`, `tests/conftest.py`
- Test: `tests/test_mongo_service.py`

**Interfaces:**
- Consumes: `Registro`, `BancoIndisponivel`, `EmailJaCadastrado`, `carregar_config`, `enderecos_sao_locais`
- Produces: `MongoService(uri: str, banco: str, registro: Registro | None = None)` — `MongoClient(uri, tz_aware=True, serverSelectionTimeoutMS=2000)`. O banco fica em `self.db`. Todo acesso ao driver vai dentro de `with self._op("<comando legível>"):`, que usa `registro.medir("MongoDB", …, erros_conexao=(pymongo.errors.ConnectionFailure,))`.

| Método | Retorno / comportamento |
|---|---|
| `close()`, `ping() -> bool` | `ping` nunca levanta exceção |
| `criar_esquema()` | Idempotente. Coleções `usuarios` (validador `$jsonSchema`: obrigatórios `nome`, `email`, `titulo`, todos `string`), `posts` (obrigatórios `autor_id`, `texto`, `criado_em`), `notificacoes`. Índices: `usuarios.email` único; `posts {autor_id:1, criado_em:-1}`, `{criado_em:-1}`, `{tags:1}`; `notificacoes {usuario_id:1, criado_em:-1}` e TTL `criado_em` com `expireAfterSeconds=2592000` |
| `apagar_tudo()` | `drop_database` |
| `inserir_usuario(usuario: dict) -> str` | Normaliza `email` (`strip().lower()`); preenche `criado_em`; duplicado → `EmailJaCadastrado` |
| `remover_usuario(usuario_id)` | |
| `buscar_usuario(usuario_id) -> dict \| None` | **sem** `senha_hash` |
| `buscar_usuario_por_email(email) -> dict \| None` | normaliza; **com** `senha_hash` |
| `listar_usuarios() -> list[dict]` | `{_id, nome, titulo}` por `nome` |
| `proximo_id_usuario() -> str` | maior `_id` + 1, formato `u%03d`; banco vazio → `"u001"` |
| `atualizar_dados_basicos(usuario_id, *, titulo=None, resumo=None, localizacao=None)` | só os campos informados |
| `atualizar_titulo_nos_posts(usuario_id, titulo) -> int` | `update_many` em `posts.autor.titulo` |
| `adicionar_item(usuario_id, campo, item: dict)` / `remover_item(...)` | `campo` ∈ `experiencias`, `formacao`, `certificacoes` (`$push` / `$pull`); outro campo → `ValueError` |
| `criar_post(autor: dict, texto, tags: list[str], anexos: list[dict]) -> str` | `autor = {"id","nome","titulo"}` → grava `autor_id` + `autor{nome,titulo}`; `curtidas=[]`, `comentarios=[]` |
| `buscar_post(post_id) -> dict \| None` | |
| `listar_posts(autores_ids: list[str], limite=30, tag=None) -> list[dict]` | ordenado por `criado_em` desc e, no empate, `_id` desc |
| `curtir(post_id, usuario_id) -> bool` | alterna; `True` se ficou curtido |
| `comentar(post_id, autor: dict, texto)` | `$push` com `criado_em` |
| `tags_em_alta(limite=8) -> list[dict]` | agregação `$unwind`→`$group`→`$sort {total:-1, _id:1}`; `[{"tag","total"}]` |
| `salvar_anexo(nome, tipo, conteudo: bytes) -> dict` | GridFS; `{"arquivo_id","nome","tipo","tamanho"}` |
| `ler_anexo(arquivo_id) -> bytes \| None` | |
| `criar_notificacoes(notificacoes: list[dict]) -> int` | grava **cópias** (não altera os dicionários recebidos); preenche `lida=False`, `criado_em`; lista vazia → 0 sem ir ao banco |
| `listar_notificacoes(usuario_id, limite=30) -> list[dict]` | mais recentes primeiro |
| `marcar_notificacoes_lidas(usuario_id) -> int` | |

- `tests/conftest.py` produz: fixture de sessão `cfg` (chama `pytest.exit("Testes só rodam contra bancos locais")` se `enderecos_sao_locais` for falso); fixtures `mongo`, `redis_svc`, `neo4j_svc` (escopo de módulo; constroem o serviço e fecham no fim). Cada arquivo de teste de serviço chama `apagar_tudo()` + `criar_esquema()` no seu `setup_module`.

- [ ] **Step 1: Testes que falham** — `tests/test_mongo_service.py` (banco limpo e esquema criado no início do módulo; os testes rodam **na ordem do arquivo e compartilham estado**; `_usuario(id, email)` devolve um usuário válido com `nome`, `titulo` e `senha_hash`)

```python
def test_ping(mongo): assert mongo.ping() is True

def test_usuario_sem_campos_obrigatorios_e_recusado(mongo):
    with pytest.raises(pymongo.errors.WriteError): mongo.inserir_usuario({"_id": "u900", "nome": "Sem título", "email": "a@b.c"})

def test_email_duplicado_ignora_maiusculas_e_espacos(mongo):
    mongo.inserir_usuario(_usuario("u001", "ana@exemplo.com"))
    with pytest.raises(EmailJaCadastrado): mongo.inserir_usuario(_usuario("u002", "  ANA@Exemplo.com "))

def test_buscar_usuario_nao_devolve_senha(mongo):
    assert "senha_hash" not in mongo.buscar_usuario("u001")
    assert "senha_hash" in mongo.buscar_usuario_por_email(" Ana@EXEMPLO.com")

def test_proximo_id(mongo): assert mongo.proximo_id_usuario() == "u002"

def test_perfil_flexivel_push_e_pull(mongo):
    exp = {"empresa": "DataNorte", "cargo": "Analista", "inicio": "2021-03", "fim": None}
    mongo.adicionar_item("u001", "experiencias", exp)
    assert mongo.buscar_usuario("u001")["experiencias"] == [exp]
    mongo.remover_item("u001", "experiencias", exp)
    assert mongo.buscar_usuario("u001")["experiencias"] == []
    with pytest.raises(ValueError): mongo.adicionar_item("u001", "senha_hash", {})

def test_posts_ordem_filtro_por_autor_e_tag(mongo):
    a = {"id": "u001", "nome": "Ana", "titulo": "Analista"}; b = {"id": "u002", "nome": "Bia", "titulo": "Dev"}
    p1 = mongo.criar_post(a, "primeiro", ["dados"], []); p2 = mongo.criar_post(b, "segundo", ["web"], [])
    p3 = mongo.criar_post(a, "terceiro", ["dados", "carreira"], [])
    assert [p["_id"] for p in mongo.listar_posts(["u001"])] == [p3, p1]
    assert [p["_id"] for p in mongo.listar_posts(["u001", "u002"], tag="web")] == [p2]
    assert isinstance(p1, str) and mongo.listar_posts([]) == []

def test_curtir_alterna_e_comentar(mongo):
    pid = mongo.criar_post({"id": "u001", "nome": "Ana", "titulo": "A"}, "x", [], [])
    assert mongo.curtir(pid, "u002") is True and mongo.curtir(pid, "u002") is False
    mongo.curtir(pid, "u002"); mongo.comentar(pid, {"id": "u002", "nome": "Bia"}, "boa!")
    p = mongo.buscar_post(pid)
    assert p["curtidas"] == ["u002"] and p["comentarios"][0]["texto"] == "boa!"

def test_tags_em_alta(mongo):            # após os posts dos testes acima: dados=2, carreira=1, web=1
    assert mongo.tags_em_alta()[0] == {"tag": "dados", "total": 2}

def test_titulo_propagado_aos_posts(mongo):
    assert mongo.atualizar_titulo_nos_posts("u001", "Analista Sênior") >= 2
    assert mongo.listar_posts(["u001"])[0]["autor"]["titulo"] == "Analista Sênior"

def test_anexo_gridfs_ida_e_volta(mongo):
    ref = mongo.salvar_anexo("a.png", "image/png", b"\x89PNG" + b"0" * 300_000)
    assert ref["tamanho"] == 300_004 and mongo.ler_anexo(ref["arquivo_id"])[:4] == b"\x89PNG"
    assert mongo.ler_anexo("000000000000000000000000") is None

def test_notificacoes(mongo):
    assert mongo.criar_notificacoes([]) == 0
    mongo.criar_notificacoes([{"usuario_id": "u001", "tipo": "post", "de": {"id": "u002", "nome": "Bia"}, "texto": "t"} for _ in range(2)])
    assert len(mongo.listar_notificacoes("u001")) == 2 and mongo.marcar_notificacoes_lidas("u001") == 2
    assert all(n["lida"] for n in mongo.listar_notificacoes("u001"))

def test_indices_criados(mongo):
    idx = mongo.db.notificacoes.index_information()
    assert any(i.get("expireAfterSeconds") == 2592000 for i in idx.values())
    assert any(i.get("unique") for i in mongo.db.usuarios.index_information().values())

def test_banco_fora_do_ar_vira_BancoIndisponivel():
    fora = MongoService("mongodb://localhost:1", "x")
    assert fora.ping() is False
    with pytest.raises(BancoIndisponivel): fora.listar_usuarios()
```

- [ ] **Step 2:** `pytest tests/test_mongo_service.py -v` → FALHA.
- [ ] **Step 3: Implementar `MongoService`.** `criar_esquema`: `create_collection` se não existir, senão `collMod` com o validador.
- [ ] **Step 4:** `pytest tests/test_mongo_service.py -v` → 14 passam.

---

### Task 4: RedisService

**Files:**
- Create: `app/servicos/redis_service.py`
- Test: `tests/test_redis_service.py`

**Interfaces:**
- Consumes: `Registro`, `BancoIndisponivel`, constantes de `config`
- Produces: `RedisService(url: str, registro=None, *, sessao_ttl=SESSAO_TTL_SEGUNDOS, janela_presenca=PRESENCA_JANELA_SEGUNDOS, relogio=time.time)` — `redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)`. Erros de conexão convertidos: `(redis.exceptions.ConnectionError, redis.exceptions.TimeoutError)`. `relogio` existe para os testes simularem a passagem do tempo.

Chaves (exatamente as da seção 6.2 do design): `sessao:{token}`, `usuario:{id}:sessoes`, `presenca:online`, `presenca:visto`, `notif:nao_lidas:{id}`, `notif:recentes:{id}`, `cache:…`.

| Método | Comandos / comportamento |
|---|---|
| `close()`, `ping() -> bool`, `apagar_tudo()` | `FLUSHDB` |
| `criar_sessao(usuario_id, nome) -> str` | token `secrets.token_urlsafe(24)`; **um pipeline transacional**: `HSET` (`usuario_id`, `nome`, `login_em`, `ultimo_acesso`), `EXPIRE`, `SADD`, `ZADD presenca:online`, `HSET presenca:visto` |
| `validar_sessao(token) -> dict \| None` | `HGETALL`; inexistente/expirada/token vazio → `None`; senão renova `EXPIRE`, atualiza `ultimo_acesso` e devolve o hash |
| `encerrar_sessao(token)` | `DEL` + `SREM`; se o usuário ficou sem sessões → `marcar_offline` |
| `listar_sessoes(usuario_id) -> list[dict]` | `{"token","login_em","ultimo_acesso","ttl"}`; tokens do SET cuja chave expirou são removidos do SET |
| `sinal_de_presenca(usuario_id)` | `ZADD presenca:online {id: agora}` + `HSET presenca:visto` |
| `marcar_offline(usuario_id)` | `ZREM` + `HSET presenca:visto` |
| `usuarios_online() -> list[str]` | `ZREMRANGEBYSCORE -inf (agora-janela` e depois `ZRANGEBYSCORE`, mais recente primeiro |
| `contar_online() -> int` | `ZCOUNT (agora-janela +inf` |
| `esta_online(usuario_id) -> bool` | `ZSCORE` |
| `presenca_de(ids: list[str]) -> dict[str, dict]` | `{id: {"online": bool, "visto": float \| None}}` num pipeline; lista vazia → `{}` |
| `notificar(usuario_id, notificacao: dict) -> int` | pipeline `INCR` + `LPUSH` (JSON) + `LTRIM 0 19`; devolve o contador |
| `notificar_varios(ids: list[str], notificacao: dict)` | um pipeline só para todos |
| `nao_lidas(usuario_id) -> int` | ausente → 0 |
| `notificacoes_recentes(usuario_id) -> list[dict]` | mais recente primeiro |
| `marcar_lidas(usuario_id)` | `SET … 0` |
| `cache_ler(chave) -> object \| None` | JSON inválido → `None` (e apaga a chave) |
| `cache_gravar(chave, valor, ttl)`, `cache_apagar(chave)` | `SET … EX ttl` / `DEL` |

- [ ] **Step 1: Testes que falham** — `tests/test_redis_service.py` (`FLUSHDB` antes de cada teste; fixture `relogio` = objeto com `.agora` ajustável passado como `relogio=lambda: r.agora`)

```python
def test_sessao_criada_com_ttl_e_presenca(redis_svc):
    t = redis_svc.criar_sessao("u001", "Ana")
    assert redis_svc.validar_sessao(t)["usuario_id"] == "u001"
    assert 1790 <= redis_svc.listar_sessoes("u001")[0]["ttl"] <= 1800
    assert redis_svc.esta_online("u001")

def test_sessao_invalida_ou_vazia(redis_svc):
    assert redis_svc.validar_sessao("nao-existe") is None and redis_svc.validar_sessao("") is None

def test_sessao_expira_e_some_da_lista(cfg):
    r = RedisService(cfg.REDIS_URL, sessao_ttl=1); t = r.criar_sessao("u001", "Ana"); time.sleep(1.5)
    assert r.validar_sessao(t) is None and r.listar_sessoes("u001") == []

def test_validar_renova_ttl(redis_svc):
    t = redis_svc.criar_sessao("u001", "Ana"); redis_svc.r.expire(f"sessao:{t}", 100)
    redis_svc.validar_sessao(t); assert redis_svc.r.ttl(f"sessao:{t}") > 1700

def test_encerrar_ultima_sessao_marca_offline(redis_svc):
    t1 = redis_svc.criar_sessao("u001", "Ana"); t2 = redis_svc.criar_sessao("u001", "Ana")
    redis_svc.encerrar_sessao(t1); assert redis_svc.esta_online("u001")
    redis_svc.encerrar_sessao(t2); assert not redis_svc.esta_online("u001")

def test_presenca_expira_pela_janela(cfg, relogio):
    r = RedisService(cfg.REDIS_URL, relogio=lambda: relogio.agora)
    relogio.agora = 1000.0; r.sinal_de_presenca("u001"); r.sinal_de_presenca("u002")
    relogio.agora = 1060.0; r.sinal_de_presenca("u002")
    relogio.agora = 1095.0
    assert r.usuarios_online() == ["u002"] and r.contar_online() == 1
    p = r.presenca_de(["u001", "u002", "u999"])
    assert p["u001"] == {"online": False, "visto": 1000.0} and p["u002"]["online"] and p["u999"] == {"online": False, "visto": None}

def test_notificacoes_contador_e_lista_limitada(redis_svc):
    for i in range(25): n = redis_svc.notificar("u001", {"texto": f"n{i}"})
    assert n == 25 and redis_svc.nao_lidas("u001") == 25
    rec = redis_svc.notificacoes_recentes("u001")
    assert len(rec) == 20 and rec[0]["texto"] == "n24"
    redis_svc.marcar_lidas("u001"); assert redis_svc.nao_lidas("u001") == 0 and redis_svc.nao_lidas("u404") == 0

def test_notificar_varios(redis_svc):
    redis_svc.notificar_varios(["u002", "u003"], {"texto": "oi"})
    assert redis_svc.nao_lidas("u002") == 1 and redis_svc.nao_lidas("u003") == 1

def test_cache_ida_volta_ttl_e_lixo(redis_svc):
    redis_svc.cache_gravar("cache:perfil:u001", {"nome": "Ana"}, 300)
    assert redis_svc.cache_ler("cache:perfil:u001") == {"nome": "Ana"} and 290 <= redis_svc.r.ttl("cache:perfil:u001") <= 300
    redis_svc.r.set("cache:x", "{isso não é json"); assert redis_svc.cache_ler("cache:x") is None
    redis_svc.cache_apagar("cache:perfil:u001"); assert redis_svc.cache_ler("cache:perfil:u001") is None

def test_redis_fora_do_ar_vira_BancoIndisponivel():
    fora = RedisService("redis://localhost:1/0"); assert fora.ping() is False
    with pytest.raises(BancoIndisponivel): fora.nao_lidas("u001")
```

- [ ] **Step 2:** `pytest tests/test_redis_service.py -v` → FALHA.
- [ ] **Step 3: Implementar `RedisService`** (o cliente fica em `self.r`).
- [ ] **Step 4:** `pytest tests/test_redis_service.py -v` → 10 passam.

---

### Task 5: Neo4jService

**Files:**
- Create: `app/servicos/neo4j_service.py`
- Test: `tests/test_neo4j_service.py`

**Interfaces:**
- Consumes: `Registro`, `BancoIndisponivel`, `MAX_SALTOS`
- Produces: `Neo4jService(uri, user, password, database="neo4j", registro=None)` — `GraphDatabase.driver(uri, auth=(user, password), connection_timeout=3, connection_acquisition_timeout=5, max_transaction_retry_time=3)`. Método interno `_executar(cypher: str, **params) -> list[dict]`: `session.run` + `[r.data() for r in resultado]`, dentro de `registro.medir("Neo4j", <1ª linha útil do Cypher>, erros_conexao=(ServiceUnavailable, SessionExpired, AuthError))`.

| Método | Retorno / comportamento |
|---|---|
| `close()`, `ping() -> bool`, `apagar_tudo()` | `MATCH (n) DETACH DELETE n` |
| `criar_esquema()` | `CREATE CONSTRAINT … IF NOT EXISTS` de unicidade em `Pessoa.id`, `Habilidade.nome`, `Empresa.nome`; `CREATE INDEX … IF NOT EXISTS` em `Pessoa.nome` |
| `criar_pessoa(id, nome, titulo, mentor=False, anos_experiencia=0)` | `MERGE` por `id` |
| `remover_pessoa(id)` | `DETACH DELETE` |
| `atualizar_pessoa(id, **props)` | só `titulo`, `mentor`, `anos_experiencia`; outra chave → `ValueError` |
| `buscar_pessoa(id) -> dict \| None` | `{id,nome,titulo,mentor,anos_experiencia}` |
| `criar_habilidade(nome, categoria)` | `MERGE`; usado pela carga |
| `criar_empresa(nome, setor)` | `MERGE`; usado pela carga |
| `conectar(a, b) -> bool` | `True` se criou; já conectados (em qualquer sentido) → `False` sem duplicar; `a == b` → `ValueError`; grava `desde` = data de hoje |
| `estao_conectados(a, b) -> bool` | sem direção |
| `ids_conexoes(id) -> list[str]` / `conexoes(id) -> list[dict]` | ordenados por nome |
| `definir_habilidade(pessoa_id, habilidade, nivel)` | `MERGE` da `Habilidade` (categoria `"Outras"` se nova) e do relacionamento; `nivel` fora de 1..5 → `ValueError` |
| `remover_habilidade(pessoa_id, habilidade)` | |
| `habilidades_de(id) -> list[dict]` | `{nome,categoria,nivel}`, nível desc, nome asc |
| `definir_interesses(pessoa_id, habilidades: list[str])` | **substitui** os `QUER_APRENDER` |
| `interesses_de(id) -> list[str]` | ordem alfabética |
| `listar_habilidades() -> list[dict]` | `{nome,categoria}` |
| `registrar_trabalho(pessoa_id, empresa, cargo, desde, ate=None)` | `MERGE` da `Empresa` (setor `"Não informado"` se nova) e de `TRABALHA_EM {cargo, desde}`; define `ate` |
| `remover_trabalho(pessoa_id, empresa, cargo, desde)` | |
| `trabalhos_de(id) -> list[dict]` | `{empresa,setor,cargo,desde,ate}`, atuais primeiro |
| `colegas_de_empresa(id) -> list[dict]` | `{id,nome,titulo,empresa}`, inclui ex-colegas |
| `pessoas_com_habilidade(habilidade, nivel_minimo=1) -> list[dict]` | `{id,nome,titulo,nivel}` |
| `menor_caminho(origem, destino) -> dict \| None` | `{"pessoas":[{id,nome,titulo}…], "graus": int}`; `origem == destino` → `graus 0` **sem chamar `shortestPath`**; sem caminho em até `MAX_SALTOS` → `None` |
| `rede_por_grau(id, max_grau=3) -> list[dict]` | `{id,nome,titulo,grau}` por `grau`, `nome` |
| `subgrafo_da_rede(id, max_grau=2) -> dict` | `{"nos":[{id,nome,titulo,grau}], "arestas":[[a,b]…]}`; inclui a própria pessoa com `grau 0` e só arestas entre nós do conjunto |
| `sugerir_conexoes(id, limite=5) -> list[dict]` | amigos de amigos não conectados: `{id,nome,titulo,em_comum,amigos:[nomes]}` por `em_comum` desc, `nome` asc |
| `recomendar_mentores(id, habilidades=None, limite=10) -> list[dict]` | ver abaixo |

**Recomendação de mentores (algoritmo fixado).** `habilidades=None` → usa `interesses_de(id)`; lista vazia → `[]`. Consulta:

```cypher
MATCH (eu:Pessoa {id: $id})
MATCH (m:Pessoa)-[ph:POSSUI_HABILIDADE]->(h:Habilidade)
WHERE m.mentor = true AND m <> eu AND ph.nivel >= 4 AND h.nome IN $habilidades
WITH eu, m, collect({nome: h.nome, nivel: ph.nivel}) AS habilidades, avg(ph.nivel) AS nivel_medio
OPTIONAL MATCH caminho = shortestPath((eu)-[:CONECTADO_COM*..6]-(m))
WITH eu, m, habilidades, nivel_medio, caminho
OPTIONAL MATCH (eu)-[:CONECTADO_COM]-(comum:Pessoa)-[:CONECTADO_COM]-(m)
WITH m, habilidades, nivel_medio, caminho, count(DISTINCT comum) AS em_comum
WITH m, habilidades, nivel_medio, em_comum,
     CASE WHEN caminho IS NULL THEN null ELSE length(caminho) END AS graus,
     CASE WHEN caminho IS NULL OR length(caminho) < 2 THEN null ELSE nodes(caminho)[1].nome END AS via
RETURN m.id AS id, m.nome AS nome, m.titulo AS titulo, habilidades, graus, em_comum, via,
       3 * size(habilidades) + nivel_medio + em_comum - coalesce(graus, 6) AS pontuacao
ORDER BY pontuacao DESC, nome ASC LIMIT $limite
```

- [ ] **Step 1: Testes que falham** — `tests/test_neo4j_service.py`. `setup_module` apaga tudo, cria o esquema e monta este mini-grafo: pessoas `t1`…`t6` (nomes "T1"…"T6"); conexões `t1-t2`, `t2-t3`, `t3-t4`, `t1-t5`, `t5-t3`; `t6` isolada; `t3` e `t4` são mentores; habilidades `t3: Neo4j 5`, `t4: Neo4j 4, Redis 5`, `t2: Neo4j 5` (não é mentor), `t5: Redis 3`.

```python
def test_esquema_cria_constraints(neo4j_svc):
    nomes = [r["name"] for r in neo4j_svc._executar("SHOW CONSTRAINTS YIELD name RETURN name")]
    assert len(nomes) >= 3

def test_conectar_e_idempotente_e_sem_direcao(neo4j_svc):
    assert neo4j_svc.conectar("t2", "t1") is False            # já existe t1-t2
    assert neo4j_svc.estao_conectados("t2", "t1")
    total = neo4j_svc._executar("MATCH (:Pessoa {id:'t1'})-[r:CONECTADO_COM]-(:Pessoa {id:'t2'}) RETURN count(r) AS n")[0]["n"]
    assert total == 1
    with pytest.raises(ValueError): neo4j_svc.conectar("t1", "t1")

def test_menor_caminho(neo4j_svc):
    c = neo4j_svc.menor_caminho("t1", "t4")
    assert c["graus"] == 3 and [p["id"] for p in c["pessoas"]][0] == "t1" and c["pessoas"][-1]["id"] == "t4"

def test_menor_caminho_para_si_mesmo(neo4j_svc):                 # Review Focus 1
    assert neo4j_svc.menor_caminho("t1", "t1") == {"pessoas": [{"id": "t1", "nome": "T1", "titulo": ANY}], "graus": 0}

def test_sem_caminho_e_pessoa_inexistente(neo4j_svc):
    assert neo4j_svc.menor_caminho("t1", "t6") is None and neo4j_svc.menor_caminho("t1", "nao-existe") is None

def test_rede_por_grau(neo4j_svc):
    assert [(p["id"], p["grau"]) for p in neo4j_svc.rede_por_grau("t1")] == [("t2", 1), ("t5", 1), ("t3", 2), ("t4", 3)]
    assert neo4j_svc.rede_por_grau("t6") == []

def test_subgrafo(neo4j_svc):
    s = neo4j_svc.subgrafo_da_rede("t1", max_grau=2)
    assert {n["id"] for n in s["nos"]} == {"t1", "t2", "t5", "t3"} and len(s["arestas"]) == 4

def test_sugerir_conexoes(neo4j_svc):
    s = neo4j_svc.sugerir_conexoes("t1")
    assert s[0]["id"] == "t3" and s[0]["em_comum"] == 2 and sorted(s[0]["amigos"]) == ["T2", "T5"]

def test_mentores_pontuacao_e_ordem(neo4j_svc):
    m = neo4j_svc.recomendar_mentores("t1", ["Neo4j", "Redis"])
    assert [x["id"] for x in m] == ["t3", "t4"]                 # t2 domina mas não é mentor
    assert m[0]["pontuacao"] == 8.0 and m[0]["graus"] == 2 and m[0]["em_comum"] == 2      # 3*1 + 5 + 2 - 2
    assert m[1]["pontuacao"] == 7.5 and m[1]["graus"] == 3 and m[1]["via"] in ("T2", "T5") # 3*2 + 4.5 + 0 - 3

def test_mentores_sem_conexoes_e_sem_interesses(neo4j_svc):
    m = neo4j_svc.recomendar_mentores("t6", ["Neo4j"])
    assert [x["id"] for x in m] == ["t3", "t4"] and m[0]["graus"] is None and m[0]["pontuacao"] == 2.0
    assert neo4j_svc.recomendar_mentores("t6") == []            # t6 não tem QUER_APRENDER

def test_interesses_sao_substituidos(neo4j_svc):
    neo4j_svc.definir_interesses("t1", ["Neo4j", "Redis"]); neo4j_svc.definir_interesses("t1", ["Redis"])
    assert neo4j_svc.interesses_de("t1") == ["Redis"]
    assert [x["id"] for x in neo4j_svc.recomendar_mentores("t1")] == ["t4"]

def test_habilidade_com_aspas_usa_parametros(neo4j_svc):
    nome = "C++ \"avançado\" 'e' {x}"
    neo4j_svc.definir_habilidade("t5", nome, 4)
    assert nome in [h["nome"] for h in neo4j_svc.habilidades_de("t5")]
    with pytest.raises(ValueError): neo4j_svc.definir_habilidade("t5", "Redis", 9)

def test_trabalho_e_colegas(neo4j_svc):
    neo4j_svc.registrar_trabalho("t1", "Empresa X", "Analista", "2021-03"); neo4j_svc.registrar_trabalho("t2", "Empresa X", "Dev", "2018-01", "2020-12")
    assert neo4j_svc.trabalhos_de("t1")[0] == {"empresa": "Empresa X", "setor": "Não informado", "cargo": "Analista", "desde": "2021-03", "ate": None}
    assert [c["id"] for c in neo4j_svc.colegas_de_empresa("t1")] == ["t2"]
    neo4j_svc.remover_trabalho("t1", "Empresa X", "Analista", "2021-03"); assert neo4j_svc.trabalhos_de("t1") == []

def test_neo4j_fora_do_ar_vira_BancoIndisponivel():
    fora = Neo4jService("bolt://localhost:1", "neo4j", "x"); assert fora.ping() is False
    with pytest.raises(BancoIndisponivel): fora.ids_conexoes("t1")
```

- [ ] **Step 2:** `pytest tests/test_neo4j_service.py -v` → FALHA.
- [ ] **Step 3: Implementar `Neo4jService`.**
- [ ] **Step 4:** `pytest tests/test_neo4j_service.py -v` → 14 passam.

---

### Task 6: Dados de exemplo e scripts de carga

**Files:**
- Create: `scripts/dados_exemplo.py`, `scripts/carga_mongo.py`, `scripts/carga_redis.py`, `scripts/carga_neo4j.py`, `scripts/carga_inicial.py`
- Modify: `tests/conftest.py` (fixture `dados_carregados` + recarga no fim da sessão)
- Test: `tests/test_carga.py`

**Interfaces:**
- Consumes: os três serviços, `gerar_hash`, `carregar_config`, `enderecos_sao_locais`
- Produces:
  - `scripts.dados_exemplo`: `PESSOAS: list[dict]`, `EMPRESAS`, `HABILIDADES`, `CONEXOES: list[tuple[str, str]]`, `TRABALHOS_ANTERIORES`, `gerar_posts() -> list[dict]`, `NOTIFICACOES_INICIAIS`
  - `carga_mongo.carregar(mongo, senha_demo: str) -> dict`, `carga_redis.carregar(redis_svc) -> dict`, `carga_neo4j.carregar(neo4j_svc) -> dict` — cada uma apaga, cria esquema, carrega e devolve contagens
  - `carga_inicial.carregar_tudo(cfg, *, confirmar_remoto=False, se_vazio=False) -> dict` — levanta `SystemExit` com mensagem se algum endereço não for local e `confirmar_remoto` for falso; com `se_vazio=True` não faz nada se `usuarios` já tiver documentos. Linha de comando: `python scripts/carga_inicial.py [--confirmar-remoto] [--se-vazio]`, imprimindo um resumo por banco.
  - `conftest.py`: fixture `dados_carregados` (escopo de módulo) roda `carregar_tudo(cfg)`; finalizador de sessão roda `carregar_tudo(cfg)` de novo.

**Dados fixados** (os testes dependem deles; e-mail = primeiro nome sem acento + `@exemplo.com`; todos com a senha `SENHA_DEMO`)

| id | Nome | Título | Empresa atual | Mentor | Anos | Habilidades (nível) | Quer aprender |
|---|---|---|---|---|---|---|---|
| u001 | Ana Beatriz Lima | Analista de Dados Júnior | DataNorte | não | 2 | Python 3, SQL 4, Power BI 3 | Neo4j, Machine Learning, Kubernetes |
| u002 | Bruno Carvalho | Engenheiro de Dados Pleno | DataNorte | não | 5 | Python 4, Spark 4, SQL 4, MongoDB 3 | — |
| u003 | Camila Nóbrega | Cientista de Dados Sênior | Mangue Labs | sim | 9 | Machine Learning 5, Python 5, SQL 4 | — |
| u004 | Diego Farias | Arquiteto de Dados | Banco Sertão | sim | 12 | Neo4j 5, MongoDB 5, Redis 4, SQL 5 | — |
| u005 | Eduarda Monteiro | Analista de BI | Sol Varejo | não | 4 | Power BI 5, SQL 4 | — |
| u006 | Felipe Gadelha | Engenheiro de Machine Learning | Mangue Labs | sim | 7 | Machine Learning 4, Python 5, Docker 3 | — |
| u007 | Marina Albuquerque | Engenheira de Dados Sênior | DataNorte | sim | 8 | Spark 5, Python 5, MongoDB 4, Neo4j 4 | — |
| u008 | Gustavo Pessoa | Administrador de Banco de Dados | Banco Sertão | não | 10 | SQL 5, Redis 4, MongoDB 4 | — |
| u009 | Helena Dantas | Desenvolvedora Full Stack | Aurora Sistemas | sim | 8 | JavaScript 5, React 5, Node.js 4, API REST 4 | — |
| u010 | Igor Medeiros | Desenvolvedor Back-end | Aurora Sistemas | não | 4 | Java 4, API REST 4, SQL 3 | — |
| u011 | Juliana Queiroz | Desenvolvedora Front-end | Litoral Tech | não | 3 | React 4, TypeScript 3, JavaScript 4 | UX Design, Node.js |
| u012 | Kleber Azevedo | Tech Lead | Litoral Tech | sim | 11 | Java 5, API REST 5, Node.js 4, Docker 4 | — |
| u013 | Larissa Toscano | Desenvolvedora Mobile | Maré Jogos | não | 5 | TypeScript 4, React 4 | — |
| u014 | Mateus Rangel | Desenvolvedor Back-end | Ponte Pagamentos | não | 6 | Node.js 5, MongoDB 4, Redis 4 | — |
| u015 | Natália Ramalho | Engenheira de Software Sênior | Ponte Pagamentos | sim | 9 | TypeScript 5, Node.js 5, API REST 5 | — |
| u016 | Otávio Lucena | Estagiário de Desenvolvimento | Aurora Sistemas | não | 1 | JavaScript 2, SQL 2 | React, Node.js, Docker |
| u017 | Patrícia Vilar | Gerente de Produto | Farol Educação | sim | 10 | Gestão de Produto 5, Scrum 5, Pesquisa com Usuários 4 | — |
| u018 | Rafael Cunha | Designer de Produto | Farol Educação | não | 5 | Figma 5, UX Design 4 | — |
| u019 | Sabrina Leite | Pesquisadora de UX | Verde Saúde | sim | 7 | Pesquisa com Usuários 5, UX Design 5 | — |
| u020 | Thiago Bezerra | Product Owner | Verde Saúde | não | 6 | Scrum 4, Gestão de Produto 4 | — |
| u021 | Úrsula Maia | Head de Design | Sol Varejo | sim | 13 | UX Design 5, Figma 5, Gestão de Produto 4 | — |
| u022 | Vinícius Paiva | Scrum Master | Cais Logística | não | 6 | Scrum 5 | — |
| u023 | Yasmin Coutinho | Designer de Interface Júnior | Maré Jogos | não | 2 | Figma 3, UX Design 3 | Pesquisa com Usuários, Gestão de Produto |
| u024 | Wagner Trigueiro | Engenheiro DevOps | Nuvem Nordeste | sim | 9 | Kubernetes 5, Docker 5, AWS 4, DevOps 5 | — |
| u025 | Aline Cavalcanti | Analista de Segurança | Banco Sertão | sim | 8 | Segurança da Informação 5, Linux 4 | — |
| u026 | Caio Sobreira | Engenheiro de Confiabilidade (SRE) | Nuvem Nordeste | não | 5 | Kubernetes 4, Linux 5, AWS 4 | — |
| u027 | Débora Figueiredo | Arquiteta de Nuvem | Nuvem Nordeste | sim | 12 | AWS 5, Kubernetes 4, Docker 4 | — |
| u028 | Emanuel Lins | Administrador de Sistemas | Cais Logística | não | 7 | Linux 5, Docker 3 | — |
| u029 | Fernanda Arruda | Engenheira de Plataforma | Ponte Pagamentos | não | 4 | Docker 4, DevOps 3 | Kubernetes, AWS |
| u030 | José Tavares | Recém-formado em Sistemas de Informação | — | não | 0 | Python 2, SQL 2 | Python, Machine Learning |

- **Conexões (53, números = sufixo do id):** `1-2 1-3 2-3 2-4 3-5 4-5 4-6 5-7 6-7 6-8 7-8 1-5 · 9-10 9-11 10-11 10-12 11-13 12-13 12-14 13-15 14-15 14-16 15-16 9-13 · 17-18 17-19 18-19 18-20 19-21 20-21 20-22 21-23 22-23 17-21 · 24-25 24-26 25-26 25-27 26-28 27-28 27-29 28-29 · pontes: 4-9 12-17 20-24 6-11 15-19 22-26 8-14 3-12 16-21 13-24 7-25`. `u030` não tem conexões.
- **Empresas (12) e setor:** DataNorte (Dados), Mangue Labs (Inteligência Artificial), Banco Sertão (Financeiro), Sol Varejo (Varejo), Aurora Sistemas (Software), Litoral Tech (Software), Maré Jogos (Jogos), Ponte Pagamentos (Fintech), Farol Educação (Educação), Verde Saúde (Saúde), Cais Logística (Logística), Nuvem Nordeste (Computação em Nuvem).
- **Habilidades (25) por categoria:** *Dados:* Python, SQL, Spark, MongoDB, Redis, Neo4j, Machine Learning, Power BI · *Desenvolvimento:* JavaScript, React, Node.js, Java, API REST, TypeScript · *Produto e Design:* UX Design, Figma, Gestão de Produto, Scrum, Pesquisa com Usuários · *Infraestrutura:* Docker, Kubernetes, AWS, Linux, Segurança da Informação, DevOps.
- **Trabalhos anteriores (`ate` preenchido):** u007 em Banco Sertão (Analista de Dados, 2016-02 a 2020-12); u004 em DataNorte (Engenheiro de Dados, 2012-01 a 2018-06); u012 em Aurora Sistemas (Desenvolvedor, 2013-03 a 2019-08); u024 em Cais Logística (Analista de Infraestrutura, 2015-05 a 2019-10). Emprego atual de cada pessoa: `desde` determinístico a partir de `anos_experiencia`.
- **Perfil no Mongo:** cada pessoa tem `resumo`, `localizacao` (cidades do Nordeste), `experiencias` coerentes com `TRABALHA_EM` (mesma empresa, cargo, início, fim), 1–2 `formacao`; mentores têm 1–2 `certificacoes`. Textos fictícios à escolha de quem implementa.
- **Posts: 40.** Um por pessoa de u001 a u029 (29) + 2 extras de u001 + 1 extra de cada um de u003, u004, u007, u009, u012, u017, u021, u024, u027 (9). `u030` não tem post. `criado_em` espalhado pelos 14 dias anteriores à carga, por deslocamentos fixos. Tags tiradas de: `dados`, `carreira`, `mentoria`, `nosql`, `web`, `design`, `produto`, `devops`, `vagas`, `eventos`. Três posts (de u003, u009, u021) têm uma imagem PNG gerada com Pillow e salva no GridFS. Algumas curtidas e comentários vindos de conexões do autor — **nenhum de `u001`** (os testes partem de Ana sem ter curtido nada).
- **Notificações iniciais:** exatamente 3 não lidas para `u001` (de u002, u003, u005), gravadas no Mongo **e** refletidas no Redis (contador = 3, lista com 3). Ninguém começa online.

- [ ] **Step 1: Testes que falham** — `tests/test_carga.py` (usa `dados_carregados`)

```python
def test_contagens(dados_carregados, mongo, neo4j_svc):
    assert mongo.db.usuarios.count_documents({}) == 30 and mongo.db.posts.count_documents({}) == 40
    assert mongo.db["fs.files"].count_documents({}) == 3
    c = lambda q: neo4j_svc._executar(q)[0]["n"]
    assert c("MATCH (n:Pessoa) RETURN count(n) AS n") == 30 and c("MATCH (n:Habilidade) RETURN count(n) AS n") == 25
    assert c("MATCH (n:Empresa) RETURN count(n) AS n") == 12 and c("MATCH ()-[r:CONECTADO_COM]->() RETURN count(r) AS n") == 53

def test_ids_iguais_nos_dois_bancos(dados_carregados, mongo, neo4j_svc):
    assert {u["_id"] for u in mongo.listar_usuarios()} == {r["id"] for r in neo4j_svc._executar("MATCH (p:Pessoa) RETURN p.id AS id")}

def test_caminhos_conhecidos(dados_carregados, neo4j_svc):
    ids = lambda c: [p["id"] for p in c["pessoas"]]
    assert ids(neo4j_svc.menor_caminho("u001", "u007")) == ["u001", "u005", "u007"]
    assert ids(neo4j_svc.menor_caminho("u001", "u019")) == ["u001", "u003", "u012", "u017", "u019"]
    assert neo4j_svc.menor_caminho("u001", "u029")["graus"] == 5 and neo4j_svc.menor_caminho("u001", "u030") is None

def test_rede_da_ana(dados_carregados, neo4j_svc):
    por_grau = {}
    for p in neo4j_svc.rede_por_grau("u001", 3): por_grau.setdefault(p["grau"], set()).add(p["id"])
    assert por_grau == {1: {"u002", "u003", "u005"}, 2: {"u004", "u007", "u012"},
                        3: {"u006", "u008", "u009", "u010", "u013", "u014", "u017", "u025"}}

def test_mentores_da_ana(dados_carregados, neo4j_svc):
    m = neo4j_svc.recomendar_mentores("u001")
    assert [x["id"] for x in m] == ["u003", "u004", "u007", "u006", "u024", "u027"]
    assert [x["pontuacao"] for x in m] == [9.0, 8.0, 6.0, 4.0, 4.0, 3.0] and m[2]["via"] == "Eduarda Monteiro"

def test_mentores_de_quem_nao_tem_conexoes(dados_carregados, neo4j_svc):
    m = neo4j_svc.recomendar_mentores("u030")
    assert [(x["id"], x["pontuacao"], x["graus"]) for x in m] == [("u003", 5.0, None), ("u006", 4.5, None), ("u007", 2.0, None)]

def test_sugestoes_da_ana(dados_carregados, neo4j_svc):
    s = neo4j_svc.sugerir_conexoes("u001")
    assert (s[0]["id"], s[0]["em_comum"]) == ("u004", 2) and {x["id"] for x in s[1:]} == {"u007", "u012"}

def test_login_e_notificacoes_iniciais(dados_carregados, cfg, mongo, redis_svc):
    assert conferir_senha(cfg.SENHA_DEMO, mongo.buscar_usuario_por_email("ana@exemplo.com")["senha_hash"])
    assert redis_svc.nao_lidas("u001") == 3 and len(mongo.listar_notificacoes("u001")) == 3
    assert redis_svc.contar_online() == 0

def test_experiencias_batem_com_o_grafo(dados_carregados, mongo, neo4j_svc):
    no_mongo = {(e["empresa"], e["cargo"]) for e in mongo.buscar_usuario("u007")["experiencias"]}
    no_grafo = {(t["empresa"], t["cargo"]) for t in neo4j_svc.trabalhos_de("u007")}
    assert no_mongo == no_grafo and len(no_grafo) == 2

def test_carga_pode_repetir(dados_carregados, cfg, mongo):
    carregar_tudo(cfg); assert mongo.db.usuarios.count_documents({}) == 30

def test_se_vazio_nao_apaga(dados_carregados, cfg, mongo):
    mongo.db.posts.delete_one({}); carregar_tudo(cfg, se_vazio=True)
    assert mongo.db.posts.count_documents({}) == 39

def test_trava_contra_banco_remoto(cfg):
    with pytest.raises(SystemExit): carregar_tudo(replace(cfg, NEO4J_URI="neo4j+s://abc.databases.neo4j.io"))
```

- [ ] **Step 2:** `pytest tests/test_carga.py -v` → FALHA.
- [ ] **Step 3: Implementar** `dados_exemplo.py` (dados acima; nada aleatório sem `random.Random(42)`), as três cargas e `carga_inicial.py`. A suíte recarrega os dados dezenas de vezes: a carga completa deve levar menos de 2 s — os hashes de senha são calculados uma vez por processo e reaproveitados, e as gravações são em lote (`insert_many`, `UNWIND $linhas`).
- [ ] **Step 4:** `pytest tests/test_carga.py -v` → 12 passam. `python scripts/carga_inicial.py` imprime o resumo. `pytest -q` → tudo passa.

---

### Task 7: Orquestrador

**Files:**
- Create: `app/servicos/orquestrador.py`
- Test: `tests/test_orquestrador.py`

**Interfaces:**
- Consumes: todos os métodos das Tarefas 2–5; `ErroDeNegocio`, `EmailJaCadastrado`, `BancoIndisponivel`; constantes de `config`
- Produces: `Orquestrador(mongo, redis, neo4j, registro, cfg)` com atributos `mongo`, `redis`, `neo4j`, `registro`, `cfg`. **Cada método público roda dentro de `with self.registro.acao("<nome>"):`** (nome entre aspas abaixo).

| Método | Retorno | Regras |
|---|---|---|
| `estado_dos_bancos()` | `{"MongoDB": bool, "Redis": bool, "Neo4j": bool}` | registro pausado |
| `fazer_login(email, senha)` — "Login" | `{"token", "usuario": {"id","nome","titulo"}}` | e-mail inexistente ou senha errada → `ErroDeNegocio("E-mail ou senha inválidos.")` |
| `validar_sessao(token)` | `{"usuario_id","nome"} \| None` | registro pausado; renova sessão e presença |
| `sair(token)` — "Sair" | `None` | |
| `cadastrar_usuario(nome, email, senha, titulo)` — "Cadastro" | `str` (novo id) | nome 3–80, título 2–80, senha ≥ 6, e-mail com `@` (senão `ErroDeNegocio`); Mongo → Neo4j; se o Neo4j falhar, `remover_usuario` e propaga |
| `abrir_perfil(usuario_id)` — "Abrir perfil" | `{"perfil","do_cache","habilidades","interesses","trabalhos","total_conexoes","online","avisos"}` | cache-aside em `cache:perfil:{id}`; partes do grafo viram `None` + aviso se o Neo4j cair; id inexistente → `ErroDeNegocio` |
| `editar_dados_basicos(usuario_id, *, titulo, resumo, cidade, estado)` — "Editar perfil" | `None` | se o título mudou: Mongo → Neo4j (`atualizar_pessoa`) → `atualizar_titulo_nos_posts`; se o Neo4j falhar, volta o título antigo no Mongo; apaga cache |
| `adicionar_experiencia(usuario_id, exp)` / `remover_experiencia(usuario_id, exp)` — "Editar experiência" | `None` | `exp = {"empresa","cargo","inicio","fim","descricao"}`; `empresa`, `cargo`, `inicio` obrigatórios; Mongo → Neo4j com compensação; apaga cache |
| `adicionar_item_perfil(usuario_id, campo, item)` / `remover_item_perfil(...)` — "Editar perfil" | `None` | `campo` ∈ `formacao`, `certificacoes`; só Mongo; apaga cache |
| `definir_habilidade(usuario_id, habilidade, nivel)` / `remover_habilidade(...)` — "Editar habilidades" | `None` | só Neo4j |
| `definir_mentoria(usuario_id, mentor: bool, anos_experiencia: int)` — "Editar perfil" | `None` | só Neo4j |
| `definir_interesses(usuario_id, habilidades)` — "Salvar interesses" | `None` | só Neo4j |
| `montar_feed(usuario_id, tag=None)` — "Montar feed" | `{"posts": [...], "avisos": [...]}` | ids = eu + `ids_conexoes` (Neo4j fora → só eu, com aviso); cada post ganha `autor_online` (Redis fora → `False`) |
| `publicar_post(usuario_id, texto, tags, arquivo=None)` — "Publicar post" | `{"post_id","notificados","avisos"}` | `arquivo = (nome, tipo, bytes) \| None`; validações abaixo; notifica cada conexão (tipo `post`) |
| `curtir_post(usuario_id, post_id)` — "Curtir" | `bool` | ao curtir post de outra pessoa, notifica o autor (tipo `curtida`); descurtir e post próprio não notificam |
| `comentar_post(usuario_id, post_id, texto)` — "Comentar" | `None` | texto 1–500 após `strip`; notifica o autor se for outra pessoa |
| `conectar(usuario_id, outro_id)` — "Conectar" | `{"criada": bool, "avisos"}` | mesmo id → `ErroDeNegocio`; só notifica (tipo `conexao`) quando `criada` |
| `pedir_mentoria(usuario_id, mentor_id, mensagem="")` — "Pedir mentoria" | `{"avisos"}` | notificação tipo `mentoria` |
| `notificacoes(usuario_id)` | `{"nao_lidas","recentes","historico"}` | contador e recentes do Redis; histórico do Mongo |
| `marcar_notificacoes_lidas(usuario_id)` — "Marcar notificações como lidas" | `None` | Redis zera; Mongo `lida=True` |
| `painel_presenca()` | `{"total_online","online":[{id,nome,titulo,visto}],"offline":[…]}` | registro pausado; nomes do Mongo, estado do Redis; offline por `visto` mais recente primeiro |
| `tags_em_alta()` | `{"tags","do_cache"}` | cache-aside em `cache:tags_em_alta`; apagado ao publicar |
| `simular_atividade(usuario_id, quantos=6)` — "Simulação (demo)" **[extra]** | `{"online":[ids],"notificacoes": 2}` | coloca `quantos` outros usuários online e gera 2 notificações com o texto terminando em `"(simulação)"` |

- **Validação de post:** texto 1–1000 caracteres após `strip` (senão `ErroDeNegocio`); tags → minúsculas, sem `#`, sem espaços nas pontas, sem repetidas, vazias descartadas, no máximo 5 (as primeiras); anexo: tipo em `ANEXO_TIPOS` e tamanho ≤ `ANEXO_MAX_BYTES` (senão `ErroDeNegocio`).
- **Notificar** (método interno `_notificar(destinatarios, tipo, de, texto) -> list[str]`): `mongo.criar_notificacoes` + `redis.notificar_varios`; cada um em seu `try`; `BancoIndisponivel` vira um texto em `avisos`, nunca exceção. Destinatário igual ao remetente é ignorado.
- Regra geral (seção 8 do design): dado duplicado → compensação e recusa; efeito colateral → aviso.

- [ ] **Step 1: Testes que falham** — `tests/test_orquestrador.py` (fixture `orq`: recarrega os dados de exemplo antes de **cada** teste e constrói os três serviços reais compartilhando **um único** `Registro`, que também vai para o `Orquestrador`; classe auxiliar `ForaDoAr(banco)` cujo `__getattr__` devolve uma função que levanta `BancoIndisponivel(banco)`)

```python
def test_login_cria_sessao_e_presenca(orq):
    r = orq.fazer_login("  ANA@exemplo.com ", SENHA)
    assert r["usuario"]["id"] == "u001" and orq.redis.validar_sessao(r["token"])["usuario_id"] == "u001"
    assert orq.redis.esta_online("u001")
    orq.sair(r["token"]); assert orq.validar_sessao(r["token"]) is None and not orq.redis.esta_online("u001")

@pytest.mark.parametrize("email,senha", [("ana@exemplo.com", "errada"), ("ninguem@exemplo.com", "x")])
def test_login_invalido(orq, email, senha):
    with pytest.raises(ErroDeNegocio): orq.fazer_login(email, senha)

def test_feed_so_tem_conexoes_e_eu(orq):
    f = orq.montar_feed("u001")
    assert {p["autor_id"] for p in f["posts"]} == {"u001", "u002", "u003", "u005"} and f["avisos"] == []
    assert all("autor_online" in p for p in f["posts"])

def test_feed_de_quem_nao_tem_conexoes_nem_posts(orq):
    assert orq.montar_feed("u030") == {"posts": [], "avisos": []}

def test_publicar_normaliza_tags_e_notifica_conexoes(orq):
    antes = orq.redis.nao_lidas("u002")
    r = orq.publicar_post("u001", "  Olá, rede!  ", ["#Dados", "dados", " Carreira ", ""])
    p = orq.mongo.buscar_post(r["post_id"])
    assert p["texto"] == "Olá, rede!" and p["tags"] == ["dados", "carreira"] and r["notificados"] == 3
    assert orq.redis.nao_lidas("u002") == antes + 1 and orq.redis.nao_lidas("u001") == 3
    assert orq.mongo.listar_notificacoes("u002")[0]["tipo"] == "post"

@pytest.mark.parametrize("texto,arquivo", [
    ("   ", None), ("x" * 1001, None),
    ("ok", ("v.exe", "application/x-msdownload", b"MZ")),
    ("ok", ("g.png", "image/png", b"0" * (5 * 1024 * 1024 + 1))),
])
def test_publicar_recusa_entradas_invalidas(orq, texto, arquivo):                  # Review Focus 5
    with pytest.raises(ErroDeNegocio): orq.publicar_post("u001", texto, [], arquivo)
    assert orq.mongo.db.posts.count_documents({}) == 40

def test_publicar_com_anexo(orq):
    r = orq.publicar_post("u001", "com imagem", [], ("g.png", "image/png", b"\x89PNG123"))
    a = orq.mongo.buscar_post(r["post_id"])["anexos"][0]
    assert a["nome"] == "g.png" and orq.mongo.ler_anexo(a["arquivo_id"]) == b"\x89PNG123"

def test_conectar_notifica_uma_vez_so(orq):                                         # Review Focus 3
    assert orq.conectar("u001", "u004")["criada"] is True and orq.redis.nao_lidas("u004") == 1
    assert orq.conectar("u004", "u001")["criada"] is False and orq.redis.nao_lidas("u004") == 1
    with pytest.raises(ErroDeNegocio): orq.conectar("u001", "u001")

def test_curtir_notifica_so_ao_curtir_post_alheio(orq):
    pid = orq.mongo.listar_posts(["u002"])[0]["_id"]
    assert orq.curtir_post("u001", pid) is True and orq.redis.nao_lidas("u002") == 1
    assert orq.curtir_post("u001", pid) is False and orq.redis.nao_lidas("u002") == 1

def test_cadastro_grava_nos_dois_bancos(orq):
    novo = orq.cadastrar_usuario("Zé Teste", "  NOVO@Exemplo.com ", "segredo1", "Desenvolvedor")
    assert novo == "u031" and orq.neo4j.buscar_pessoa("u031")["nome"] == "Zé Teste"
    assert orq.fazer_login("novo@exemplo.com", "segredo1")["usuario"]["id"] == "u031"

def test_cadastro_com_email_repetido_nao_deixa_no_orfao(orq):                       # Review Focus 4
    with pytest.raises(EmailJaCadastrado): orq.cadastrar_usuario("Outra Ana", " Ana@EXEMPLO.com", "segredo1", "Dev")
    assert orq.neo4j._executar("MATCH (p:Pessoa) RETURN count(p) AS n")[0]["n"] == 30

def test_cadastro_desfaz_mongo_se_neo4j_falhar(orq):
    quebrado = Orquestrador(orq.mongo, orq.redis, ForaDoAr("Neo4j"), orq.registro, orq.cfg)
    with pytest.raises(BancoIndisponivel): quebrado.cadastrar_usuario("Zé Teste", "ze@exemplo.com", "segredo1", "Dev")
    assert orq.mongo.buscar_usuario_por_email("ze@exemplo.com") is None

def test_perfil_cache_miss_hit_e_invalidacao(orq):
    assert orq.abrir_perfil("u001")["do_cache"] is False and orq.abrir_perfil("u001")["do_cache"] is True
    orq.editar_dados_basicos("u001", titulo="Analista de Dados Pleno", resumo="novo", cidade="Recife", estado="PE")
    p = orq.abrir_perfil("u001")
    assert p["do_cache"] is False and p["perfil"]["titulo"] == "Analista de Dados Pleno" and p["total_conexoes"] == 3
    assert orq.neo4j.buscar_pessoa("u001")["titulo"] == "Analista de Dados Pleno"
    assert orq.mongo.listar_posts(["u001"])[0]["autor"]["titulo"] == "Analista de Dados Pleno"
    assert "senha_hash" not in p["perfil"]

def test_titulo_volta_se_neo4j_falhar(orq):
    quebrado = Orquestrador(orq.mongo, orq.redis, ForaDoAr("Neo4j"), orq.registro, orq.cfg)
    with pytest.raises(BancoIndisponivel): quebrado.editar_dados_basicos("u001", titulo="X", resumo="r", cidade="c", estado="PB")
    assert orq.mongo.buscar_usuario("u001")["titulo"] == "Analista de Dados Júnior"

def test_experiencia_vai_para_mongo_e_grafo(orq):
    exp = {"empresa": "Farol Educação", "cargo": "Analista", "inicio": "2019-01", "fim": "2020-06", "descricao": ""}
    orq.adicionar_experiencia("u001", exp)
    assert exp in orq.mongo.buscar_usuario("u001")["experiencias"]
    assert ("Farol Educação", "2020-06") in {(t["empresa"], t["ate"]) for t in orq.neo4j.trabalhos_de("u001")}
    orq.remover_experiencia("u001", exp)
    assert "Farol Educação" not in {t["empresa"] for t in orq.neo4j.trabalhos_de("u001")}

def test_neo4j_fora_feed_mostra_so_meus_posts_com_aviso(orq):
    f = Orquestrador(orq.mongo, orq.redis, ForaDoAr("Neo4j"), orq.registro, orq.cfg).montar_feed("u001")
    assert {p["autor_id"] for p in f["posts"]} == {"u001"} and len(f["avisos"]) == 1

def test_neo4j_fora_post_e_salvo_sem_notificar(orq):
    r = Orquestrador(orq.mongo, orq.redis, ForaDoAr("Neo4j"), orq.registro, orq.cfg).publicar_post("u001", "mesmo assim", [])
    assert orq.mongo.buscar_post(r["post_id"]) and r["notificados"] == 0 and r["avisos"]

def test_redis_fora_conexao_e_mantida_com_aviso(orq):
    r = Orquestrador(orq.mongo, ForaDoAr("Redis"), orq.neo4j, orq.registro, orq.cfg).conectar("u001", "u004")
    assert r["criada"] is True and r["avisos"] and orq.neo4j.estao_conectados("u001", "u004")

def test_notificacoes_e_marcar_lidas(orq):
    n = orq.notificacoes("u001"); assert n["nao_lidas"] == 3 and len(n["recentes"]) == 3 and len(n["historico"]) == 3
    orq.marcar_notificacoes_lidas("u001")
    assert orq.notificacoes("u001")["nao_lidas"] == 0 and all(x["lida"] for x in orq.notificacoes("u001")["historico"])

def test_painel_presenca(orq):
    orq.fazer_login("ana@exemplo.com", SENHA); p = orq.painel_presenca()
    assert p["total_online"] == 1 and p["online"][0]["id"] == "u001" and len(p["offline"]) == 29

def test_tags_em_alta_usa_cache_e_invalida_ao_publicar(orq):
    assert orq.tags_em_alta()["do_cache"] is False and orq.tags_em_alta()["do_cache"] is True
    orq.publicar_post("u001", "novo", ["nosql"]); assert orq.tags_em_alta()["do_cache"] is False

def test_acoes_aparecem_no_registro_com_os_tres_bancos(orq):
    orq.registro.limpar(); orq.publicar_post("u001", "bastidores", ["dados"])
    g = orq.registro.grupos()[0]
    assert g["acao"] == "Publicar post" and {o["banco"] for o in g["operacoes"]} == {"MongoDB", "Redis", "Neo4j"}

def test_simulador(orq):
    r = orq.simular_atividade("u001", quantos=6)
    assert len(r["online"]) == 6 and "u001" not in r["online"] and orq.redis.contar_online() == 6
    assert orq.redis.nao_lidas("u001") == 5 and orq.redis.notificacoes_recentes("u001")[0]["texto"].endswith("(simulação)")
```

- [ ] **Step 2:** `pytest tests/test_orquestrador.py -v` → FALHA.
- [ ] **Step 3: Implementar `Orquestrador`** (sem `simular_atividade`).
- [ ] **Step 4:** `pytest tests/test_orquestrador.py -v -k "not simulador"` → todos passam.
- [ ] **Step 5 [extra]:** implementar `simular_atividade`; `pytest tests/test_orquestrador.py -v` → 27 passam (23 funções; duas são parametrizadas).

---

### Task 8: Casca da aplicação — entrada, barra lateral, navegação, Bastidores

**Files:**
- Create: `app/estado.py`, `app/Inicio.py`, `app/paginas/entrada.py`, `app/componentes/bastidores.py`, `.streamlit/config.toml`, `.claude/launch.json`
- Create (provisórias, 1 linha de título cada, substituídas nas Tarefas 9–11): `app/paginas/feed_perfil.py`, `presenca_notificacoes.py`, `rede_mentores.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `Orquestrador`, serviços, `Registro`, `carregar_config`
- Produces:
  - `estado.Servicos` (dataclass): `cfg`, `registro`, `mongo`, `redis`, `neo4j`, `orq`
  - `estado.servicos() -> Servicos` — cria uma vez por sessão do navegador e guarda em `st.session_state["servicos"]` (comentário no código: cada aba tem seus serviços e seu próprio Bastidores)
  - `estado.usuario_atual() -> dict | None` — `{"id","nome"}`; valida `st.session_state["token"]` com `orq.validar_sessao`; se inválido, apaga o token, grava `st.session_state["aviso_entrada"] = "Sua sessão expirou. Entre novamente."` e devolve `None`
  - `estado.entrar(token)`, `estado.sair()`
  - `estado.mostrar_avisos(avisos: list[str])` — `st.warning` para cada um
  - `estado.tentar(funcao, *args, **kwargs)` — executa; `ErroDeNegocio` → `st.error(mensagem)`; `BancoIndisponivel` → `st.error(f"{banco} está fora do ar. Tente novamente em instantes.")`; devolve o resultado ou `None`
  - `bastidores.painel()` — `st.expander("🔎 Bastidores — o que cada banco fez")`; lista `registro.grupos(...)` (até 8 ações), cada operação numa linha `banco · comando · tempo`, cor por banco; caixa "mostrar também as leituras da tela" (padrão desmarcada); botão "limpar"
  - Cada página expõe `pagina() -> None`.
- `Inicio.py`: `st.set_page_config(page_title=NOME_APP, page_icon="🤝", layout="wide")`; sem usuário → `entrada.pagina()` e para; com usuário → barra lateral + `st.navigation([st.Page(feed_perfil.pagina, title="Feed & Perfil", icon="📰", url_path="feed", default=True), st.Page(presenca_notificacoes.pagina, title="Presença & Notificações", icon="🟢", url_path="presenca"), st.Page(rede_mentores.pagina, title="Rede & Mentores", icon="🕸️", url_path="rede")]).run()`; por fim `bastidores.painel()`.
- Barra lateral: nome do usuário; **fragmento com `run_every=10`** que envia o sinal de presença e mostra "🔔 N não lidas" (chamado dentro de `with st.sidebar:`; registro pausado); estado dos três bancos (🟢/🔴); botão "Sair".
- `entrada.pagina()`: abas "Entrar" (e-mail, senha) e "Criar conta" (nome, e-mail, título, senha); com `cfg.MODO_DEMO`, um seletor "Entrar como…" com os usuários de exemplo que faz login com `cfg.SENHA_DEMO`. Mostra e apaga `aviso_entrada`. Se o Redis ou o Mongo estiverem fora, mostra qual e não exibe o formulário.
- `.claude/launch.json`: configuração `app` que roda `.venv/Scripts/python -m streamlit run app/Inicio.py --server.headless true --server.port 8501`.

- [ ] **Step 1: Testes que falham** — `tests/test_app.py` (usa `dados_carregados`; `AppTest.from_file("app/Inicio.py", default_timeout=30)`)

```python
def test_sem_login_mostra_entrada(dados_carregados):
    at = AppTest.from_file("app/Inicio.py", default_timeout=30).run()
    assert not at.exception and any("Entrar" in t.label for t in at.tabs)

def test_login_pelo_formulario(dados_carregados, cfg):
    at = AppTest.from_file("app/Inicio.py", default_timeout=30).run()
    at.text_input(key="login_email").set_value("ana@exemplo.com"); at.text_input(key="login_senha").set_value(cfg.SENHA_DEMO)
    at.button(key="login_entrar").click().run()
    assert not at.exception and "token" in at.session_state and "Ana Beatriz Lima" in at.sidebar.markdown[0].value

def test_senha_errada_mostra_erro(dados_carregados):
    at = AppTest.from_file("app/Inicio.py", default_timeout=30).run()
    at.text_input(key="login_email").set_value("ana@exemplo.com"); at.text_input(key="login_senha").set_value("errada")
    at.button(key="login_entrar").click().run()
    assert "token" not in at.session_state and at.error[0].value == "E-mail ou senha inválidos."

def test_sessao_expirada_volta_para_entrada_com_aviso(dados_carregados):            # Review Focus 2
    at = AppTest.from_file("app/Inicio.py", default_timeout=30); at.session_state["token"] = "token-que-nao-existe"; at.run()
    assert not at.exception and "token" not in at.session_state
    assert any("sessão expirou" in w.value for w in at.warning)

def test_bastidores_mostra_login_nos_dois_bancos(dados_carregados, cfg):
    at = _logado(cfg)                   # auxiliar: faz o login pelo formulário
    grupos = at.session_state["servicos"].registro.grupos()
    assert {o["banco"] for g in grupos if g["acao"] == "Login" for o in g["operacoes"]} == {"MongoDB", "Redis"}
```

- [ ] **Step 2:** `pytest tests/test_app.py -v` → FALHA.
- [ ] **Step 3: Implementar** os arquivos da tarefa. Chaves de widget fixas: `login_email`, `login_senha`, `login_entrar`, `cad_nome`, `cad_email`, `cad_titulo`, `cad_senha`, `cad_criar`, `demo_usuario`, `demo_entrar`, `sair`.
- [ ] **Step 4:** `pytest tests/test_app.py -v` → 5 passam.
- [ ] **Step 5: No navegador** (`preview_start` com `app`): entrar como Ana; conferir barra lateral (🔔 3, três bancos 🟢), as três páginas vazias navegáveis e o Bastidores com a ação "Login". Parar o Redis (`docker compose stop redis`), recarregar → tela de entrada avisa que o Redis está fora, sem stack trace; `docker compose start redis`.

---

### Task 9: Tela Rede de Conexões & Busca de Mentores

**Files:**
- Create: `app/componentes/grafo.py`, `app/componentes/cartoes.py`, `tests/apoio.py`
- Modify: `app/paginas/rede_mentores.py` (substitui a provisória)
- Test: `tests/test_grafo.py`, `tests/test_pagina_rede.py`

**Interfaces:**
- Consumes: `estado.*`, `orq.conectar`, `orq.pedir_mentoria`, `orq.definir_interesses`, e do `Neo4jService`: `menor_caminho`, `rede_por_grau`, `subgrafo_da_rede`, `recomendar_mentores`, `sugerir_conexoes`, `listar_habilidades`, `interesses_de`, `ids_conexoes`, `colegas_de_empresa`, `pessoas_com_habilidade`; `mongo.listar_usuarios`
- Produces:
  - `tests/apoio.py`: `abrir_pagina(nome_modulo: str, email: str) -> AppTest` — `AppTest.from_function(..., args=(nome_modulo, email), default_timeout=30)` cujo corpo insere a raiz no `sys.path`, faz login pelo orquestrador na primeira execução (grava `st.session_state["token"]`) e chama `app.paginas.<nome_modulo>.pagina()`; devolve já executado (`.run()`). Usado também nas Tarefas 10 e 11.
  - `grafo.montar_html(nos: list[dict], arestas: list, destaque: list[str] = (), altura: int = 460) -> str` — pyvis com `cdn_resources="in_line"`; remove do HTML as duas referências externas (`<link>`/`<script>` do Bootstrap em `cdn.jsdelivr.net`) para funcionar sem internet; nó com rótulo = primeiro nome, dica = nome + título; cor por `grau` (0 = você); nós e arestas de `destaque` (ids em ordem de caminho) em cor de realce e mais grossos
  - `grafo.desenhar(nos, arestas, destaque=(), altura=460) -> None` — `st.iframe(montar_html(...), height=altura + 20)` (`st.components.v1.html` está obsoleto no Streamlit 1.67)
  - `cartoes.cartao_pessoa(pessoa: dict, *, online: bool | None = None, extra: str = "") -> None` — nome, título, bolinha de presença; reutilizado nas três telas
  - `cartoes.tempo_relativo(quando) -> str` — "agora", "há 5 min", "há 3 h", "há 2 dias" (aceita `datetime` ou segundos)
- `rede_mentores.pagina()` — quatro abas:
  1. **Graus de separação:** seletor de pessoa (todas menos eu) → `menor_caminho`. Mostra "Você → … → Fulano: N graus", o grafo do caminho destacado sobre a minha rede de 2 graus + os nós do caminho, e a lista. Sem caminho → `st.info("Não há caminho entre vocês em até 6 conexões.")`.
  2. **Minha rede:** métricas (1º, 2º, 3º grau), grafo de `subgrafo_da_rede(eu, 2)`, lista por grau, e a lista "Colegas e ex-colegas de empresa". Sem conexões → mensagem amigável e a aba 4 como sugestão.
  3. **Buscar mentores:** `st.multiselect` de habilidades (pré-preenchido com `interesses_de`) + botão "Salvar e buscar" → `definir_interesses` + `recomendar_mentores`. Cada mentor: cartão, pontuação, o **porquê** em texto ("Domina Neo4j (nível 5). Está a 2 graus de você, via Bruno. 2 conexões em comum." / "Fora da sua rede."), botões "Conectar" (oculto se já conectado) e "Pedir mentoria". A lista é recalculada a cada execução a partir dos interesses **salvos** (o botão só salva a seleção). Abaixo, um `st.expander("Quem domina uma habilidade?")` com seletor de habilidade → `pessoas_com_habilidade` (mentores ou não).
  4. **Talvez você conheça:** `sugerir_conexoes` com "N conexões em comum: A, B" e botão "Conectar".
- Chaves de widget: `sep_destino`, `mentor_habilidades`, `mentor_buscar`, `conectar_{id}`, `mentoria_{id}`.

- [ ] **Step 1: Testes que falham**

```python
# tests/test_grafo.py
NOS = [{"id": "a", "nome": "Ana Lima", "titulo": "Dev", "grau": 0}, {"id": "b", "nome": "João Sá", "titulo": "PO", "grau": 1}]
def test_html_funciona_sem_internet():
    h = montar_html(NOS, [["a", "b"]], destaque=["a", "b"])
    assert "jsdelivr" not in h and "cdnjs" not in h and "unpkg" not in h and "vis.Network" in h
def test_html_tem_os_nos_e_aceita_grafo_vazio():
    assert "Ana" in montar_html(NOS, [["a", "b"]]) and "João" in montar_html(NOS, [])
    assert isinstance(montar_html([], []), str)
def test_tempo_relativo():
    agora = time.time()
    assert tempo_relativo(agora - 20) == "agora" and tempo_relativo(agora - 300) == "há 5 min"
    assert tempo_relativo(agora - 3 * 3600) == "há 3 h" and tempo_relativo(agora - 2 * 86400) == "há 2 dias"

# tests/test_pagina_rede.py — usa `abrir_pagina` de tests/apoio.py
def test_pagina_abre_para_ana(dados_carregados):
    at = abrir_pagina("rede_mentores", "ana@exemplo.com"); assert not at.exception and len(at.tabs) == 4
def test_caminho_ate_sabrina(dados_carregados):
    at = abrir_pagina("rede_mentores", "ana@exemplo.com"); at.selectbox(key="sep_destino").select("u019").run()
    assert any("4 graus" in m.value for m in at.markdown)
def test_sem_caminho_ate_jose(dados_carregados):
    at = abrir_pagina("rede_mentores", "ana@exemplo.com"); at.selectbox(key="sep_destino").select("u030").run()
    assert any("Não há caminho" in i.value for i in at.info)
def test_mentores_e_conectar(dados_carregados):
    at = abrir_pagina("rede_mentores", "ana@exemplo.com"); at.button(key="mentor_buscar").click().run()
    assert any("Camila Nóbrega" in m.value for m in at.markdown)
    at.button(key="conectar_u004").click().run()
    assert not at.exception and at.session_state["servicos"].neo4j.estao_conectados("u001", "u004")
def test_pagina_abre_para_quem_nao_tem_conexoes(dados_carregados):
    assert not abrir_pagina("rede_mentores", "jose@exemplo.com").exception
```

- [ ] **Step 2:** `pytest tests/test_grafo.py tests/test_pagina_rede.py -v` → FALHA.
- [ ] **Step 3: Implementar** componentes e página. `st.selectbox` de pessoas usa `options` = ids e `format_func` = nome.
- [ ] **Step 4:** mesmos testes → 8 passam.
- [ ] **Step 5: No navegador:** como Ana, caminho até Sabrina Leite (4 graus, destacado no grafo); buscar mentores (Camila em 1º); conectar com Diego → Bastidores mostra "Conectar" com Neo4j, MongoDB e Redis.

---

### Task 10: Tela Feed & Perfil

**Files:**
- Modify: `app/paginas/feed_perfil.py` (substitui a provisória)
- Test: `tests/test_pagina_feed.py`

**Interfaces:**
- Consumes: `estado.*`, `cartoes.*`, e do orquestrador: `montar_feed`, `publicar_post`, `curtir_post`, `comentar_post`, `tags_em_alta`, `abrir_perfil`, `editar_dados_basicos`, `adicionar_experiencia`, `remover_experiencia`, `adicionar_item_perfil`, `remover_item_perfil`, `definir_habilidade`, `remover_habilidade`, `definir_mentoria`; `mongo.ler_anexo`, `mongo.listar_usuarios`, `neo4j.listar_habilidades`
- Produces: `feed_perfil.pagina()` — três abas:
  1. **Feed:** formulário "Publicar" (`st.form`, `clear_on_submit=True`): texto, tags (separadas por vírgula), anexo (`st.file_uploader`, png/jpg/pdf). Coluna lateral "Tags em alta" (clicar filtra o feed; indica "cache HIT/MISS"). Cada post num `st.container(border=True)`: cartão do autor com presença, tempo relativo, texto, tags, anexo (imagem → `st.image`; PDF → `st.download_button`), botão "👍 N", comentários num `st.expander` com campo para comentar. Feed vazio → mensagem convidando a publicar ou conectar-se.
  2. **Perfil:** seletor "Ver perfil de" (padrão: eu). Cabeçalho (nome, título, cidade, presença, nº de conexões, selo "Mentor"), resumo, experiências, formação, certificações, habilidades com nível (barra de 1 a 5), interesses. Legenda discreta dizendo de qual banco veio cada bloco e se o perfil veio do cache.
  3. **Editar meu perfil:** dados básicos (título, resumo, cidade, estado); experiências (lista com "remover" + formulário de inclusão); formação; certificações; habilidades (seletor + nível 1–5; remover); "Disponível para mentoria" + anos de experiência.
- Toda ação passa por `estado.tentar(...)`, mostra os `avisos` e chama `st.rerun()` quando muda dados.
- Chaves de widget: `post_texto`, `post_tags`, `post_arquivo`, `post_publicar`, `curtir_{post_id}`, `coment_{post_id}`, `coment_enviar_{post_id}`, `perfil_de`, `ed_titulo`, `ed_resumo`, `ed_cidade`, `ed_estado`, `ed_salvar`, `hab_nome`, `hab_nivel`, `hab_salvar`.

- [ ] **Step 1: Testes que falham** — `tests/test_pagina_feed.py`

```python
def test_feed_da_ana_abre(dados_carregados):
    at = abrir_pagina("feed_perfil", "ana@exemplo.com"); assert not at.exception and len(at.tabs) == 3
def test_publicar_pelo_formulario(dados_carregados):
    at = abrir_pagina("feed_perfil", "ana@exemplo.com")
    at.text_area(key="post_texto").set_value("Post do teste de tela"); at.text_input(key="post_tags").set_value("#NoSQL, dados")
    at.button(key="post_publicar").click().run()
    sv = at.session_state["servicos"]; p = sv.mongo.listar_posts(["u001"])[0]
    assert not at.exception and p["texto"] == "Post do teste de tela" and p["tags"] == ["nosql", "dados"]
def test_post_vazio_mostra_erro_e_nao_grava(dados_carregados):
    at = abrir_pagina("feed_perfil", "ana@exemplo.com"); at.button(key="post_publicar").click().run()
    assert at.error and not at.exception
def test_editar_titulo_reflete_nos_dois_bancos(dados_carregados):
    at = abrir_pagina("feed_perfil", "ana@exemplo.com")
    at.text_input(key="ed_titulo").set_value("Analista de Dados Pleno"); at.button(key="ed_salvar").click().run()
    sv = at.session_state["servicos"]
    assert sv.mongo.buscar_usuario("u001")["titulo"] == sv.neo4j.buscar_pessoa("u001")["titulo"] == "Analista de Dados Pleno"
def test_perfil_de_outra_pessoa(dados_carregados):
    at = abrir_pagina("feed_perfil", "ana@exemplo.com"); at.selectbox(key="perfil_de").select("u004").run()
    assert not at.exception and any("Diego Farias" in m.value for m in at.markdown)
def test_feed_vazio_para_quem_nao_tem_conexoes(dados_carregados):
    at = abrir_pagina("feed_perfil", "jose@exemplo.com"); assert not at.exception and at.info
```

- [ ] **Step 2:** `pytest tests/test_pagina_feed.py -v` → FALHA.
- [ ] **Step 3: Implementar a página** sem anexos.
- [ ] **Step 4:** `pytest tests/test_pagina_feed.py -v` → 6 passam.
- [ ] **Step 5 [extra]: Anexos** — `st.file_uploader` no formulário e exibição no post.
- [ ] **Step 6: No navegador:** publicar com imagem (Bastidores: MongoDB/GridFS, Neo4j, Redis); curtir e comentar; abrir o perfil duas vezes e ver MISS → HIT; adicionar uma experiência e conferi-la no Neo4j Browser (`MATCH (:Pessoa {id:"u001"})-[t:TRABALHA_EM]->(e) RETURN t, e`).

---

### Task 11: Tela Presença & Notificações

**Files:**
- Modify: `app/paginas/presenca_notificacoes.py` (substitui a provisória)
- Test: `tests/test_pagina_presenca.py`

**Interfaces:**
- Consumes: `estado.*`, `cartoes.*`, `orq.painel_presenca`, `orq.notificacoes`, `orq.marcar_notificacoes_lidas`, `orq.simular_atividade`, `redis.listar_sessoes`, `redis.encerrar_sessao`
- Produces: `presenca_notificacoes.pagina()`:
  - Um **fragmento com `run_every=5`** (registro pausado) com: três `st.metric` ("Online agora", "Notificações não lidas", "Minhas sessões ativas"); colunas "🟢 Online" e "⚪ Offline" (com "visto por último há…"; quem nunca entrou → "nunca entrou"); legenda "atualizado às HH:MM:SS".
  - Notificações: recentes (Redis) e histórico (Mongo) em abas; botão "Marcar todas como lidas".
  - Minhas sessões: início, último acesso, tempo restante (TTL em min), "esta sessão" marcada; botão "Encerrar" nas outras.
  - **[extra]** Bloco "🎬 Simulador (demonstração)" com aviso de que gera atividade fictícia e o botão "Simular atividade".
- Chaves de widget: `notif_marcar_lidas`, `sessao_encerrar_{i}`, `simular`.

- [ ] **Step 1: Testes que falham** — `tests/test_pagina_presenca.py`

```python
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
def test_pagina_abre_sem_notificacoes(dados_carregados):
    assert not abrir_pagina("presenca_notificacoes", "jose@exemplo.com").exception
```

- [ ] **Step 2:** `pytest tests/test_pagina_presenca.py -v` → FALHA.
- [ ] **Step 3: Implementar a página** (simulador por último).
- [ ] **Step 4:** `pytest tests/test_pagina_presenca.py -v` → 4 passam. `pytest -q` → toda a suíte passa.
- [ ] **Step 5: No navegador, com duas abas:** Ana numa, Bruno na outra. Bruno publica → o 🔔 da Ana sobe sozinho em até 10 s e Bruno aparece em "Online" em até 5 s. Bruno sai → passa para "Offline" com "visto por último agora". Simulador → 6 pessoas online, que saem sozinhas após 90 s.

---

### Task 12: Empacotamento, README e guia da defesa

**Files:**
- Create: `Dockerfile`, `.dockerignore`, `README.md`, `docs/guia_da_defesa.md`
- Modify: `docker-compose.yml`

**Interfaces:**
- Consumes: tudo.
- Produces: `docker compose up -d --build` entrega a aplicação em `http://localhost:8501` com os dados carregados.

- [ ] **Step 1: `Dockerfile`** — `python:3.11-slim`, instala `requirements.txt`, copia o projeto, comando `streamlit run app/Inicio.py --server.address=0.0.0.0 --server.port=8501 --server.headless=true`.
- [ ] **Step 2: `docker-compose.yml`** — acrescentar:
  - `carga`: mesma imagem, comando `python scripts/carga_inicial.py --se-vazio`, `restart: "no"`, depende dos três bancos `service_healthy`.
  - `app`: mesma imagem, porta `127.0.0.1:8501:8501`, depende de `carga` com `service_completed_successfully`.
  - Ambos com `MONGO_URI=mongodb://mongo:27017`, `REDIS_URL=redis://redis:6379/0`, `NEO4J_URI=bolt://neo4j:7687` e o restante vindo do `.env`.
  - **[extra]** perfil `ferramentas`: `mongo-express` (porta 8081) e `redis/redisinsight` (porta 5540), só em `127.0.0.1`.
- [ ] **Step 3: Verificar o empacotamento.** `docker compose down -v` e `docker compose up -d --build` → `docker compose ps` mostra os três bancos `healthy`, `carga` terminada com código 0 e `app` no ar; `http://localhost:8501` abre a tela de entrada e o login da Ana funciona. `docker compose restart app` → os dados continuam (a carga `--se-vazio` não apaga).
- [ ] **Step 4: `README.md`** — o que é; diagrama da arquitetura; pré-requisitos; "Subir tudo" (um comando); "Desenvolver" (bancos no Docker + `streamlit run`); carga inicial e a trava de banco remoto; como entrar (usuários de exemplo; a senha está em `.env.example`); testes (com o aviso de que recarregam os dados); como apontar o Neo4j para o Aura; estrutura de pastas; endereços (app 8501, Neo4j Browser 7474, ferramentas).
- [ ] **Step 5: `docs/guia_da_defesa.md`** — (a) roteiro de demo de ~5 min, passo a passo, com o que falar e o que aparece no Bastidores em cada passo; (b) tabela "por que este dado está neste banco"; (c) 20–25 perguntas prováveis com resposta curta, cobrindo: persistência poliglota, documento embutido × referência, `$jsonSchema`, índices e TTL do Mongo, GridFS, tipos do Redis usados e por quê (HASH, SET, ZSET, LIST, STRING), TTL, pipeline/MULTI, cache-aside e invalidação, por que presença em ZSET, index-free adjacency, `shortestPath`, `MERGE` × `CREATE`, constraints, parâmetros no Cypher, a pontuação de mentores, consistência entre bancos e compensação, o que acontece se cada banco cair; (d) consultas prontas para colar no Neo4j Browser, `mongosh` e `redis-cli` durante a arguição.
- [ ] **Step 6: Conferir os documentos contra o código** — todo comando do README executado uma vez; toda consulta do guia executada uma vez e com o resultado descrito.

---

### Task 13: Verificação final

- [ ] **Step 1:** `python scripts/carga_inicial.py` e `pytest -v` → toda a suíte passa (registrar o total).
- [ ] **Step 2: Roteiro da demo no navegador**, do início ao fim, exatamente como em `docs/guia_da_defesa.md`, com duas abas. Conferir no Bastidores os três bancos em "Publicar post" e "Conectar".
- [ ] **Step 3: Quedas.** Com a aplicação aberta e logada, parar um banco por vez (`docker compose stop neo4j` / `redis` / `mongo`) e navegar pelas três telas: sempre aviso amigável, nunca stack trace; religar e confirmar que volta sozinha.
- [ ] **Step 4: Requisitos do enunciado.** Percorrer o Anexo A do design item a item e anotar onde cada um é atendido (vai para o fim do README como "Atendimento ao enunciado").
- [ ] **Step 5:** Relatar ao grupo o que foi verificado, o que ficou de fora e oferecer o commit inicial.
