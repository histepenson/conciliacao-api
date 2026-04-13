from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
import logging

from schemas.conciliacao_schema import RequestConciliacao
from services.conciliacao_service import ConciliacaoService
from services.ctbr140_service import Ctbr140Service
from core.config import settings

router = APIRouter(prefix="/conciliacoes", tags=["Conciliações"])
logger = logging.getLogger(__name__)


async def _resolver_base_contabil(request: RequestConciliacao) -> RequestConciliacao:
    """
    Se base_contabil_filtrada.ctbr140_params estiver preenchido, busca os registros
    diretamente do Protheus (ZCTBR140API) e substitui registros no request.
    Caso contrário, retorna o request inalterado.
    """
    params = request.base_contabil_filtrada.ctbr140_params
    if not params:
        return request

    url = params.protheus_url or getattr(settings, "PROTHEUS_URL", None)
    if not url:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "ctbr140_params fornecido mas PROTHEUS_URL não configurado. "
                "Informe 'protheus_url' dentro de ctbr140_params ou defina PROTHEUS_URL no .env"
            ),
        )

    user = getattr(settings, "PROTHEUS_USER", "")
    password = getattr(settings, "PROTHEUS_PASSWORD", "")
    tenant_id = getattr(settings, "PROTHEUS_TENANT", "02,0201")
    ctbr140_svc = Ctbr140Service(url, user, password, tenant_id)

    logger.info(
        "🔗 Buscando CTBR140 do Protheus — data_fim=%s  conta_de=%s  conta_ate=%s",
        params.data_fim,
        params.conta_de,
        params.conta_ate,
    )

    registros = await ctbr140_svc.buscar_como_registros(
        params.model_dump(exclude_none=True)
    )
    logger.info("📊 CTBR140 retornou %s registros do Protheus", len(registros))

    base_filtrada = request.base_contabil_filtrada.model_copy(
        update={"registros": registros}
    )
    return request.model_copy(update={"base_contabil_filtrada": base_filtrada})


@router.post("/contabil")
async def processar_conciliacao(request: RequestConciliacao):
    """
    Processa uma conciliação contábil comparando origem vs contabilidade.

    **Modos de fornecer a base contábil filtrada (CTBR140):**

    1. **Upload manual** — envie `base_contabil_filtrada.registros` com os dados
       exportados do relatório CTBR140 (comportamento original).

    2. **Busca automática via Protheus** — preencha `base_contabil_filtrada.ctbr140_params`
       com os parâmetros do período/conta e deixe `registros` vazio (ou omita).
       O backend buscará os dados diretamente da API ZCTBR140API.

    **Modos de fornecer a base geral contábil (CTBR480):**

    1. **Upload manual** — envie `base_contabil_geral.registros` com os dados
       exportados do relatório CTBR480 (comportamento original).

    2. **Busca automática via Protheus** — preencha `base_contabil_geral.ctbr480_params`
       com os parâmetros do período/item e deixe `registros` vazio (ou omita).
       O backend buscará os dados diretamente da API ZCTBR480API.

    Exemplo com busca automática de ambos:
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
        logger.info("📥 Recebendo requisição de conciliação")

        # Resolve base contábil filtrada: busca do Protheus se ctbr140_params presente
        request = await _resolver_base_contabil(request)

        logger.info("📊 Origem: %s registros", len(request.base_origem.registros))
        logger.info("📊 Contábil: %s registros", len(request.base_contabil_filtrada.registros))
        logger.info(
            "📊 Geral: %s registros (ctbr480_params=%s)",
            len(request.base_contabil_geral.registros),
            bool(request.base_contabil_geral.ctbr480_params),
        )

        service = ConciliacaoService()

        valido, mensagem = service.validar_dados(request)
        if not valido:
            logger.error("❌ Validação falhou: %s", mensagem)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=mensagem,
            )

        # Usa executar_async para suportar busca automática do CTBR480
        resultado = await service.executar_async(request)

        logger.info("✅ Conciliação processada com sucesso")
        logger.info("📊 Resultado: %s", resultado.get("resumo", {}))

        return resultado

    except HTTPException:
        raise

    except Exception as e:
        logger.error("❌ Erro ao processar conciliação: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao processar conciliação: {str(e)}",
        )