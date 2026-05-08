# routers/arquivo_router.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from db import get_db
from models.arquivoconciliacao import ArquivoConciliacao
from schemas.arquivo_conciliacao_schema import (
    ArquivoConciliacaoCreate,
    ArquivoConciliacaoUpdate,
    ArquivoConciliacaoResponse,
)
from middleware.permission import Permissions, require_permission
from middleware.tenant import EmpresaContext, resolve_empresa_id

router = APIRouter(prefix="/arquivos", tags=["Arquivos"])


@router.get("", response_model=List[ArquivoConciliacaoResponse])
def listar_arquivos(
    empresa_id: Optional[int] = None,
    tipo_arquivo: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission(Permissions.ARQUIVO_READ)),
):
    empresa_id_resolvido = resolve_empresa_id(context, empresa_id)
    query = db.query(ArquivoConciliacao).filter(
        ArquivoConciliacao.empresa_id == empresa_id_resolvido
    )
    if tipo_arquivo:
        query = query.filter(ArquivoConciliacao.tipo_arquivo == tipo_arquivo)
    return query.offset(skip).limit(limit).all()


@router.get("/{id}", response_model=ArquivoConciliacaoResponse)
def buscar_arquivo(
    id: int,
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission(Permissions.ARQUIVO_READ)),
):
    query = db.query(ArquivoConciliacao).filter(ArquivoConciliacao.id == id)
    if context.empresa_id is not None:
        query = query.filter(ArquivoConciliacao.empresa_id == context.empresa_id)
    arquivo = query.first()
    if not arquivo:
        raise HTTPException(status_code=404, detail="Arquivo nao encontrado")
    return arquivo


@router.post("", response_model=ArquivoConciliacaoResponse, status_code=201)
def criar_arquivo(
    arquivo: ArquivoConciliacaoCreate,
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission(Permissions.ARQUIVO_UPLOAD)),
):
    db_arquivo = ArquivoConciliacao(**arquivo.model_dump())
    db.add(db_arquivo)
    db.commit()
    db.refresh(db_arquivo)
    return db_arquivo


@router.put("/{id}", response_model=ArquivoConciliacaoResponse)
def atualizar_arquivo(
    id: int,
    arquivo: ArquivoConciliacaoUpdate,
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission(Permissions.ARQUIVO_UPLOAD)),
):
    query = db.query(ArquivoConciliacao).filter(ArquivoConciliacao.id == id)
    if context.empresa_id is not None:
        query = query.filter(ArquivoConciliacao.empresa_id == context.empresa_id)
    db_arquivo = query.first()
    if not db_arquivo:
        raise HTTPException(status_code=404, detail="Arquivo nao encontrado")
    for key, value in arquivo.model_dump(exclude_unset=True).items():
        setattr(db_arquivo, key, value)
    db.commit()
    db.refresh(db_arquivo)
    return db_arquivo


@router.delete("/{id}", status_code=204)
def deletar_arquivo(
    id: int,
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission(Permissions.ARQUIVO_DELETE)),
):
    query = db.query(ArquivoConciliacao).filter(ArquivoConciliacao.id == id)
    if context.empresa_id is not None:
        query = query.filter(ArquivoConciliacao.empresa_id == context.empresa_id)
    db_arquivo = query.first()
    if not db_arquivo:
        raise HTTPException(status_code=404, detail="Arquivo nao encontrado")
    db.delete(db_arquivo)
    db.commit()
    return None
