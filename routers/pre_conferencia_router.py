from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db import get_db
from middleware.tenant import EmpresaContext, get_empresa_context, resolve_empresa_id
from services import pre_conferencia_service as service

router = APIRouter(prefix="/v1/pre-conferencia", tags=["Pre Conferencia"])


@router.get(
    "/conferir",
    summary="Confrontar CT2RAZCT5 vs SFTENT",
    description=(
        "Compara os lançamentos do razão contábil (CT2RAZCT5) com o livro fiscal (SFT). "
        "Usa a ultima carga concluida de cada tipo para a empresa, "
        "a menos que carga_id_ct2 / carga_id_sft sejam informados. "
        "Requer que a tabela ct5_referencia esteja populada para a empresa "
        "(via script importar_ct5_referencia.py)."
    ),
)
def get_conferencia(
    empresa_id: Optional[int] = Query(None, description="ID da empresa"),
    carga_id_ct2: Optional[int] = Query(None, description="ID da carga CT2RAZCT5 (usa a ultima concluida se omitido)"),
    carga_id_sft: Optional[int] = Query(None, description="ID da carga SFTENT (usa a ultima concluida se omitido)"),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(get_empresa_context),
):
    resolved_id = resolve_empresa_id(context, empresa_id)
    return service.conferir(db, resolved_id, carga_id_ct2, carga_id_sft)
