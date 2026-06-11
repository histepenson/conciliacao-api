from fastapi import APIRouter, Depends, BackgroundTasks, Query, UploadFile, File
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date

from db import get_db
from middleware.permission import require_permission
from middleware.tenant import EmpresaContext, resolve_empresa_id
from schemas.nfe_schema import (
    NfeEntradaOut, NfeSaidaOut, NfeItemVinculoRequest,
    NfeImportarRequest, TaskStatusOut,
)
from schemas.estoque_alerta_schema import AlertaOut
from models.nfe import NfeEntrada, NfeSaida, NfeEntradaItem, NfeSaidaItem
from models.estoque_alerta import EstoqueAlerta
from services import task_service
from services.nfe_service import (
    importar_nfes_background,
    importar_nfe_saida_xml,
    cancelar_nfe_entrada, cancelar_nfe_saida,
    vincular_item_entrada, vincular_item_saida,
    reprocessar_nfe_entrada,
)

router = APIRouter(prefix="/nfe", tags=["Estoque - NF-e"])


# ─────────────────────────────────────────
# IMPORTAÇÃO ASSÍNCRONA
# ─────────────────────────────────────────

@router.post("/importar", status_code=202)
def importar(
    payload: NfeImportarRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission("estoque:write")),
):
    """Inicia importação assíncrona de NFs da SEFAZ. Retorna task_id para polling."""
    tid = task_service.criar_task()
    empresa_id = resolve_empresa_id(context, payload.empresa_id)
    background_tasks.add_task(
        importar_nfes_background,
        db,
        empresa_id,
        payload.cnpj_certificado,
        payload.data_inicio,
        payload.data_fim,
        tid,
    )
    return {"task_id": tid, "message": "Importacao iniciada"}


@router.get("/importar/{task_id}", response_model=TaskStatusOut)
def status_importacao(
    task_id: str,
    _: EmpresaContext = Depends(require_permission("estoque:read")),
):
    """Polling do status de importação."""
    from fastapi import HTTPException
    dados = task_service.obter_task(task_id)
    if not dados:
        raise HTTPException(404, "Task nao encontrada")
    return TaskStatusOut(task_id=task_id, **dados)


# ─────────────────────────────────────────
# IMPORTAÇÃO MANUAL DE XML (NF DE SAÍDA)
# ─────────────────────────────────────────

@router.post("/saida/importar-xml")
async def importar_saida_xml(
    files: list[UploadFile] = File(...),
    empresa_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission("estoque:write")),
):
    """
    Importa NF(s) de saída a partir do XML completo (nfeProc), gerado pela
    própria empresa na emissão. A SEFAZ não disponibiliza o XML completo de
    notas emitidas pela empresa via DistDFe, apenas resumo.
    """
    empresa_id = resolve_empresa_id(context, empresa_id)

    resultados = []
    for f in files:
        conteudo = await f.read()
        resultado = importar_nfe_saida_xml(db, empresa_id, conteudo)
        resultado["arquivo"] = f.filename
        resultados.append(resultado)

    return {
        "importadas": sum(1 for r in resultados if r["status"] == "importada"),
        "duplicadas": sum(1 for r in resultados if r["status"] == "duplicada"),
        "erros": sum(1 for r in resultados if r["status"] == "erro"),
        "pendentes_vinculo": sum(r.get("pendentes_vinculo", 0) for r in resultados),
        "detalhes": resultados,
    }


# ─────────────────────────────────────────
# LISTAGEM
# ─────────────────────────────────────────

@router.get("/entrada", response_model=list[NfeEntradaOut])
def listar_entrada(
    empresa_id: Optional[int] = Query(None),
    data_inicio: Optional[date] = Query(None),
    data_fim: Optional[date] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission("estoque:read")),
):
    empresa_id = resolve_empresa_id(context, empresa_id)
    q = db.query(NfeEntrada).filter(NfeEntrada.empresa_id == empresa_id)
    if data_inicio:
        q = q.filter(NfeEntrada.data_autorizacao >= data_inicio)
    if data_fim:
        q = q.filter(NfeEntrada.data_autorizacao <= data_fim)
    if status:
        q = q.filter(NfeEntrada.status == status)
    return q.order_by(NfeEntrada.data_autorizacao.desc()).all()


