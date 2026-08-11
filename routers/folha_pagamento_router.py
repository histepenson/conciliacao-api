import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.particularidades import ChaveParticularidade
from core.protheus import resolve_protheus_config
from core.situacoes_folha import SituacaoConferenciaFolha
from db import get_db
from middleware.empresa_config import require_configuracao
from middleware.tenant import EmpresaContext, get_empresa_context, resolve_empresa_id
from schemas.folha_pagamento_schema import FolhaSituacaoResponse
from services.folha_pagamento_service import FolhaPagamentoService

router = APIRouter(
    prefix="/v1/folha-pagamento",
    tags=["Folha Pagamento"],
    dependencies=[Depends(require_configuracao(ChaveParticularidade.TEM_CONFERENCIA_FOLHA))],
)
logger = logging.getLogger(__name__)


def _get_service(context: EmpresaContext, empresa_id: Optional[int], db: Session) -> FolhaPagamentoService:
    resolved_id = resolve_empresa_id(context, empresa_id)
    cfg = resolve_protheus_config(resolved_id, db)
    return FolhaPagamentoService(cfg.url, cfg.user, cfg.password, cfg.tenant, cfg.rest_prefix)


async def _buscar(service: FolhaPagamentoService, situacao: SituacaoConferenciaFolha, params: dict) -> dict:
    try:
        return await service.buscar_situacao(situacao, params)
    except Exception as exc:
        logger.exception("Erro ao consultar ZFOLPAGAPI/%s", situacao.value)
        raise HTTPException(status_code=502, detail=f"Erro ao consultar Protheus: {exc}")


@router.get("/emprestimo-funcionario", response_model=FolhaSituacaoResponse)
async def get_emprestimo_funcionario(
    vencto: str = Query(..., description="Vencimento exato, formato YYYYMMDD"),
    empresa_id: Optional[int] = Query(None),
    context: EmpresaContext = Depends(get_empresa_context),
    db: Session = Depends(get_db),
):
    service = _get_service(context, empresa_id, db)
    return await _buscar(service, SituacaoConferenciaFolha.EMPRESTIMO_FUNCIONARIO, {"vencto": vencto})


@router.get("/adiantamento-ferias", response_model=FolhaSituacaoResponse)
async def get_adiantamento_ferias(
    baixa_de: str = Query(..., description="Baixa (de), formato YYYYMMDD"),
    baixa_ate: str = Query(..., description="Baixa (ate), formato YYYYMMDD"),
    historico_competencia: str = Query(..., description="Competencia no historico, formato MMAAAA"),
    datarq: str = Query(..., description="Competencia da folha (RD_DATARQ), formato AAAAMM"),
    empresa_id: Optional[int] = Query(None),
    context: EmpresaContext = Depends(get_empresa_context),
    db: Session = Depends(get_db),
):
    service = _get_service(context, empresa_id, db)
    return await _buscar(service, SituacaoConferenciaFolha.ADIANTAMENTO_FERIAS, {
        "baixa_de": baixa_de, "baixa_ate": baixa_ate,
        "historico_competencia": historico_competencia, "datarq": datarq,
    })


@router.get("/adiantamento-rescisao", response_model=FolhaSituacaoResponse)
async def get_adiantamento_rescisao(
    baixa_de: str = Query(..., description="Baixa (de), formato YYYYMMDD"),
    baixa_ate: str = Query(..., description="Baixa (ate), formato YYYYMMDD"),
    historico_competencia: str = Query(..., description="Competencia no historico, formato MMAAAA"),
    empresa_id: Optional[int] = Query(None),
    context: EmpresaContext = Depends(get_empresa_context),
    db: Session = Depends(get_db),
):
    service = _get_service(context, empresa_id, db)
    return await _buscar(service, SituacaoConferenciaFolha.ADIANTAMENTO_RESCISAO, {
        "baixa_de": baixa_de, "baixa_ate": baixa_ate, "historico_competencia": historico_competencia,
    })


@router.get("/fgts", response_model=FolhaSituacaoResponse)
async def get_fgts(
    vencto: str = Query(..., description="Vencimento exato, formato YYYYMMDD"),
    empresa_id: Optional[int] = Query(None),
    context: EmpresaContext = Depends(get_empresa_context),
    db: Session = Depends(get_db),
):
    service = _get_service(context, empresa_id, db)
    return await _buscar(service, SituacaoConferenciaFolha.FGTS, {"vencto": vencto})


