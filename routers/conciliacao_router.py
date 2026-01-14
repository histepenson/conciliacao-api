from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
import logging

from schemas.conciliacao_schema import RequestConciliacao
from services.conciliacao_service import ConciliacaoService

router = APIRouter(prefix="/conciliacoes", tags=["Conciliações"])
logger = logging.getLogger(__name__)


@router.post("/contabil")
async def processar_conciliacao(request: RequestConciliacao):
    """
    Processa uma conciliação contábil comparando origem vs contabilidade
    """
    try:
        logger.info("📥 Recebendo requisição de conciliação")
        logger.info(f"📊 Origem: {len(request.base_origem.registros)} registros")
        logger.info(f"📊 Contábil: {len(request.base_contabil_filtrada.registros)} registros")
        logger.info(f"📊 Geral: {len(request.base_contabil_geral.registros)} registros")
        
        service = ConciliacaoService()
        
        # Validar
        valido, mensagem = service.validar_dados(request)
        if not valido:
            logger.error(f"❌ Validação falhou: {mensagem}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=mensagem
            )
        
        # Executar
        resultado = service.executar(request)
        
        logger.info("✅ Conciliação processada com sucesso")
        logger.info(f"📊 Resultado: {resultado.get('resumo', {})}")
        
        # Retornar como dict direto (FastAPI converte para JSON)
        return resultado
        
    except HTTPException:
        raise
        
    except Exception as e:
        logger.error(f"❌ Erro ao processar conciliação: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao processar conciliação: {str(e)}"
        )