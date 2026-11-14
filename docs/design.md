# Conecta Talentos — Documento de Design

**Disciplina:** Implementação de Bancos de Dados NoSQL (Prof. Ricardo Roberto de Lima)
**Estudo de Caso 02:** Rede Social Profissional & Plataforma de Talentos/Mentoria
**Data:** 13/11/2026

> Legenda: **[decidido]** = escolhido pelo grupo na conversa. **[proposta]** = decisão
> minha (Claude), com o motivo; pode ser trocada sem refazer o resto.

---

## 1. Intenção e porquê

Entregar o projeto final da disciplina: uma aplicação Streamlit funcional que usa
MongoDB, Redis e Neo4j ao mesmo tempo, cada um no papel em que é mais forte
(persistência poliglota), e que o grupo consiga **demonstrar ao vivo e defender
oralmente**.

A nota é composta por: integração arquitetural (25%), modelagem e Cypher (20%),
aplicação Streamlit/Python (25%) e defesa oral (30%). Por isso o projeto precisa
ser, além de correto, **fácil de explicar**: cada dado tem um motivo claro para
estar no banco em que está, e a própria tela mostra o que cada banco fez.

## 2. Objetivos, não-objetivos e anti-objetivos

**Objetivos**

1. As três telas mínimas do enunciado, funcionando de ponta a ponta.
2. Fluxos que tocam os três bancos numa única ação do usuário (login, publicar
   post, conectar-se a alguém), visíveis na tela.
3. Scripts de carga que criam coleções, validação, índices, constraints e dados
   iniciais nos três bancos, e que podem ser executados várias vezes.
4. Subir tudo com um comando (`docker compose up`) em qualquer máquina com Docker.
5. Código organizado e comentado em português, com tratamento de erros.
6. Material de apoio para a defesa: decisões de arquitetura e perguntas prováveis.

**Não-objetivos**

- Segurança de produção (HTTPS, recuperação de senha, perfis de permissão).
- Chat entre usuários, moderação, busca full-text avançada.
- Ciclo completo de mentoria (agenda, aceite, avaliação). "Pedir mentoria" apenas
  gera uma notificação para o mentor.
- Escala: os dados de exemplo são ~30 pessoas; nada de sharding, cluster ou réplica.
- Slides da apresentação (podem ser pedidos depois, à parte).

**Anti-objetivos** (o projeto falha se cair nisso, mesmo "funcionando")

- Usar um banco como enfeite: Redis guardando o que caberia no Mongo, ou o grafo
  sendo consultado como se fosse tabela.
- Código que o grupo não consegue explicar na arguição (abstrações demais,
  "mágica").
- Demo que quebra por depender de internet ou de conta em serviço externo.
- Tela mostrando stack trace quando um banco está fora do ar.

## 3. Restrições

- Python + Streamlit; drivers oficiais `pymongo`, `redis`, `neo4j`.
- Rótulos e relacionamentos do grafo exatamente como no enunciado:
  `(:Pessoa)-[:CONECTADO_COM]->(:Pessoa)`, `(:Pessoa)-[:POSSUI_HABILIDADE]->(:Habilidade)`,
  `(:Pessoa)-[:TRABALHA_EM]->(:Empresa)`, com consulta `shortestPath`.
- Conexão Neo4j por variáveis `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`,
  `NEO4J_DATABASE` (item 3.1 do enunciado) e classe de serviço no estilo do item 3.2.
- Máquina de desenvolvimento: Windows 11, Python 3.11, Docker Desktop instalado.
- Apresentação de até 10 minutos: a demo precisa ter dados prontos e um roteiro curto.
- O enunciado aceita Neo4j local ou no AuraDB; nenhum dos dois é obrigatório.
- **[proposta] Código simples de propósito:** classes e funções diretas, sem
  metaprogramação nem camadas extras. Onde aparecer algo menos comum (pipeline do
  Redis, atualização automática do Streamlit), um comentário explica o que é e por
  quê. Motivo: todo integrante precisa conseguir explicar qualquer trecho.

