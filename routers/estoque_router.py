from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from db import get_db
from middleware.permission import require_permission, Permissions
from middleware.tenant import EmpresaContext, resolve_empresa_id
from schemas.estoque_schema import (
    SaldoOut,
    MovimentacaoOut,
    AjusteRequest,
    ReprocessarRequest,
    FechamentoRequest,
    FechamentoOut,
    ReaberturaRequest,
)
from services import estoque_service, fechamento_service, relatorio_service

router = APIRouter(prefix="/api/estoque", tags=["estoque"])


# ── Saldos ───────────────────────────────────────────────────────────────────

@router.get("/saldos", response_model=list[SaldoOut])
def listar_saldos(
    empresa_id: int | None = Query(None),
    periodo: date = Query(...),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission(Permissions.ESTOQUE_READ)),
):
    empresa_id_resolvido = resolve_empresa_id(context, empresa_id)
    return estoque_service.listar_saldos(db, empresa_id_resolvido, periodo)


@router.post("/reprocessar")
def reprocessar_periodo(
    req: ReprocessarRequest,
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission(Permissions.ESTOQUE_WRITE)),
):
    empresa_id = resolve_empresa_id(context, req.empresa_id)
    count = estoque_service.reprocessar_periodo(db, empresa_id, req.periodo)
    return {"message": f"{count} produto(s) reprocessado(s).", "count": count}


# ── Movimentações ─────────────────────────────────────────────────────────────

@router.get("/movimentacoes", response_model=list[MovimentacaoOut])
def listar_movimentacoes(
    empresa_id: int | None = Query(None),
    produto_id: int | None = Query(None),
    periodo: date | None = Query(None),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission(Permissions.ESTOQUE_READ)),
):
    empresa_id_resolvido = resolve_empresa_id(context, empresa_id)
    return estoque_service.listar_movimentacoes(db, empresa_id_resolvido, produto_id, periodo)


@router.post("/ajuste", response_model=MovimentacaoOut)
def registrar_ajuste(
    req: AjusteRequest,
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission(Permissions.ESTOQUE_WRITE)),
):
    req_resolvido = req.model_copy(
        update={"empresa_id": resolve_empresa_id(context, req.empresa_id)}
    )
    return estoque_service.registrar_ajuste(db, req_resolvido)


# ── Fechamento ───────────────────────────────────────────────────────────────

@router.post("/fechar", response_model=FechamentoOut)
def fechar_periodo(
    req: FechamentoRequest,
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission(Permissions.ESTOQUE_WRITE)),
):
    empresa_id = resolve_empresa_id(context, req.empresa_id)
    return fechamento_service.fechar_periodo(db, empresa_id, req.periodo)


@router.post("/reabrir", response_model=FechamentoOut)
def reabrir_periodo(
    req: ReaberturaRequest,
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission(Permissions.ESTOQUE_WRITE)),
):
    empresa_id = resolve_empresa_id(context, req.empresa_id)
    return fechamento_service.reabrir_periodo(db, empresa_id, req.periodo)


@router.get("/fechamentos")
def listar_fechamentos(
    empresa_id: int | None = Query(None),
    ano: int = Query(...),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission(Permissions.ESTOQUE_READ)),
):
    empresa_id_resolvido = resolve_empresa_id(context, empresa_id)
    return fechamento_service.listar_status_fechamentos(db, empresa_id_resolvido, ano)


# ── Relatórios ────────────────────────────────────────────────────────────────

@router.get("/relatorio/saldos/excel")
def exportar_saldos_excel(
    empresa_id: int | None = Query(None),
    periodo: date = Query(...),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission(Permissions.ESTOQUE_READ)),
):
    empresa_id_resolvido = resolve_empresa_id(context, empresa_id)
    data = relatorio_service.gerar_excel_saldos(db, empresa_id_resolvido, periodo)
    filename = f"saldos_{periodo.strftime('%Y_%m')}.xlsx"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/relatorio/saldos/pdf")
def exportar_saldos_pdf(
    empresa_id: int | None = Query(None),
    periodo: date = Query(...),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission(Permissions.ESTOQUE_READ)),
):
    empresa_id_resolvido = resolve_empresa_id(context, empresa_id)
    data = relatorio_service.gerar_pdf_saldos(db, empresa_id_resolvido, periodo)
    filename = f"saldos_{periodo.strftime('%Y_%m')}.pdf"
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/relatorio/movimentacoes/excel")
def exportar_movimentacoes_excel(
    empresa_id: int | None = Query(None),
    produto_id: int | None = Query(None),
    periodo: date | None = Query(None),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission(Permissions.ESTOQUE_READ)),
):
    empresa_id_resolvido = resolve_empresa_id(context, empresa_id)
    data = relatorio_service.gerar_excel_movimentacoes(db, empresa_id_resolvido, produto_id, periodo)
    filename = f"movimentacoes_{periodo.strftime('%Y_%m') if periodo else 'todos'}.xlsx"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/relatorio/movimentacoes/pdf")
def exportar_movimentacoes_pdf(
    empresa_id: int | None = Query(None),
    produto_id: int | None = Query(None),
    periodo: date | None = Query(None),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission(Permissions.ESTOQUE_READ)),
):
    empresa_id_resolvido = resolve_empresa_id(context, empresa_id)
    data = relatorio_service.gerar_pdf_movimentacoes(db, empresa_id_resolvido, produto_id, periodo)
    filename = f"movimentacoes_{periodo.strftime('%Y_%m') if periodo else 'todos'}.pdf"
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
