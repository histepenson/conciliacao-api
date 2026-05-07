from sqlalchemy.orm import Session
from fastapi import HTTPException
from models.produto import Produto
from schemas.produto_schema import ProdutoCreate, ProdutoUpdate


def criar_produto(db: Session, dados: ProdutoCreate) -> Produto:
    existente = db.query(Produto).filter(
        Produto.empresa_id == dados.empresa_id,
        Produto.codigo_interno == dados.codigo_interno,
    ).first()
    if existente:
        raise HTTPException(400, "Codigo interno ja cadastrado para esta empresa")

    produto = Produto(**dados.model_dump())
    db.add(produto)
    db.commit()
    db.refresh(produto)
    return produto


def listar_produtos(db: Session, empresa_id: int, ativo: bool = None) -> list[Produto]:
    q = db.query(Produto).filter(Produto.empresa_id == empresa_id)
    if ativo is not None:
        q = q.filter(Produto.ativo == ativo)
    return q.order_by(Produto.descricao).all()


def obter_produto(db: Session, produto_id: int) -> Produto | None:
    return db.query(Produto).filter(Produto.id == produto_id).first()


def atualizar_produto(db: Session, produto_id: int, dados: ProdutoUpdate) -> Produto:
    produto = obter_produto(db, produto_id)
    if not produto:
        raise HTTPException(404, "Produto nao encontrado")

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(produto, campo, valor)

    db.commit()
    db.refresh(produto)
    return produto


def deletar_produto(db: Session, produto_id: int) -> bool:
    produto = obter_produto(db, produto_id)
    if not produto:
        raise HTTPException(404, "Produto nao encontrado")

    db.delete(produto)
    db.commit()
    return True
