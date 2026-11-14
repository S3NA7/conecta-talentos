"""Dados de exemplo (fictícios) compartilhados pelos três bancos.

Uma única fonte: o Mongo guarda os perfis e posts, o Neo4j guarda a rede, as habilidades e os
empregos, o Redis guarda os contadores. Os testes dependem destes valores exatos.
Nada é aleatório sem semente fixa (random.Random(42)).
"""
import random
import unicodedata
from datetime import datetime, timedelta, timezone

# ---------- empresas e habilidades ----------

EMPRESAS = [
    {"nome": "DataNorte", "setor": "Dados"},
    {"nome": "Mangue Labs", "setor": "Inteligência Artificial"},
    {"nome": "Banco Sertão", "setor": "Financeiro"},
    {"nome": "Sol Varejo", "setor": "Varejo"},
    {"nome": "Aurora Sistemas", "setor": "Software"},
    {"nome": "Litoral Tech", "setor": "Software"},
    {"nome": "Maré Jogos", "setor": "Jogos"},
    {"nome": "Ponte Pagamentos", "setor": "Fintech"},
    {"nome": "Farol Educação", "setor": "Educação"},
    {"nome": "Verde Saúde", "setor": "Saúde"},
    {"nome": "Cais Logística", "setor": "Logística"},
    {"nome": "Nuvem Nordeste", "setor": "Computação em Nuvem"},
]

_CATEGORIAS = {
    "Dados": ["Python", "SQL", "Spark", "MongoDB", "Redis", "Neo4j", "Machine Learning", "Power BI"],
    "Desenvolvimento": ["JavaScript", "React", "Node.js", "Java", "API REST", "TypeScript"],
    "Produto e Design": ["UX Design", "Figma", "Gestão de Produto", "Scrum", "Pesquisa com Usuários"],
    "Infraestrutura": ["Docker", "Kubernetes", "AWS", "Linux", "Segurança da Informação", "DevOps"],
}
HABILIDADES = [{"nome": nome, "categoria": categoria}
               for categoria, nomes in _CATEGORIAS.items() for nome in nomes]

