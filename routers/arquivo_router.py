# routers/arquivo_router.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from db import get_db
from models.arquivoconciliacao import ArquivoConciliacao  # ← Modelo SQLAlchemy
from schemas.arquivo_conciliacao_schema import (  # ← Schemas Pydantic
    ArquivoConciliacaoCreate,
    ArquivoConciliacaoUpdate,
    ArquivoConciliacaoResponse
)
import os
from pathlib import Path

router = APIRouter(prefix="/arquivos", tags=["Arquivos"])

# Diretório para uploads - usa env var STORAGE_DIR, default "data"
UPLOAD_DIR = Path(os.environ.get("STORAGE_DIR", "data"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/", response_model=List[ArquivoConciliacaoResponse])
def listar_arquivos(
    empresa_id: Optional[int] = None,
    tipo_arquivo: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Lista todos os arquivos com filtros opcionais"""
    
    query = db.query(ArquivoConciliacao)
    
    if empresa_id:
        query = query.filter(ArquivoConciliacao.empresa_id == empresa_id)
    
    if tipo_arquivo:
        query = query.filter(ArquivoConciliacao.tipo_arquivo == tipo_arquivo)
    
    return query.offset(skip).limit(limit).all()


@router.get("/{id}", response_model=ArquivoConciliacaoResponse)
def buscar_arquivo(id: int, db: Session = Depends(get_db)):
    """Busca um arquivo específico por ID"""
    
    arquivo = db.query(ArquivoConciliacao).filter(ArquivoConciliacao.id == id).first()
    
    if not arquivo:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    
    return arquivo


@router.post("/", response_model=ArquivoConciliacaoResponse, status_code=201)
def criar_arquivo(
    arquivo: ArquivoConciliacaoCreate,  # ← Schema Pydantic, não modelo SQLAlchemy
    db: Session = Depends(get_db)
):
    """Cria um novo registro de arquivo"""
    
    # Converte schema Pydantic para modelo SQLAlchemy
    db_arquivo = ArquivoConciliacao(**arquivo.model_dump())
    
    db.add(db_arquivo)
    db.commit()
    db.refresh(db_arquivo)
    
    return db_arquivo


@router.post("/upload", response_model=ArquivoConciliacaoResponse, status_code=201)
async def upload_arquivo(
    empresa_id: int,
    tipo_arquivo: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Faz upload de um arquivo e cria registro no banco"""
    
    # Gera caminho para o arquivo
    file_path = UPLOAD_DIR / f"{empresa_id}_{tipo_arquivo}_{file.filename}"
    
    # Salva o arquivo
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Cria registro no banco
    db_arquivo = ArquivoConciliacao(
        empresa_id=empresa_id,
        tipo_arquivo=tipo_arquivo,
        nome_arquivo=file.filename,
        caminho_arquivo=str(file_path),
        status="pendente"
    )
    
    db.add(db_arquivo)
    db.commit()
    db.refresh(db_arquivo)
    
    return db_arquivo


@router.put("/{id}", response_model=ArquivoConciliacaoResponse)
def atualizar_arquivo(
    id: int,
    arquivo: ArquivoConciliacaoUpdate,  # ← Schema Pydantic
    db: Session = Depends(get_db)
):
    """Atualiza um arquivo existente"""
    
    db_arquivo = db.query(ArquivoConciliacao).filter(ArquivoConciliacao.id == id).first()
    
    if not db_arquivo:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    
    # Atualiza apenas campos enviados
    for key, value in arquivo.model_dump(exclude_unset=True).items():
        setattr(db_arquivo, key, value)
    
    db.commit()
    db.refresh(db_arquivo)
    
    return db_arquivo


@router.delete("/{id}", status_code=204)
def deletar_arquivo(id: int, db: Session = Depends(get_db)):
    """Deleta um arquivo"""
    
    db_arquivo = db.query(ArquivoConciliacao).filter(ArquivoConciliacao.id == id).first()
    
    if not db_arquivo:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    
    # Remove arquivo físico se existir
    if os.path.exists(db_arquivo.caminho_arquivo):
        os.remove(db_arquivo.caminho_arquivo)
    
    db.delete(db_arquivo)
    db.commit()
    
    return None