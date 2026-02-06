from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from core.config import settings
import traceback
from routers.empresa_router import router as empresa_router
from routers.planodecontas_router import router as planodecontas_router
from routers.conciliacao_router import router as conciliacao_router
from routers.arquivo_router import router as arquivo_router
from routers.auth_router import router as auth_router
from routers.admin_usuarios_router import router as admin_usuarios_router
from routers.admin_empresas_router import router as admin_empresas_router
from routers.admin_perfis_router import router as admin_perfis_router
from routers.efetivacao_router import router as efetivacao_router
from routers.dashboard_router import router as dashboard_router
from routers.conciliacao_bancaria_router import router as conciliacao_bancaria_router

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

app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Captura exceções não tratadas para que a resposta 500
    passe pelo CORSMiddleware e inclua os headers corretos."""
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": f"Erro interno do servidor: {str(exc)}"},
    )


app.include_router(empresa_router, prefix="/api")
app.include_router(planodecontas_router, prefix="/api")
app.include_router(conciliacao_router, prefix="/api")
app.include_router(arquivo_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(admin_usuarios_router, prefix="/api")
app.include_router(admin_empresas_router, prefix="/api")
app.include_router(admin_perfis_router, prefix="/api")
app.include_router(efetivacao_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(conciliacao_bancaria_router, prefix="/api")
