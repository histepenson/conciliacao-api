# routers/planodecontas_router.py
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from db import get_db
import pandas as pd
import io

from middleware.permission import Permissions, require_permission
from middleware.tenant import EmpresaContext, resolve_empresa_id
from services.planodecontas_services import (
    listar_planos_de_contas,
    buscar_conta,
    criar_conta,
    atualizar_conta,
    deletar_conta,
    preparar_dados_importacao,
    importar_plano_contas
)
from schemas.planodecontas_schema import PlanoDeContasResponse, PlanoDeContasCreate, PlanoDeContasUpdate, ImportacaoResultado

router = APIRouter(prefix="/plano-contas", tags=["Plano de Contas"])


@router.get("", response_model=List[PlanoDeContasResponse])
def route_listar_planos(
    empresa_id: Optional[int] = Query(None),
    skip: int = 0,
    limit: int = 1000,
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission(Permissions.PLANO_CONTAS_READ)),
):
    empresa_id_resolvido = resolve_empresa_id(context, empresa_id)
    return listar_planos_de_contas(db, empresa_id_resolvido, skip, limit)


@router.get("/{id}", response_model=PlanoDeContasResponse)
def route_buscar_conta(
    id: int,
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission(Permissions.PLANO_CONTAS_READ)),
):
    conta = buscar_conta(db, id, context.empresa_id)
    if not conta:
        raise HTTPException(status_code=404, detail="Conta nao encontrada")
    return conta


@router.post("", response_model=PlanoDeContasResponse, status_code=201)
def route_criar_conta(
    conta: PlanoDeContasCreate,
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission(Permissions.PLANO_CONTAS_WRITE)),
):
    dados = conta.model_dump()
    dados["empresa_id"] = resolve_empresa_id(context, dados.get("empresa_id"))
    return criar_conta(db, dados)


@router.put("/{id}", response_model=PlanoDeContasResponse)
def route_atualizar_conta(
    id: int,
    conta: PlanoDeContasUpdate,
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission(Permissions.PLANO_CONTAS_WRITE)),
):
    updated = atualizar_conta(db, id, conta.model_dump(exclude_unset=True), context.empresa_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Conta nao encontrada")
    return updated


@router.delete("/{id}", status_code=204)
def route_deletar_conta(
    id: int,
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission(Permissions.PLANO_CONTAS_WRITE)),
):
    sucesso = deletar_conta(db, id, context.empresa_id)
    if not sucesso:
        raise HTTPException(status_code=404, detail="Conta nao encontrada")
    return None


@router.post("/importar", response_model=ImportacaoResultado)
def route_importar_plano(
    file: UploadFile = File(...),
    empresa_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission(Permissions.PLANO_CONTAS_IMPORT)),
):
    try:
        empresa_id_resolvido = resolve_empresa_id(context, empresa_id)
        contents = file.file.read()
        df = pd.read_excel(io.BytesIO(contents), dtype=str)
        df_sinteticas, df_analiticas = preparar_dados_importacao(df)
        resultado = importar_plano_contas(df_sinteticas, df_analiticas, empresa_id_resolvido, db)
        return resultado
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao importar plano de contas: {str(e)}")
    finally:
        file.file.close()