# ---------- pessoas ----------
# (id, nome, título, empresa atual, mentor, anos, habilidades {nome: nível}, quer aprender)
_BASE = [
    ("u001", "Ana Beatriz Lima", "Analista de Dados Júnior", "DataNorte", False, 2,
     {"Python": 3, "SQL": 4, "Power BI": 3}, ["Neo4j", "Machine Learning", "Kubernetes"]),
    ("u002", "Bruno Carvalho", "Engenheiro de Dados Pleno", "DataNorte", False, 5,
     {"Python": 4, "Spark": 4, "SQL": 4, "MongoDB": 3}, []),
    ("u003", "Camila Nóbrega", "Cientista de Dados Sênior", "Mangue Labs", True, 9,
     {"Machine Learning": 5, "Python": 5, "SQL": 4}, []),
    ("u004", "Diego Farias", "Arquiteto de Dados", "Banco Sertão", True, 12,
     {"Neo4j": 5, "MongoDB": 5, "Redis": 4, "SQL": 5}, []),
    ("u005", "Eduarda Monteiro", "Analista de BI", "Sol Varejo", False, 4,
     {"Power BI": 5, "SQL": 4}, []),
    ("u006", "Felipe Gadelha", "Engenheiro de Machine Learning", "Mangue Labs", True, 7,
     {"Machine Learning": 4, "Python": 5, "Docker": 3}, []),
    ("u007", "Marina Albuquerque", "Engenheira de Dados Sênior", "DataNorte", True, 8,
     {"Spark": 5, "Python": 5, "MongoDB": 4, "Neo4j": 4}, []),
    ("u008", "Gustavo Pessoa", "Administrador de Banco de Dados", "Banco Sertão", False, 10,
     {"SQL": 5, "Redis": 4, "MongoDB": 4}, []),
    ("u009", "Helena Dantas", "Desenvolvedora Full Stack", "Aurora Sistemas", True, 8,
     {"JavaScript": 5, "React": 5, "Node.js": 4, "API REST": 4}, []),
    ("u010", "Igor Medeiros", "Desenvolvedor Back-end", "Aurora Sistemas", False, 4,
     {"Java": 4, "API REST": 4, "SQL": 3}, []),
    ("u011", "Juliana Queiroz", "Desenvolvedora Front-end", "Litoral Tech", False, 3,
     {"React": 4, "TypeScript": 3, "JavaScript": 4}, ["UX Design", "Node.js"]),
    ("u012", "Kleber Azevedo", "Tech Lead", "Litoral Tech", True, 11,
     {"Java": 5, "API REST": 5, "Node.js": 4, "Docker": 4}, []),
    ("u013", "Larissa Toscano", "Desenvolvedora Mobile", "Maré Jogos", False, 5,
     {"TypeScript": 4, "React": 4}, []),
    ("u014", "Mateus Rangel", "Desenvolvedor Back-end", "Ponte Pagamentos", False, 6,
     {"Node.js": 5, "MongoDB": 4, "Redis": 4}, []),
    ("u015", "Natália Ramalho", "Engenheira de Software Sênior", "Ponte Pagamentos", True, 9,
     {"TypeScript": 5, "Node.js": 5, "API REST": 5}, []),
    ("u016", "Otávio Lucena", "Estagiário de Desenvolvimento", "Aurora Sistemas", False, 1,
     {"JavaScript": 2, "SQL": 2}, ["React", "Node.js", "Docker"]),
    ("u017", "Patrícia Vilar", "Gerente de Produto", "Farol Educação", True, 10,
     {"Gestão de Produto": 5, "Scrum": 5, "Pesquisa com Usuários": 4}, []),
    ("u018", "Rafael Cunha", "Designer de Produto", "Farol Educação", False, 5,
     {"Figma": 5, "UX Design": 4}, []),
    ("u019", "Sabrina Leite", "Pesquisadora de UX", "Verde Saúde", True, 7,
     {"Pesquisa com Usuários": 5, "UX Design": 5}, []),
    ("u020", "Thiago Bezerra", "Product Owner", "Verde Saúde", False, 6,
     {"Scrum": 4, "Gestão de Produto": 4}, []),
    ("u021", "Úrsula Maia", "Head de Design", "Sol Varejo", True, 13,
     {"UX Design": 5, "Figma": 5, "Gestão de Produto": 4}, []),
    ("u022", "Vinícius Paiva", "Scrum Master", "Cais Logística", False, 6,
     {"Scrum": 5}, []),
    ("u023", "Yasmin Coutinho", "Designer de Interface Júnior", "Maré Jogos", False, 2,
     {"Figma": 3, "UX Design": 3}, ["Pesquisa com Usuários", "Gestão de Produto"]),
    ("u024", "Wagner Trigueiro", "Engenheiro DevOps", "Nuvem Nordeste", True, 9,
     {"Kubernetes": 5, "Docker": 5, "AWS": 4, "DevOps": 5}, []),
    ("u025", "Aline Cavalcanti", "Analista de Segurança", "Banco Sertão", True, 8,
     {"Segurança da Informação": 5, "Linux": 4}, []),
    ("u026", "Caio Sobreira", "Engenheiro de Confiabilidade (SRE)", "Nuvem Nordeste", False, 5,
     {"Kubernetes": 4, "Linux": 5, "AWS": 4}, []),
    ("u027", "Débora Figueiredo", "Arquiteta de Nuvem", "Nuvem Nordeste", True, 12,
     {"AWS": 5, "Kubernetes": 4, "Docker": 4}, []),
    ("u028", "Emanuel Lins", "Administrador de Sistemas", "Cais Logística", False, 7,
     {"Linux": 5, "Docker": 3}, []),
    ("u029", "Fernanda Arruda", "Engenheira de Plataforma", "Ponte Pagamentos", False, 4,
     {"Docker": 4, "DevOps": 3}, ["Kubernetes", "AWS"]),
    ("u030", "José Tavares", "Recém-formado em Sistemas de Informação", None, False, 0,
     {"Python": 2, "SQL": 2}, ["Python", "Machine Learning"]),
]

