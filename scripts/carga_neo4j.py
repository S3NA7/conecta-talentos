"""Carga do Neo4j: pessoas, habilidades, empresas, conexões e empregos.

Cada consulta recebe uma lista de linhas por parâmetro e usa UNWIND para criar tudo de uma vez:
uma ida ao banco por tipo de dado, em vez de uma por registro.
"""
from scripts.dados_exemplo import CONEXOES, EMPRESAS, HABILIDADES, PESSOAS, TRABALHOS


def _desde_da_conexao(posicao: int) -> str:
    """Data ISO fixa para cada conexão (o grafo guarda datas como texto)."""
    return f"{2022 + posicao % 4}-{posicao * 5 % 12 + 1:02d}-{posicao * 7 % 28 + 1:02d}"


def carregar(neo4j_svc) -> dict:
    """Apaga o grafo, recria constraints e grava todos os nós e relacionamentos."""
    neo4j_svc.apagar_tudo()
    neo4j_svc.criar_esquema()

    # nós do catálogo: uma linha por habilidade e por empresa
    neo4j_svc._executar("""
        UNWIND $linhas AS l
        CREATE (:Habilidade {nome: l.nome, categoria: l.categoria})""", linhas=HABILIDADES)
    neo4j_svc._executar("""
        UNWIND $linhas AS l
        CREATE (:Empresa {nome: l.nome, setor: l.setor})""", linhas=EMPRESAS)

    neo4j_svc._executar("""
        UNWIND $linhas AS l
        CREATE (:Pessoa {id: l.id, nome: l.nome, titulo: l.titulo,
                         mentor: l.mentor, anos_experiencia: l.anos_experiencia})""",
                        linhas=[{k: p[k] for k in ("id", "nome", "titulo", "mentor", "anos_experiencia")}
                                for p in PESSOAS])

    # conexão gravada em um sentido só; as consultas a leem sem direção
    neo4j_svc._executar("""
        UNWIND $linhas AS l
        MATCH (a:Pessoa {id: l.de}), (b:Pessoa {id: l.para})
        CREATE (a)-[:CONECTADO_COM {desde: l.desde}]->(b)""",
                        linhas=[{"de": a, "para": b, "desde": _desde_da_conexao(i)}
                                for i, (a, b) in enumerate(CONEXOES)])

    # nível da habilidade mora no relacionamento
    neo4j_svc._executar("""
        UNWIND $linhas AS l
        MATCH (p:Pessoa {id: l.pessoa}), (h:Habilidade {nome: l.habilidade})
        CREATE (p)-[:POSSUI_HABILIDADE {nivel: l.nivel}]->(h)""",
                        linhas=[{"pessoa": p["id"], "habilidade": h, "nivel": n}
                                for p in PESSOAS for h, n in p["habilidades"].items()])

    neo4j_svc._executar("""
        UNWIND $linhas AS l
        MATCH (p:Pessoa {id: l.pessoa}), (h:Habilidade {nome: l.habilidade})
        CREATE (p)-[:QUER_APRENDER]->(h)""",
                        linhas=[{"pessoa": p["id"], "habilidade": h}
                                for p in PESSOAS for h in p["quer_aprender"]])

    # ate nulo = emprego atual
    neo4j_svc._executar("""
        UNWIND $linhas AS l
        MATCH (p:Pessoa {id: l.pessoa}), (e:Empresa {nome: l.empresa})
        CREATE (p)-[:TRABALHA_EM {cargo: l.cargo, desde: l.desde, ate: l.ate}]->(e)""",
                        linhas=[{"pessoa": t["pessoa_id"], "empresa": t["empresa"], "cargo": t["cargo"],
                                 "desde": t["desde"], "ate": t["ate"]} for t in TRABALHOS])

    return {"pessoas": len(PESSOAS), "habilidades": len(HABILIDADES), "empresas": len(EMPRESAS),
            "conexoes": len(CONEXOES), "trabalhos": len(TRABALHOS)}
