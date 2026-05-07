"""Utilitários compartilhados para integração com o Protheus."""
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from core.config import settings
from models.empresa import Empresa


def resolve_protheus_tenant(empresa_id: Optional[int], db: Optional[Session]) -> str:
    """
    Resolve o Tenant ID do Protheus para a empresa informada.

    - Se empresa_id fornecido: busca empresa e usa seu protheus_tenant.
      Se a empresa não tiver tenant configurado, retorna 422 com mensagem clara.
    - Se empresa_id não fornecido: usa settings.PROTHEUS_TENANT (fallback global).
    """
    if empresa_id is not None and db is not None:
        empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
        if not empresa:
            raise HTTPException(status_code=404, detail=f"Empresa {empresa_id} nao encontrada")
        if not empresa.protheus_tenant:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"A empresa '{empresa.nome}' nao possui Tenant ID do Protheus configurado. "
                    "Acesse Administracao > Empresas e informe o Tenant ID."
                ),
            )
        return empresa.protheus_tenant

    # Sem empresa_id: fallback para configuracao global
    tenant = settings.PROTHEUS_TENANT
    if not tenant:
        raise HTTPException(
            status_code=422,
            detail=(
                "Tenant ID nao configurado. "
                "Informe o parametro 'empresa_id' ou defina PROTHEUS_TENANT no .env"
            ),
        )
    return tenant