# id -> (cidade, estado, resumo, formação [(instituição, curso, nível, início, fim)],
#        certificações [(nome, emissor, ano)])
_PERFIS = {
    "u001": ("João Pessoa", "PB",
             "Analista de dados em início de carreira, apaixonada por transformar planilhas em histórias. "
             "Estou aprendendo bancos de grafos e quero chegar a Machine Learning.",
             [("UFPB", "Sistemas de Informação", "Graduação", 2019, 2023)], []),
    "u002": ("João Pessoa", "PB",
             "Engenheiro de dados focado em pipelines confiáveis e bem documentados. "
             "Gosto de ensinar o time a olhar para o custo de cada etapa.",
             [("UFPB", "Ciência da Computação", "Graduação", 2015, 2019)], []),
    "u003": ("Recife", "PE",
             "Cientista de dados com nove anos de estrada em modelos de previsão e recomendação. "
             "Mentoro pessoas que querem entrar em Machine Learning sem medo de estatística.",
             [("UFPE", "Estatística", "Graduação", 2010, 2014), ("UFPE", "Ciência da Computação", "Mestrado", 2015, 2017)],
             [("TensorFlow Developer Certificate", "Google", 2022)]),
    "u004": ("Natal", "RN",
             "Arquiteto de dados com doze anos de experiência em bancos relacionais, de documentos e de grafos. "
             "Acredito em escolher o banco pela pergunta, não pela moda.",
             [("UFRN", "Engenharia da Computação", "Graduação", 2008, 2012)],
             [("MongoDB Certified DBA", "MongoDB", 2021), ("Neo4j Certified Professional", "Neo4j", 2023)]),
    "u005": ("Recife", "PE",
             "Analista de BI que gosta de painéis simples e decisões baseadas em dados. "
             "Ajudo áreas de negócio a perguntar melhor.",
             [("UNICAP", "Sistemas de Informação", "Graduação", 2016, 2020)], []),
    "u006": ("Recife", "PE",
             "Engenheiro de machine learning que leva modelos do notebook para a produção. "
             "Cuido de monitoramento, versionamento e de tudo que acontece depois do treino.",
             [("CESAR School", "Ciência da Computação", "Graduação", 2013, 2017)],
             [("AWS Machine Learning Specialty", "Amazon Web Services", 2023)]),
    "u007": ("João Pessoa", "PB",
             "Engenheira de dados sênior, com experiência em data lakes e processamento distribuído. "
             "Trabalhei em banco antes de migrar para o mundo de dados e hoje mentoro quem quer fazer o mesmo.",
             [("UNIPÊ", "Ciência da Computação", "Graduação", 2012, 2016)],
             [("MongoDB Associate Developer", "MongoDB", 2024)]),
    "u008": ("Fortaleza", "CE",
             "DBA há dez anos, responsável por manter bancos rápidos, seguros e restauráveis. "
             "Gosto de automatizar tudo o que se repete.",
             [("UFC", "Ciência da Computação", "Graduação", 2011, 2015)], []),
    "u009": ("Salvador", "BA",
             "Desenvolvedora full stack com foco em aplicações web acessíveis e rápidas. "
             "Organizo meetups de desenvolvimento e gosto de mentorar quem está começando.",
             [("UFBA", "Ciência da Computação", "Graduação", 2014, 2018)],
             [("Meta Front-End Developer", "Meta", 2022)]),
    "u010": ("Salvador", "BA",
             "Desenvolvedor back-end que valoriza APIs bem desenhadas e testes automatizados. "
             "Atualmente estudo arquitetura de serviços.",
             [("UNIFACS", "Análise e Desenvolvimento de Sistemas", "Graduação", 2018, 2021)], []),
    "u011": ("Maceió", "AL",
             "Desenvolvedora front-end com olhar de design. Quero entender melhor UX e começar a trabalhar também com o lado do servidor.",
             [("UFAL", "Sistemas de Informação", "Graduação", 2018, 2022)], []),
    "u012": ("Maceió", "AL",
             "Tech lead com onze anos de código, liderando times de back-end. "
             "Acredito em revisão de código gentil e em documentação viva.",
             [("UFAL", "Ciência da Computação", "Graduação", 2009, 2013)],
             [("Oracle Certified Professional Java", "Oracle", 2019)]),
    "u013": ("Aracaju", "SE",
             "Desenvolvedora mobile apaixonada por interfaces fluidas. Trabalho com jogos casuais e aplicativos de utilidade.",
             [("UFS", "Ciência da Computação", "Graduação", 2015, 2019)], []),
    "u014": ("Aracaju", "SE",
             "Desenvolvedor back-end em meios de pagamento, com foco em desempenho e consistência de dados.",
             [("UFS", "Sistemas de Informação", "Graduação", 2014, 2018)], []),
    "u015": ("Recife", "PE",
             "Engenheira de software sênior, escrevo código limpo e ajudo o time a manter a qualidade. "
             "Gosto de mentorar pessoas em início de carreira.",
             [("UFPE", "Engenharia da Computação", "Graduação", 2012, 2016)],
             [("Node.js Application Developer", "OpenJS Foundation", 2021)]),
    "u016": ("Salvador", "BA",
             "Estagiário de desenvolvimento, curioso e disposto a aprender. "
             "Quero dominar React, Node.js e Docker até o fim do estágio.",
             [("UNIFACS", "Análise e Desenvolvimento de Sistemas", "Graduação", 2024, 2026)], []),
    "u017": ("João Pessoa", "PB",
             "Gerente de produto na área de educação, com dez anos entre tecnologia e negócio. "
             "Gosto de descoberta contínua e de conversar com usuários toda semana.",
             [("UFPB", "Administração", "Graduação", 2010, 2014), ("UFPB", "Gestão de Projetos", "Especialização", 2015, 2016)],
             [("Certified Scrum Product Owner", "Scrum Alliance", 2020)]),
    "u018": ("João Pessoa", "PB",
             "Designer de produto que cuida de sistemas de design e prototipação. Apaixonado por consistência visual.",
             [("UFPB", "Design", "Graduação", 2015, 2019)], []),
    "u019": ("Fortaleza", "CE",
             "Pesquisadora de UX na área de saúde. Transformo entrevistas e testes de usabilidade em decisões de produto.",
             [("UFC", "Psicologia", "Graduação", 2012, 2017), ("UFC", "Design de Interação", "Especialização", 2018, 2019)],
             [("NN/g UX Certification", "Nielsen Norman Group", 2022)]),
    "u020": ("Fortaleza", "CE",
             "Product owner de plataformas de saúde digital, entre o time técnico e o negócio. Priorizar é a parte mais difícil e mais divertida.",
             [("UNIFOR", "Sistemas de Informação", "Graduação", 2014, 2018)], []),
    "u021": ("Recife", "PE",
             "Head de design com treze anos de carreira, liderando times de produto no varejo. "
             "Gosto de ensinar design como decisão, não como enfeite.",
             [("UFPE", "Design", "Graduação", 2008, 2012)],
             [("Certified Usability Analyst", "Human Factors International", 2018)]),
    "u022": ("Natal", "RN",
             "Scrum Master que ajuda equipes de logística a entregar com menos atrito e mais clareza.",
             [("UFRN", "Administração", "Graduação", 2014, 2018)], []),
    "u023": ("Salvador", "BA",
             "Designer de interface júnior em um estúdio de jogos. Quero aprender pesquisa com usuários e como produtos são priorizados.",
             [("UNEB", "Design Gráfico", "Graduação", 2020, 2024)], []),
    "u024": ("Recife", "PE",
             "Engenheiro DevOps com nove anos de experiência em automação, contêineres e entrega contínua. "
             "Falo em eventos e mentoro quem quer entrar na área.",
             [("CESAR School", "Engenharia de Software", "Graduação", 2012, 2016)],
             [("Certified Kubernetes Administrator", "CNCF", 2021), ("AWS Solutions Architect", "Amazon Web Services", 2022)]),
    "u025": ("Natal", "RN",
             "Analista de segurança no setor financeiro. Gosto de explicar riscos de forma simples para quem não é da área.",
             [("UFRN", "Tecnologia da Informação", "Graduação", 2012, 2016)],
             [("Security+", "CompTIA", 2019)]),
    "u026": ("Recife", "PE",
             "Engenheiro de confiabilidade focado em observabilidade e resposta a incidentes.",
             [("UFPE", "Ciência da Computação", "Graduação", 2015, 2019)], []),
    "u027": ("Recife", "PE",
             "Arquiteta de nuvem com doze anos de experiência e muitas migrações no currículo. "
             "Mentora de quem quer entender AWS na prática.",
             [("UFPE", "Engenharia da Computação", "Graduação", 2008, 2013)],
             [("AWS Solutions Architect Professional", "Amazon Web Services", 2020)]),
    "u028": ("Natal", "RN",
             "Administrador de sistemas Linux, apaixonado por terminal e por automação com scripts.",
             [("IFRN", "Redes de Computadores", "Tecnólogo", 2013, 2016)], []),
    "u029": ("Recife", "PE",
             "Engenheira de plataforma que constrói ferramentas internas para times de desenvolvimento. Estudando Kubernetes e AWS.",
             [("UFPE", "Sistemas de Informação", "Graduação", 2017, 2021)], []),
    "u030": ("Campina Grande", "PB",
             "Recém-formado em Sistemas de Informação, à procura da primeira oportunidade. "
             "Tenho base em Python e SQL e quero seguir para ciência de dados.",
             [("UFCG", "Sistemas de Informação", "Graduação", 2021, 2025)], []),
}

