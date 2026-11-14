# Conecta Talentos

Rede social profissional com busca de mentores, feita para o **Estudo de Caso 02** da
disciplina *Implementação de Bancos de Dados NoSQL* (Prof. Ricardo Roberto de Lima).

A aplicação é escrita em Python com Streamlit e usa três bancos ao mesmo tempo, cada um no
papel em que é mais forte (persistência poliglota):

| Banco | O que guarda | Por que ele |
|---|---|---|
| **MongoDB** | perfis (experiências, formação, certificações), posts com curtidas e comentários, anexos (GridFS) e o histórico de notificações | documentos de forma variável, lidos inteiros, sem JOIN; é o dado que precisa durar |
| **Redis** | sessões com prazo de validade, presença online, contador e lista curta de notificações, cache | dados quentes, pequenos, que mudam a cada segundo e podem ser perdidos sem prejuízo |
| **Neo4j** | rede de conexões, habilidades, histórico profissional, interesses de aprendizado | as perguntas são sobre caminhos ("como chego nessa pessoa?"), e é isso que grafo faz bem |

Cada tela tem um painel recolhível, **"🔎 Bastidores — o que cada banco fez"**, que lista os
comandos que a última ação enviou a cada banco, com o tempo de cada um.

O design completo (modelo de dados, fluxos, regra de consistência) está em
[`docs/design.md`](docs/design.md). O roteiro da apresentação e as perguntas prováveis da
arguição estão em [`docs/guia_da_defesa.md`](docs/guia_da_defesa.md).

## Arquitetura

```
                 navegador (http://127.0.0.1:8501)
                                |
                +---------------+----------------+
                |   Streamlit — app/Inicio.py    |   telas em app/paginas/
                |   Feed & Perfil · Presença &   |   (não importam drivers)
                |   Notificações · Rede &        |
                |   Mentores · painel Bastidores |
                +---------------+----------------+
                                |
                +---------------+----------------+
                | app/servicos/orquestrador.py   |   um método por ação que cruza bancos
                +----+-----------+-----------+---+
                     |           |           |
              MongoService  RedisService  Neo4jService   uma classe por banco
                     |           |           |
                  MongoDB      Redis       Neo4j          containers do docker compose
                  :27017       :6379    :7474 / :7687
```

O identificador que liga os três bancos é o `id` do usuário (`u001`, `u002`…): é o `_id` no
MongoDB, a propriedade `id` do nó `:Pessoa` no Neo4j e o sufixo das chaves no Redis
(`notif:nao_lidas:u001`).

## Pré-requisitos

- **Docker Desktop** aberto (com Docker Compose; testado com Docker 29.6 e Compose 5.3).
- Para desenvolver e rodar os testes fora do container: **Python 3.11**.
- As portas 8501, 27017, 6379, 7474 e 7687 livres nesta máquina.

Nada depende de internet depois que as imagens foram baixadas.

## Subir tudo (um comando)

Na primeira vez, crie o arquivo `.env` a partir do exemplo. Ele traz as senhas do Neo4j e da
demonstração e já funciona como está:

```powershell
Copy-Item .env.example .env        # no Git Bash: cp .env.example .env
```

Depois, sempre:

```powershell
docker compose up -d --build
```

O que acontece, nesta ordem:

1. `mongo`, `redis` e `neo4j` sobem e o Compose espera os três ficarem `healthy`.
2. `carga` roda `python scripts/carga_inicial.py --se-vazio` e termina. Na primeira vez ela
   cria coleções, validação, índices e constraints e carrega os dados de exemplo. Nas próximas,
   como o MongoDB já tem usuários, ela não apaga nada e só escreve
   `Carga ignorada: o banco já tem dados.`
3. `app` (Streamlit) sobe só depois que a `carga` terminou com código 0.

A primeira vez leva alguns minutos (baixa as imagens e instala as dependências); depois,
cerca de um minuto. Para conferir:

```powershell
docker compose ps -a
```

Os três bancos aparecem `(healthy)`, a `carga` aparece `Exited (0)` e o `app` aparece `Up …
(healthy)`. Abra **http://127.0.0.1:8501** (`http://localhost:8501` também funciona).

Comandos úteis:

