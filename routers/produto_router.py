from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from db import get_db
from middleware.permission import require_permission
from middleware.tenant import EmpresaContext, resolve_empresa_id
from schemas.produto_schema import ProdutoCreate, ProdutoUpdate, ProdutoOut
from services.produto_service import (
    criar_produto, listar_produtos, obter_produto, atualizar_produto, deletar_produto
)

router = APIRouter(prefix="/produtos", tags=["Estoque - Produtos"])


@router.post("", response_model=ProdutoOut)
def criar(
    dados: ProdutoCreate,
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission("estoque:write")),
):
    dados_resolvidos = dados.model_copy(
        update={"empresa_id": resolve_empresa_id(context, dados.empresa_id)}
    )
    return criar_produto(db, dados_resolvidos)


@router.get("", response_model=list[ProdutoOut])
def listar(
    empresa_id: Optional[int] = Query(None),
    ativo: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission("estoque:read")),
):
    empresa_id_resolvido = resolve_empresa_id(context, empresa_id)
    return listar_produtos(db, empresa_id_resolvido, ativo)


@router.get("/{produto_id}", response_model=ProdutoOut)
def obter(
    produto_id: int,
    db: Session = Depends(get_db),
    _: EmpresaContext = Depends(require_permission("estoque:read")),
):
    from fastapi import HTTPException
    produto = obter_produto(db, produto_id)
    if not produto:
        raise HTTPException(404, "Produto nao encontrado")
    return produto


@router.put("/{produto_id}", response_model=ProdutoOut)
def atualizar(
    produto_id: int,
    dados: ProdutoUpdate,
    db: Session = Depends(get_db),
    _: EmpresaContext = Depends(require_permission("estoque:write")),
):
    return atualizar_produto(db, produto_id, dados)


@router.delete("/{produto_id}")
def deletar(
    produto_id: int,
    db: Session = Depends(get_db),
    _: EmpresaContext = Depends(require_permission("estoque:write")),
):
    deletar_produto(db, produto_id)
    return {"message": "Produto removido com sucesso"}
