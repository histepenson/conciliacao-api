from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.protheus import encrypt_password
from models.empresa import Empresa
from schemas.empresa_schema import EmpresaCreate, EmpresaUpdate

_PROTHEUS_FIELDS = [
    "protheus_tenant",
    "protheus_url",
    "protheus_rest_prefix",
    "protheus_user",
    "protheus_password",
]


def criar_empresa(db: Session, emp: EmpresaCreate):
    if db.query(Empresa).filter(Empresa.cnpj == emp.cnpj).first():
        raise HTTPException(status_code=400, detail="CNPJ ja cadastrado")

    now = datetime.now(timezone.utc)
    nova = Empresa(
        nome=emp.nome,
        cnpj=emp.cnpj,
        status=emp.status,
        protheus_tenant=emp.protheus_tenant,
        protheus_url=emp.protheus_url,
        protheus_rest_prefix=emp.protheus_rest_prefix,
        protheus_user=emp.protheus_user,
        protheus_password=encrypt_password(emp.protheus_password) if emp.protheus_password else None,
        updated_at=now,
        created_at=now,
    )
    db.add(nova)
    db.commit()
    db.refresh(nova)
    return nova


def listar_empresas(db: Session):
    return db.query(Empresa).all()


def obter_empresa(db: Session, empresa_id: int):
    return db.query(Empresa).filter(Empresa.id == empresa_id).first()


def atualizar_empresa(db: Session, empresa_id: int, dados: EmpresaUpdate, is_admin: bool = False):
    empresa = obter_empresa(db, empresa_id)
    if not empresa:
        return None

    campos = dados.model_dump(exclude_unset=True)

    if not is_admin:
        for f in _PROTHEUS_FIELDS:
            campos.pop(f, None)

    # Criptografa a senha antes de salvar
    if "protheus_password" in campos:
        raw = campos["protheus_password"]
        campos["protheus_password"] = encrypt_password(raw) if raw else None

    for campo, valor in campos.items():
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