Os trechos do enunciado em que este design se apoia estão no **Anexo A**.

## 4. Abordagens consideradas

| | Abordagem | Vantagem | Custo |
|---|---|---|---|
| A | **Docker local** — os três bancos em containers | Um comando sobe tudo; não depende de internet; igual em qualquer máquina | Docker Desktop precisa estar aberto |
| B | Tudo na nuvem (Atlas + Redis Cloud + Aura) | Nada a instalar | Depende do Wi-Fi da sala e de três contas |
| C | Híbrido (Mongo/Redis locais, Neo4j no Aura) | Usa o Aura citado no enunciado | Junta os riscos das duas |

**[decidido] Abordagem A.** As conexões ficam num arquivo `.env`, então apontar o
Neo4j para o Aura (ou qualquer banco para a nuvem) é trocar uma linha, sem mexer
em código.

## 5. Arquitetura

```
                +---------------------------------------+
                |        Streamlit (app/Inicio.py)       |
                |  páginas: Feed/Perfil · Presença ·    |
                |           Rede/Mentores                |
                +-------------------+-------------------+
                                    |
                        +-----------+-----------+
                        |   orquestrador.py     |  fluxos que cruzam bancos
                        +--+--------+--------+--+
                           |        |        |
                 MongoService  RedisService  Neo4jService
                           |        |        |
                        MongoDB   Redis    Neo4j
```

**[proposta] Três camadas, e só três:**

- **Páginas** (`app/paginas/`): só interface. Não importam drivers.
- **Orquestrador** (`app/servicos/orquestrador.py`): um método por ação de negócio
  que envolve mais de um banco (`fazer_login`, `publicar_post`, `conectar`,
  `cadastrar_usuario`, `montar_feed`, `pedir_mentoria`). É aqui que a persistência
  poliglota fica explícita — bom para mostrar na defesa.
- **Serviços** (`app/servicos/`): uma classe por banco, cada uma só conhece o seu
  driver. `Neo4jService` segue o modelo do item 3.2 do enunciado.

Motivo: quem pergunta "onde está a consulta Cypher?" ou "onde o Redis é chamado?"
acha em um arquivo só.

**O identificador que liga os três bancos** é o `id` do usuário (texto curto, ex.
`u007`): é o `_id` no Mongo, a propriedade `id` do nó `:Pessoa` e o sufixo das
chaves no Redis.

### Estrutura de pastas

```
docker-compose.yml        Dockerfile        requirements.txt
.env.example              README.md
app/
  Inicio.py               # ponto de entrada, login e navegação
  config.py               # lê o .env
  paginas/
    feed_perfil.py
    presenca_notificacoes.py
    rede_mentores.py
  servicos/
    mongo_service.py   redis_service.py   neo4j_service.py
    orquestrador.py
    registro.py           # registra cada operação p/ o painel "Bastidores"
  componentes/            # pedaços de tela reutilizados (bastidores, cartões)
scripts/
  dados_exemplo.py        # o conjunto de dados fictício, único para os 3 bancos
  carga_mongo.py   carga_redis.py   carga_neo4j.py
  carga_inicial.py        # executa as três
tests/
docs/
  design.md               # este arquivo
  guia_da_defesa.md       # roteiro da demo + perguntas prováveis
```

## 6. Modelo de dados

### 6.1 MongoDB — banco `conecta_talentos`

Por que aqui: perfis têm forma variável (uma pessoa tem 1 experiência, outra tem 8
e três certificações), posts carregam comentários e anexos embutidos, e é o dado
que precisa durar. Documento resolve sem JOIN e sem migração de esquema.

