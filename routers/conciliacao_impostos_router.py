"""
Router para endpoints de Conciliacao de Impostos.

Endpoints:
- POST /conciliacoes/impostos - Processa conciliacao de impostos
- POST /conciliacoes/impostos/efetivar - Efetiva conciliacao de impostos
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
import logging
import json

from schemas.conciliacao_impostos_schema import RequestConciliacaoImpostos
from services.conciliacao_impostos_service import ConciliacaoImpostosService, COLUNAS_IMPOSTO_SFT
from services.conciliacao_impostos_efetivacao_service import ConciliacaoImpostosEfetivacaoService
from schemas.efetivacao_schema import EfetivarConciliacaoResponse, StatusConciliacao
from middleware.auth import get_current_user, CurrentUser
from db import get_db
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/conciliacoes",
    tags=["Conciliacao de Impostos"],
)


@router.get("/impostos/colunas-disponiveis")
def listar_colunas_imposto():
    """Lista as colunas de imposto do SFT disponiveis para o usuario escolher."""
    return [
        {"campo": campo, "label": label}
        for campo, label in COLUNAS_IMPOSTO_SFT.items()
    ]


@router.post("/impostos", response_model=None)
def processar_conciliacao_impostos(request: RequestConciliacaoImpostos, db: Session = Depends(get_db)):
    """
    Processa conciliacao de impostos.

    Recebe:
    - base_sft: Entradas fiscais (SFTENT)
    - base_razao: Razao contabil com ct2_key (CT2RAZCT5)
    - parametros: Data-base, conta contabil e coluna de imposto escolhida

    Retorna:
    - Relatorio de conciliacao de impostos (somente diferencas)
    """
    logger.info("=" * 50)
    logger.info("ENDPOINT: POST /conciliacoes/impostos")
    logger.info("=" * 50)

    service = ConciliacaoImpostosService()

    valido, mensagem = service.validar_dados(request)
    if not valido:
        logger.error(f"Validacao falhou: {mensagem}")
        raise HTTPException(status_code=400, detail=mensagem)

    try:
        resultado = service.executar(request)
        logger.info("Conciliacao de impostos executada com sucesso")
        return resultado

    except ValueError as e:
        logger.error(f"Erro de validacao: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.exception(f"Erro interno: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno ao processar conciliacao de impostos: {str(e)}"
        )


@router.post("/impostos/efetivar", response_model=EfetivarConciliacaoResponse, status_code=201)
async def efetivar_conciliacao_impostos(
    dados: str = Form(...),
    arquivo_sft: UploadFile = File(...),
    arquivo_razao: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    try:
        dados_json = json.loads(dados)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="JSON invalido no campo 'dados'")

    sft_bytes = await arquivo_sft.read()
    razao_bytes = await arquivo_razao.read()

    service = ConciliacaoImpostosEfetivacaoService()
    conciliacao = service.efetivar(
        db=db,
        empresa_id=dados_json["empresa_id"],
        conta_contabil_id=dados_json["conta_contabil_id"],
        data_base=dados_json["data_base"],
        campo_imposto=dados_json["campo_imposto"],
        resultado=dados_json["resultado"],
        current_user=current_user,
        arquivo_sft=sft_bytes,
        arquivo_razao=razao_bytes,
        nome_sft=arquivo_sft.filename or "sft.xlsx",
        nome_razao=arquivo_razao.filename or "razao.xlsx"
    )
    return EfetivarConciliacaoResponse(
        id=conciliacao.id,
        message="Conciliacao de impostos efetivada com sucesso",
        status=StatusConciliacao.EFETIVADA,
        data_efetivacao=conciliacao.data_efetivacao
    )
