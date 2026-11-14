# Imagem única da aplicação: serve tanto para o serviço `app` (Streamlit) quanto para a
# `carga` (scripts/carga_inicial.py) do docker-compose.yml.
FROM python:3.11-slim

# sem arquivos .pyc dentro da imagem e com a saída do Python aparecendo na hora nos logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /projeto

# as dependências vêm antes do código: enquanto o requirements.txt não mudar, o Docker
# reaproveita esta camada e o build seguinte não reinstala nada
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# o resto do projeto (o .dockerignore deixa de fora .env, .venv, .git, testes e caches)
COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app/Inicio.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