**`usuarios`**
```json
{
  "_id": "u007",
  "nome": "Marina Albuquerque",
  "email": "marina@exemplo.com",
  "senha_hash": "pbkdf2$...",
  "titulo": "Engenheira de Dados Sênior",
  "resumo": "...",
  "localizacao": { "cidade": "João Pessoa", "estado": "PB" },
  "experiencias": [
    { "empresa": "DataNorte", "cargo": "Engenheira de Dados",
      "inicio": "2021-03", "fim": null, "descricao": "...",
      "tecnologias": ["Python", "Spark"] }
  ],
  "formacao": [
    { "instituicao": "UNIPÊ", "curso": "Ciência da Computação",
      "nivel": "Graduação", "inicio": 2014, "fim": 2018 }
  ],
  "certificacoes": [
    { "nome": "MongoDB Associate Developer", "emissor": "MongoDB", "ano": 2024 }
  ],
  "criado_em": "ISODate"
}
```
- Validação `$jsonSchema` exigindo só `nome`, `email`, `titulo` — o resto é livre
  (mostra "esquema flexível com garantias mínimas").
- Índice único em `email`.

**`posts`**
```json
{
  "_id": "ObjectId",
  "autor_id": "u007",
  "autor": { "nome": "Marina Albuquerque", "titulo": "Engenheira de Dados Sênior" },
  "texto": "...",
  "tags": ["dados", "carreira"],
  "anexos": [ { "arquivo_id": "ObjectId(GridFS)", "nome": "grafico.png",
                "tipo": "image/png", "tamanho": 48213 } ],
  "curtidas": ["u002", "u015"],
  "comentarios": [ { "autor_id": "u002", "autor_nome": "...", "texto": "...",
                     "criado_em": "ISODate" } ],
  "criado_em": "ISODate"
}
```
- `autor` é uma cópia pequena dos dados do autor (padrão *extended reference*):
  o feed é montado sem buscar cada perfil.
- Comentários e curtidas embutidos (`$push`, `$addToSet`): pertencem ao post e
  são lidos junto com ele.
- Índices: `{autor_id: 1, criado_em: -1}`, `{criado_em: -1}`, `{tags: 1}`.
- Agregação "tags em alta" (`$unwind` → `$group` → `$sort`).

**Anexos multimídia:** GridFS (`fs.files` / `fs.chunks`). O post guarda só a
referência.

**`notificacoes`** — histórico durável
```json
{ "_id": "ObjectId", "usuario_id": "u007", "tipo": "conexao|post|curtida|comentario|mentoria",
  "de": { "id": "u002", "nome": "..." }, "texto": "...", "lida": false,
  "criado_em": "ISODate" }
```
- Índice `{usuario_id: 1, criado_em: -1}` e índice TTL de 30 dias em `criado_em`.

### 6.2 Redis

Por que aqui: são dados quentes, pequenos, que mudam a cada segundo e que podem
ser perdidos sem prejuízo (presença, sessão, contadores). Lê-los do Mongo a cada
atualização de tela seria desperdício.

| Chave | Tipo | Conteúdo | Expira |
|---|---|---|---|
| `sessao:{token}` | HASH | `usuario_id`, `nome`, `login_em`, `ultimo_acesso` | 30 min, renovado a cada uso |
| `usuario:{id}:sessoes` | SET | tokens ativos do usuário | — |
| `presenca:online` | ZSET | membro = id do usuário, score = horário do último sinal | limpeza por score |
| `presenca:visto` | HASH | id → horário em que foi visto por último | — |
| `notif:nao_lidas:{id}` | STRING | contador (`INCR`; zera ao ler) | — |
| `notif:recentes:{id}` | LIST | últimas 20 notificações em JSON (`LPUSH` + `LTRIM`) | — |
| `cache:perfil:{id}` | STRING | JSON do perfil vindo do Mongo | 5 min; apagado ao editar o perfil |
| `cache:tags_em_alta` | STRING | resultado da agregação | 60 s |

