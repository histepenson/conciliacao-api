from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.lancamento_padrao import LancamentoPadraoCt2Layout


def _validar_layout_campos(layout_campos: Optional[list]) -> None:
    if not layout_campos:
        return
    campos = [c["campo"] for c in layout_campos]
    duplicados = {c for c in campos if campos.count(c) > 1}
    if duplicados:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Campo(s) duplicado(s) em layout_campos: {sorted(duplicados)}",
        )


def listar(db: Session, empresa_id: Optional[int] = None) -> List[LancamentoPadraoCt2Layout]:
    query = db.query(LancamentoPadraoCt2Layout)
    if empresa_id is not None:
        query = query.filter(LancamentoPadraoCt2Layout.empresa_id == empresa_id)
    return query.order_by(LancamentoPadraoCt2Layout.empresa_id, LancamentoPadraoCt2Layout.lp_codigo).all()


def obter(db: Session, layout_id: int) -> LancamentoPadraoCt2Layout:
    layout = db.query(LancamentoPadraoCt2Layout).filter(LancamentoPadraoCt2Layout.id == layout_id).first()
    if not layout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cadastro nao encontrado")
    return layout


def criar(db: Session, data: dict) -> LancamentoPadraoCt2Layout:
    existente = (
        db.query(LancamentoPadraoCt2Layout)
        .filter(
            LancamentoPadraoCt2Layout.empresa_id == data["empresa_id"],
            LancamentoPadraoCt2Layout.lp_codigo == data["lp_codigo"],
        )
        .first()
    )
    if existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ja existe cadastro para o LP {data['lp_codigo']} nessa empresa",
        )

    if not data.get("tipo_chave") and not data.get("codigo_movimento_ct2_vazio") and not data.get("layout_campos"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Informe tipo_chave (CT2_KEY preenchido), codigo_movimento_ct2_vazio (CT2_KEY vazio) ou layout_campos (layout generico de posicoes)",
        )
    _validar_layout_campos(data.get("layout_campos"))

    layout = LancamentoPadraoCt2Layout(
        empresa_id=data["empresa_id"],
        lp_codigo=data["lp_codigo"],
        tipo_chave=data.get("tipo_chave"),
        codigo_movimento_ct2_vazio=data.get("codigo_movimento_ct2_vazio"),
        layout_campos=data.get("layout_campos"),
        descricao=data.get("descricao"),
    )
    db.add(layout)
    db.commit()
    db.refresh(layout)
    return layout


def atualizar(db: Session, layout_id: int, data: dict) -> LancamentoPadraoCt2Layout:
    layout = obter(db, layout_id)

    if "tipo_chave" in data:
        layout.tipo_chave = data["tipo_chave"]
    if "codigo_movimento_ct2_vazio" in data:
        layout.codigo_movimento_ct2_vazio = data["codigo_movimento_ct2_vazio"]
    if "layout_campos" in data:
        _validar_layout_campos(data["layout_campos"])
        layout.layout_campos = data["layout_campos"]
    if "descricao" in data:
        layout.descricao = data["descricao"]

    if not layout.tipo_chave and not layout.codigo_movimento_ct2_vazio and not layout.layout_campos:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Informe tipo_chave (CT2_KEY preenchido), codigo_movimento_ct2_vazio (CT2_KEY vazio) ou layout_campos (layout generico de posicoes)",
        )

    db.commit()
    db.refresh(layout)
    return layout


def deletar(db: Session, layout_id: int) -> dict:
    layout = obter(db, layout_id)
    db.delete(layout)
    db.commit()
    return {"message": "Cadastro removido"}