@router.get("/saida", response_model=list[NfeSaidaOut])
def listar_saida(
    empresa_id: Optional[int] = Query(None),
    data_inicio: Optional[date] = Query(None),
    data_fim: Optional[date] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission("estoque:read")),
):
    empresa_id = resolve_empresa_id(context, empresa_id)
    q = db.query(NfeSaida).filter(NfeSaida.empresa_id == empresa_id)
    if data_inicio:
        q = q.filter(NfeSaida.data_autorizacao >= data_inicio)
    if data_fim:
        q = q.filter(NfeSaida.data_autorizacao <= data_fim)
    if status:
        q = q.filter(NfeSaida.status == status)
    return q.order_by(NfeSaida.data_autorizacao.desc()).all()


# ─────────────────────────────────────────
# CANCELAMENTO
# ─────────────────────────────────────────

@router.patch("/entrada/{nfe_id}/cancelar")
def cancelar_entrada(
    nfe_id: int,
    db: Session = Depends(get_db),
    _: EmpresaContext = Depends(require_permission("estoque:write")),
):
    cancelar_nfe_entrada(db, nfe_id)
    return {"message": "NF de entrada cancelada e estorno gerado"}


@router.patch("/saida/{nfe_id}/cancelar")
def cancelar_saida(
    nfe_id: int,
    db: Session = Depends(get_db),
    _: EmpresaContext = Depends(require_permission("estoque:write")),
):
    cancelar_nfe_saida(db, nfe_id)
    return {"message": "NF de saida cancelada e estorno gerado"}


# ─────────────────────────────────────────
# VÍNCULO MANUAL DE ITEM
# ─────────────────────────────────────────

@router.patch("/entrada/item/{item_id}/vincular")
def vincular_entrada(
    item_id: int,
    body: NfeItemVinculoRequest,
    db: Session = Depends(get_db),
    _: EmpresaContext = Depends(require_permission("estoque:write")),
):
    vincular_item_entrada(db, item_id, body.produto_id)
    return {"message": "Item vinculado com sucesso"}


@router.patch("/saida/item/{item_id}/vincular")
def vincular_saida(
    item_id: int,
    body: NfeItemVinculoRequest,
    db: Session = Depends(get_db),
    _: EmpresaContext = Depends(require_permission("estoque:write")),
):
    vincular_item_saida(db, item_id, body.produto_id)
    return {"message": "Item vinculado com sucesso"}


# ─────────────────────────────────────────
# REPROCESSAR
# ─────────────────────────────────────────

@router.post("/entrada/{nfe_id}/reprocessar")
def reprocessar_entrada(
    nfe_id: int,
    db: Session = Depends(get_db),
    _: EmpresaContext = Depends(require_permission("estoque:write")),
):
    vinculados = reprocessar_nfe_entrada(db, nfe_id)
    return {"message": f"{vinculados} item(ns) vinculado(s) automaticamente"}


# ─────────────────────────────────────────
# ALERTAS
# ─────────────────────────────────────────

@router.get("/alertas", response_model=list[AlertaOut])
def listar_alertas(
    empresa_id: Optional[int] = Query(None),
    resolvido: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission("estoque:read")),
):
    empresa_id = resolve_empresa_id(context, empresa_id)
    q = db.query(EstoqueAlerta).filter(EstoqueAlerta.empresa_id == empresa_id)
    if resolvido is not None:
        q = q.filter(EstoqueAlerta.resolvido == resolvido)
    return q.order_by(EstoqueAlerta.created_at.desc()).all()


@router.patch("/alertas/{alerta_id}/resolver")
def resolver_alerta(
    alerta_id: int,
    db: Session = Depends(get_db),
    _: EmpresaContext = Depends(require_permission("estoque:write")),
):
    from fastapi import HTTPException
    alerta = db.query(EstoqueAlerta).filter(EstoqueAlerta.id == alerta_id).first()
    if not alerta:
        raise HTTPException(404, "Alerta nao encontrado")
    alerta.resolvido = True
    db.commit()
    return {"message": "Alerta marcado como resolvido"}