- **Presença:** está online quem enviou sinal nos últimos 90 s. O sinal é
  reenviado sozinho enquanto a aba está aberta. Uma consulta por faixa de score
  (`ZREVRANGEBYSCORE`) lista quem está online, e o total é o tamanho dessa lista.
  Ao sair, o usuário é removido do ZSET.
- **Sessão:** o Streamlit guarda apenas o token; os dados da sessão ficam no Redis.
  A cada interação o token é validado e o TTL renovado. Dá para listar e encerrar
  sessões.
- **Notificações:** o contador vive no Redis (atualiza o sininho na hora); o
  conteúdo durável vive no Mongo. Ao marcar como lidas: zera o contador no Redis e
  atualiza `lida` no Mongo.
- **Cache-aside** no perfil e nas tags em alta. O painel Bastidores mostra
  "cache HIT" ou "cache MISS".
- Operações em conjunto (login: HASH + EXPIRE + SADD + ZADD) vão num `pipeline`
  transacional.

### 6.3 Neo4j

Por que aqui: as perguntas são sobre **caminhos** — "como eu chego nessa pessoa?",
"quem está a 2 graus de mim e domina X?". Em grafo, percorrer vizinhos custa o
mesmo independentemente do tamanho total da base (*index-free adjacency*); em
documento ou tabela seriam vários JOINs/buscas encadeadas.

**Nós**
- `(:Pessoa {id, nome, titulo, mentor, anos_experiencia})` — `nome` e `titulo` são
  cópia mínima do Mongo, para desenhar o grafo sem ir ao outro banco.
- `(:Habilidade {nome, categoria})`
- `(:Empresa {nome, setor})`

**Relacionamentos**
- `(:Pessoa)-[:CONECTADO_COM {desde}]->(:Pessoa)` — gravado em um sentido,
  consultado sem direção.
- `(:Pessoa)-[:POSSUI_HABILIDADE {nivel}]->(:Habilidade)` — `nivel` de 1 a 5.
- `(:Pessoa)-[:TRABALHA_EM {cargo, desde, ate}]->(:Empresa)` — `ate` nulo = emprego
  atual; com valor = histórico.
- **[proposta]** `(:Pessoa)-[:QUER_APRENDER]->(:Habilidade)` — extensão ao
  enunciado. Sem ela, "recomendar mentor" não tem critério: é o que diz em que a
  pessoa quer ser mentorada.

**Constraints e índices:** unicidade em `Pessoa.id`, `Habilidade.nome`,
`Empresa.nome`; índice em `Pessoa.nome`.

**Onde cada dado do grafo nasce e é editado [proposta]**

Nada no grafo é "só da carga inicial": um usuário cadastrado ao vivo na demo
consegue montar seu perfil e receber recomendações.

| Dado | Onde o usuário cria/edita | Gravado em |
|---|---|---|
| Nó `:Pessoa` | Cadastro | Mongo (perfil) + Neo4j (nó) |
| `POSSUI_HABILIDADE` e `nivel` | Editar perfil → "Minhas habilidades" | só Neo4j |
| `mentor` (disponível para mentoria) | Editar perfil | só Neo4j |
| `anos_experiencia` | Editar perfil | só Neo4j |
| `QUER_APRENDER` | Tela de mentores → "Quero aprender" (fica salvo) | só Neo4j |
| `TRABALHA_EM` | Editar perfil → adicionar/remover experiência | Mongo (experiência rica) + Neo4j (relacionamento com `cargo`, `desde`, `ate`) |
| `CONECTADO_COM` | Botão "Conectar" | só Neo4j |
| `titulo` | Editar perfil | Mongo (fonte) → copiado para `:Pessoa.titulo` e para `posts.autor.titulo` (`update_many`); cache do perfil apagado |
| `nome` | Só no cadastro; **não é editável** | Mongo + Neo4j |

`nome` não ser editável é uma simplificação: ele está copiado em posts,
comentários, notificações, sessão e grafo, e propagar a mudança para tudo isso
não acrescenta nada à avaliação. `titulo` é editável justamente para ter **um**
exemplo de propagação de dado duplicado para mostrar.

