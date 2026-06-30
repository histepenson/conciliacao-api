"""
Chamada HTTP compartilhada para o servico externo smartconciliacoes_ia
(diagnostico de divergencias de conciliacao). Usado tanto pela rota
fiscal dedicada (pre_conferencia_service.analisar_divergencia, que monta
o payload re-derivando dados do banco) quanto pela rota generica
(routers/analise_ia_router.py, usada por financeiro/bancario/estoque, que
so' reencaminha o que o frontend ja tem calculado).
"""
import logging

import httpx
from fastapi import HTTPException

from core.config import settings

logger = logging.getLogger(__name__)


def chamar_diagnostico(payload: dict) -> dict:
    if not settings.SMARTCONCILIACOES_IA_URL:
        raise HTTPException(503, "SMARTCONCILIACOES_IA_URL nao configurada.")

    headers = {"X-API-Key": settings.SMARTCONCILIACOES_IA_API_KEY} if settings.SMARTCONCILIACOES_IA_API_KEY else {}
    try:
        resp = httpx.post(
            f"{settings.SMARTCONCILIACOES_IA_URL}/api/v1/analise/divergencia",
            json=payload, headers=headers, timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as e:
        logger.exception("Erro ao chamar smartconciliacoes_ia")
        raise HTTPException(502, f"Erro ao chamar servico de analise IA: {e}")
