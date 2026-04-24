from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
import logging

from schemas.conciliacao_schema import RequestConciliacao
from services.conciliacao_service import ConciliacaoService
from services.ctbr140_service import Ctbr140Service
from core.config import settings

router = APIRouter(prefix="/conciliacoes", tags=["Conciliacoes"])
logger = logging.getLogger(__name__)


async def _resolver_base_contabil(request: RequestConciliacao) -> RequestConciliacao:
    """
    Se base_contabil_filtrada.ctbr140_params estiver preenchido, busca os registros
    diretamente do Protheus (ZCTBR140API) e substitui registros no request.
    Caso contrario, retorna o request inalterado.
    """
    params = request.base_contabil_filtrada.ctbr140_params
    if not params:
        return request

    url = params.protheus_url or getattr(settings, "PROTHEUS_URL", None)
    if not url:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "ctbr140_params fornecido mas PROTHEUS_URL nao configurado. "
                "Informe 'protheus_url' dentro de ctbr140_params ou defina PROTHEUS_URL no .env"
            ),
        )

    user = getattr(settings, "PROTHEUS_USER", "")
    password = getattr(settings, "PROTHEUS_PASSWORD", "")
    tenant_id = getattr(settings, "PROTHEUS_TENANT", "02,0201")
    ctbr140_svc = Ctbr140Service(url, user, password, tenant_id)

    logger.info(
        " Buscando CTBR140 do Protheus -- data_fim=%s  conta_de=%s  conta_ate=%s",
        params.data_fim,
        params.conta_de,
        params.conta_ate,
    )

    registros = await ctbr140_svc.buscar_como_registros(
        params.model_dump(exclude_none=True)
    )
    logger.info(" CTBR140 retornou %s registros do Protheus", len(registros))

    base_filtrada = request.base_contabil_filtrada.model_copy(
        update={"registros": registros}
    )
    return request.model_copy(update={"base_contabil_filtrada": base_filtrada})


@router.post("/contabil")
async def processar_conciliacao(request: RequestConciliacao):
    """
    Processa uma conciliacao contabil comparando origem vs contabilidade.

    **Modos de fornecer a base contabil filtrada (CTBR140):**

    1. **Upload manual** -- envie `base_contabil_filtrada.registros` com os dados
       exportados do relatorio CTBR140 (comportamento original).

    2. **Busca automatica via Protheus** -- preencha `base_contabil_filtrada.ctbr140_params`
       com os parametros do periodo/conta e deixe `registros` vazio (ou omita).
       O backend buscara os dados diretamente da API ZCTBR140API.

    **Modos de fornecer a base geral contabil (CTBR480):**

    1. **Upload manual** -- envie `base_contabil_geral.registros` com os dados
       exportados do relatorio CTBR480 (comportamento original).

    2. **Busca automatica via Protheus** -- preencha `base_contabil_geral.ctbr480_params`
       com os parametros do periodo/item e deixe `registros` vazio (ou omita).
       O backend buscara os dados diretamente da API ZCTBR480API.

    Exemplo com busca automatica de ambos:
    ```json
    {
      "base_contabil_filtrada": {
        "conta_contabil": "1.1.1.01.0001",
        "ctbr140_params": { "data_fim": "20241231" }
      },
      "base_contabil_geral": {
        "ctbr480_params": {
          "data_fim": "20241231",
          "conta_de": "1.1.1.01.0001",
          "conta_ate": "1.1.1.01.0001"
        }
      }
    }
    ```
    """
    try:
        logger.info(" Recebendo requisicao de conciliacao")

        # Resolve base contabil filtrada: busca do Protheus se ctbr140_params presente
        request = await _resolver_base_contabil(request)

        logger.info(" Origem: %s registros", len(request.base_origem.registros))
        logger.info(" Contabil: %s registros", len(request.base_contabil_filtrada.registros))
        logger.info(
            " Geral: %s registros (ctbr480_params=%s)",
            len(request.base_contabil_geral.registros),
            bool(request.base_contabil_geral.ctbr480_params),
        )

        service = ConciliacaoService()

        valido, mensagem = service.validar_dados(request)
        if not valido:
            logger.error(" Validacao falhou: %s", mensagem)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=mensagem,
            )

        # Usa executar_async para suportar busca automatica do CTBR480
        resultado = await service.executar_async(request)

        logger.info(" Conciliacao processada com sucesso")
        logger.info(" Resultado: %s", resultado.get("resumo", {}))

        return resultado

    except HTTPException:
        raise

    except Exception as e:
        logger.error(" Erro ao processar conciliacao: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao processar conciliacao: {str(e)}",
        )