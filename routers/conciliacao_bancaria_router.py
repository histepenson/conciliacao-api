"""
Router para endpoints de Conciliacao Bancaria.

Endpoints:
- POST /conciliacoes/bancaria - Processa conciliacao bancaria
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
import logging
import json
from typing import Optional

from schemas.conciliacao_bancaria_schema import (
    RequestConciliacaoBancaria,
    RelatorioConciliacaoBancaria,
)
from services.conciliacao_bancaria_service import ConciliacaoBancariaService
from services.conciliacao_bancaria_efetivacao_service import ConciliacaoBancariaEfetivacaoService
from services import balancete_service
from schemas.efetivacao_schema import EfetivarConciliacaoResponse, StatusConciliacao
from middleware.auth import get_current_user, CurrentUser
from db import get_db
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/conciliacoes",
    tags=["Conciliacao Bancaria"],
)


@router.post("/bancaria", response_model=None)
def processar_conciliacao_bancaria(request: RequestConciliacaoBancaria, db: Session = Depends(get_db)):
    """
    Processa conciliacao bancaria.

    Recebe:
    - base_extrato: Extrato bancario (FINR470)
    - base_razao: Razao contabil do banco (CTBR400)
    - parametros: Data-base e configuracoes

    Retorna:
    - Relatorio completo de conciliacao bancaria
    """
    logger.info("="*50)
    logger.info("ENDPOINT: POST /conciliacoes/bancaria")
    logger.info("="*50)

    service = ConciliacaoBancariaService()

    # Validar dados de entrada
    valido, mensagem = service.validar_dados(request)
    if not valido:
        logger.error(f"Validacao falhou: {mensagem}")
        raise HTTPException(status_code=400, detail=mensagem)

    try:
        # Executar conciliacao
        resultado = service.executar(request)

        # Validar saldo calculado contra balancete importado (se houver)
        # Movimentos do periodo vem da ORIGEM (extrato bancario): entradas = debito, saidas = credito
        resumo = resultado.get("resumo", {})
        movimentos_periodo = float(resumo.get("total_entradas_extrato", 0) or 0) - float(
            resumo.get("total_saidas_extrato", 0) or 0
        )
        validacao_balancete = balancete_service.validar_saldo_calculado(
            db,
            request.parametros.empresa_id,
            request.base_razao.conta_contabil_id,
            request.parametros.data_base,
            movimentos_periodo,
            saldo_final_origem=resumo.get("saldo_final_extrato"),
        )
        if validacao_balancete:
            resumo.update(validacao_balancete)

            # Saldo bate com o balancete (calculado ou pelo saldo final do proprio
            # extrato) -> considerar tudo conciliado, mesmo com divergencias internas.
            if validacao_balancete.get("balancete_bate") and resumo.get("situacao") != "CONCILIADO":
                for dia_info in resultado.get("movimentos_por_dia", []):
                    dia_info["status"] = "CONCILIADO"
                resultado["dias_conciliados"] = resultado.get("movimentos_por_dia", [])
                resultado["dias_divergentes"] = []
                resultado["registros_so_extrato"] = []
                resultado["registros_so_razao"] = []
                resumo["situacao"] = "CONCILIADO"
                resumo["qtd_conciliados"] = resumo.get("qtd_dias", 0)
                resumo["qtd_divergentes"] = 0
                resumo["percentual_conciliacao"] = 100.0

        logger.info("Conciliacao bancaria executada com sucesso")
        return resultado

    except ValueError as e:
        logger.error(f"Erro de validacao: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.exception(f"Erro interno: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno ao processar conciliacao bancaria: {str(e)}"
        )


@router.post("/bancaria/efetivar", response_model=EfetivarConciliacaoResponse, status_code=201)
async def efetivar_conciliacao_bancaria(
    dados: str = Form(...),
    arquivo_extrato: list[UploadFile] = File(default_factory=list),
    arquivo_razao: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    try:
        dados_json = json.loads(dados)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="JSON invalido no campo 'dados'")

    arquivos_extrato_bytes = [
        (await arquivo.read(), arquivo.filename or "extrato.xlsx")
        for arquivo in arquivo_extrato
        if arquivo.filename
    ]
    razao_bytes = await arquivo_razao.read() if arquivo_razao and arquivo_razao.filename else None

    service = ConciliacaoBancariaEfetivacaoService()
    conciliacao = service.efetivar(
        db=db,
        empresa_id=dados_json["empresa_id"],
        conta_contabil_id=dados_json["conta_contabil_id"],
        data_base=dados_json["data_base"],
        resultado=dados_json["resultado"],
        current_user=current_user,
        arquivos_extrato=arquivos_extrato_bytes or None,
        arquivo_razao=razao_bytes,
        nome_razao=(arquivo_razao.filename if arquivo_razao else None) or "razao.xlsx"
    )
    return EfetivarConciliacaoResponse(
        id=conciliacao.id,
        message="Conciliacao bancaria efetivada com sucesso",
        status=StatusConciliacao.EFETIVADA,
        data_efetivacao=conciliacao.data_efetivacao
    )