| Comando | Para quê |
|---|---|
| `docker compose logs carga` | ver o resumo da carga (quantos usuários, posts, conexões…) |
| `docker compose logs -f app` | acompanhar o log do Streamlit |
| `docker compose restart app` | reiniciar só a aplicação; os dados continuam |
| `docker compose stop` | parar tudo sem apagar nada |
| `docker compose down` | remover os containers; os dados ficam nos volumes |
| `docker compose down -v` | remover containers **e volumes** (apaga os dados; o próximo `up` recarrega tudo) |

A imagem da aplicação (`Dockerfile`, base `python:3.11-slim`) não contém o `.env`: as
variáveis chegam ao container pelo `env_file` do Compose. Dentro da rede do Compose, os
serviços `app` e `carga` trocam os três endereços por nomes de serviço
(`mongodb://mongo:27017`, `redis://redis:6379/0`, `bolt://neo4j:7687`); o restante vem do `.env`.
O Compose também entrega `TZ` (fuso horário) a esses dois containers, com padrão
`America/Fortaleza` (UTC-3): sem ele, os horários da tela sairiam em UTC. Para outro fuso,
defina a variável no terminal só para o comando do Compose (`$env:TZ = "America/Manaus"` no
PowerShell, antes do `docker compose up -d`). Não deixe essa variável definida num terminal em
que você vai rodar o Streamlit na máquina (modo "Desenvolver"), nem a ponha no `.env`: no
Windows, um nome de fuso no ambiente faz o Python local mostrar os horários em UTC. No modo
"Desenvolver" os horários já vêm do relógio do Windows.

## Desenvolver (bancos no Docker, Streamlit na máquina)

```powershell
docker compose up -d mongo redis neo4j     # só os bancos
python -m venv .venv
.venv\Scripts\Activate.ps1                 # no Git Bash: source .venv/Scripts/activate
pip install -r requirements.txt
python scripts/carga_inicial.py            # apaga e recarrega os dados de exemplo
streamlit run app/Inicio.py
```

Se o container `app` estiver no ar, ele já ocupa a porta 8501: pare-o antes
(`docker compose stop app`) ou use outra porta (`streamlit run app/Inicio.py --server.port 8502`).

Fora do Docker a aplicação lê o `.env`, que aponta para `127.0.0.1`. Usamos `127.0.0.1` e não
`localhost` de propósito: no Windows, `localhost` tenta IPv6 primeiro e cada primeira conexão
esperava 2 segundos.

## Carga inicial e a trava de banco remoto

`python scripts/carga_inicial.py` apaga os três bancos e recria tudo: coleções com validação
`$jsonSchema`, índices (inclusive o TTL das notificações), constraints do grafo e os dados de
exemplo. Pode ser repetido quantas vezes quiser. O conteúdo é sempre o mesmo: 30 pessoas,
53 conexões, 25 habilidades, 12 empresas, 33 empregos, 40 posts (com as mesmas curtidas e
comentários), 3 imagens no GridFS e 3 notificações não lidas para a Ana. O que muda de uma
carga para outra: o sal de cada hash de senha (aleatório de propósito), os bytes exatos das
imagens PNG geradas (o tamanho fica perto de 2,5 KB) e os horários, que são calculados a partir
do momento da carga (os posts ficam espalhados pelos 14 dias anteriores).

| Opção | Efeito |
|---|---|
| (nenhuma) | apaga e recarrega os três bancos |
| `--se-vazio` | não faz nada se o MongoDB já tiver usuários (é o que o Compose usa) |
| `--confirmar-remoto` | permite rodar contra bancos que não são locais |

**Trava de segurança:** como a carga apaga dados, ela só roda direto quando os três endereços
são locais (`localhost`, `127.0.0.1`, `::1` ou os nomes dos containers `mongo`, `redis`,
`neo4j`). Se algum apontar para fora (por exemplo, um Neo4j Aura), o script para com uma
mensagem e só continua com `--confirmar-remoto`. A verificação está em
`enderecos_sao_locais` (`app/config.py`).

Para recarregar os dados com tudo rodando no Docker:

```powershell
docker compose run --rm carga python scripts/carga_inicial.py
```

## Como entrar

Os 30 usuários de exemplo têm e-mail `primeiro-nome@exemplo.com`, sem acento, e todos usam
a mesma senha de demonstração, que está na variável `SENHA_DEMO` do `.env.example` (e,
portanto, do seu `.env`).