# ---------- trabalhos ----------

TRABALHOS_ANTERIORES = [
    {"pessoa_id": "u007", "empresa": "Banco Sertão", "cargo": "Analista de Dados", "desde": "2016-02", "ate": "2020-12"},
    {"pessoa_id": "u004", "empresa": "DataNorte", "cargo": "Engenheiro de Dados", "desde": "2012-01", "ate": "2018-06"},
    {"pessoa_id": "u012", "empresa": "Aurora Sistemas", "cargo": "Desenvolvedor", "desde": "2013-03", "ate": "2019-08"},
    {"pessoa_id": "u024", "empresa": "Cais Logística", "cargo": "Analista de Infraestrutura", "desde": "2015-05", "ate": "2019-10"},
]

ANO_DE_REFERENCIA = 2026


def _mes_seguinte(ano_mes: str) -> str:
    ano, mes = int(ano_mes[:4]), int(ano_mes[5:])
    return f"{ano + (mes == 12)}-{mes % 12 + 1:02d}"


def _desde_do_emprego_atual(numero: int, anos: int, anterior: dict | None) -> str:
    """Quem tinha emprego anterior começa no mês seguinte ao fim dele; os demais, a partir dos anos de experiência."""
    if anterior is not None:
        return _mes_seguinte(anterior["ate"])
    return f"{ANO_DE_REFERENCIA - max(1, anos // 2)}-{numero % 12 + 1:02d}"


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode()


