"""
Router para endpoints de Conciliacao de Estoque.

Endpoints:
- POST /conciliacoes/estoque - Processa conciliacao de estoque (Kardex vs Razao)
- POST /conciliacoes/estoque/efetivar - Efetiva conciliacao de estoque
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
import logging
import json

from schemas.conciliacao_estoque_schema import (
    RequestConciliacaoEstoque,
)
from services.conciliacao_estoque_service import ConciliacaoEstoqueService
from services.conciliacao_estoque_efetivacao_service import ConciliacaoEstoqueEfetivacaoService
from services import balancete_service
from schemas.efetivacao_schema import EfetivarConciliacaoResponse, StatusConciliacao
from middleware.auth import get_current_user, CurrentUser
from db import get_db
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/conciliacoes",
    tags=["Conciliacao Estoque"],
)


@router.post("/estoque", response_model=None)
def processar_conciliacao_estoque(request: RequestConciliacaoEstoque, db: Session = Depends(get_db)):
    """
    Processa conciliacao de estoque.

    Recebe:
    - base_kardex: Kardex de estoque (movimentacoes)
    - base_razao: Razao contabil de estoque (CTBR400)
    - parametros: Data-base e configuracoes

    Retorna:
    - Relatorio completo de conciliacao de estoque
    """
    logger.info("=" * 50)
    logger.info("ENDPOINT: POST /conciliacoes/estoque")
    logger.info("=" * 50)

    service = ConciliacaoEstoqueService()

    valido, mensagem = service.validar_dados(request)
    if not valido:
        logger.error(f"Validacao falhou: {mensagem}")
        raise HTTPException(status_code=400, detail=mensagem)

    try:
        resultado = service.executar(request)

        # Validar saldo calculado contra balancete importado (se houver)
        resumo = resultado.get("resumo", {})
        movimentos_periodo = float(resumo.get("total_debito_razao", 0) or 0) - float(
            resumo.get("total_credito_razao", 0) or 0
        )
        validacao_balancete = balancete_service.validar_saldo_calculado(
            db,
            request.parametros.empresa_id,
            request.base_razao.conta_contabil_id,
            request.parametros.data_base,
            movimentos_periodo,
        )
        if validacao_balancete:
            resumo.update(validacao_balancete)

        logger.info("Conciliacao de estoque executada com sucesso")
        return resultado

    except ValueError as e:
        logger.error(f"Erro de validacao: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.exception(f"Erro interno: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno ao processar conciliacao de estoque: {str(e)}"
        )


@router.post("/estoque/efetivar", response_model=EfetivarConciliacaoResponse, status_code=201)
async def efetivar_conciliacao_estoque(
    dados: str = Form(..., description="JSON com dados da conciliacao de estoque"),
    arquivo_kardex: UploadFile = File(..., description="Arquivo Excel do Kardex"),
    arquivo_razao: UploadFile = File(..., description="Arquivo Excel do Razao contabil"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Efetiva uma conciliacao de estoque.

    Requisitos:
    - Nao deve haver divergencias (situacao deve ser CONCILIADO)
    - Periodo nao pode ter sido efetivado anteriormente

    Recebe via FormData:
    - dados: JSON string com empresa_id, conta_contabil_id, data_base, resultado
    - arquivo_kardex: Arquivo Excel do Kardex original
    - arquivo_razao: Arquivo Excel do Razao contabil original
    """
    try:
        dados_json = json.loads(dados)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="JSON invalido no campo 'dados'")

    # Validar acesso a empresa
    empresa_id = dados_json.get("empresa_id")
    if not current_user.is_admin and current_user.empresa_id != empresa_id:
        raise HTTPException(status_code=403, detail="Sem acesso a esta empresa")

    kardex_bytes = await arquivo_kardex.read()
    razao_bytes = await arquivo_razao.read()

    service = ConciliacaoEstoqueEfetivacaoService()
    conciliacao = service.efetivar(
        db=db,
        empresa_id=empresa_id,
        conta_contabil_id=dados_json["conta_contabil_id"],
        data_base=dados_json["data_base"],
        resultado=dados_json["resultado"],
        current_user=current_user,
        arquivo_kardex=kardex_bytes,
        arquivo_razao=razao_bytes,
        nome_kardex=arquivo_kardex.filename or "kardex.xlsx",
        nome_razao=arquivo_razao.filename or "razao.xlsx"
    )
    return EfetivarConciliacaoResponse(
        id=conciliacao.id,
        message="Conciliacao de estoque efetivada com sucesso",
        status=StatusConciliacao.EFETIVADA,
        data_efetivacao=conciliacao.data_efetivacao
    )
