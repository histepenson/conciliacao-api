"""
Router para endpoints do Dashboard.
"""
import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db import get_db
from middleware.auth import get_current_user, CurrentUser
from schemas.dashboard_schema import DashboardResponse
from services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
logger = logging.getLogger(__name__)


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    empresa_id: int = Query(None, description="ID da empresa (opcional para admin)"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Retorna dados do dashboard para a empresa.

    Para usuarios normais, usa a empresa vinculada.
    Para admins, pode especificar empresa_id.
    """
    # Determinar empresa_id
    if current_user.is_admin and empresa_id:
        target_empresa_id = empresa_id
    elif current_user.empresa_id:
        target_empresa_id = current_user.empresa_id
    else:
        target_empresa_id = empresa_id

    if not target_empresa_id:
        # Retornar dashboard vazio se nao houver empresa
        return DashboardResponse(
            saudacao=f"Ola, {current_user.nome}!",
            data_atual="",
            empresa_nome="Selecione uma empresa",
            stats={
                "total_contas": 0,
                "contas_conciliadas": 0,
                "contas_pendentes": 0,
                "taxa_sucesso": 0
            },
            conciliacoes_recentes=[],
            grafico_mensal=[],
            alertas=[]
        )

    service = DashboardService()
    return service.get_dashboard(
        db=db,
        empresa_id=target_empresa_id,
        user_nome=current_user.nome
    )