def _montar_pessoas() -> tuple[list[dict], list[dict]]:
    anteriores = {t["pessoa_id"]: t for t in TRABALHOS_ANTERIORES}
    pessoas, trabalhos = [], []
    for id_, nome, titulo, empresa, mentor, anos, habilidades, quer in _BASE:
        cidade, estado, resumo, formacao, certificacoes = _PERFIS[id_]
        pessoas.append({
            "id": id_, "nome": nome, "email": _sem_acento(nome.split()[0]).lower() + "@exemplo.com",
            "titulo": titulo, "empresa": empresa, "mentor": mentor, "anos_experiencia": anos,
            "habilidades": habilidades, "quer_aprender": quer,
            "resumo": resumo, "localizacao": {"cidade": cidade, "estado": estado},
            "formacao": [{"instituicao": i, "curso": c, "nivel": n, "inicio": a, "fim": f}
                         for i, c, n, a, f in formacao],
            "certificacoes": [{"nome": n, "emissor": e, "ano": a} for n, e, a in certificacoes],
        })
        if id_ in anteriores:
            trabalhos.append(anteriores[id_])
        if empresa is not None:
            desde = _desde_do_emprego_atual(int(id_[1:]), anos, anteriores.get(id_))
            trabalhos.append({"pessoa_id": id_, "empresa": empresa, "cargo": titulo, "desde": desde, "ate": None})
    return pessoas, trabalhos


