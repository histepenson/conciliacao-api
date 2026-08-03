# middleware/empresa_config.py
"""
Dependency de gate para endpoints que so devem ficar acessiveis para
empresas com determinada particularidade habilitada (ver
core/particularidades.py e services/empresa_configuracao_service.py).
"""
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from db import get_db
from core.particularidades import ChaveParticularidade
from services.empresa_configuracao_service import obter_valor
from .tenant import EmpresaContext, get_empresa_context


def require_configuracao(chave: ChaveParticularidade):
    """Factory de dependency: exige que a empresa do contexto tenha `chave` habilitada."""

    def _checker(
        context: EmpresaContext = Depends(get_empresa_context),
        db: Session = Depends(get_db),
    ) -> bool:
        if context.is_admin:
            return True

        valor = obter_valor(db, context.empresa_id, chave.value)
        if not valor:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Recurso nao habilitado para esta empresa.",
            )
        return True

    return _checker
