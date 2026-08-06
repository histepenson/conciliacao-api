# routers/conferencia_leasing_router.py
"""
Conferencia LEASING (BBC): compara a movimentacao unificada dos relatorios
de leasing (Cancelamento, Contratos 2 e 6, Contratos 4, Extrato Bradesco)
contra o razao contabil, agrupado por natureza (cadastro Operacao
Financeira). Modulo exclusivo da empresa BBC, habilitado via
ChaveParticularidade.TEM_CONFERENCIA_LEASING.

Este router fica fino: so orquestra (resolve empresa, chama a camada de
persistencia/servico) -- toda regra de negocio exclusiva da BBC (parsers
dos relatorios, classificacao do extrato Bradesco, motor de matching)
fica isolada em services/estrategias/bbc/, seguindo o mesmo padrao ja
usado para outras particularidades (ver services/estrategias/rancheiro/).
"""
import io
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from db import get_db
from core.particularidades import ChaveParticularidade
from middleware.empresa_config import require_configuracao
from middleware.tenant import EmpresaContext, get_empresa_context, resolve_empresa_id
from models.leasing_lote_importacao import LeasingLoteImportacao
from models.operacao_financeira import OperacaoFinanceira
from schemas.leasing_regra_classificacao_schema import (
    LeasingRegraClassificacaoCreate,
    LeasingRegraClassificacaoResponse,
    LeasingRegraClassificacaoUpdate,
)
from services.estrategias.bbc.leasing_extrato_bradesco import parsear_extrato_bradesco
from services.estrategias.bbc.leasing_imagem_ocr import extrair_naturezas_de_imagens
from services.estrategias.bbc.leasing_matching import conferir as conferir_leasing
from services.estrategias.bbc.leasing_relatorio_diario import parsear_relatorio_diario
from services.estrategias.bbc.leasing_razao_contabil import parsear_razao_contabil
from services.leasing_movimentacao_service import registrar_lote
from services.leasing_razao_service import registrar_lote_razao
from services.leasing_regra_classificacao_service import (
    atualizar_regra,
    buscar_regra,
    criar_regra,
    deletar_regra,
    listar_regras,
)

router = APIRouter(
    prefix="/v1/conferencia-leasing",
    tags=["Conferencia Leasing"],
    dependencies=[Depends(require_configuracao(ChaveParticularidade.TEM_CONFERENCIA_LEASING))],
)


def _upload_relatorio_diario(
    tipo_relatorio: str,
    file: UploadFile,
    empresa_id: Optional[int],
    db: Session,
    context: EmpresaContext,
) -> dict:
    resolved_id = resolve_empresa_id(context, empresa_id)
    try:
        contents = file.file.read()
        df = parsear_relatorio_diario(io.BytesIO(contents))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao ler o arquivo: {e}")
    finally:
        file.file.close()

    return registrar_lote(db, resolved_id, tipo_relatorio, file.filename, context.user_id, df, modalidade="LEASING")


@router.get("/lotes", summary="Listar lotes de importacao ja realizados")
def route_listar_lotes(
    empresa_id: Optional[int] = Query(None, description="ID da empresa"),
    tipo_relatorio: Optional[str] = Query(None, description="Filtra por tipo de relatorio"),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(get_empresa_context),
):
    resolved_id = resolve_empresa_id(context, empresa_id)
    query = db.query(LeasingLoteImportacao).filter(LeasingLoteImportacao.empresa_id == resolved_id)
    if tipo_relatorio:
        query = query.filter(LeasingLoteImportacao.tipo_relatorio == tipo_relatorio.upper())
    lotes = query.order_by(LeasingLoteImportacao.created_at.desc()).all()
    return [
        {
            "id": lote.id,
            "tipo_relatorio": lote.tipo_relatorio,
            "nome_arquivo": lote.nome_arquivo,
            "qtd_linhas": lote.qtd_linhas,
            "status": lote.status,
            "created_at": lote.created_at,
        }
        for lote in lotes
    ]


@router.post("/upload/cancelamento", summary="Upload do Relatorio de Cancelamento")
def route_upload_cancelamento(
    file: UploadFile = File(...),
    empresa_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(get_empresa_context),
):
    return _upload_relatorio_diario("CANCELAMENTO", file, empresa_id, db, context)


@router.post("/upload/contratos-2-6", summary="Upload do Relatorio de Contratos 2 e 6")
def route_upload_contratos_2_6(
    file: UploadFile = File(...),
    empresa_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(get_empresa_context),
):
    return _upload_relatorio_diario("CONTRATOS_2_6", file, empresa_id, db, context)


@router.post("/upload/contratos-4", summary="Upload do Relatorio de Contratos 4")
def route_upload_contratos_4(
    file: UploadFile = File(...),
    empresa_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(get_empresa_context),
):
    return _upload_relatorio_diario("CONTRATOS_4", file, empresa_id, db, context)


