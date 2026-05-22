from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from db import get_db
from middleware.permission import require_permission
from middleware.tenant import EmpresaContext, resolve_empresa_id
from schemas.produto_fornecedor_schema import ProdutoFornecedorCreate, ProdutoFornecedorUpdate, ProdutoFornecedorOut
from services.produto_fornecedor_service import (
    criar_depara, listar_depara, obter_depara, atualizar_depara, deletar_depara
)

router = APIRouter(prefix="/de-para", tags=["Estoque - De-Para"])


@router.post("", response_model=ProdutoFornecedorOut)
def criar(
    dados: ProdutoFornecedorCreate,
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission("estoque:write")),
):
    dados_resolvidos = dados.model_copy(
        update={"empresa_id": resolve_empresa_id(context, dados.empresa_id)}
    )
    return criar_depara(db, dados_resolvidos)


@router.get("", response_model=list[ProdutoFornecedorOut])
def listar(
    empresa_id: Optional[int] = Query(None),
    produto_id: Optional[int] = Query(None),
    cnpj_fornecedor: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission("estoque:read")),
):
    empresa_id_resolvido = resolve_empresa_id(context, empresa_id)
    return listar_depara(db, empresa_id_resolvido, produto_id, cnpj_fornecedor)


@router.get("/{depara_id}", response_model=ProdutoFornecedorOut)
def obter(
    depara_id: int,
    db: Session = Depends(get_db),
    _: EmpresaContext = Depends(require_permission("estoque:read")),
):
    from fastapi import HTTPException
    depara = obter_depara(db, depara_id)
    if not depara:
        raise HTTPException(404, "De-Para nao encontrado")
    return depara


@router.put("/{depara_id}", response_model=ProdutoFornecedorOut)
def atualizar(
    depara_id: int,
    dados: ProdutoFornecedorUpdate,
    db: Session = Depends(get_db),
    _: EmpresaContext = Depends(require_permission("estoque:write")),
):
    return atualizar_depara(db, depara_id, dados)


@router.delete("/{depara_id}")
def deletar(
    depara_id: int,
    db: Session = Depends(get_db),
    _: EmpresaContext = Depends(require_permission("estoque:write")),
):
    deletar_depara(db, depara_id)
    return {"message": "De-Para removido com sucesso"}
