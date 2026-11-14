# Guia da defesa — Conecta Talentos

Material de apoio para a apresentação (até 10 minutos) e para a arguição. A defesa oral vale
30% da nota e as perguntas são individuais, sobre o código, o Cypher, a estratégia de cache e
as consultas NoSQL. Cada resposta abaixo diz **onde a coisa está no código**, para quem
responder poder abrir o arquivo e mostrar.

Sumário:

1. [Antes de começar](#1-antes-de-começar)
2. [Roteiro da demonstração (~5 min)](#2-roteiro-da-demonstração-5-min)
3. [Por que este dado está neste banco](#3-por-que-este-dado-está-neste-banco)
4. [Perguntas prováveis e respostas](#4-perguntas-prováveis-e-respostas)
5. [Consultas prontas para a arguição](#5-consultas-prontas-para-a-arguição)
6. [Se algo der errado na hora](#6-se-algo-der-errado-na-hora)

---

## 1. Antes de começar

Uns cinco minutos antes da apresentação:

1. Suba tudo e confira que está saudável:
   ```powershell
   docker compose up -d --build
   docker compose ps -a
   ```
   Os três bancos `(healthy)`, `carga` em `Exited (0)` e `app` em `Up … (healthy)`.
2. Deixe os dados limpos (apaga o que foi criado em ensaios e recarrega os exemplos):
   ```powershell
   docker compose run --rm carga python scripts/carga_inicial.py
   ```
   A saída termina com `neo4j: 30 pessoas, 25 habilidades, 12 empresas, 53 conexoes, 33 trabalhos`.
3. Abra **duas abas** do navegador em http://127.0.0.1:8501. A **aba A** será a Ana Beatriz
   Lima; a **aba B**, o Bruno Carvalho (conexão direta da Ana). Cada aba tem sua própria
   sessão e seu próprio painel Bastidores.

**Como ler o painel Bastidores.** Ele fica no fim de cada tela, num bloco recolhível chamado
**"🔎 Bastidores — o que cada banco fez"**. Cada grupo é uma ação (Login, Publicar post,
Conectar…), com a hora, e dentro dele uma linha por comando: o banco (etiqueta verde MongoDB,
vermelha Redis, azul Neo4j), o comando e o tempo em milissegundos. A ação mais recente vem
primeiro.

Por padrão o painel **esconde as leituras que só desenham a tela** (montar o feed, abrir um
perfil, calcular as tags em alta), para a última ação do usuário não ficar soterrada. Para
mostrar o cache funcionando, marque a caixa **"mostrar também as leituras da tela"**: as
leituras aparecem com a etiqueta `leitura`. O botão **"limpar"** esvazia o painel. As
atualizações automáticas (o sininho a cada 10 s e o painel de presença a cada 5 s) nunca
aparecem no Bastidores, de propósito.

## 2. Roteiro da demonstração (~5 min)

Os tempos são aproximados. "Falar" é uma sugestão de uma ou duas frases.

> **Não aperte F5 durante a demonstração.** Recarregar a página desconecta quem está
> apresentando: o token vive só na sessão do Streamlit daquela aba. A sessão antiga continua no
> Redis por até 30 minutos, então, depois de entrar de novo, "Minhas sessões ativas" mostraria 2;
> e, depois de "Sair", a pessoa ainda pode aparecer online por até 90 s (como a sessão antiga
> continua existindo, "Sair" não a tira do ZSET de presença; o último sinal vence pela janela).

### Passo 1 — Login da Ana (aba A, ~40 s)

- **Clicar:** na tela de entrada, bloco **"Modo demonstração"** → **"Entrar como…"** →
  *Ana Beatriz Lima — Analista de Dados Júnior* → **"Entrar como esta pessoa"**.
- **Aparece:** na barra lateral, **👤 Ana Beatriz Lima**, **🔔 3 não lidas** e os três bancos
  com 🟢 *conectado*.
- **Falar:** "O login confere o hash da senha no MongoDB e cria a sessão no Redis, com prazo de
  30 minutos, num único pipeline transacional; o Streamlit guarda só o token."
- **Bastidores — Login:** MongoDB `usuarios.find_one` · MongoDB `usuarios.find_one (por e-mail)` ·
  Redis `HSET + EXPIRE + SADD + ZADD + HSET (login)`. Dois bancos: MongoDB e Redis.

### Passo 2 — Feed e o cache das tags (aba A, ~50 s)

- **Clicar:** a tela abre em **📰 Feed & Perfil**, aba **"📰 Feed"**. No Bastidores, marque
  **"mostrar também as leituras da tela"**.
- **Aparece:** os posts da Ana e das conexões dela (Bruno, Camila, Eduarda); o post da Camila
  tem a imagem *comparativo_modelos.png*. Na coluna **"🔥 Tags em alta"**, logo depois do
  login, a legenda diz **"cache MISS: calculada agora no MongoDB e guardada no Redis por
  60 s"**; depois do clique na caixa (que redesenha a tela) ela passa a dizer **"cache HIT:
  lista lida do Redis"**. Se passar mais de 60 s entre o login e o clique, aparece MISS de
  novo: é o TTL vencendo, e o próximo clique já dá HIT.
- **Falar:** "O feed cruza os três bancos: o Neo4j diz quem são minhas conexões, o MongoDB traz
  os posts delas e o Redis dá a bolinha verde de quem está online. As tags em alta são uma
  agregação do Mongo guardada 60 s no Redis: é o cache-aside."
- **Bastidores (leituras):** grupo **Tags em alta** `leitura` com só Redis
  `GET cache:tags_em_alta` (é o HIT; no MISS apareceriam também MongoDB
  `posts.aggregate (tags em alta)` e Redis `SET cache:tags_em_alta EX 60`). Grupo **Montar
  feed** `leitura`: Neo4j `MATCH (:Pessoa {id: $id})-[:CONECTADO_COM]-(outra:Pessoa) RETURN outra.id AS id ORDER BY outra.nome` ·
  MongoDB `posts.find (feed)` · Redis `ZSCORE + HGET (presença de vários)`. Três bancos.

### Passo 3 — Perfil e o cache do perfil (aba A, ~30 s)

- **Clicar:** aba **"👤 Perfil"** → **"Ver perfil de"** → *Camila Nóbrega*. Depois troque para
  *Ana Beatriz Lima (você)* e volte para *Camila Nóbrega*.
- **Aparece:** na primeira vez, a legenda embaixo das certificações diz **"perfil: MongoDB (lido
  agora) · presença: Redis"**; na volta, **"perfil: MongoDB (do cache Redis) · presença:
  Redis"**. À direita, as habilidades (Machine Learning e Python nível 5, SQL nível 4), o bloco
  **Empresas (grafo)** (*Mangue Labs · Inteligência Artificial · Cientista de Dados Sênior · desde
  2022-04*, com a legenda *TRABALHA_EM: Neo4j*), o selo **Mentor · 9 anos de experiência** e
  **Conexões 4**, que vêm do grafo.
- **Falar:** "O documento do perfil vem do MongoDB e fica 5 minutos no Redis; habilidades,
  empresas e número de conexões vêm sempre ao vivo do Neo4j."
- **Bastidores (leituras) — Abrir perfil:** no MISS, Redis `GET cache:perfil:u003` · MongoDB
  `usuarios.find_one` · Redis `SET cache:perfil:u003 EX 300` · quatro consultas Neo4j, cada uma
  numa linha com o Cypher inteiro (começam por `MATCH (:Pessoa {id: $id})-[ph:POSSUI_HABILIDADE]->…`,
  `…-[:QUER_APRENDER]->…`, `…-[t:TRABALHA_EM]->…` e `…-[:CONECTADO_COM]-…`) · Redis
  `ZSCORE presenca:online`. No HIT, o MongoDB some: só Redis, Neo4j e Redis.
- Desmarque **"mostrar também as leituras da tela"** antes do próximo passo.

### Passo 4 — Bruno publica; a Ana vê chegar (abas A e B, ~60 s)

- **Clicar (aba A):** **🟢 Presença & Notificações**. Aparecem **Online agora 1**,
  **Notificações não lidas 3** e **Minhas sessões ativas 1**.
- **Clicar (aba B):** **"Entrar como…"** → *Bruno Carvalho — Engenheiro de Dados Pleno* →
  **"Entrar como esta pessoa"**. No campo **"Publicar"**, escreva um texto (por exemplo
  "Hoje apresentamos persistência poliglota com MongoDB, Redis e Neo4j."), em **"Tags
  (separadas por vírgula)"** escreva `nosql, dados` e clique **"📤 Publicar"**. Se quiser
  mostrar o GridFS, anexe uma imagem PNG/JPG pequena em **"Anexo (imagem PNG/JPG ou PDF, até
  5 MB)"**.
- **Aparece (aba B):** o aviso **"Post publicado. 3 conexões foram notificadas."** (Ana, Camila
  e Diego).
- **Bastidores (aba B) — Publicar post:** MongoDB `usuarios.find_one` · (MongoDB `GridFS.put`,
  se houver anexo) · MongoDB `posts.insert_one` · Redis `DEL cache:tags_em_alta` · Neo4j
  `MATCH (:Pessoa {id: $id})-[:CONECTADO_COM]-(outra:Pessoa) RETURN outra.id AS id ORDER BY outra.nome` · MongoDB
  `notificacoes.insert_many` · Redis `INCR + LPUSH + LTRIM x3 (notificar vários)`. **Os três
  bancos numa ação só.**
- **Aparece (aba A, sem clicar em nada, em até 5–10 s):** **Online agora 2**, o Bruno na coluna
  **🟢 Online**, **Notificações não lidas 4**, a aba **"Recentes · Redis (4)"** com *Bruno
  Carvalho publicou um post novo.* no topo, e o sininho da barra lateral em **🔔 4 não lidas**.
- **Falar:** "O post é durável, então vai para o MongoDB; quem notificar é pergunta de rede, então
  vem do Neo4j; o contador e a lista curta são estado quente no Redis, e é por isso que a tela
  da Ana muda sozinha." Essas atualizações automáticas não aparecem no Bastidores.

### Passo 5 — Marcar como lidas (aba A, ~20 s)

- **Clicar:** **"✔️ Marcar todas como lidas"**.
- **Aparece:** **"Notificações marcadas como lidas."**, o indicador vai a 0 e o sininho a
  **🔔 0 não lidas**. Mostre também **"🔑 Minhas sessões"**: *Esta sessão · Iniciada às … ·
  expira em 30 min*.
- **Falar:** "O contador vive no Redis e o histórico no MongoDB; marcar como lidas atualiza os
  dois. A sessão é uma chave com TTL que renova a cada interação."
- **Bastidores — Marcar notificações como lidas:** MongoDB
  `notificacoes.update_many ($set lida)` · Redis `SET notif:nao_lidas 0`. MongoDB e Redis.

### Passo 6 — Graus de separação (aba A, ~45 s)

- **Clicar:** **🕸️ Rede & Mentores** → aba **"🧭 Graus de separação"** → **"Pessoa"** →
  *Sabrina Leite*. Depois escolha *José Tavares*.
- **Aparece:** **"Você → Camila → Kleber → Patrícia → Sabrina: 4 graus"**, o grafo com o caminho
  em laranja e a lista numerada. Para o José: **"Não há caminho entre vocês em até 6
  conexões."**
- **Falar:** "É um `shortestPath` com no máximo 6 saltos, sem direção. Em grafo, andar para o
  vizinho custa o mesmo, seja a base pequena ou grande: é a index-free adjacency."
- **Bastidores (leituras):** o caminho em si é calculado só pelo Neo4j, numa única consulta,
  que fica num grupo próprio **Graus de separação** `leitura`: Neo4j
  `MATCH (a:Pessoa {id: $origem}), (b:Pessoa {id: $destino}) MATCH caminho = shortestPath((a)-[:CONECTADO_COM*..…`
  (passe o mouse sobre a linha para ver o Cypher inteiro). Por ser leitura, só aparece com a
  caixa **"mostrar também as leituras da tela"** marcada. A tela não é só Neo4j: a lista de nomes
  do campo "Pessoa" vem do MongoDB (`MongoDB usuarios.find (nome, título)`); essa leitura e as das
  outras abas (minha rede, mentores, sugestões), que o Streamlit desenha a cada clique, ficam nos
  grupos **Leitura da tela**, antes e depois do grupo do caminho.

### Passo 7 — Mentores e Conectar (aba A, ~50 s)

- **Clicar:** aba **"🎓 Buscar mentores"**. Em **"O que você quer aprender?"** já estão os
  interesses salvos da Ana (Kubernetes, Machine Learning, Neo4j). No cartão do **Diego
  Farias**, clique **"🤝 Conectar"**.
- **Aparece antes do clique:** *Camila Nóbrega* com **Pontuação 9,0** — "Domina Machine
  Learning (nível 5). Já é sua conexão direta. 2 conexões em comum." — e *Diego Farias* com
  **Pontuação 8,0** — "Domina Neo4j (nível 5). Está a 2 graus de você, via Bruno [ou
  Eduarda]. 2 conexões em comum." — via Bruno ou Eduarda: há dois caminhos de 2 graus até o
  Diego e o `shortestPath` devolve um deles (pergunta 26). Depois vêm Marina (6,0), Felipe (4,0), Wagner (4,0) e Débora (3,0).
- **Aparece depois do clique:** **"Agora você e Diego estão conectados."** O Diego sobe para
  9,0 (agora está a 1 grau), fica logo depois da Camila (empate desfeito pelo nome) e o botão
  "Conectar" some do cartão dele.
- **Falar:** "A pontuação é 3 por habilidade que a pessoa ensina, mais o nível médio, mais as
  conexões em comum, menos a distância na rede. Conectar grava a aresta no Neo4j e notifica o
  Diego no MongoDB e no Redis."
- **Bastidores — Conectar:** Neo4j `MATCH (p:Pessoa {id: $id}) RETURN p.id AS id, p.nome AS nome, …`
  (duas vezes: confere que as duas pessoas existem) · Neo4j
  `MATCH (a:Pessoa {id: $a}), (b:Pessoa {id: $b}) WHERE NOT (a)-[:CONECTADO_COM]-(b) CREATE (a)-[:CONECTADO_COM …`
  (cria a conexão) ·
  MongoDB `notificacoes.insert_many` · Redis `INCR + LPUSH + LTRIM x1 (notificar vários)`.
  **Os três bancos.**
- Opcional, se sobrar tempo: **"🎓 Pedir mentoria"** no cartão da Camila → "Pedido de
  mentoria enviado para Camila." (Bastidores **Pedir mentoria**: Neo4j ×2, MongoDB, Redis.)

### Passo 8 — Sair (aba A, ~10 s)

- **Clicar:** **"Sair"** na barra lateral. A aba A volta para a tela de entrada.
- **Falar:** "Sair apaga a sessão no Redis e, como era a única sessão da Ana, tira ela do ZSET de
  presença." Na aba B, em **🟢 Presença & Notificações**, a Ana aparece em **⚪ Offline** com
  *visto por último agora*.

Recapitulando para a banca: **Publicar post** e **Conectar** mostraram os três bancos numa
única ação do usuário; Login e Marcar como lidas mostraram MongoDB + Redis; em Graus de
separação, o caminho foi calculado pelo Neo4j numa só consulta `shortestPath`.

## 3. Por que este dado está neste banco

| Dado | Banco e estrutura | Por que ali |
|---|---|---|
| Perfil (experiências, formação, certificações, resumo, localização) | MongoDB, coleção `usuarios` | forma variável por pessoa, lido inteiro de uma vez; documento resolve sem JOIN nem migração |
| E-mail e hash da senha | MongoDB, `usuarios` (índice único em `email`) | é a fonte da verdade de quem existe; precisa durar |
| Posts, curtidas e comentários | MongoDB, `posts` (curtidas e comentários embutidos) | pertencem ao post e são lidos junto com ele |
| Imagens e PDFs anexados | MongoDB, GridFS (`fs.files` + `fs.chunks`) | arquivo binário fora do documento do post; o post guarda só a referência |
| Histórico de notificações | MongoDB, `notificacoes` (TTL de 30 dias) | registro durável; o próprio Mongo apaga as antigas |
| Sessão | Redis, HASH `sessao:{token}` com TTL de 30 min + SET `usuario:{id}:sessoes` | dado temporário, lido a cada clique, que deve sumir sozinho |
| Presença online | Redis, ZSET `presenca:online` (score = horário do último sinal) + HASH `presenca:visto` | muda a cada poucos segundos; o painel pergunta "quem mandou sinal nos últimos 90 s" numa consulta por faixa de score e, na mesma leitura, apaga por score quem passou da janela |
| Contador de não lidas | Redis, STRING `notif:nao_lidas:{id}` (`INCR`) | contador atômico, lido a cada 10 s pelo sininho |
| Últimas 20 notificações | Redis, LIST `notif:recentes:{id}` (`LPUSH` + `LTRIM`) | lista curta e de tamanho fixo para abrir na hora |
| Cache do perfil e das tags em alta | Redis, STRING com JSON (`EX 300` e `EX 60`) | evita repetir leitura e agregação no Mongo; pode ser perdido sem prejuízo |
| Conexões entre pessoas | Neo4j, `(:Pessoa)-[:CONECTADO_COM {desde}]->(:Pessoa)` | as perguntas são sobre caminhos e vizinhanças |
| Habilidades e nível | Neo4j, `(:Pessoa)-[:POSSUI_HABILIDADE {nivel}]->(:Habilidade)` | o nível é de cada pessoa, então mora no relacionamento; a recomendação cruza habilidade com rede |
| O que a pessoa quer aprender | Neo4j, `(:Pessoa)-[:QUER_APRENDER]->(:Habilidade)` | é o critério da busca de mentores (extensão nossa ao enunciado) |
| Histórico profissional | Neo4j, `(:Pessoa)-[:TRABALHA_EM {cargo, desde, ate}]->(:Empresa)` + a experiência completa no Mongo | no grafo serve para "colegas de empresa"; no Mongo fica a descrição rica |
| Disponibilidade para mentoria e anos de experiência | Neo4j, propriedades `mentor` e `anos_experiencia` de `:Pessoa` | só a recomendação usa |
| Nome e título | Mongo (fonte) com cópias em `:Pessoa` e em `posts.autor` | o grafo e o feed se desenham sem ir a outro banco |

## 4. Perguntas prováveis e respostas

### Arquitetura e consistência

**1. Por que três bancos e não um só?**
Cada dado tem um padrão de acesso diferente: perfis e posts são documentos lidos inteiros
(MongoDB), sessão, presença e contadores são estado quente e descartável (Redis), e rede e
recomendação são perguntas de caminho (Neo4j). Isso é persistência poliglota. A tabela da
seção 3 dá o motivo de cada dado, e o `app/servicos/orquestrador.py` é onde se vê, método a
método, qual banco é usado em cada ação.

**2. Como o código está organizado?**
Em três camadas: as páginas (`app/paginas/`) só desenham e não importam driver nenhum; o
`Orquestrador` (`app/servicos/orquestrador.py`) tem um método por ação que cruza bancos
(`fazer_login`, `publicar_post`, `conectar`…); e há uma classe por banco
(`MongoService`, `RedisService`, `Neo4jService`), cada uma só com o seu driver. O que liga os
três bancos é o id do usuário (`u001`): `_id` no Mongo, `id` do nó `:Pessoa` e sufixo das
chaves do Redis.

**3. Não existe transação entre os três bancos. Como vocês mantêm tudo consistente?**
A regra tem duas partes, escrita no topo do `orquestrador.py`. Primeira: dado que existe em
dois bancos tem de ficar igual nos dois; grava-se primeiro no MongoDB (fonte da verdade) e, se
o Neo4j falhar, a gravação do Mongo é desfeita (compensação) e a ação é recusada. Segunda:
efeito colateral (notificação, contador, presença, cache) nunca desfaz a ação principal; se
falhar, a ação vale e a tela mostra um aviso (método `_notificar`).

**4. Mostre a compensação no cadastro.**
Em `Orquestrador.cadastrar_usuario`: o perfil é inserido no Mongo (`inserir_usuario`) e depois o
nó é criado no Neo4j (`criar_pessoa`); se o Neo4j levantar qualquer exceção, o `except` chama
`mongo.remover_usuario(novo_id)` e relança o erro, e a tela mostra a mensagem. E-mail repetido
para antes de tocar o Neo4j (`EmailJaCadastrado`, vindo do índice único), então nunca sobra nó
órfão. O teste é `test_cadastro_desfaz_mongo_se_neo4j_falhar`.

**5. E na edição de experiência?**
Uma experiência é identificada nos dois bancos por **empresa + cargo + início**
(`_chave_experiencia`); no grafo é a chave do `MERGE (p)-[:TRABALHA_EM {cargo, desde}]->(e:Empresa
{nome})`. Ao adicionar (`adicionar_experiencia`): `$push` no Mongo, depois `registrar_trabalho`; se
o Neo4j falhar, `$pull` desfaz. Ao remover (`remover_experiencia`): acha o item guardado pela
chave, faz `$pull` dele exatamente como está no Mongo, depois `remover_trabalho`; se o Neo4j
falhar, o item volta ao Mongo com `$push`. Repetir a mesma chave é recusado antes de gravar,
porque o grafo juntaria as duas num relacionamento só.

**6. O que acontece se cada banco cair?**
- **MongoDB:** a tela de entrada mostra "MongoDB fora do ar" e não deixa entrar (é onde estão
  as senhas). Quem já estava logado continua (a sessão está no Redis), mas as partes que leem o
  Mongo mostram "MongoDB está fora do ar. Tente novamente em instantes."
- **Redis:** não há login, porque a sessão mora lá; quem estava logado volta para a tela de
  entrada, que explica que a sessão está guardada no Redis, fora do ar, e que basta clicar em
  "Tentar de novo" quando ele voltar (o token fica guardado na aba e a pessoa continua de onde
  parou). O cache indisponível conta como MISS e a leitura vai direto ao Mongo.
- **Neo4j:** o login funciona com um aviso; o feed mostra só os meus posts; o perfil aparece sem
  o bloco do grafo (habilidades, "Empresas (grafo)" e interesses); publicar salva o post sem notificar; a tela Rede & Mentores mostra "A
  rede de conexões está indisponível no momento (Neo4j fora do ar)."; o cadastro é recusado
  (compensação). A barra lateral mostra o banco com 🔴. Isso vem de `BancoIndisponivel`, que o
  `Registro.medir` (`app/servicos/registro.py`) levanta quando o driver não conecta (no Neo4j,
  também quando o banco responde que está subindo ou parando, o `TransientError`).

Para a tela não travar esperando o timeout em cada consulta, cada serviço tem um **disjuntor**
(`app/servicos/disjuntor.py`, chamado em `_op` do Mongo e do Redis e em `_executar` do Neo4j):
depois de uma falha de conexão, o serviço passa 10 s (`PAUSA_APOS_FALHA_SEGUNDOS`, em
`config.py`) respondendo "fora do ar" na hora, sem tocar o driver. Passada a pausa, a próxima
chamada tenta o banco de verdade; por isso a primeira tela com o banco parado leva alguns
segundos e as seguintes respondem logo, e a aplicação volta sozinha quando o banco volta.

### MongoDB

**7. Por que comentários e curtidas ficam embutidos no post, e o autor não?**
Comentários e curtidas pertencem ao post e são sempre lidos junto com ele, então embutir evita
uma segunda consulta (`$push` em `comentar`, `$addToSet`/`$pull` em `curtir`, em
`mongo_service.py`). O autor é uma entidade própria, então o post guarda a referência
`autor_id` e, além dela, uma **cópia pequena** `autor: {nome, titulo}` (padrão *extended
reference*). Assim o feed se desenha sem buscar o perfil de cada autor.

**8. E se o título do autor mudar? A cópia fica velha?**
Não: `Orquestrador.editar_dados_basicos` atualiza o Mongo, depois `:Pessoa.titulo` no Neo4j
(com compensação) e, por fim, todas as cópias com `MongoService.atualizar_titulo_nos_posts`
(`update_many` com `$set` em `autor.titulo`), além de apagar o cache do perfil. É o custo de
duplicar dado. O **nome** não é editável justamente para não ter de propagar para posts,
comentários, notificações, sessão e grafo.

**9. O que o `$jsonSchema` valida?**
Em `MongoService.criar_esquema`: a coleção `usuarios` exige `nome`, `email` e `titulo`, todos
`string`; `posts` exige `autor_id`, `texto` e `criado_em`. O resto é livre: é "esquema flexível
com garantias mínimas". Se a coleção já existe, o validador é reaplicado com `collMod`. Um
`insertOne` sem e-mail é recusado com *Document failed validation* (consulta M3 da seção 5).

**10. Quais índices existem e para quê?**
`usuarios.email` único: o login busca por e-mail e o banco impede e-mail repetido.
`posts {autor_id: 1, criado_em: -1}`: o feed busca os posts de uma lista de autores do mais novo
para o mais velho. Com **um** autor, o `explain` mostra `FETCH` sobre `IXSCAN` nesse índice e a
ordem já sai do índice (consulta M5). No feed de verdade (`$in` com vários autores, ordenado por
`criado_em` e `_id`) o plano é `SORT` sobre `FETCH` sobre `IXSCAN` no mesmo índice: o índice
acha os posts, mas a ordenação final é feita em memória (consulta M7). `posts {criado_em: -1}` e
`posts {tags: 1}` (índice multikey, para filtrar por tag). `notificacoes {usuario_id: 1,
criado_em: -1}` para listar as notificações de uma pessoa. Todos em `criar_esquema`.

**11. Como funciona o índice TTL?**
É um índice simples em `notificacoes.criado_em` com `expireAfterSeconds: 2592000` (30 dias,
`TTL_NOTIFICACOES_SEGUNDOS` em `mongo_service.py`). Um processo do próprio MongoDB passa
periodicamente (por volta de uma vez por minuto) e apaga os documentos cujo `criado_em` tem
mais de 30 dias. A aplicação não precisa de rotina de limpeza.

**12. O que é o GridFS e por que usar?**
É a forma do MongoDB guardar arquivos: o arquivo é cortado em pedaços (por padrão de 255 KB) na
coleção `fs.chunks`, e os metadados (nome, tipo, tamanho) ficam em `fs.files`. O post guarda só
a referência `{arquivo_id, nome, tipo, tamanho}`, então continua pequeno e longe do limite de
16 MB por documento. Está em `MongoService.salvar_anexo` / `ler_anexo`; antes de gravar, o
orquestrador aceita só PNG, JPEG e PDF até 5 MB e confere os bytes (`_conteudo_confere`).

**13. Como são as "tags em alta"?**
Uma agregação em `MongoService.tags_em_alta`: `$unwind` abre o array `tags` (um documento por
tag), `$group` conta por tag, `$sort` ordena pelo total e `$limit` fica com 8. Com os dados de
exemplo, o topo é `carreira` (19), `dados` (11), `devops` (9) e `web` (9). O resultado fica 60 s
no cache do Redis (pergunta 18).

### Redis

**14. Quais tipos do Redis vocês usam, e por quê?**
- **HASH** `sessao:{token}` (`usuario_id`, `nome`, `login_em`, `ultimo_acesso`): vários campos
  de um objeto, lidos de uma vez (`HGETALL`) e atualizados um a um. `presenca:visto` também é
  HASH (id → último horário visto).
- **SET** `usuario:{id}:sessoes`: os tokens de uma pessoa, sem repetição; serve para listar e
  encerrar sessões e saber se a última foi fechada (`SCARD` = 0 → offline).
- **ZSET** `presenca:online`: id com score = horário do último sinal (pergunta 17).
- **STRING** `notif:nao_lidas:{id}`: contador com `INCR` atômico; e `cache:*`, com o JSON e prazo.
- **LIST** `notif:recentes:{id}`: `LPUSH` + `LTRIM 0 19` mantém só as últimas 20.
Tudo em `app/servicos/redis_service.py`.

**15. Como funciona o TTL da sessão? É renovado?**
`criar_sessao` grava o HASH e dá `EXPIRE` de 1800 s (`SESSAO_TTL_SEGUNDOS`, em `config.py`). A
cada interação, `validar_sessao` atualiza `ultimo_acesso` e dá `EXPIRE` de novo: é expiração
deslizante, a sessão só vence depois de 30 minutos sem uso. Quando vence, o Redis apaga a chave
sozinho e a tela mostra "Sua sessão expirou. Entre novamente." O bloco "🔑 Minhas sessões" mostra
o TTL que falta (comando `TTL`).

**16. O que é o pipeline? E o MULTI/EXEC?**
Pipeline manda vários comandos numa ida só ao servidor, em vez de uma ida por comando. Com
`transaction=True`, o redis-py envolve os comandos em `MULTI`/`EXEC`: eles rodam em sequência,
sem comando de outro cliente no meio, e se a conexão cair antes do `EXEC` nenhum deles roda.
Atenção: o Redis **não tem rollback**; se um comando falhar durante o `EXEC` (por exemplo, por
tipo errado de chave), os outros continuam valendo. O login usa assim
(`criar_sessao`: `HSET` + `EXPIRE` + `SADD` + `ZADD` + `HSET`), e também `notificar_varios`. Em
`presenca_de` o pipeline é `transaction=False`: só para juntar as perguntas de vários usuários
numa ida.

**17. Por que a presença é um ZSET com horário, e não uma chave por usuário com TTL?**
O score é o horário do último sinal (`time.time()`), então "quem está online" é uma faixa de
score: quem mandou sinal nos últimos 90 s (`PRESENCA_JANELA_SEGUNDOS`). O painel de presença
(`Orquestrador.painel_presenca`) chama `RedisService.usuarios_online`, que primeiro apaga do
ZSET, por score, quem passou da janela (`ZREMRANGEBYSCORE`: limpeza preguiçosa, feita na hora
da leitura) e depois lista o resto numa consulta por faixa (`ZREVRANGEBYSCORE`); "Online agora"
é o tamanho dessa lista. Com uma chave por usuário com TTL, saber quem está online exigiria
varrer as chaves (`SCAN`). Para "esta pessoa específica está online?" (a bolinha de cada autor
no feed, `presenca_de`) usamos consulta pontual, `ZSCORE` em pipeline comparado com "agora −
90 s". O sinal é renovado a cada 10 s pelo sininho (`st.fragment` em `app/Inicio.py`); fechou a
aba, o sinal para e em 90 s a pessoa aparece offline. O painel se atualiza em modo pausado, então
esses comandos não aparecem no Bastidores: mostre-os no `redis-cli` (consulta R3).

**18. O que é cache-aside, e o que significam HIT e MISS?**
A aplicação procura primeiro no cache; se achar (**HIT**), usa e pronto; se não achar
(**MISS**), lê da fonte (MongoDB), grava no Redis com prazo e devolve. Está em
`Orquestrador.abrir_perfil` (`cache:perfil:{id}`, 300 s) e `Orquestrador.tags_em_alta`
(`cache:tags_em_alta`, 60 s). A tela mostra qual foi ("lido agora" / "do cache Redis", "cache
MISS" / "cache HIT"). Redis fora do ar ou JSON estragado no cache contam como MISS.

**19. Como o cache é invalidado?**
Apagando a chave quando a fonte muda: editar título, resumo, experiência, formação ou
certificação faz `DEL cache:perfil:{id}`; publicar um post faz `DEL cache:tags_em_alta`
(método `_apagar_cache`). O TTL é a rede de segurança: se o `DEL` falhar, a entrada velha vence
sozinha em no máximo 5 minutos ou 60 s. Conectar não apaga nada porque o cache guarda só o
documento do Mongo; o número de conexões vem sempre ao vivo do Neo4j.

### Neo4j

**20. O que é index-free adjacency?**
No Neo4j cada nó guarda referências diretas aos seus relacionamentos. Ir de uma pessoa para os
vizinhos é seguir essas referências, sem procurar num índice global; o custo depende de quantos
vizinhos se visita, não do tamanho total da base. Por isso "amigos de amigos" e caminhos de
vários saltos são baratos no grafo, enquanto no documento ou na tabela seriam buscas ou JOINs
encadeados.

**21. Como funciona o `shortestPath` e por que o limite de 6?**
Em `Neo4jService.menor_caminho`:
`MATCH caminho = shortestPath((a)-[:CONECTADO_COM*..6]-(b))` acha o caminho com menos saltos,
sem direção (a conexão é gravada num sentido e lida nos dois). O limite (`MAX_SALTOS = 6`, em
`config.py`) limita a busca e corresponde aos "seis graus de separação"; acima disso a tela diz
"Não há caminho entre vocês em até 6 conexões". O Cypher não aceita parâmetro dentro de `*..6`,
então o número (sempre um inteiro nosso) é colocado por `_fixar`. Origem igual ao destino é
tratada em Python, porque o `shortestPath` falha nesse caso.

**22. `MERGE` ou `CREATE`? Quando cada um?**
`MERGE` é "ache ou crie": se o padrão já existe, não duplica. Usamos em `criar_pessoa`,
`criar_habilidade`, `criar_empresa`, `definir_habilidade`, `registrar_trabalho` e
`definir_interesses`, que podem rodar de novo sobre dados existentes. `CREATE` sempre cria: a
carga (`scripts/carga_neo4j.py`) usa porque roda depois de apagar tudo; e `conectar` usa
`WHERE NOT (a)-[:CONECTADO_COM]-(b)` + `CREATE` por dois motivos: precisa saber se a conexão foi
criada agora (devolve `count(*)`; só conexão nova gera notificação, e o `MERGE`, sozinho, não diz
se achou ou criou) e grava sempre num sentido fixo, de quem clicou para a outra pessoa. O padrão sem seta
no `WHERE NOT` olha os dois sentidos, então a conexão não é duplicada.

**23. Quais constraints existem?**
Em `Neo4jService.criar_esquema`: unicidade em `Pessoa.id` (`pessoa_id_unico`), `Habilidade.nome`
e `Empresa.nome`, mais o índice `pessoa_nome`. A constraint impede duplicata e cria um índice,
então `MATCH (p:Pessoa {id: $id})` começa por uma busca no índice e não varrendo todos os nós.
`IF NOT EXISTS` deixa o script seguro de rodar várias vezes.

**24. Por que o Cypher usa parâmetros (`$id`) em vez de montar o texto?**
Segurança: o valor nunca vira código Cypher, então um nome com aspas não quebra nem altera a
consulta (o teste `test_habilidade_com_aspas_usa_parametros` prova isso). Desempenho: o texto
da consulta é sempre o mesmo, então o Neo4j reaproveita o plano de execução. E os tipos
chegam certos (lista, número, booleano). É o formato do item 3.2 do enunciado, e o docstring de
`neo4j_service.py` registra a única exceção (os limites de saltos).

**25. Como é calculada a pontuação dos mentores?**
Em `Neo4jService.recomendar_mentores`, candidato é quem tem `mentor = true` e nível ≥ 4 em alguma
habilidade que eu `QUER_APRENDER`. A fórmula é
`pontuação = 3 × (nº de habilidades minhas que ele ensina) + nível médio dessas habilidades +
conexões em comum − graus de separação` (graus = 6 se não há caminho). **Exemplo com os dados:**
a Ana quer Kubernetes, Machine Learning e Neo4j. A Camila Nóbrega ensina 1 delas (Machine
Learning, nível 5), tem 2 conexões em comum com a Ana (Bruno e Eduarda) e está a 1 grau:
3 × 1 + 5 + 2 − 1 = **9,0**, a primeira da lista. O Diego Farias: 3 × 1 + 5 + 2 − 2 = 8,0.

**26. Como sai o "porquê" de cada mentor?**
A mesma consulta devolve as habilidades (com nível), os graus, as conexões em comum e o `via`
(o primeiro intermediário do caminho, `nodes(caminho)[1].nome`). A tela só transforma isso em
frase em `porque_do_mentor` (`app/paginas/rede_mentores.py`): "Domina Neo4j (nível 5). Está a 2
graus de você, via Bruno. 2 conexões em comum."

Ponto de defesa: **o "via" do Diego pode mudar de uma carga para outra.** Da Ana até o Diego há
dois caminhos de 2 graus (pelo Bruno e pela Eduarda), e o `shortestPath` devolve um só, sem
garantir qual; já vimos os dois aparecerem. A pontuação não muda, porque ela usa só o tamanho do
caminho. Se a pergunta fosse "por onde eu chego", `allShortestPaths` devolveria os dois.

**27. E "Pessoas que talvez você conheça"?**
`Neo4jService.sugerir_conexoes`: o padrão `eu - amigo - sugestao`, onde `sugestao` não sou eu
nem já é minha conexão; `collect(DISTINCT amigo.nome)` junta os amigos em comum e a lista sai
ordenada pelo número deles (`ORDER BY em_comum DESC, nome`). Para a Ana, o primeiro é o Diego
Farias, com 2 em comum: Bruno e Eduarda. A ordem dos nomes dentro da lista de amigos não é
garantida, porque o `collect` não ordena.

### Aplicação e testes

**28. O que era a história do `127.0.0.1` em vez de `localhost`?**
No Windows, `localhost` resolve primeiro para o endereço IPv6 `::1`, mas as portas do Docker
estão publicadas só em `127.0.0.1` (IPv4). Cada driver tentava o IPv6, esperava cerca de 2
segundos e só então caía para o IPv4, em cada primeira conexão. Por isso o `.env` e os padrões
de `app/config.py` usam `127.0.0.1`; dentro do Compose os serviços usam os nomes `mongo`,
`redis` e `neo4j`, e `enderecos_sao_locais` trata todos esses como locais.

**29. Como o painel Bastidores sabe o que cada banco fez?**
Todo serviço executa os comandos dentro de `Registro.medir` (`app/servicos/registro.py`), que
mede o tempo e anota banco e comando (no Neo4j, a consulta Cypher inteira numa linha; o painel
mostra o começo e o resto aparece ao passar o mouse). O orquestrador abre
`Registro.acao("Publicar post")`, e tudo o que roda dentro leva esse nome; cada execução de uma
ação ganha um número, então curtir e descurtir em seguida aparecem como dois grupos. Leituras de tela são marcadas com `leitura=True` e
ficam escondidas por padrão; as atualizações automáticas rodam em `Registro.pausado()` e nem
são anotadas. Cada aba do navegador tem o seu `Registro` (`app/estado.py`).

**30. O que os testes cobrem?**
São 159 testes `pytest` contra os bancos reais do Docker, com os dados de exemplo (as respostas
são conhecidas: Ana → Sabrina são 4 graus, a primeira mentora da Ana é a Camila com 9,0, José
não tem caminho). Cobrem cada serviço, a carga (contagens, ids iguais nos bancos, `--se-vazio`,
a trava de banco remoto), o orquestrador (cada ação, cache HIT/MISS e invalidação, compensação
no cadastro, no título e nas experiências, e banco fora do ar simulado pela classe `ForaDoAr`
em `tests/test_orquestrador.py`), o disjuntor (com relógio falso, em `tests/test_disjuntor.py`),
o registro do Bastidores e as três telas com o `AppTest` do
Streamlit. Eles recarregam os dados no começo e no fim, por isso apagam o que foi criado pela
aplicação.

## 5. Consultas prontas para a arguição

Todas foram executadas contra os containers logo depois de uma carga limpa; os resultados
descritos são os desses dados de exemplo. Nenhum comando abaixo exige digitar senha no
documento: o Neo4j lê a senha da variável de ambiente do próprio container.

### Abrir cada shell

```powershell
# Neo4j (cypher-shell): a senha vem de NEO4J_AUTH, dentro do container
docker compose exec neo4j sh -c 'cypher-shell -u neo4j -p "${NEO4J_AUTH#neo4j/}"'

# MongoDB, já no banco da aplicação (sem senha)
docker compose exec mongo mongosh conecta_talentos

# Redis (sem senha)
docker compose exec redis redis-cli
```

As aspas simples fazem o `$` ser lido pelo shell do container, e o comando funciona igual no
PowerShell e no Git Bash. Para sair: `:exit` (cypher-shell), `exit` (mongosh), `quit`
(redis-cli). O **Neo4j Browser** (http://127.0.0.1:7474, usuário `neo4j`, senha em
`NEO4J_PASSWORD` do `.env`) aceita as mesmas consultas Cypher e desenha o resultado. Nas
consultas abaixo os valores estão escritos direto para colar mais fácil; na aplicação os
mesmos valores vão como parâmetros (`$id`, `$origem`…).

### Neo4j (Cypher)

**N1. Quantos nós de cada rótulo e quantos relacionamentos de cada tipo**
```cypher
MATCH (n) RETURN labels(n)[0] AS rotulo, count(*) AS total ORDER BY rotulo;
MATCH ()-[r]->() RETURN type(r) AS tipo, count(*) AS total ORDER BY tipo;
```
Resultado: Empresa 12, Habilidade 25, Pessoa 30; CONECTADO_COM 53, POSSUI_HABILIDADE 83,
QUER_APRENDER 14, TRABALHA_EM 33.

**N2. Constraints e índices**
```cypher
SHOW CONSTRAINTS YIELD name, labelsOrTypes, properties RETURN name, labelsOrTypes, properties ORDER BY name;
SHOW INDEXES YIELD name, type, labelsOrTypes, properties WHERE type = 'RANGE' RETURN name, labelsOrTypes, properties ORDER BY name;
```
Resultado: três constraints (`empresa_nome_unico`, `habilidade_nome_unico`, `pessoa_id_unico`)
e quatro índices RANGE: os três criados pelas constraints e o `pessoa_nome`.

**N3. Graus de separação: Ana → Sabrina**
```cypher
MATCH (a:Pessoa {id: 'u001'}), (b:Pessoa {id: 'u019'})
MATCH caminho = shortestPath((a)-[:CONECTADO_COM*..6]-(b))
RETURN [n IN nodes(caminho) | n.nome] AS pessoas, length(caminho) AS graus;
```
Resultado: `["Ana Beatriz Lima", "Camila Nóbrega", "Kleber Azevedo", "Patrícia Vilar",
"Sabrina Leite"]`, 4 graus. Trocando `'u019'` por `'u030'` (José Tavares, sem conexões), a
consulta não devolve nenhuma linha: é o "não há caminho".

**N4. A rede da Ana por grau (até 3 saltos)**
```cypher
MATCH caminho = (eu:Pessoa {id: 'u001'})-[:CONECTADO_COM*1..3]-(p:Pessoa)
WHERE p <> eu
WITH p, min(length(caminho)) AS grau
RETURN grau, count(p) AS pessoas, collect(p.nome)[..4] AS exemplos ORDER BY grau;
```
Resultado: 1º grau 3 pessoas (Bruno, Camila e Eduarda), 2º grau 3 (Diego, Kleber e Marina),
3º grau 8. A ordem dos nomes em `exemplos` não é garantida (o `collect` não ordena), e no 3º
grau os 4 exemplos mostrados podem variar. `min(length(...))` fica com o menor caminho, porque uma pessoa pode ser alcançada por
vários.

**N5. Pessoas que a Ana talvez conheça**
```cypher
MATCH (eu:Pessoa {id: 'u001'})-[:CONECTADO_COM]-(amigo:Pessoa)-[:CONECTADO_COM]-(sugestao:Pessoa)
WHERE sugestao <> eu AND NOT (eu)-[:CONECTADO_COM]-(sugestao)
WITH sugestao, collect(DISTINCT amigo.nome) AS amigos
RETURN sugestao.nome AS nome, size(amigos) AS em_comum, amigos ORDER BY em_comum DESC, nome LIMIT 5;
```
Resultado: Diego Farias (2 em comum: Bruno Carvalho e Eduarda Monteiro, em qualquer ordem, porque
o `collect` não ordena), Kleber Azevedo (1: Camila Nóbrega), Marina Albuquerque (1: Eduarda
Monteiro).

**N5b. Os dois caminhos mais curtos até o Diego (por que o "via" pode mudar)**
```cypher
MATCH (a:Pessoa {id: 'u001'}), (b:Pessoa {id: 'u004'})
MATCH caminho = allShortestPaths((a)-[:CONECTADO_COM*..6]-(b))
RETURN [n IN nodes(caminho) | n.nome] AS caminho;
```
Resultado: duas linhas, Ana → Bruno Carvalho → Diego Farias e Ana → Eduarda Monteiro → Diego
Farias. O `shortestPath` da aplicação devolve só um desses dois, sem garantir qual (pergunta 26).

**N6. Quem pode ser mentor da Ana (antes da pontuação)**
```cypher
MATCH (eu:Pessoa {id: 'u001'})-[:QUER_APRENDER]->(h:Habilidade)<-[ph:POSSUI_HABILIDADE]-(m:Pessoa)
WHERE m.mentor = true AND ph.nivel >= 4
RETURN m.nome AS mentor, h.nome AS habilidade, ph.nivel AS nivel ORDER BY nivel DESC, mentor;
```
Resultado: Camila (Machine Learning 5), Diego (Neo4j 5), Wagner (Kubernetes 5), Débora
(Kubernetes 4), Felipe (Machine Learning 4), Marina (Neo4j 4).

**N7. A pontuação dos mentores, com cada parcela à mostra**
```cypher
MATCH (eu:Pessoa {id: 'u001'})
MATCH (m:Pessoa)-[ph:POSSUI_HABILIDADE]->(h:Habilidade)
WHERE m.mentor = true AND m <> eu AND ph.nivel >= 4 AND h.nome IN ['Kubernetes', 'Machine Learning', 'Neo4j']
WITH eu, m, collect({nome: h.nome, nivel: ph.nivel}) AS habilidades, avg(ph.nivel) AS nivel_medio
OPTIONAL MATCH caminho = shortestPath((eu)-[:CONECTADO_COM*..6]-(m))
WITH eu, m, habilidades, nivel_medio, caminho
OPTIONAL MATCH (eu)-[:CONECTADO_COM]-(comum:Pessoa)-[:CONECTADO_COM]-(m)
WITH m, habilidades, nivel_medio, caminho, count(DISTINCT comum) AS em_comum
WITH m, habilidades, nivel_medio, em_comum,
     CASE WHEN caminho IS NULL THEN null ELSE length(caminho) END AS graus
RETURN m.nome AS mentor, size(habilidades) AS ensina, nivel_medio, em_comum, graus,
       3 * size(habilidades) + nivel_medio + em_comum - coalesce(graus, 6) AS pontuacao
ORDER BY pontuacao DESC, mentor LIMIT 10;
```
É a consulta de `recomendar_mentores` com as parcelas separadas. Resultado:

| mentor | ensina | nível médio | em comum | graus | pontuação |
|---|---|---|---|---|---|
| Camila Nóbrega | 1 | 5.0 | 2 | 1 | 9.0 |
| Diego Farias | 1 | 5.0 | 2 | 2 | 8.0 |
| Marina Albuquerque | 1 | 4.0 | 1 | 2 | 6.0 |
| Felipe Gadelha | 1 | 4.0 | 0 | 3 | 4.0 |
| Wagner Trigueiro | 1 | 5.0 | 0 | 4 | 4.0 |
| Débora Figueiredo | 1 | 4.0 | 0 | 4 | 3.0 |

**N8. Colegas de empresa da Ana e o histórico profissional da Marina**
```cypher
MATCH (eu:Pessoa {id: 'u001'})-[:TRABALHA_EM]->(e:Empresa)<-[:TRABALHA_EM]-(colega:Pessoa)
WHERE colega <> eu
RETURN DISTINCT colega.nome AS colega, e.nome AS empresa ORDER BY colega;

MATCH (p:Pessoa {id: 'u007'})-[t:TRABALHA_EM]->(e:Empresa)
RETURN e.nome AS empresa, t.cargo AS cargo, t.desde AS desde, t.ate AS ate ORDER BY t.desde;
```
Resultado: Bruno Carvalho, Diego Farias e Marina Albuquerque, todos pela DataNorte (o Diego
trabalhou lá antes). A Marina tem dois `TRABALHA_EM`: Banco Sertão (Analista de Dados,
2016-02 a 2020-12) e DataNorte (Engenheira de Dados Sênior, desde 2021-01, `ate` nulo =
emprego atual).

### MongoDB (`mongosh`, já dentro de `conecta_talentos`)

**M1. Coleções**
```js
show collections
```
Resultado: `fs.chunks`, `fs.files`, `notificacoes`, `posts`, `usuarios`.

**M2. O perfil da Ana (sem o hash da senha)**
```js
db.usuarios.findOne({_id: "u001"}, {senha_hash: 0})
```
Resultado: o documento com `nome`, `email: 'ana@exemplo.com'`, `titulo: 'Analista de Dados
Júnior'`, `localizacao` (João Pessoa, PB), um item em `experiencias` (DataNorte, desde
2025-02, `fim: null`), um em `formacao` (UFPB, Sistemas de Informação) e `certificacoes` vazio.

**M3. O validador e a recusa**
```js
db.getCollectionInfos({name: "usuarios"})[0].options.validator
db.usuarios.insertOne({_id: "teste", nome: "Sem email"})
```
Resultado: o `$jsonSchema` com `required: ['nome', 'email', 'titulo']`; o `insertOne` falha com
`MongoServerError: Document failed validation` e nada é gravado.

**M4. Índices (inclusive o TTL)**
```js
db.usuarios.getIndexes()
db.posts.getIndexes().map(i => i.key)
db.notificacoes.getIndexes()
```
Resultado: `email_1` com `unique: true`; nos posts `{autor_id: 1, criado_em: -1}`,
`{criado_em: -1}` e `{tags: 1}`; nas notificações `{usuario_id: 1, criado_em: -1}` e
`criado_em_1` com `expireAfterSeconds: 2592000` (30 dias).

**M5. O índice sendo usado**
```js
db.posts.find({autor_id: "u007"}).sort({criado_em: -1}).explain().queryPlanner.winningPlan
```
Resultado: estágio `FETCH` sobre `IXSCAN` com `indexName: 'autor_id_1_criado_em_-1'`: com um
autor só, o Mongo não varre a coleção nem ordena em memória (a ordem sai do índice). Para o
feed com vários autores, veja o segundo comando de M7.

**M6. Tags em alta (a mesma agregação da aplicação)**
```js
db.posts.aggregate([{$unwind: "$tags"}, {$group: {_id: "$tags", total: {$sum: 1}}}, {$sort: {total: -1, _id: 1}}, {$limit: 8}])
```
Resultado: carreira 19, dados 11, devops 9, web 9, produto 7, design 6, nosql 5, eventos 4.

**M7. O feed da Ana (ela e as conexões dela, do mais novo para o mais velho)**
```js
db.posts.find({autor_id: {$in: ["u001", "u002", "u003", "u005"]}}, {autor: 1, texto: 1, tags: 1, criado_em: 1}).sort({criado_em: -1}).limit(3)
db.posts.find({autor_id: {$in: ["u001", "u002", "u003", "u005"]}}).sort({criado_em: -1, _id: -1}).limit(30).explain().queryPlanner.winningPlan
```
Resultado: os três posts mais recentes são da própria Ana (o do dashboard no Power BI, o
pedido de material sobre bancos de grafos e o da primeira semana com Cypher), cada um com a
cópia `autor: {nome, titulo}`. Os ids das conexões vieram do Neo4j (consulta N4, 1º grau). O
segundo comando é o plano da consulta que a aplicação faz (`listar_posts`): `SORT` sobre `FETCH`
sobre `IXSCAN` em `autor_id_1_criado_em_-1`. O índice acha os posts dos quatro autores, mas a
ordenação final (por `criado_em` e `_id`) é feita em memória, o que é barato com 30 posts.

**M8. Um post com anexo, curtidas e comentários embutidos; os arquivos no GridFS**
```js
db.posts.findOne({"anexos.0": {$exists: true}}, {autor: 1, anexos: 1, curtidas: 1, "comentarios.autor_nome": 1})
db.fs.files.find({}, {filename: 1, contentType: 1, length: 1})
db.fs.chunks.countDocuments()
```
Resultado: o post da Camila Nóbrega, com `curtidas: ['u012']`, dois comentários (Bruno
Carvalho e Kleber Azevedo) e `anexos: [{arquivo_id: ObjectId(...), nome:
'comparativo_modelos.png', tipo: 'image/png', tamanho: …}]`, com tamanho de ~2,5 KB (os bytes
do PNG gerado podem mudar um pouco de uma carga para outra). Em `fs.files`, três PNG
(`comparativo_modelos.png`, `cartaz_meetup_web.png`, `prototipo_onboarding.png`, de cerca de
2 a 2,5 KB); em `fs.chunks`, 3 pedaços (cada arquivo cabe num só).

**M9. O histórico de notificações da Ana**
```js
db.notificacoes.find({usuario_id: "u001"}, {_id: 0, tipo: 1, texto: 1, lida: 1})
```
Resultado: três notificações com `lida: false` (curtida do Bruno, mentoria da Camila, post da
Eduarda). Depois de "Marcar todas como lidas", as três ficam `lida: true`.

### Redis (`redis-cli`)

**R1. Logo depois da carga**
```
DBSIZE
SCAN 0
GET notif:nao_lidas:u001
TYPE notif:recentes:u001
LRANGE notif:recentes:u001 0 -1
```
Resultado: 2 chaves, `notif:nao_lidas:u001` e `notif:recentes:u001`. O contador vale `"3"`; a
lista é do tipo `list` e tem os três JSON, o mais novo primeiro (Eduarda, Camila, Bruno).
Ninguém está online.

**R2. Depois que alguém entra (por exemplo, a Ana, no passo 1 da demo)**
```
SCAN 0 MATCH sessao:*
SMEMBERS usuario:u001:sessoes
HGETALL sessao:<cole aqui o token que o SMEMBERS mostrou>
TTL sessao:<o mesmo token>
ZRANGE presenca:online 0 -1 WITHSCORES
HGETALL presenca:visto
```
Resultado: uma chave `sessao:…` por login; o SET com o token da Ana; o HASH com `usuario_id
u001`, `nome Ana Beatriz Lima`, `login_em` e `ultimo_acesso` (segundos desde a época); o `TTL`
perto de 1800 e voltando para 1800 a cada clique na aplicação; o ZSET com `u001` e o horário do
último sinal como score; o HASH `presenca:visto` com o mesmo horário. `TYPE` dessas chaves
responde `hash`, `set`, `zset` e `hash`.

**R3. Quem está online, pelo score (o que o painel de presença faz)**
```
TIME
ZRANGE presenca:online 0 -1 WITHSCORES
ZRANGEBYSCORE presenca:online <agora-90> +inf WITHSCORES
ZCOUNT presenca:online <agora-90> +inf
ZREMRANGEBYSCORE presenca:online -inf (<agora-90>
```
`TIME` devolve o horário do servidor; o primeiro número são os segundos desde a época. Troque
`<agora-90>` por esse número menos 90. O painel se atualiza em modo pausado, então estes
comandos não aparecem no Bastidores: é aqui no `redis-cli` que se mostra a consulta por faixa.
Resultado (executado com a Ana logada e um sinal antigo do Bruno, de 10 minutos atrás, gravado à
mão com `ZADD presenca:online <agora-600> u002`): o `ZRANGE` mostra os dois; o `ZRANGEBYSCORE`
devolve só `u001` com o seu horário; o `ZCOUNT` responde `1`; o `ZREMRANGEBYSCORE` responde `1`
(apagou o Bruno), e um novo `ZRANGE` só mostra `u001`. É a mesma limpeza preguiçosa que
`usuarios_online` faz a cada atualização do painel. Quem sai pelo botão "Sair" é removido na
hora (`ZREM`).

**R4. Notificações depois que o Bruno publica (passo 4 da demo)**
```
GET notif:nao_lidas:u001
LRANGE notif:recentes:u001 0 0
```
Resultado: `"4"`, e o JSON mais novo é
`{"tipo": "post", "de": {"id": "u002", "nome": "Bruno Carvalho"}, "texto": "Bruno Carvalho publicou um post novo.", ...}`.
Depois de "Marcar todas como lidas", o contador volta a `"0"`.

**R5. O cache e o seu prazo**
```
TTL cache:tags_em_alta
GET cache:tags_em_alta
TTL cache:perfil:u003
```
Resultado: com a aplicação aberta no feed, `cache:tags_em_alta` tem TTL de até 60 e guarda o
JSON `[{"tag": "carreira", "total": 19}, ...]`; depois de abrir o perfil da Camila,
`cache:perfil:u003` tem TTL de até 300. `-2` quer dizer que a chave não existe (expirou ou foi
apagada): o próximo acesso será um MISS.

## 6. Se algo der errado na hora

| Sintoma | O que fazer |
|---|---|
| `docker compose ps -a` mostra banco sem `(healthy)`, ou o `app` não sobe | Espere uns 30 s (o Neo4j é o mais lento) e rode `docker compose up -d` de novo. Veja o motivo com `docker compose logs neo4j` (ou `mongo`, `redis`, `carga`). Se a `carga` saiu com erro, o `app` não sobe: `docker compose logs carga` mostra por quê. |
| Os dados ficaram estranhos (posts e conexões de ensaio, notificações demais) | Recarregue: `docker compose run --rm carga python scripts/carga_inicial.py`. Depois recarregue as abas do navegador e entre de novo (F5 desconecta). |
| "port is already allocated" ou a porta 8501 está ocupada | Algum Streamlit rodando fora do Docker ocupa a porta: feche-o, ou rode o seu com `--server.port 8502`. Para as portas dos bancos, pare a outra instância de MongoDB/Redis/Neo4j da máquina. |
| Um banco parou no meio da demo (barra lateral com 🔴) | `docker compose start mongo` (ou `redis`, `neo4j`). A aplicação volta sozinha quando o banco responde (em até 10 s depois disso, por causa do disjuntor da pergunta 6); clique em "Tentar de novo" na tela de entrada, se for ela que estiver aberta. Aproveite para mostrar o aviso amigável: é parte da avaliação. |