@router.post("/upload/imagem", summary="Upload de capturas de tela do Relatorio Movimentacao Diaria (extraido via IA)")
async def route_upload_imagem(
    file: List[UploadFile] = File(...),
    empresa_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(get_empresa_context),
):
    resolved_id = resolve_empresa_id(context, empresa_id)

    imagens = []
    nomes = []
    for upload in file:
        conteudo = await upload.read()
        media_type = upload.content_type or "image/png"
        imagens.append((conteudo, media_type))
        nomes.append(upload.filename or "imagem")

    try:
        df = extrair_naturezas_de_imagens(imagens)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao processar as imagens: {e}")

    nome_arquivo = f"{len(nomes)} imagem(ns): " + ", ".join(nomes[:5]) + ("..." if len(nomes) > 5 else "")
    return registrar_lote(db, resolved_id, "IMAGEM_OCR", nome_arquivo, context.user_id, df, modalidade="LEASING")


@router.post("/upload/bradesco", summary="Upload do Extrato Bradesco")
def route_upload_bradesco(
    file: UploadFile = File(...),
    empresa_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(get_empresa_context),
):
    resolved_id = resolve_empresa_id(context, empresa_id)

    regras = listar_regras(db, resolved_id, apenas_ativas=True)
    if not regras:
        raise HTTPException(
            status_code=400,
            detail="Nenhuma regra de classificacao cadastrada para esta empresa. "
                   "Cadastre ao menos uma regra (Cliente Debitado -> Natureza) antes de importar o extrato.",
        )

    try:
        contents = file.file.read()
        df = parsear_extrato_bradesco(
            io.BytesIO(contents),
            regras=[{"padrao_cliente": r.padrao_cliente, "natureza_codigo": r.natureza_codigo} for r in regras],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao ler o arquivo: {e}")
    finally:
        file.file.close()

    if df.empty:
        raise HTTPException(
            status_code=400,
            detail="Nenhuma linha do extrato bateu com as regras de classificacao cadastradas.",
        )

    naturezas = {
        op.codigo: op.descricao
        for op in db.query(OperacaoFinanceira).filter(
            OperacaoFinanceira.empresa_id == resolved_id,
            OperacaoFinanceira.modalidade == "LEASING",
        ).all()
    }
    df["natureza_descricao"] = df["natureza_codigo"].map(naturezas)

    return registrar_lote(db, resolved_id, "BRADESCO", file.filename, context.user_id, df, modalidade="LEASING")


# ============================================================
# Regras de classificacao do Extrato Bradesco (Cliente Debitado -> Natureza)
# ============================================================

@router.get("/regras-classificacao", response_model=List[LeasingRegraClassificacaoResponse])
def route_listar_regras(
    empresa_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(get_empresa_context),
):
    resolved_id = resolve_empresa_id(context, empresa_id)
    return listar_regras(db, resolved_id)


@router.post("/regras-classificacao", response_model=LeasingRegraClassificacaoResponse, status_code=201)
def route_criar_regra(
    regra: LeasingRegraClassificacaoCreate,
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(get_empresa_context),
):
    dados = regra.model_dump()
    dados["empresa_id"] = resolve_empresa_id(context, dados.get("empresa_id"))
    return criar_regra(db, dados)


@router.put("/regras-classificacao/{id}", response_model=LeasingRegraClassificacaoResponse)
def route_atualizar_regra(
    id: int,
    regra: LeasingRegraClassificacaoUpdate,
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(get_empresa_context),
):
    updated = atualizar_regra(db, id, regra.model_dump(exclude_unset=True), context.empresa_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Regra de classificacao nao encontrada")
    return updated


@router.delete("/regras-classificacao/{id}", status_code=204)
def route_deletar_regra(
    id: int,
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(get_empresa_context),
):
    sucesso = deletar_regra(db, id, context.empresa_id)
    if not sucesso:
        raise HTTPException(status_code=404, detail="Regra de classificacao nao encontrada")
    return None


@router.post("/upload/razao", summary="Upload do Razao Contabil")
def route_upload_razao(
    file: UploadFile = File(...),
    empresa_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(get_empresa_context),
):
    resolved_id = resolve_empresa_id(context, empresa_id)
    try:
        contents = file.file.read()
        df = parsear_razao_contabil(io.BytesIO(contents))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao ler o arquivo: {e}")
    finally:
        file.file.close()

    return registrar_lote_razao(db, resolved_id, file.filename, context.user_id, df)


@router.get("/conferir", summary="Conferir base unificada x razao contabil, agrupado por natureza")
def route_conferir(
    empresa_id: Optional[int] = Query(None, description="ID da empresa"),
    lote_razao_id: Optional[int] = Query(None, description="Lote do razao a conferir (usa todos se omitido)"),
    lote_movimentacao_ids: Optional[str] = Query(None, description="IDs de lote de movimentacao separados por virgula (usa todos se omitido)"),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(get_empresa_context),
):
    resolved_id = resolve_empresa_id(context, empresa_id)
    ids_mov = None
    if lote_movimentacao_ids:
        try:
            ids_mov = [int(x) for x in lote_movimentacao_ids.split(",") if x.strip()]
        except ValueError:
            raise HTTPException(status_code=400, detail="lote_movimentacao_ids deve ser uma lista de IDs separados por virgula")

    try:
        return conferir_leasing(db, resolved_id, lote_razao_id, ids_mov)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
