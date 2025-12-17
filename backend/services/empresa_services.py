from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from models.empresa import Empresa
from schemas.empresa_schema import EmpresaCreate, EmpresaUpdate
from datetime import datetime, timezone



from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from models.empresa import Empresa
from schemas.empresa_schema import EmpresaCreate

from datetime import datetime

def criar_empresa(db: Session, emp: EmpresaCreate):
    # Verifica duplicidade
    if db.query(Empresa).filter(Empresa.cnpj == emp.cnpj).first():
        raise HTTPException(status_code=400, detail="CNPJ já cadastrado")

    now = datetime.now(timezone.utc)  # datetime aware em UTC
    nova_empresa = Empresa(
        nome=emp.nome,
        cnpj=emp.cnpj,
        status=emp.status,
        updated_at=now,
        created_at=now
    )
    
    db.add(nova_empresa)
    db.commit()
    db.refresh(nova_empresa)
    return nova_empresa


def listar_empresas(db: Session):
    return db.query(Empresa).all()


def obter_empresa(db: Session, empresa_id: int):
    return db.query(Empresa).filter(Empresa.id == empresa_id).first()


def atualizar_empresa(db: Session, empresa_id: int, dados: EmpresaUpdate):
    empresa = obter_empresa(db, empresa_id)
    if not empresa:
        return None

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(empresa, campo, valor)

    db.commit()
    db.refresh(empresa)
    return empresa


def deletar_empresa(db: Session, empresa_id: int):
    empresa = obter_empresa(db, empresa_id)
    if not empresa:
        return None

    db.delete(empresa)
    db.commit()
    return True
