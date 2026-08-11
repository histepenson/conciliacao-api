from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from core.config import settings
import logging
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
from routers.conciliacao_estoque_router import router as conciliacao_estoque_router
from routers.conciliacao_impostos_router import router as conciliacao_impostos_router
from routers.matching_manual_fiscal_router import router as matching_manual_fiscal_router
from routers.finr130_router import router as finr130_router
from routers.ctbr140_router import router as ctbr140_router
from routers.ctbr480_router import router as ctbr480_router
from routers.finr470_router import router as finr470_router
from routers.ctbr400_router import router as ctbr400_router
from routers.matr900_router import router as matr900_router
from routers.finr150_router import router as finr150_router
from routers.croms051_router import router as croms051_router
from routers.protheus_carga_router import router as protheus_carga_router
from routers.produto_router import router as produto_router
from routers.produto_fornecedor_router import router as produto_fornecedor_router
from routers.certificado_router import router as certificado_router
from routers.nfe_router import router as nfe_router
from routers.estoque_router import router as estoque_router
from routers.pre_conferencia_router import router as pre_conferencia_router
from routers.analise_ia_router import router as analise_ia_router
from routers.lancamento_padrao_router import router as lancamento_padrao_router
from routers.ativo_fixo_router import router as ativo_fixo_router
from routers.balancete_router import router as balancete_router
from routers.operacao_financeira_router import router as operacao_financeira_router
from routers.conferencia_leasing_router import router as conferencia_leasing_router
from routers.folha_pagamento_router import router as folha_pagamento_router
from routers.conferencia_folha_router import router as conferencia_folha_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    from apscheduler.schedulers.background import BackgroundScheduler
    from db import SessionLocal
    from services.fechamento_service import job_fechar_mes_anterior

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        job_fechar_mes_anterior,
        trigger="cron",
        day=1,
        hour=2,
        minute=0,
        args=[SessionLocal],
        id="fechar_mes_anterior",
        replace_existing=True,
    )
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    lifespan=lifespan,
    title="Conciliacao API",
    description="""
API para conciliacao contabil e financeira.

Fluxo:
1. Cadastro de empresa
2. Plano de contas
3. Upload de arquivos
4. Conciliacao mensal
""",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Captura excecoes nao tratadas para que a resposta 500
    passe pelo CORSMiddleware e inclua os headers corretos."""
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": f"Erro interno do servidor: {str(exc)}"},
    )


# Log de storage ao iniciar
logging.getLogger(__name__).info(
    f"Storage S3 configurado: bucket={settings.STORAGE_BUCKET or '(nao definido)'} "
    f"endpoint={settings.STORAGE_ENDPOINT or '(nao definido)'}"
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
app.include_router(conciliacao_estoque_router, prefix="/api")
app.include_router(conciliacao_impostos_router, prefix="/api")
app.include_router(matching_manual_fiscal_router, prefix="/api")
app.include_router(finr130_router, prefix="/api")
app.include_router(ctbr140_router, prefix="/api")
app.include_router(ctbr480_router, prefix="/api")
app.include_router(finr470_router, prefix="/api")
app.include_router(ctbr400_router, prefix="/api")
app.include_router(matr900_router, prefix="/api")
app.include_router(finr150_router, prefix="/api")
app.include_router(croms051_router, prefix="/api")
app.include_router(protheus_carga_router, prefix="/api")
app.include_router(produto_router, prefix="/api")
app.include_router(produto_fornecedor_router, prefix="/api")
app.include_router(certificado_router, prefix="/api")
app.include_router(nfe_router, prefix="/api")
app.include_router(estoque_router)
app.include_router(pre_conferencia_router, prefix="/api")
app.include_router(analise_ia_router, prefix="/api")
app.include_router(ativo_fixo_router, prefix="/api")
app.include_router(lancamento_padrao_router, prefix="/api")
app.include_router(balancete_router, prefix="/api")
app.include_router(operacao_financeira_router, prefix="/api")
app.include_router(conferencia_leasing_router, prefix="/api")
app.include_router(folha_pagamento_router, prefix="/api")
app.include_router(conferencia_folha_router, prefix="/api")
