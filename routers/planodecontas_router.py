# routers/planodecontas_router.py
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from db import get_db
import pandas as pd
import io

from services.planodecontas_services import (
    listar_planos_de_contas,
    buscar_conta,
    criar_conta,
    atualizar_conta,
    deletar_conta,
    preparar_dados_importacao,
    importar_plano_contas
)
from schemas.planodecontas_schema import PlanoDeContasResponse, PlanoDeContasCreate, PlanoDeContasUpdate

router = APIRouter(prefix="/plano-contas", tags=["Plano de Contas"])


@router.get("/", response_model=List[PlanoDeContasResponse])
def route_listar_planos(empresa_id: int, skip: int = 0, limit: int = 1000, db: Session = Depends(get_db)):
    return listar_planos_de_contas(db, empresa_id, skip, limit)


@router.get("/{id}", response_model=PlanoDeContasResponse)
def route_buscar_conta(id: int, db: Session = Depends(get_db)):
    conta = buscar_conta(db, id)
    if not conta:
        raise HTTPException(status_code=404, detail="Conta não encontrada")
    return conta


@router.post("/", response_model=PlanoDeContasResponse, status_code=201)
def route_criar_conta(conta: PlanoDeContasCreate, db: Session = Depends(get_db)):
    return criar_conta(db, conta.model_dump())


@router.put("/{id}", response_model=PlanoDeContasResponse)
def route_atualizar_conta(id: int, conta: PlanoDeContasUpdate, db: Session = Depends(get_db)):
    updated = atualizar_conta(db, id, conta.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Conta não encontrada")
    return updated


@router.delete("/{id}", status_code=204)
def route_deletar_conta(id: int, db: Session = Depends(get_db)):
    sucesso = deletar_conta(db, id)
    if not sucesso:
        raise HTTPException(status_code=404, detail="Conta não encontrada")
    return None


@router.post("/importar", response_model=dict)
def route_importar_plano(file: UploadFile = File(...), empresa_id: int = Form(...), db: Session = Depends(get_db)):
    try:
        contents = file.file.read()
        df = pd.read_excel(io.BytesIO(contents), dtype=str)
        df_sinteticas, df_analiticas = preparar_dados_importacao(df)
        resultado = importar_plano_contas(df_sinteticas, df_analiticas, empresa_id, db)
        return resultado
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao importar plano de contas: {str(e)}")
    finally:
        file.file.close()