| Pessoa | E-mail | Por que é útil na demo |
|---|---|---|
| Ana Beatriz Lima | `ana@exemplo.com` | júnior, quer aprender Neo4j, Machine Learning e Kubernetes; começa com 3 notificações não lidas |
| Bruno Carvalho | `bruno@exemplo.com` | conexão da Ana; bom para a segunda aba do navegador |
| Marina Albuquerque | `marina@exemplo.com` | mentora sênior, com emprego anterior no histórico |
| Otávio Lucena | `otavio@exemplo.com` | estagiário, quer aprender React, Node.js e Docker |
| José Tavares | `jose@exemplo.com` | não tem nenhuma conexão (mostra o caso "não há caminho") |

Com `MODO_DEMO=1` (o padrão), a tela de entrada tem o bloco **"Modo demonstração"**: escolha
uma pessoa em **"Entrar como…"** e clique em **"Entrar como esta pessoa"**. Ele passa pelo
mesmo login do formulário, com a senha da demonstração. Contas criadas na aba **"Criar
conta"** têm senha própria e entram pelo formulário.

## Testes

```powershell
.venv\Scripts\python -m pytest -q
```

São 159 testes (`pytest`), todos contra os bancos do Docker: os três serviços, o orquestrador
(inclusive compensação e banco fora do ar), o disjuntor, a carga, o registro do painel
Bastidores e as três telas, abertas com o `AppTest` do Streamlit. Os bancos precisam estar no
ar (`docker compose up -d`).

> **Atenção:** os testes rodam sobre os mesmos bancos da demonstração e **recarregam os dados
> de exemplo** no começo e no fim. Tudo o que tiver sido criado pela aplicação (contas,
> posts, conexões, notificações) é apagado. A mesma trava da carga vale aqui: os testes se
> recusam a rodar se algum endereço não for local.

## Usar o Neo4j Aura em vez do container

O enunciado aceita Neo4j local ou no AuraDB. As quatro variáveis do item 3.1 ficam no `.env`:

```
NEO4J_URI=neo4j+s://<sua-instancia>.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<senha da instância>
NEO4J_DATABASE=neo4j
```

O Aura funciona **só no modo "Desenvolver"**: Streamlit rodando fora do Docker
(`streamlit run app/Inicio.py`), com o `.env` apontando para o Aura e o MongoDB e o Redis no
Docker. No modo "Subir tudo" ele não é suportado: o `docker-compose.yml` fixa
`NEO4J_URI=bolt://neo4j:7687` para os serviços `app` e `carga`.

A carga recusa endereços remotos: com o `.env` apontando para o Aura,
`python scripts/carga_inicial.py` para com uma mensagem e só continua com
`python scripts/carga_inicial.py --confirmar-remoto`. **Cuidado: com essa opção a carga APAGA
todos os dados daquela instância do Aura** (e também o MongoDB e o Redis locais) antes de
gravar os dados de exemplo. Os testes nunca rodam contra o Aura.

## Estrutura de pastas

```
docker-compose.yml        bancos + carga + app (+ perfil "ferramentas")
Dockerfile                imagem da aplicação (python:3.11-slim)
requirements.txt          versões fixadas
.env.example              modelo do .env (endereços, senhas, MODO_DEMO)
.streamlit/config.toml    tema e limite de upload (5 MB)
app/
  Inicio.py               ponto de entrada: login, barra lateral, navegação
  config.py               lê o .env; constantes (TTLs, limites) e a trava de endereço local
  estado.py               serviços e usuário logado de cada aba do navegador
  paginas/
    entrada.py              login, cadastro e "Entrar como…"
    feed_perfil.py          Tela 1 — Feed & Perfil
    presenca_notificacoes.py  Tela 2 — Presença & Notificações
    rede_mentores.py        Tela 3 — Rede & Mentores
  componentes/            bastidores.py (painel), cartoes.py, grafo.py (desenho com pyvis)
  servicos/
    mongo_service.py   redis_service.py   neo4j_service.py   um por banco
    orquestrador.py       ações que cruzam bancos e a regra de consistência
    registro.py           o que alimenta o painel Bastidores
    disjuntor.py          depois de uma falha de conexão, 10 s sem tentar de novo: a 1ª tela com o banco
                          parado ainda espera alguns segundos, as seguintes respondem na hora
    seguranca.py          hash de senha (PBKDF2)
    erros.py              BancoIndisponivel, ErroDeNegocio, EmailJaCadastrado
scripts/
  dados_exemplo.py        os dados fictícios, uma fonte só para os três bancos
  carga_mongo.py   carga_redis.py   carga_neo4j.py
  carga_inicial.py        roda as três (com a trava de banco remoto)
tests/                    pytest + AppTest
docs/
  design.md               o design aprovado
  guia_da_defesa.md       roteiro da demo, perguntas prováveis, consultas prontas
```