**Consultas principais**

1. Graus de separação entre duas pessoas:
   ```cypher
   MATCH (a:Pessoa {id: $origem}), (b:Pessoa {id: $destino}),
         caminho = shortestPath((a)-[:CONECTADO_COM*..6]-(b))
   RETURN [n IN nodes(caminho) | n {.id, .nome, .titulo}] AS pessoas,
          length(caminho) AS graus
   ```
2. Minha rede por grau (1º, 2º, 3º) — padrão de tamanho variável `[:CONECTADO_COM*1..3]`
   de mim até cada pessoa, ficando com o menor tamanho (`min(length(caminho))`) como grau.
3. Recomendação de mentores: pessoas com `mentor = true` que possuem, em nível ≥ 4,
   habilidades que eu `QUER_APRENDER`, ordenadas por uma pontuação que soma
   habilidades em comum e nível, e favorece quem está mais perto na rede e tem
   mais conexões em comum. Cada recomendação vem com o **porquê** ("domina Neo4j
   nível 5; está a 2 graus de você, via Carlos").
4. "Pessoas que talvez você conheça" — amigos de amigos, ordenados por conexões em comum.
5. Colegas de empresa e busca de pessoas por habilidade.

## 7. Telas

**Entrada (login)** — e-mail e senha. Para a demo, um seletor "entrar como…"
troca de usuário rápido. Há também cadastro de novo usuário.

**1. Feed & Perfil** (MongoDB, com apoio dos outros dois)
- Feed: posts meus e das minhas conexões (os ids vêm do Neo4j, os posts do Mongo,
  a bolinha verde de "online" de cada autor vem do Redis).
- Publicar post com texto, tags e anexo (imagem/PDF → GridFS). Curtir e comentar.
- Perfil: cabeçalho, resumo, experiências, formação, certificações; habilidades e
  número de conexões vêm do grafo. Editar perfil: adicionar/remover experiência,
  formação e certificação.
- Tags em alta.

**2. Presença & Notificações** (Redis)
- Indicadores: quantos online agora, minhas notificações não lidas, sessões ativas.
- Lista de profissionais online / offline com "visto por último há…".
- Minhas notificações recentes e botão "marcar todas como lidas".
- Minhas sessões ativas, com o tempo restante (TTL) e botão para encerrar.
- Atualização automática a cada poucos segundos, sem recarregar a página.
- **[proposta] Simulador para a demo:** botão que coloca alguns usuários de exemplo
  online e gera notificações. Motivo: com uma pessoa só logada, o painel ficaria
  vazio na apresentação. Fica claramente marcado como simulação.

**3. Rede de Conexões & Busca de Mentores** (Neo4j)
- Graus de separação: escolho uma pessoa e vejo o caminho até ela, desenhado como
  grafo com o caminho destacado, e também em lista ("Você → Carlos → Ana → Marina:
  3 graus"). Trata o caso "não há caminho".
- Minha rede: grafo interativo das conexões até o 2º grau, e lista por grau.
- Buscar mentores: escolho habilidades que quero aprender, recebo a lista
  ordenada com o porquê de cada um, e os botões "Conectar" e "Pedir mentoria".
- Pessoas que talvez você conheça.

**Em todas as telas**

- **[proposta] Painel "Bastidores":** área recolhível que lista, para a última
  ação, o que foi executado em cada banco, com o comando e o tempo. Exemplo ao
  publicar um post:
  ```
  MongoDB  posts.insert_one({...})                         4 ms
  Neo4j    MATCH (:Pessoa {id:"u007"})-[:CONECTADO_COM]-…  9 ms
  Redis    INCR notif:nao_lidas:u002  (+5 chaves)          1 ms
  MongoDB  notificacoes.insert_many([6 documentos])        3 ms
  ```
  Motivo: o enunciado pede que a demo mostre "as chamadas e atualizações
  acontecendo nos três bancos simultaneamente". Isso mostra sem precisar abrir
  três terminais.
- **Barra lateral:** usuário logado, sininho com o contador do Redis, e o estado
  de cada banco (conectado / fora do ar).

## 8. Fluxos que cruzam os três bancos

| Ação | MongoDB | Redis | Neo4j |
|---|---|---|---|
| **Login** | busca usuário por e-mail, confere senha | cria sessão (TTL), marca presença | — |
| **Cadastro** | insere perfil | — | cria nó `:Pessoa` |
| **Publicar post** | grava post (+ anexo no GridFS) e notificações | incrementa contador e lista de cada conexão | busca minhas conexões |
| **Conectar** | grava notificação | incrementa contador do outro; invalida cache | `MERGE` do relacionamento |
| **Abrir perfil** | lê perfil (se não estiver em cache) | cache-aside; presença | habilidades e nº de conexões |
| **Montar feed** | posts dos ids recebidos | presença dos autores | ids das conexões |
| **Sair** | — | apaga sessão, remove presença | — |

| **Editar experiência** | `$push` / `$pull` em `experiencias` | apaga cache do perfil | `MERGE` / remoção de `TRABALHA_EM` |
| **Editar título** | atualiza `usuarios` e `posts.autor` | apaga cache do perfil | atualiza `:Pessoa.titulo` |
| **Pedir mentoria** | grava notificação | incrementa contador do mentor | — |

**Consistência entre bancos [proposta].** Não existe transação que cubra os três.
A regra tem duas partes, e é a mesma em todo o orquestrador:

1. **Dado que existe em dois bancos tem de ficar igual nos dois.** Grava-se
   primeiro no Mongo (fonte da verdade); se a gravação no Neo4j falhar, desfaz-se
   a do Mongo (compensação) e a ação inteira é recusada com mensagem clara.
   Vale para: cadastro, editar experiência, editar título.
2. **Efeito colateral nunca desfaz a ação principal.** Notificação, contador,
   presença e cache são "melhor esforço": se falharem, a ação principal continua
   valendo, a falha é registrada e a tela mostra um aviso.

Aplicando a regra a cada caso de falha:

| Situação | O que acontece |
|---|---|
| Cadastro: Neo4j falha após o Mongo gravar | remove o documento do Mongo; cadastro recusado |
| Editar experiência/título: Neo4j falha | desfaz a alteração no Mongo; edição recusada |
| Conectar: notificação (Mongo/Redis) falha após o `MERGE` | conexão **mantida**; aviso "conectado, mas não foi possível notificar" |
| Publicar com Neo4j fora do ar | post **salvo**; conexões não são notificadas; aviso na tela |
| Publicar com Redis fora do ar | não acontece logado (sem Redis não há sessão) |
| Feed com Neo4j fora do ar | mostra só os meus posts, com aviso |
| Perfil com Neo4j fora do ar | mostra o perfil do Mongo; bloco de habilidades com aviso |
| Cache indisponível ou corrompido | lê direto do Mongo |
| Mongo fora do ar | tela de entrada informa que a aplicação está indisponível |

## 9. Tratamento de erros

- Cada serviço tem `ping()`; a barra lateral mostra o estado dos três bancos.
- Banco fora do ar não derruba a aplicação: a parte que depende dele mostra um
  aviso ("Rede de conexões indisponível: Neo4j fora do ar") e o resto continua.
  Sem Redis não há login (a sessão vive lá) — a tela de entrada explica isso.
- Sessão expirada leva de volta ao login com aviso.
- Entradas validadas antes de gravar (campos obrigatórios, tamanho e tipo do anexo).

## 10. Execução e entrega

- `docker-compose.yml` com `mongo`, `redis`, `neo4j` (com volumes e healthcheck) e
  o serviço `app` (Streamlit). Versões das imagens fixadas.
- **[proposta]** Perfil opcional `ferramentas` no compose com Mongo Express e
  Redis Insight, para quem quiser olhar os dados por fora durante a demo. O Neo4j
  Browser já vem na porta 7474.
- Também roda sem container para o app: `pip install -r requirements.txt` e
  `streamlit run app/Inicio.py`, com os bancos no Docker.
- `python scripts/carga_inicial.py` cria tudo e carrega os dados. Pode ser
  repetido: apaga e recria. **Trava de segurança:** como a carga apaga dados, ela
  só roda direto quando os três endereços do `.env` são locais (`localhost` ou os
  nomes dos containers). Se algum apontar para fora (ex.: Aura), o script para e
  exige a opção `--confirmar-remoto`. Os testes seguem a mesma trava e nunca rodam
  contra banco remoto.
- **Dados de exemplo:** ~30 pessoas fictícias, ~12 empresas fictícias, ~25
  habilidades, 53 conexões formando grupos ligados por poucas "pontes" (para os
  caminhos de 2 a 4 graus ficarem interessantes) e uma pessoa sem conexões (para
  mostrar o caso "sem caminho"). ~40 posts, alguns com imagem. Geração
  determinística: toda carga produz os mesmos dados. Senha única de demonstração
  para todos, registrada no `README`.
- `README.md`: como subir, como carregar, como rodar, como testar.
- `docs/guia_da_defesa.md`: roteiro de demo de ~5 minutos e perguntas prováveis da
  arguição com respostas (por que cada dado está em cada banco, TTL, cache-aside,
  `shortestPath`, index-free adjacency, consistência).

## 11. Testes

- Testes automatizados (`pytest`) dos três serviços e do orquestrador contra os
  bancos do Docker, com os dados de exemplo (as respostas são conhecidas: ex. "de
  u001 a u019 são 4 graus").
- Teste de fumaça das páginas com o `AppTest` do Streamlit.
- Verificação manual final no navegador, seguindo o roteiro da demo.

## 12. Deixado para quem implementar

- Biblioteca de desenho do grafo (precisa funcionar sem internet e permitir
  destacar um caminho).
- Fórmula exata da pontuação de mentores, desde que o "porquê" apareça na tela.
- Versões exatas de imagens e bibliotecas (as estáveis atuais, fixadas).
- Aparência: cores, ícones, disposição dos blocos em cada tela.
- Conteúdo dos dados fictícios.
- Como isolar os dados de teste dos dados da demo.

## 13. Ordem de construção e o que cortar primeiro [proposta]

Construído nesta ordem, de modo que parar em qualquer ponto deixa algo que roda e
pode ser apresentado:

1. **Base:** Docker Compose, `.env`, os três serviços com `ping()`, carga inicial
   nos três bancos.
2. **Login e sessão** (Mongo + Redis) e barra lateral com o estado dos bancos.
3. **Tela 3 — Rede & Mentores** (Neo4j): graus de separação, minha rede, mentores.
4. **Tela 1 — Feed & Perfil** (Mongo): feed, publicar, curtir, comentar, perfil.
5. **Tela 2 — Presença & Notificações** (Redis), com atualização automática.
6. **Fluxos cruzados completos:** notificações ao publicar/conectar, cadastro,
   edição de perfil com sincronização e compensação.
7. **Painel Bastidores.**
8. Cache-aside (perfil e tags em alta).
9. Anexos no GridFS.
10. Simulador da demo.
11. Guia da defesa, README final, testes de página.
12. Perfil `ferramentas` do compose (Mongo Express, Redis Insight).

Os itens 1 a 6 cobrem tudo que o enunciado exige. **Se faltar tempo, corta-se de
baixo para cima** (12 primeiro). Os testes dos serviços são escritos junto com
cada item, não no fim.

## 14. Em aberto

- **Prazo de entrega:** não informado. Com a ordem acima, o prazo só decide até
  que item se chega.
- **Neo4j Aura:** o enunciado termina com um usuário e senha que parecem ser de
  uma instância Aura. Não são usados. Se o grupo confirmar que são dele, basta
  preencher o `.env`.
- **Nome "Conecta Talentos":** [proposta]; trocar é mudar uma constante.
- **Git:** a entrega é um repositório. O repositório é criado localmente; commits
  e envio ao GitHub só quando o grupo pedir.

---

## Anexo A — O que o enunciado exige (resumo fiel)

**Tecnologias:** MongoDB, Redis, Neo4j, Python e Streamlit. O Streamlit é o
orquestrador central e conecta-se diretamente aos três bancos.

**Entregas**
- Repositório com código Python/Streamlit organizado e comentado, com
  `requirements.txt` ou Docker Compose.
- Scripts de carga e inicialização: criação de schemas/coleções, índices e carga
  inicial nos três bancos.
- Defesa oral: todos os integrantes aptos a responder perguntas conceituais e
  práticas.

**Item 3.1 — variáveis de conexão do Neo4j**
```
NEO4J_URI=neo4j+s://<instancia>.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<SUA_SENHA>
NEO4J_DATABASE=neo4j
```
(No Docker local, `NEO4J_URI=bolt://localhost:7687`.)

**Item 3.2 — modelo de classe de serviço** (o formato a seguir no `Neo4jService`)
```python
from neo4j import GraphDatabase

class Neo4jService:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def get_recommendations(self, user_name):
        query = """
        MATCH (p1:Pessoa {nome: $nome})-[r1:ASSISTIU]->(f:Filme)<-[r2:ASSISTIU]-(p2:Pessoa)
        WHERE p1 <> p2 AND abs(r1.nota - r2.nota) < 1
        RETURN DISTINCT f.titulo AS recomendacao, p2.nome AS origem LIMIT 10;
        """
        with self.driver.session() as session:
            result = session.run(query, nome=user_name)
            return [record["recomendacao"] for record in result]
```
Ou seja: classe com o driver criado no construtor, um método por consulta, Cypher
em texto com parâmetros (`$nome`), `driver.session()` + `session.run(...)`, e
retorno em lista Python. `MongoService` e `RedisService` seguem o mesmo formato.

**Estudo de Caso 02 — responsabilidade de cada banco**
- **MongoDB:** perfil estendido dos usuários (experiências em JSON, formação,
  certificações), posts da linha do tempo e anexos multimídia.
- **Redis:** estados de presença online/offline, gerenciamento de sessões ativas e
  contador em tempo real de notificações não lidas.
- **Neo4j:** rede de conexões (`(:Pessoa)-[:CONECTADO_COM]->(:Pessoa)`), mapa de
  habilidades (`(:Pessoa)-[:POSSUI_HABILIDADE]->(:Habilidade)`) e histórico
  profissional (`(:Pessoa)-[:TRABALHA_EM]->(:Empresa)`), permitindo consultas de
  menor caminho (`shortestPath`).

**Telas mínimas**
1. Feed & Perfil do Usuário — perfil rico e postagens alimentadas pelo MongoDB.
2. Dashboard de Presença & Notificações — indicadores em tempo real com Redis.
3. Rede de Conexões & Busca de Mentores — exibição gráfica ou em lista dos graus
   de separação e recomendações de mentores baseadas em grafos Neo4j.

**Demonstração:** simular um fluxo de uso completo mostrando as chamadas e
atualizações acontecendo nos três bancos simultaneamente.

**Avaliação**

| Critério | Peso |
|---|---|
| Integração arquitetural NoSQL (cada banco usado em sua fortaleza) | 25% |
| Modelagem de dados & Cypher (documento JSON, chaves Redis, consultas em grafo) | 20% |
| Aplicação Streamlit & Python (funcionamento, usabilidade, organização, erros) | 25% |
| Defesa oral e domínio técnico | 30% |

A arguição inclui perguntas individuais sobre o código, comandos Cypher,
estratégias de cache e consultas NoSQL.
