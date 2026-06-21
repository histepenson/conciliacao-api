from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db import get_db
from middleware.tenant import EmpresaContext, get_empresa_context, resolve_empresa_id
from services import ativo_fixo_service as service

router = APIRouter(prefix="/v1/ativo-fixo", tags=["Ativo Fixo"])


@router.get(
    "/conferir",
    summary="Confrontar SN3/SN4 vs Razao (CT2RAZCT5)",
    description=(
        "Compara os movimentos de Baixa (SN3) e Lancamento (SN4) de Ativo Fixo "
        "com o razao contabil (CT2RAZCT5), filtrado pela(s) conta(s) informada(s). "
        "Usa a ultima carga concluida de cada tipo para a empresa, "
        "a menos que carga_id_sn3 / carga_id_sn4 / carga_id_razao sejam informados."
    ),
)
def get_conferencia(
    empresa_id: Optional[int] = Query(None, description="ID da empresa"),
    carga_id_sn3: Optional[int] = Query(None, description="ID da carga SN3 (usa a ultima concluida se omitido)"),
    carga_id_sn4: Optional[int] = Query(None, description="ID da carga SN4 (usa a ultima concluida se omitido)"),
    carga_id_razao: Optional[int] = Query(None, description="ID da carga CT2RAZCT5 (usa a ultima concluida se omitido)"),
    conta_de: Optional[str] = Query(None, description="Conta contabil inicial de Ativo Fixo (filtra o razao)"),
    conta_ate: Optional[str] = Query(None, description="Conta contabil final de Ativo Fixo (filtra o razao)"),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(get_empresa_context),
):
    resolved_id = resolve_empresa_id(context, empresa_id)
    return service.conferir(db, resolved_id, carga_id_sn3, carga_id_sn4, carga_id_razao, conta_de, conta_ate)
