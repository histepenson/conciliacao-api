from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.empresa_router import router as empresa_router

app = FastAPI(
    title="Conciliação API",
    description="""
API para conciliação contábil e financeira.

Fluxo:
1. Cadastro de empresa
2. Plano de contas
3. Upload de arquivos
4. Conciliação mensal
""",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(empresa_router, prefix="/api")