PESSOAS, TRABALHOS = _montar_pessoas()

# ---------- conexões ----------

_CONEXOES_TEXTO = (
    "1-2 1-3 2-3 2-4 3-5 4-5 4-6 5-7 6-7 6-8 7-8 1-5 "
    "9-10 9-11 10-11 10-12 11-13 12-13 12-14 13-15 14-15 14-16 15-16 9-13 "
    "17-18 17-19 18-19 18-20 19-21 20-21 20-22 21-23 22-23 17-21 "
    "24-25 24-26 25-26 25-27 26-28 27-28 27-29 28-29 "
    "4-9 12-17 20-24 6-11 15-19 22-26 8-14 3-12 16-21 13-24 7-25"
)
CONEXOES = [tuple(f"u{int(n):03d}" for n in par.split("-")) for par in _CONEXOES_TEXTO.split()]

# ---------- posts ----------

# (autor, texto, tags, imagem). Os três posts com imagem usam as chaves de IMAGENS.
_POSTS = [
    ("u001", "Terminei meu primeiro dashboard no Power BI para o time comercial. Aprendi muito sobre modelagem de dados no caminho!", ["dados", "carreira"], None),
    ("u001", "Alguém tem indicação de material para começar com bancos de grafos? Quero entender Neo4j e ainda não sei por onde começar.", ["nosql", "dados"], None),
    ("u001", "Primeira semana estudando Cypher: pensar em relacionamentos em vez de tabelas muda totalmente a forma de enxergar os dados.", ["nosql", "carreira"], None),
    ("u002", "Migramos um pipeline de ETL de horas para minutos usando Spark com um particionamento melhor. Vale rever os joins antes de aumentar o cluster.", ["dados"], None),
    ("u003", "Compartilho o comparativo de modelos que apresentei hoje no meetup de ciência de dados. Menos complexidade rendeu um resultado melhor do que eu esperava.", ["dados", "eventos"], "comparativo"),
    ("u003", "Estou com vagas de mentoria abertas para quem quer entrar em Machine Learning. Conversa de 30 minutos, sem compromisso.", ["mentoria", "carreira"], None),
    ("u004", "Modelar bem vem antes de escolher o banco: cada tipo de dado pede a ferramenta certa. Documento, chave-valor e grafo convivem muito bem no mesmo sistema.", ["nosql", "dados"], None),
    ("u004", "Dica de arquiteto: desenhe primeiro as perguntas que o sistema precisa responder e só depois o esquema.", ["nosql", "carreira"], None),
    ("u005", "Publiquei um guia rápido de boas práticas de visualização no Power BI: menos cores, mais clareza.", ["dados", "design"], None),
    ("u006", "Colocar um modelo em produção é 20% de treinar e 80% de monitorar. O Docker ajudou muito a padronizar o ambiente.", ["dados", "devops"], None),
    ("u007", "Orgulhosa de ter apresentado nosso data lake para a diretoria. Tem muito trabalho por trás de um gráfico simples.", ["dados", "carreira"], None),
    ("u007", "Abertas as inscrições para o workshop de Spark que vou ministrar no mês que vem. Vagas limitadas!", ["eventos", "dados"], None),
    ("u008", "Backup que nunca foi restaurado é só uma esperança. Neste mês testamos a restauração completa do banco e aprendemos bastante.", ["dados", "carreira"], None),
    ("u009", "Cartaz do nosso meetup de desenvolvimento web: React, Node.js e muita troca de experiência. Quem vai?", ["web", "eventos"], "meetup"),
    ("u009", "Dica para quem está começando em front-end: aprenda JavaScript de verdade antes de pular de framework em framework.", ["web", "carreira"], None),
    ("u010", "Documentar a API REST antes de escrever o código evitou três retrabalhos nesta sprint. Recomendo.", ["web", "carreira"], None),
    ("u011", "Estou migrando meu projeto de JavaScript para TypeScript. Os erros que o compilador pega antes da produção valem o esforço.", ["web"], None),
    ("u012", "Como tech lead, aprendi que revisar código é a melhor forma de ensinar. Revisões gentis constroem times melhores.", ["carreira", "mentoria"], None),
    ("u012", "Estamos com duas vagas para desenvolvedor back-end no nosso time. Interessados, me chamem no privado.", ["vagas", "web"], None),
    ("u013", "Publiquei meu primeiro app mobile na loja! Foram meses de estudo com React e TypeScript. Feedback é muito bem-vindo.", ["web", "carreira"], None),
    ("u014", "O cache com Redis reduziu pela metade o tempo de resposta da nossa API de pagamentos. Medir antes de otimizar faz toda a diferença.", ["nosql", "web"], None),
    ("u015", "Código limpo é aquele que o colega entende em seis meses. Escrevo para humanos primeiro e para a máquina depois.", ["web", "carreira"], None),
    ("u016", "Primeiro mês de estágio concluído! Aprendi a usar Git de verdade e já estou ansioso para estudar React e Docker.", ["carreira", "web"], None),
    ("u017", "Produto bom nasce da conversa com o usuário, não de suposições. Esta semana ouvimos dez clientes e mudamos o roadmap.", ["produto", "carreira"], None),
    ("u017", "Vagas abertas para pessoas de produto júnior na Farol Educação. Quem quer crescer com a gente?", ["vagas", "produto"], None),
    ("u018", "Montei uma biblioteca de componentes no Figma para o nosso time. Consistência visual economiza muito tempo de desenvolvimento.", ["design", "produto"], None),
    ("u019", "Resultados da nossa última rodada de pesquisa: usuários abandonavam o cadastro no terceiro passo. Reduzimos o formulário pela metade.", ["design", "produto"], None),
    ("u020", "Como Product Owner, aprendi a dizer não com carinho: priorizar é escolher o que não vai ser feito agora.", ["produto", "carreira"], None),
    ("u021", "Protótipo do novo fluxo de onboarding que desenhamos na Sol Varejo. Muita pesquisa por trás de cada tela.", ["design", "produto"], "prototipo"),
    ("u021", "Design não é decoração: é decidir como a pessoa vai se sentir ao usar o produto. Estou aberta a mentorias em UX.", ["design", "mentoria"], None),
    ("u022", "Retrospectiva boa é a que termina com uma ação concreta e um responsável. Sem isso, vira só reclamação coletiva.", ["produto", "carreira"], None),
    ("u023", "Estou começando em design de interface e queria muito entender melhor pesquisa com usuários. Indicações de leitura são bem-vindas!", ["design", "carreira"], None),
    ("u024", "Automatizamos o deploy com pipelines e o tempo de entrega caiu de dias para minutos. Kubernetes e Docker ajudaram demais.", ["devops"], None),
    ("u024", "Vou palestrar sobre DevOps no evento de tecnologia de Recife. Quem estiver por lá, vamos tomar um café!", ["eventos", "devops"], None),
    ("u025", "Lembrete de segurança: ative a verificação em duas etapas hoje. Leva um minuto e evita muita dor de cabeça.", ["devops", "carreira"], None),
    ("u026", "Plantão de SRE ensina humildade: alertas bons avisam antes de o usuário perceber o problema.", ["devops"], None),
    ("u027", "Migração para a nuvem concluída com custo 30% menor. O segredo foi dimensionar bem antes de mover qualquer carga.", ["devops", "dados"], None),
    ("u027", "Abri vagas de mentoria em arquitetura de nuvem. Se você quer entender AWS na prática, vamos conversar.", ["mentoria", "devops"], None),
    ("u028", "Linux no dia a dia: dominar a linha de comando ainda é a habilidade que mais economiza tempo no meu trabalho.", ["devops", "carreira"], None),
    ("u029", "Estou estudando Kubernetes e AWS para evoluir na engenharia de plataforma. Alguém topa trocar ideias?", ["devops", "carreira"], None),
]

