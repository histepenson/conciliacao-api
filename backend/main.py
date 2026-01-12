"""
API Python para Conciliação com IA
FastAPI
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.empresa_router import router as empresa_router
from routers.planodecontas_router import router as plano_router
from routers.conciliacao_router import router as conciliacao_router
from routers.arquivo_router import router as arquivo_router

from db import engine
from models import Base
import uvicorn
from dotenv import load_dotenv
load_dotenv()

app = FastAPI(
    title="API Conciliação IA",
    version="1.0.0"
)

@app.middleware("http")
async def no_cache_middleware(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response

# CORS
# Domínios permitidos (frontend)
origins = [
    #"http://localhost:3000",
    #"http://localhost:8000",  # Vite
    "https://conciliacao-app-production.up.railway.app",
]


# Configura CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # ou ["*"] para liberar todos em dev
    allow_credentials=True,
    allow_methods=["*"],    # GET, POST, PUT, DELETE
    allow_headers=["*"],    # Content-Type, Authorization, etc
)

# Routers
app.include_router(empresa_router)
app.include_router(plano_router)
app.include_router(conciliacao_router)
app.include_router(arquivo_router)

# Create tables
Base.metadata.create_all(bind=engine)

@app.get("/")
async def root():
    return {
        "message": "API Conciliação IA",
        "status": "online",
        "version": "1.0.0"
    }
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)