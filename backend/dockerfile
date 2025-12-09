# Build do Frontend
FROM node:18-alpine as frontend-build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# Backend Python
FROM python:3.11-slim
WORKDIR /app

# Instalar dependências do backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código do backend
COPY backend/ ./backend/

# Copiar build do frontend
COPY --from=frontend-build /app/dist ./frontend/dist

# Expor porta
EXPOSE 8000

# Comando para iniciar
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]