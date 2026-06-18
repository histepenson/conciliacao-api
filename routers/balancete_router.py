import io
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from db import get_db
from middleware.permission import Permissions, require_permission
from middleware.tenant import EmpresaContext, resolve_empresa_id
from schemas.balancete_schema import BalanceteContaOut, BalanceteImportResult
from services import balancete_service as service

router = APIRouter(prefix="/balancete", tags=["Balancete"])

EXTENSOES_PERMITIDAS = {".xlsx", ".xls"}


@router.post("/importar", response_model=BalanceteImportResult)
async def importar(
    data_base: str = Form(...),
    empresa_id: int | None = Form(None),
    arquivo: UploadFile = File(...),
    aba: str | None = Form(None),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission(Permissions.CONCILIACAO_WRITE)),
):
    ext = Path(arquivo.filename).suffix.lower()
    if ext not in EXTENSOES_PERMITIDAS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Apenas arquivos .xlsx ou .xls sao aceitos",
        )

    resolved_id = resolve_empresa_id(context, empresa_id)
    conteudo = await arquivo.read()

    try:
        buffer = io.BytesIO(conteudo)
        if aba:
            df_raw = pd.read_excel(buffer, sheet_name=aba, header=0)
        else:
            xls = pd.ExcelFile(buffer)
            sheet_name = xls.sheet_names[-1]
            df_raw = pd.read_excel(xls, sheet_name=sheet_name, header=0)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erro ao ler arquivo Excel: {exc}",
        )

    resultado = service.importar_balancete(db, resolved_id, data_base, df_raw)
    return resultado


@router.get("/conta", response_model=BalanceteContaOut | None)
def obter_conta(
    conta_contabil_id: int = Query(...),
    data_base: str = Query(...),
    empresa_id: int | None = Query(None),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission(Permissions.CONCILIACAO_READ)),
):
    resolved_id = resolve_empresa_id(context, empresa_id)
    return service.obter_balancete_conta(db, resolved_id, conta_contabil_id, data_base)
