# Backend Python (FastAPI)
FROM python:3.11-slim
WORKDIR /app

# Instalar dependencias
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copiar codigo da API
COPY . .

# Expor porta
EXPOSE 8000

# Aplica migracoes pendentes e sobe o servidor
CMD alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
