"""Neo4jService: rede de conexões, habilidades, histórico profissional e recomendações (grafo).

Todo Cypher daqui usa parâmetros ($nome), nunca texto montado com os valores. As únicas
exceções são os limites de saltos em padrões como [:CONECTADO_COM*1..3]: o Cypher não
aceita parâmetro nesse lugar, então o número (sempre um int nosso) é fixado por _fixar().
"""
from datetime import date

from neo4j import GraphDatabase
from neo4j.exceptions import AuthError, ServiceUnavailable, SessionExpired, TransientError

from app.config import MAX_SALTOS
from app.servicos.disjuntor import Disjuntor
from app.servicos.erros import BancoIndisponivel
from app.servicos.registro import Registro

# TransientError: enquanto o Neo4j está subindo ou parando, o servidor responde
# "DatabaseUnavailable"; para a tela, é o mesmo que estar fora do ar
ERROS_DE_CONEXAO = (ServiceUnavailable, SessionExpired, AuthError, TransientError)
PROPRIEDADES_EDITAVEIS = ("titulo", "mentor", "anos_experiencia")


def _fixar(cypher: str, **limites: int) -> str:
    """Troca marcadores __NOME__ por números inteiros (limites de saltos não aceitam $parâmetro)."""
    for nome, valor in limites.items():
        cypher = cypher.replace(f"__{nome.upper()}__", str(int(valor)))
    return cypher