## Endereços

Todas as portas são publicadas só em `127.0.0.1`: ninguém de fora desta máquina acessa.

| O quê | Endereço | Observação |
|---|---|---|
| Aplicação | http://127.0.0.1:8501 | |
| Neo4j Browser | http://127.0.0.1:7474 | usuário `neo4j`, senha em `NEO4J_PASSWORD` do `.env`; conectar em `bolt://127.0.0.1:7687` |
| MongoDB | `mongodb://127.0.0.1:27017` | banco `conecta_talentos`, sem senha |
| Redis | `redis://127.0.0.1:6379/0` | sem senha |
| Mongo Express | http://127.0.0.1:8081 | só com o perfil `ferramentas` |
| Redis Insight | http://127.0.0.1:5540 | só com o perfil `ferramentas` |

**Ferramentas opcionais** para olhar os dados por fora durante a demonstração:

```powershell
docker compose --profile ferramentas up -d mongo-express redisinsight    # sobe as duas
docker compose --profile ferramentas stop mongo-express redisinsight     # para as duas
```

Dar o nome dos dois serviços evita mexer no resto: um `docker compose --profile ferramentas
up -d` sem nomes também funciona, mas roda a `carga` de novo (ela é ignorada) e reinicia o
`app`, o que desconecta quem estiver com a aplicação aberta.

O Mongo Express abre direto, sem tela de login, e mostra o banco `conecta_talentos`. O Redis
Insight pede, na primeira abertura, que você leia e aceite os termos de uso dele; a conexão
`conecta-talentos` (host `redis`, porta `6379`) já vem configurada pelo Compose. Se ela não
aparecer na lista, adicione um banco com host `redis` e porta `6379`.

## Limitações conhecidas

- **O nome não é editável.** Ele é copiado em posts, comentários, notificações, sessão e no
  grafo; o título é editável e serve de exemplo de propagação de dado duplicado.
- **A senha do Neo4j não pode ter espaço, aspas nem `$`**, porque ela é inserida no
  comando de healthcheck do `docker-compose.yml`. Além disso, o Neo4j só grava a senha na
  primeira vez que o volume é criado: depois de trocar `NEO4J_PASSWORD`, é preciso
  `docker compose down -v` (que apaga os dados) para a senha nova valer.
- **Recarregar a página do navegador (F5) desconecta.** O token da sessão fica só na sessão
  do Streamlit daquela aba; a sessão no Redis continua até expirar (30 minutos sem uso) e
  pode ser encerrada pela tela de Presença.
- **Projeto didático.** Não foi preparado para produção: sem HTTPS, sem recuperação de senha,
  bancos sem autenticação (MongoDB e Redis) e portas abertas só para esta máquina.

## Atendimento ao enunciado

O resumo do enunciado está no Anexo A de `docs/design.md`. Onde cada item é atendido:

| Item do enunciado | Onde está no projeto |
|---|---|
| **Tecnologias:** MongoDB, Redis, Neo4j, Python e Streamlit; o Streamlit conecta-se diretamente aos três bancos | `app/Inicio.py` + `app/servicos/` (drivers oficiais `pymongo`, `redis`, `neo4j`; versões em `requirements.txt`) |
| **Entrega:** código organizado e comentado, com `requirements.txt` ou Docker Compose | `requirements.txt`, `docker-compose.yml`, `Dockerfile`; estrutura em três camadas (páginas → orquestrador → serviços), comentários em português |
| **Entrega:** scripts de carga e inicialização (schemas/coleções, índices, carga nos três bancos) | `scripts/carga_inicial.py` (+ `carga_mongo.py`, `carga_redis.py`, `carga_neo4j.py`); esquema em `MongoService.criar_esquema` e `Neo4jService.criar_esquema`; roda sozinho no serviço `carga` do Compose |
| **Entrega:** defesa oral, todos aptos a responder | `docs/guia_da_defesa.md` (roteiro de 5 minutos, perguntas e respostas, consultas prontas) |
| **Item 3.1:** variáveis `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE` | `.env.example` e `app/config.py`; seção "Usar o Neo4j Aura" acima |
| **Item 3.2:** classe de serviço com driver no construtor, `close()`, um método por consulta, Cypher com `$parâmetros`, `session.run`, retorno em listas | `app/servicos/neo4j_service.py` (`Neo4jService`); `MongoService` e `RedisService` seguem o mesmo formato |
| **MongoDB:** perfil estendido (experiências, formação, certificações) | coleção `usuarios` (`MongoService`); tela Feed & Perfil → abas "👤 Perfil" e "✏️ Editar meu perfil" |
| **MongoDB:** posts da linha do tempo | coleção `posts` com curtidas e comentários embutidos; tela Feed & Perfil → aba "📰 Feed" |
| **MongoDB:** anexos multimídia | GridFS (`MongoService.salvar_anexo` / `ler_anexo`); campo "Anexo" ao publicar; 3 imagens nos dados de exemplo |
| **Redis:** presença online/offline | ZSET `presenca:online` + HASH `presenca:visto` (`RedisService`); tela Presença & Notificações |
| **Redis:** sessões ativas | HASH `sessao:{token}` com TTL + SET `usuario:{id}:sessoes`; bloco "🔑 Minhas sessões" (com tempo restante e "Encerrar") |
| **Redis:** contador em tempo real de notificações não lidas | STRING `notif:nao_lidas:{id}` (`INCR`); sininho da barra lateral e indicador "Notificações não lidas" |
| **Neo4j:** rede de conexões `(:Pessoa)-[:CONECTADO_COM]->(:Pessoa)` | `Neo4jService.conectar`, `ids_conexoes`; botão "Conectar"; aba "🕸️ Minha rede" |
| **Neo4j:** mapa de habilidades `(:Pessoa)-[:POSSUI_HABILIDADE]->(:Habilidade)` | `definir_habilidade`, `habilidades_de`; "Editar meu perfil" → "Minhas habilidades" |
| **Neo4j:** histórico profissional `(:Pessoa)-[:TRABALHA_EM]->(:Empresa)` | `registrar_trabalho`, `trabalhos_de`, `colegas_de_empresa`; experiências no perfil e bloco "Empresas (grafo)" da aba "👤 Perfil" |
| **Neo4j:** consultas de menor caminho (`shortestPath`) | `Neo4jService.menor_caminho` e `recomendar_mentores`; aba "🧭 Graus de separação" |
| **Tela 1:** Feed & Perfil, alimentados pelo MongoDB | `app/paginas/feed_perfil.py` |
| **Tela 2:** Dashboard de Presença & Notificações, em tempo real com Redis | `app/paginas/presenca_notificacoes.py` (atualiza sozinho a cada 5 s com `st.fragment`) |
| **Tela 3:** Rede de Conexões & Busca de Mentores, gráfico ou lista de graus de separação e recomendação de mentores | `app/paginas/rede_mentores.py` (grafo desenhado com o caminho destacado, lista por grau, mentores com o porquê) |
| **Demonstração:** fluxo completo mostrando as chamadas nos três bancos | painel "🔎 Bastidores" em todas as telas; roteiro em `docs/guia_da_defesa.md` ("Publicar post" e "Conectar" tocam os três bancos) |
| **Avaliação — integração arquitetural (25%)** | `app/servicos/orquestrador.py` (uma ação por método, regra de consistência com compensação); tabela "Por que este dado está neste banco" no guia |
| **Avaliação — modelagem e Cypher (20%)** | modelo em `docs/design.md` (seção 6); `$jsonSchema` e índices em `mongo_service.py`; chaves em `redis_service.py`; Cypher em `neo4j_service.py` |
| **Avaliação — aplicação Streamlit e Python (25%)** | as três telas, cadastro e login, banco fora do ar vira aviso na tela (`BancoIndisponivel` em `app/estado.py` e nas páginas), 159 testes em `tests/` |
| **Avaliação — defesa oral (30%)** | `docs/guia_da_defesa.md` |