# chave -> (nome do arquivo, título desenhado na imagem, cor principal RGB). Título sem acentos:
# a fonte padrão do Pillow não desenha acentos.
IMAGENS = {
    "comparativo": ("comparativo_modelos.png", "Comparativo de modelos", (46, 125, 190)),
    "meetup": ("cartaz_meetup_web.png", "Meetup Web", (214, 99, 52)),
    "prototipo": ("prototipo_onboarding.png", "Prototipo de onboarding", (76, 154, 96)),
}

_COMENTARIOS = [
    "Parabéns pela conquista!", "Ótima dica, obrigado por compartilhar.",
    "Concordo totalmente, já passei por isso.", "Muito bom! Vou aplicar no meu time.",
    "Interessante, pode contar mais detalhes?", "Excelente conteúdo, salvei aqui.",
    "Que legal ver isso por aí!", "Isso me ajudou bastante, valeu!",
]


def gerar_posts(agora: datetime | None = None) -> list[dict]:
    """40 posts com datas espalhadas pelos 14 dias anteriores a `agora`; curtidas e comentários
    vêm só de conexões do autor, e nunca de u001 (os testes partem da Ana sem ter curtido nada)."""
    agora = agora or datetime.now(timezone.utc)
    sorteio = random.Random(42)
    nomes = {p["id"]: p["nome"] for p in PESSOAS}
    titulos = {p["id"]: p["titulo"] for p in PESSOAS}
    vizinhos: dict[str, set[str]] = {}
    for a, b in CONEXOES:
        vizinhos.setdefault(a, set()).add(b)
        vizinhos.setdefault(b, set()).add(a)

    posts = []
    for i, (autor_id, texto, tags, imagem) in enumerate(_POSTS):
        # deslocamento fixo: entre 2 e 331 horas atrás (menos de 14 dias), sem repetir
        criado_em = agora - timedelta(hours=2 + (i * 61) % 330, minutes=(i * 17) % 60)
        candidatos = sorted(vizinhos.get(autor_id, set()) - {"u001"})
        curtidas = sorted(sorteio.sample(candidatos, sorteio.randint(0, min(4, len(candidatos)))))
        if i == 0 and "u002" not in curtidas:
            # o 1º post (o dashboard da Ana) tem a curtida do Bruno: é a que a primeira notificação
            # de NOTIFICACOES_INICIAIS anuncia. Vem depois do sorteio para não mudar os outros posts
            curtidas = sorted(curtidas + ["u002"])
        comentadores = sorteio.sample(candidatos, min(len(candidatos), sorteio.choice([0, 0, 1, 1, 2])))
        comentarios = [{"autor_id": c, "autor_nome": nomes[c], "texto": sorteio.choice(_COMENTARIOS),
                        "criado_em": min(agora, criado_em + timedelta(hours=1 + k))}
                       for k, c in enumerate(comentadores)]
        posts.append({"autor_id": autor_id, "autor": {"nome": nomes[autor_id], "titulo": titulos[autor_id]},
                      "texto": texto, "tags": tags, "imagem": imagem, "curtidas": curtidas,
                      "comentarios": comentarios, "criado_em": criado_em})
    return posts


# ---------- notificações ----------

# Três não lidas para a Ana; ficam no Mongo (histórico) e no Redis (contador e lista curta).
NOTIFICACOES_INICIAIS = [
    {"usuario_id": "u001", "tipo": "curtida", "de": {"id": "u002", "nome": "Bruno Carvalho"},
     "texto": "Bruno Carvalho curtiu o seu post sobre o dashboard no Power BI."},
    {"usuario_id": "u001", "tipo": "mentoria", "de": {"id": "u003", "nome": "Camila Nóbrega"},
     "texto": "Camila Nóbrega está com vagas de mentoria em Machine Learning."},
    {"usuario_id": "u001", "tipo": "post", "de": {"id": "u005", "nome": "Eduarda Monteiro"},
     "texto": "Eduarda Monteiro publicou um guia de visualização no Power BI."},
]
