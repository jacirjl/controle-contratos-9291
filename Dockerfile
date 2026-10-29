# Imagem oficial enxuta do Python 3.12 para Google Cloud Run
FROM python:3.12-slim

WORKDIR /app

# Variáveis de ambiente de produção
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

# Instala dependências Python (PyMuPDF possui wheel binário pré-compilado)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código-fonte, plataforma web e banco vetorial pré-indexado (db/contrato_9291.sqlite)
COPY . .

EXPOSE 8080

# Cloud Run injeta automaticamente a variável PORT (padrão 8080), lida pelo server.py
CMD ["python", "server.py"]