class Neo4jService:
    def __init__(self, uri: str, user: str, password: str, database: str = "neo4j",
                 registro: Registro | None = None):
        self.registro = registro if registro is not None else Registro()
        self.database = database
        self.driver = GraphDatabase.driver(
            uri, auth=(user, password), connection_timeout=3,
            connection_acquisition_timeout=5, max_transaction_retry_time=3)
        self.disjuntor = Disjuntor("Neo4j")

    def _executar(self, cypher: str, **params) -> list[dict]:
        """Roda uma consulta Cypher e devolve as linhas como lista de dicionários.

        Antes, o disjuntor confere se não estamos na pausa depois de uma falha (disjuntor.py).
        """
        # no painel Bastidores vai a consulta inteira numa linha só (split() + join tiram as
        # quebras de linha e os espaços repetidos)
        comando = " ".join(cypher.split())
        self.disjuntor.conferir()
        try:
            with self.registro.medir("Neo4j", comando, erros_conexao=ERROS_DE_CONEXAO):
                with self.driver.session(database=self.database) as session:
                    resultado = session.run(cypher, **params)
                    linhas = [registro.data() for registro in resultado]
        except BancoIndisponivel:
            self.disjuntor.falhou()
            raise
        self.disjuntor.funcionou()
        return linhas

    # ---------- infraestrutura ----------

    def close(self) -> None:
        self.driver.close()

    # "RETURN 1" não lê nenhum dado: só prova que o servidor responde e que a senha vale.
    # Nunca levanta exceção; qualquer falha vira False.
    def ping(self) -> bool:
        try:
            self._executar("RETURN 1 AS ok")
            return True
        except Exception:
            return False

    # Apaga todos os nós; DETACH remove junto os relacionamentos (sem ele o Neo4j recusa).
    def apagar_tudo(self) -> None:
        self._executar("MATCH (n) DETACH DELETE n")

    # Constraint de unicidade também cria um índice que acelera o MATCH por essa propriedade.
    # IF NOT EXISTS deixa o método seguro de rodar várias vezes.
    def criar_esquema(self) -> None:
        self._executar("""
            CREATE CONSTRAINT pessoa_id_unico IF NOT EXISTS
            FOR (p:Pessoa) REQUIRE p.id IS UNIQUE""")
        self._executar("""
            CREATE CONSTRAINT habilidade_nome_unico IF NOT EXISTS
            FOR (h:Habilidade) REQUIRE h.nome IS UNIQUE""")
        self._executar("""
            CREATE CONSTRAINT empresa_nome_unico IF NOT EXISTS
            FOR (e:Empresa) REQUIRE e.nome IS UNIQUE""")
        self._executar("""
            CREATE INDEX pessoa_nome IF NOT EXISTS
            FOR (p:Pessoa) ON (p.nome)""")

    # ---------- pessoas ----------

    # MERGE por id: criar a mesma pessoa duas vezes atualiza as propriedades em vez de duplicar.
    def criar_pessoa(self, id: str, nome: str, titulo: str, mentor: bool = False,
                     anos_experiencia: int = 0) -> None:
        self._executar("""
            MERGE (p:Pessoa {id: $id})
            SET p.nome = $nome, p.titulo = $titulo,
                p.mentor = $mentor, p.anos_experiencia = $anos_experiencia""",
                       id=id, nome=nome, titulo=titulo, mentor=mentor,
                       anos_experiencia=anos_experiencia)

    # DETACH DELETE apaga o nó e todos os relacionamentos dele (conexões, habilidades, empregos).
    def remover_pessoa(self, id: str) -> None:
        self._executar("MATCH (p:Pessoa {id: $id}) DETACH DELETE p", id=id)

    # "SET p += $props" copia o dicionário para o nó sem apagar as demais propriedades.
    # As chaves são validadas antes, então ninguém grava propriedade arbitrária (ex.: id).
    def atualizar_pessoa(self, id: str, **props) -> None:
        invalidas = set(props) - set(PROPRIEDADES_EDITAVEIS)
        if invalidas:
            raise ValueError(f"Propriedade não editável: {', '.join(sorted(invalidas))}")
        if not props:
            return
        self._executar("MATCH (p:Pessoa {id: $id}) SET p += $props", id=id, props=props)

    # Procura o nó pelo id (campo com constraint de unicidade, logo a busca usa índice) e
    # devolve só as propriedades que a tela precisa; sem nó, a lista vem vazia e o retorno é None.
    def buscar_pessoa(self, id: str) -> dict | None:
        linhas = self._executar("""
            MATCH (p:Pessoa {id: $id})
            RETURN p.id AS id, p.nome AS nome, p.titulo AS titulo,
                   p.mentor AS mentor, p.anos_experiencia AS anos_experiencia""", id=id)
        return linhas[0] if linhas else None

    # ---------- catálogo (usado pela carga) ----------

    # MERGE = "ache ou crie": rodar a carga duas vezes não duplica a habilidade (o nome é único).
    # O SET fica fora do MERGE para atualizar a categoria se a habilidade já existia.
    def criar_habilidade(self, nome: str, categoria: str) -> None:
        self._executar("""
            MERGE (h:Habilidade {nome: $nome})
            SET h.categoria = $categoria""", nome=nome, categoria=categoria)

    # Mesmo raciocínio da habilidade: MERGE pelo nome evita empresas repetidas e o SET
    # grava ou corrige o setor.
    def criar_empresa(self, nome: str, setor: str) -> None:
        self._executar("""
            MERGE (e:Empresa {nome: $nome})
            SET e.setor = $setor""", nome=nome, setor=setor)

    # ---------- conexões ----------

    # A conexão é gravada em um sentido só (a)->(b), mas lida sempre sem direção.
    # O WHERE NOT (a)--(b) olha os dois sentidos: se já existe a-b ou b-a, nada é criado
    # e count(*) volta 0. Se uma das pessoas não existir, o MATCH não acha linhas e também dá 0.
    # "desde" é texto ISO calculado em Python (o grafo não usa tipos de data do Neo4j).
    def conectar(self, a: str, b: str) -> bool:
        if a == b:
            raise ValueError("Uma pessoa não pode se conectar consigo mesma.")
        linhas = self._executar("""
            MATCH (a:Pessoa {id: $a}), (b:Pessoa {id: $b})
            WHERE NOT (a)-[:CONECTADO_COM]-(b)
            CREATE (a)-[:CONECTADO_COM {desde: $desde}]->(b)
            RETURN count(*) AS criadas""", a=a, b=b, desde=date.today().isoformat())
        return linhas[0]["criadas"] > 0

    # Sem seta no padrão: casa a->b e b->a. count(r) > 0 sempre devolve uma linha (true/false).
    def estao_conectados(self, a: str, b: str) -> bool:
        linhas = self._executar("""
            MATCH (:Pessoa {id: $a})-[r:CONECTADO_COM]-(:Pessoa {id: $b})
            RETURN count(r) > 0 AS conectados""", a=a, b=b)
        return linhas[0]["conectados"]

    # Sem seta no padrão: pega quem eu conectei e quem me conectou (a conexão é gravada em um
    # sentido só). Só os ids, ordenados pelo nome da outra pessoa.
    def ids_conexoes(self, id: str) -> list[str]:
        linhas = self._executar("""
            MATCH (:Pessoa {id: $id})-[:CONECTADO_COM]-(outra:Pessoa)
            RETURN outra.id AS id
            ORDER BY outra.nome""", id=id)
        return [linha["id"] for linha in linhas]

    # Mesma consulta de ids_conexoes (padrão sem direção), mas devolvendo id, nome e título
    # para a tela listar as conexões sem precisar ir ao Mongo.
    def conexoes(self, id: str) -> list[dict]:
        return self._executar("""
            MATCH (:Pessoa {id: $id})-[:CONECTADO_COM]-(outra:Pessoa)
            RETURN outra.id AS id, outra.nome AS nome, outra.titulo AS titulo
            ORDER BY outra.nome""", id=id)

    # ---------- habilidades ----------

    # Um MERGE para a Habilidade (categoria "Outras" só quando é nova, via ON CREATE) e outro
    # para o relacionamento; repetir a chamada só atualiza o nível, não duplica nada.
    def definir_habilidade(self, pessoa_id: str, habilidade: str, nivel: int) -> None:
        if not isinstance(nivel, int) or not 1 <= nivel <= 5:
            raise ValueError("O nível deve ser um inteiro de 1 a 5.")
        self._executar("""
            MATCH (p:Pessoa {id: $pessoa_id})
            MERGE (h:Habilidade {nome: $habilidade})
              ON CREATE SET h.categoria = 'Outras'
            MERGE (p)-[ph:POSSUI_HABILIDADE]->(h)
            SET ph.nivel = $nivel""", pessoa_id=pessoa_id, habilidade=habilidade, nivel=nivel)

    # Apaga só o relacionamento POSSUI_HABILIDADE (DELETE ph); a Habilidade continua no
    # catálogo porque outras pessoas podem usá-la.
    def remover_habilidade(self, pessoa_id: str, habilidade: str) -> None:
        self._executar("""
            MATCH (:Pessoa {id: $pessoa_id})-[ph:POSSUI_HABILIDADE]->(:Habilidade {nome: $habilidade})
            DELETE ph""", pessoa_id=pessoa_id, habilidade=habilidade)

    # O nível mora no relacionamento (ph.nivel), não na Habilidade, pois cada pessoa tem o seu.
    # Ordena do maior nível para o menor e, no empate, pelo nome.
    def habilidades_de(self, id: str) -> list[dict]:
        return self._executar("""
            MATCH (:Pessoa {id: $id})-[ph:POSSUI_HABILIDADE]->(h:Habilidade)
            RETURN h.nome AS nome, h.categoria AS categoria, ph.nivel AS nivel
            ORDER BY nivel DESC, nome ASC""", id=id)

    # Substitui os interesses numa única consulta (uma transação, então nunca fica pela metade):
    # 1) apaga os QUER_APRENDER atuais (OPTIONAL MATCH não derruba a consulta se não houver nenhum);
    # 2) WITH DISTINCT p volta a uma linha só (o DELETE multiplicou as linhas);
    # 3) UNWIND percorre a lista nova e o MERGE cria cada relacionamento (lista vazia = só apaga).
    def definir_interesses(self, pessoa_id: str, habilidades: list[str]) -> None:
        self._executar("""
            MATCH (p:Pessoa {id: $pessoa_id})
            OPTIONAL MATCH (p)-[antigo:QUER_APRENDER]->(:Habilidade)
            DELETE antigo
            WITH DISTINCT p
            UNWIND $habilidades AS nome
            MERGE (h:Habilidade {nome: nome})
              ON CREATE SET h.categoria = 'Outras'
            MERGE (p)-[:QUER_APRENDER]->(h)""", pessoa_id=pessoa_id, habilidades=habilidades)

    # Segue as setas QUER_APRENDER (o que a pessoa quer aprender, não o que sabe) e devolve
    # só os nomes em ordem alfabética; é a lista usada na recomendação de mentores.
    def interesses_de(self, id: str) -> list[str]:
        linhas = self._executar("""
            MATCH (:Pessoa {id: $id})-[:QUER_APRENDER]->(h:Habilidade)
            RETURN h.nome AS nome
            ORDER BY nome""", id=id)
        return [linha["nome"] for linha in linhas]

    # Catálogo inteiro: todos os nós Habilidade, agrupados por categoria na ordenação,
    # para a tela montar listas de escolha.
    def listar_habilidades(self) -> list[dict]:
        return self._executar("""
            MATCH (h:Habilidade)
            RETURN h.nome AS nome, h.categoria AS categoria
            ORDER BY categoria, nome""")

    # ---------- trabalho ----------

    # O MERGE do TRABALHA_EM usa cargo e desde como chave: a mesma pessoa pode ter cargos
    # diferentes na mesma empresa, mas repetir o mesmo cargo/data não duplica.
    # "ate" fica fora do MERGE (é só um valor): null = emprego atual.
    def registrar_trabalho(self, pessoa_id: str, empresa: str, cargo: str, desde: str,
                           ate: str | None = None) -> None:
        self._executar("""
            MATCH (p:Pessoa {id: $pessoa_id})
            MERGE (e:Empresa {nome: $empresa})
              ON CREATE SET e.setor = 'Não informado'
            MERGE (p)-[t:TRABALHA_EM {cargo: $cargo, desde: $desde}]->(e)
            SET t.ate = $ate""", pessoa_id=pessoa_id, empresa=empresa, cargo=cargo,
                       desde=desde, ate=ate)

    # Casa o relacionamento exato por cargo e desde (a chave usada no MERGE de registrar_trabalho)
    # e apaga só ele; a Empresa permanece, pois outras pessoas podem trabalhar nela.
    def remover_trabalho(self, pessoa_id: str, empresa: str, cargo: str, desde: str) -> None:
        self._executar("""
            MATCH (:Pessoa {id: $pessoa_id})-[t:TRABALHA_EM {cargo: $cargo, desde: $desde}]->
                  (:Empresa {nome: $empresa})
            DELETE t""", pessoa_id=pessoa_id, empresa=empresa, cargo=cargo, desde=desde)

    # Empregos atuais primeiro (ate nulo), depois os mais recentes.
    def trabalhos_de(self, id: str) -> list[dict]:
        return self._executar("""
            MATCH (:Pessoa {id: $id})-[t:TRABALHA_EM]->(e:Empresa)
            RETURN e.nome AS empresa, e.setor AS setor, t.cargo AS cargo,
                   t.desde AS desde, t.ate AS ate
            ORDER BY t.ate IS NULL DESC, t.desde DESC""", id=id)

    # Quem passou pela mesma empresa (atual ou antiga); c <> eu tira a própria pessoa.
    def colegas_de_empresa(self, id: str) -> list[dict]:
        return self._executar("""
            MATCH (eu:Pessoa {id: $id})-[:TRABALHA_EM]->(e:Empresa)<-[:TRABALHA_EM]-(colega:Pessoa)
            WHERE colega <> eu
            RETURN DISTINCT colega.id AS id, colega.nome AS nome, colega.titulo AS titulo,
                            e.nome AS empresa
            ORDER BY nome, empresa""", id=id)

    # Casa cada Pessoa com uma seta POSSUI_HABILIDADE apontando para a Habilidade pedida; o
    # WHERE filtra pelo nível mínimo no relacionamento. Ordem: quem tem nível mais alto primeiro.
    def pessoas_com_habilidade(self, habilidade: str, nivel_minimo: int = 1) -> list[dict]:
        return self._executar("""
            MATCH (p:Pessoa)-[ph:POSSUI_HABILIDADE]->(:Habilidade {nome: $habilidade})
            WHERE ph.nivel >= $nivel_minimo
            RETURN p.id AS id, p.nome AS nome, p.titulo AS titulo, ph.nivel AS nivel
            ORDER BY nivel DESC, nome ASC""", habilidade=habilidade, nivel_minimo=nivel_minimo)

    # ---------- caminhos e rede ----------

    # shortestPath acha o caminho com menos saltos, ignorando o sentido das conexões, até
    # MAX_SALTOS. Ele falha se origem e destino forem o mesmo nó, por isso esse caso é
    # tratado antes, em Python. Sem caminho (ou pessoa inexistente) o MATCH não devolve
    # linhas e o método devolve None.
    def menor_caminho(self, origem: str, destino: str) -> dict | None:
        if origem == destino:
            pessoa = self.buscar_pessoa(origem)
            if pessoa is None:
                return None
            return {"pessoas": [{"id": pessoa["id"], "nome": pessoa["nome"],
                                 "titulo": pessoa["titulo"]}], "graus": 0}
        linhas = self._executar(_fixar("""
            MATCH (a:Pessoa {id: $origem}), (b:Pessoa {id: $destino})
            MATCH caminho = shortestPath((a)-[:CONECTADO_COM*..__MAX__]-(b))
            RETURN [n IN nodes(caminho) | {id: n.id, nome: n.nome, titulo: n.titulo}] AS pessoas,
                   length(caminho) AS graus""", max=MAX_SALTOS), origem=origem, destino=destino)
        return linhas[0] if linhas else None

    # [:CONECTADO_COM*1..N] anda de 1 a N saltos; uma pessoa pode ser alcançada por vários
    # caminhos, então min(length(...)) fica com o menor (o grau de separação real).
    def rede_por_grau(self, id: str, max_grau: int = 3) -> list[dict]:
        return self._executar(_fixar("""
            MATCH caminho = (eu:Pessoa {id: $id})-[:CONECTADO_COM*1..__MAX__]-(p:Pessoa)
            WHERE p <> eu
            RETURN p.id AS id, p.nome AS nome, p.titulo AS titulo, min(length(caminho)) AS grau
            ORDER BY grau, nome""", max=max_grau), id=id)

    # Nós = a pessoa (grau 0) + a rede até max_grau. Arestas = conexões entre esses nós.
    # O padrão das arestas tem seta para ler cada conexão uma vez só (ela é gravada em um sentido).
    def subgrafo_da_rede(self, id: str, max_grau: int = 2) -> dict:
        pessoa = self.buscar_pessoa(id)
        if pessoa is None:
            return {"nos": [], "arestas": []}
        nos = [{"id": pessoa["id"], "nome": pessoa["nome"], "titulo": pessoa["titulo"], "grau": 0}]
        nos += self.rede_por_grau(id, max_grau)
        linhas = self._executar("""
            MATCH (a:Pessoa)-[:CONECTADO_COM]->(b:Pessoa)
            WHERE a.id IN $ids AND b.id IN $ids
            RETURN a.id AS de, b.id AS para""", ids=[no["id"] for no in nos])
        return {"nos": nos, "arestas": [[linha["de"], linha["para"]] for linha in linhas]}

    # Amigo de amigo: eu - amigo - sugestao, onde eu e sugestao ainda não estão conectados.
    # collect(DISTINCT ...) junta os amigos em comum numa lista e size() os conta.
    def sugerir_conexoes(self, id: str, limite: int = 5) -> list[dict]:
        return self._executar("""
            MATCH (eu:Pessoa {id: $id})-[:CONECTADO_COM]-(amigo:Pessoa)-[:CONECTADO_COM]-(sugestao:Pessoa)
            WHERE sugestao <> eu AND NOT (eu)-[:CONECTADO_COM]-(sugestao)
            WITH sugestao, collect(DISTINCT amigo.nome) AS amigos
            RETURN sugestao.id AS id, sugestao.nome AS nome, sugestao.titulo AS titulo,
                   size(amigos) AS em_comum, amigos
            ORDER BY em_comum DESC, nome ASC
            LIMIT $limite""", id=id, limite=limite)

    # ---------- recomendação de mentores ----------

    # Mentor candidato = pessoa com mentor = true e nível >= 4 em alguma habilidade de interesse.
    # Pontuação = 3 * (nº de habilidades que ela ensina) + nível médio + amigos em comum
    #             - graus de separação (6 se não há caminho).
    # Cada WITH fecha uma etapa e agrupa: collect() junta as habilidades por mentor;
    # shortestPath (OPTIONAL: pode não haver caminho) dá os graus e o 1º intermediário ("via");
    # o segundo OPTIONAL MATCH conta os amigos em comum; count(DISTINCT) evita contar repetido.
    def recomendar_mentores(self, id: str, habilidades: list[str] | None = None,
                            limite: int = 10) -> list[dict]:
        if habilidades is None:
            habilidades = self.interesses_de(id)
        if not habilidades:
            return []
        return self._executar(_fixar("""
            MATCH (eu:Pessoa {id: $id})
            MATCH (m:Pessoa)-[ph:POSSUI_HABILIDADE]->(h:Habilidade)
            WHERE m.mentor = true AND m <> eu AND ph.nivel >= 4 AND h.nome IN $habilidades
            WITH eu, m, collect({nome: h.nome, nivel: ph.nivel}) AS habilidades, avg(ph.nivel) AS nivel_medio
            OPTIONAL MATCH caminho = shortestPath((eu)-[:CONECTADO_COM*..__MAX__]-(m))
            WITH eu, m, habilidades, nivel_medio, caminho
            OPTIONAL MATCH (eu)-[:CONECTADO_COM]-(comum:Pessoa)-[:CONECTADO_COM]-(m)
            WITH m, habilidades, nivel_medio, caminho, count(DISTINCT comum) AS em_comum
            WITH m, habilidades, nivel_medio, em_comum,
                 CASE WHEN caminho IS NULL THEN null ELSE length(caminho) END AS graus,
                 CASE WHEN caminho IS NULL OR length(caminho) < 2 THEN null ELSE nodes(caminho)[1].nome END AS via
            RETURN m.id AS id, m.nome AS nome, m.titulo AS titulo, habilidades, graus, em_comum, via,
                   3 * size(habilidades) + nivel_medio + em_comum - coalesce(graus, __MAX__) AS pontuacao
            ORDER BY pontuacao DESC, nome ASC LIMIT $limite""", max=MAX_SALTOS),
                              id=id, habilidades=habilidades, limite=limite)
