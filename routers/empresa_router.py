from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db import get_db
from schemas.empresa_schema import EmpresaCreate, EmpresaOut, EmpresaUpdate
from services.empresa_services import (
    criar_empresa, listar_empresas, obter_empresa,
    atualizar_empresa, deletar_empresa
)
from middleware.auth import CurrentUser
from middleware.permission import require_admin

router = APIRouter(prefix="/empresas", tags=["Empresa"])



@router.post("/", response_model=EmpresaOut)
def criar(emp: EmpresaCreate, db: Session = Depends(get_db), current_user: CurrentUser = Depends(require_admin)):
    return criar_empresa(db, emp)


@router.get("/", response_model=list[EmpresaOut])
def listar(db: Session = Depends(get_db)):
    return listar_empresas(db)


@router.get("/{empresa_id}", response_model=EmpresaOut)
def obter(empresa_id: int, db: Session = Depends(get_db)):
    empresa = obter_empresa(db, empresa_id)
    if not empresa:
        raise HTTPException(404, "Empresa não encontrada")
    return empresa


@router.put("/{empresa_id}", response_model=EmpresaOut)
def atualizar(empresa_id: int, dados: EmpresaUpdate, db: Session = Depends(get_db)):
    empresa = atualizar_empresa(db, empresa_id, dados)
    if not empresa:
        raise HTTPException(404, "Empresa não encontrada")
    return empresa


@router.delete("/{empresa_id}")
def excluir(empresa_id: int, db: Session = Depends(get_db)):
    sucesso = deletar_empresa(db, empresa_id)
    if not sucesso:
        raise HTTPException(404, "Empresa não encontrada")
    return {"message": "Empresa deletada com sucesso"}
