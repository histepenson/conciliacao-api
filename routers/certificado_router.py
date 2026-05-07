from fastapi import APIRouter, Depends, UploadFile, File, Form, Query
from sqlalchemy.orm import Session

from db import get_db
from middleware.permission import require_permission
from middleware.tenant import EmpresaContext, resolve_empresa_id
from schemas.certificado_schema import CertificadoOut
from services.certificado_service import salvar_certificado, listar_certificados, deletar_certificado

router = APIRouter(prefix="/certificados", tags=["Estoque - Certificados"])

EXTENSOES_PERMITIDAS = {".pfx", ".p12"}


@router.post("", response_model=CertificadoOut)
async def upload(
    empresa_id: int | None = Form(None),
    senha: str = Form(...),
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission("estoque:write")),
):
    from pathlib import Path
    from fastapi import HTTPException

    ext = Path(arquivo.filename).suffix.lower()
    if ext not in EXTENSOES_PERMITIDAS:
        raise HTTPException(400, "Apenas arquivos .pfx ou .p12 sao aceitos")

    empresa_id_resolvido = resolve_empresa_id(context, empresa_id)
    return salvar_certificado(db, empresa_id_resolvido, arquivo, senha)


@router.get("", response_model=list[CertificadoOut])
def listar(
    empresa_id: int | None = Query(None),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission("estoque:read")),
):
    empresa_id_resolvido = resolve_empresa_id(context, empresa_id)
    return listar_certificados(db, empresa_id_resolvido)


@router.delete("/{cert_id}")
def deletar(
    cert_id: int,
    db: Session = Depends(get_db),
    _: EmpresaContext = Depends(require_permission("estoque:write")),
):
    deletar_certificado(db, cert_id)
    return {"message": "Certificado removido com sucesso"}
