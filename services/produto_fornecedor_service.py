from sqlalchemy.orm import Session
from fastapi import HTTPException
from models.produto_fornecedor import ProdutoFornecedor
from schemas.produto_fornecedor_schema import ProdutoFornecedorCreate, ProdutoFornecedorUpdate


def criar_depara(db: Session, dados: ProdutoFornecedorCreate) -> ProdutoFornecedor:
    existente = db.query(ProdutoFornecedor).filter(
        ProdutoFornecedor.empresa_id == dados.empresa_id,
        ProdutoFornecedor.cnpj_fornecedor == dados.cnpj_fornecedor,
        ProdutoFornecedor.codigo_produto_fornecedor == dados.codigo_produto_fornecedor,
    ).first()
    if existente:
        raise HTTPException(400, "De-Para ja cadastrado para este fornecedor e codigo")

    depara = ProdutoFornecedor(**dados.model_dump())
    db.add(depara)
    db.commit()
    db.refresh(depara)
    return depara


def listar_depara(db: Session, empresa_id: int, produto_id: int = None, cnpj_fornecedor: str = None) -> list[ProdutoFornecedor]:
    q = db.query(ProdutoFornecedor).filter(ProdutoFornecedor.empresa_id == empresa_id)
    if produto_id is not None:
        q = q.filter(ProdutoFornecedor.produto_id == produto_id)
    if cnpj_fornecedor:
        q = q.filter(ProdutoFornecedor.cnpj_fornecedor == cnpj_fornecedor)
    return q.order_by(ProdutoFornecedor.razao_social_fornecedor).all()


def obter_depara(db: Session, depara_id: int) -> ProdutoFornecedor | None:
    return db.query(ProdutoFornecedor).filter(ProdutoFornecedor.id == depara_id).first()


def buscar_depara_por_codigo(db: Session, empresa_id: int, cnpj_fornecedor: str, codigo: str) -> ProdutoFornecedor | None:
    return db.query(ProdutoFornecedor).filter(
        ProdutoFornecedor.empresa_id == empresa_id,
        ProdutoFornecedor.cnpj_fornecedor == cnpj_fornecedor,
        ProdutoFornecedor.codigo_produto_fornecedor == codigo,
    ).first()


def atualizar_depara(db: Session, depara_id: int, dados: ProdutoFornecedorUpdate) -> ProdutoFornecedor:
    depara = obter_depara(db, depara_id)
    if not depara:
        raise HTTPException(404, "De-Para nao encontrado")

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(depara, campo, valor)

    db.commit()
    db.refresh(depara)
    return depara


def deletar_depara(db: Session, depara_id: int) -> bool:
    depara = obter_depara(db, depara_id)
    if not depara:
        raise HTTPException(404, "De-Para nao encontrado")

    db.delete(depara)
    db.commit()
    return True