@router.get("/irrf", response_model=FolhaSituacaoResponse)
async def get_irrf(
    datpgt_maior_que: str = Query(..., description="RD_DATPGT >, formato YYYYMMDD"),
    datarq_de: str = Query(..., description="RD_DATARQ (de), formato AAAAMM"),
    datarq_ate: str = Query(..., description="RD_DATARQ (ate), formato AAAAMM"),
    emissao_de: str = Query(..., description="E2_EMISSAO (de), formato YYYYMMDD"),
    emissao_ate: str = Query(..., description="E2_EMISSAO (ate), formato YYYYMMDD"),
    empresa_id: Optional[int] = Query(None),
    context: EmpresaContext = Depends(get_empresa_context),
    db: Session = Depends(get_db),
):
    service = _get_service(context, empresa_id, db)
    return await _buscar(service, SituacaoConferenciaFolha.IRRF, {
        "datpgt_maior_que": datpgt_maior_que, "datarq_de": datarq_de, "datarq_ate": datarq_ate,
        "emissao_de": emissao_de, "emissao_ate": emissao_ate,
    })


@router.get("/inss", response_model=FolhaSituacaoResponse)
async def get_inss(
    vencto: str = Query(..., description="Vencimento exato, formato YYYYMMDD"),
    empresa_id: Optional[int] = Query(None),
    context: EmpresaContext = Depends(get_empresa_context),
    db: Session = Depends(get_db),
):
    service = _get_service(context, empresa_id, db)
    return await _buscar(service, SituacaoConferenciaFolha.INSS, {"vencto": vencto})


@router.get("/fgts-rescisorio", response_model=FolhaSituacaoResponse)
async def get_fgts_rescisorio(
    baixa_de: str = Query(..., description="Baixa (de), formato YYYYMMDD"),
    baixa_ate: str = Query(..., description="Baixa (ate), formato YYYYMMDD"),
    historico_competencia: str = Query(..., description="Competencia no historico, formato MMAAAA"),
    empresa_id: Optional[int] = Query(None),
    context: EmpresaContext = Depends(get_empresa_context),
    db: Session = Depends(get_db),
):
    service = _get_service(context, empresa_id, db)
    return await _buscar(service, SituacaoConferenciaFolha.FGTS_RESCISORIO, {
        "baixa_de": baixa_de, "baixa_ate": baixa_ate, "historico_competencia": historico_competencia,
    })


@router.get("/contribuicao-assistencial", response_model=FolhaSituacaoResponse)
async def get_contribuicao_assistencial(
    vencto: str = Query(..., description="Vencimento exato, formato YYYYMMDD"),
    empresa_id: Optional[int] = Query(None),
    context: EmpresaContext = Depends(get_empresa_context),
    db: Session = Depends(get_db),
):
    service = _get_service(context, empresa_id, db)
    return await _buscar(service, SituacaoConferenciaFolha.CONTRIBUICAO_ASSISTENCIAL, {"vencto": vencto})


@router.get("/salario", response_model=FolhaSituacaoResponse)
async def get_salario(
    baixa_de: str = Query(..., description="Baixa (de), formato YYYYMMDD"),
    baixa_ate: str = Query(..., description="Baixa (ate), formato YYYYMMDD"),
    empresa_id: Optional[int] = Query(None),
    context: EmpresaContext = Depends(get_empresa_context),
    db: Session = Depends(get_db),
):
    service = _get_service(context, empresa_id, db)
    return await _buscar(service, SituacaoConferenciaFolha.SALARIO, {"baixa_de": baixa_de, "baixa_ate": baixa_ate})


@router.get("/ferias-a-pagar", response_model=FolhaSituacaoResponse)
async def get_ferias_a_pagar(
    datarq: str = Query(..., description="Competencia da folha (RD_DATARQ), formato AAAAMM"),
    empresa_id: Optional[int] = Query(None),
    context: EmpresaContext = Depends(get_empresa_context),
    db: Session = Depends(get_db),
):
    service = _get_service(context, empresa_id, db)
    return await _buscar(service, SituacaoConferenciaFolha.FERIAS_A_PAGAR, {"datarq": datarq})


@router.get("/pensao-alimenticia", response_model=FolhaSituacaoResponse)
async def get_pensao_alimenticia(
    baixa_de: str = Query(..., description="Baixa (de), formato YYYYMMDD"),
    baixa_ate: str = Query(..., description="Baixa (ate), formato YYYYMMDD"),
    empresa_id: Optional[int] = Query(None),
    context: EmpresaContext = Depends(get_empresa_context),
    db: Session = Depends(get_db),
):
    service = _get_service(context, empresa_id, db)
    return await _buscar(service, SituacaoConferenciaFolha.PENSAO_ALIMENTICIA, {"baixa_de": baixa_de, "baixa_ate": baixa_ate})


@router.get("/plr", response_model=FolhaSituacaoResponse)
async def get_plr(
    empresa_id: Optional[int] = Query(None),
    context: EmpresaContext = Depends(get_empresa_context),
    db: Session = Depends(get_db),
):
    service = _get_service(context, empresa_id, db)
    return await _buscar(service, SituacaoConferenciaFolha.PLR, {})
