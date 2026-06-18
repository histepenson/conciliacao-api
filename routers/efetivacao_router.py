"""
Router para endpoints de efetivacao de conciliacoes.
"""
import io
import logging
import json
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form, Response
from sqlalchemy.orm import Session

from core import storage
from db import get_db
from middleware.auth import get_current_user, CurrentUser
from schemas.efetivacao_schema import (
    EfetivarConciliacaoRequest,
    EfetivarConciliacaoResponse,
    ConciliacaoEfetivadaDetalhe,
    ListaConciliacoesEfetivadas,
    ContasEfetivadas,
    PeriodoDisponivel,
    PeriodosDisponiveis,
    ValidacaoEfetivacaoResponse,
    ArquivoDownloadInfo,
    StatusConciliacao,
)
from services.efetivacao_service import EfetivacaoService

router = APIRouter(prefix="/conciliacoes", tags=["Efetivacao"])
logger = logging.getLogger(__name__)


@router.post("/efetivar", response_model=EfetivarConciliacaoResponse, status_code=201)
async def efetivar_conciliacao(
    dados: str = Form(..., description="JSON com dados da conciliacao"),
    arquivo_origem: UploadFile = File(..., description="Arquivo Excel original de origem"),
    arquivo_contabil_filtrado: UploadFile = File(..., description="Arquivo Excel contabil filtrado"),
    arquivo_contabil_geral: UploadFile = File(..., description="Arquivo Excel contabil geral (razao)"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Efetiva uma conciliacao.

    Requisitos:
    - Nao deve haver divergencias (situacao deve ser CONCILIADO)
    - Periodo nao pode ter sido efetivado anteriormente

    Esta operacao:
    1. Valida o resultado da conciliacao
    2. Salva arquivos originais e normalizados em estrutura hierarquica
    3. Cria registros no banco de dados
    4. E irreversivel (somente admin pode excluir)
    """
    logger.info(f"Efetivando conciliacao - usuario: {current_user.user_id}")

    # Parse dos dados JSON
    try:
        request_data = json.loads(dados)
        request = EfetivarConciliacaoRequest(**request_data)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"JSON invalido: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dados invalidos: {str(e)}"
        )

    # Validar acesso a empresa
    if not current_user.is_admin and current_user.empresa_id != request.empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem acesso a esta empresa"
        )

    # Ler arquivos
    arquivo_origem_bytes = await arquivo_origem.read()
    arquivo_contabil_filtrado_bytes = await arquivo_contabil_filtrado.read()
    arquivo_contabil_geral_bytes = await arquivo_contabil_geral.read()

    service = EfetivacaoService()
    conciliacao = service.efetivar(
        db=db,
        request=request,
        current_user=current_user,
        arquivo_origem=arquivo_origem_bytes,
        arquivo_contabil_filtrado=arquivo_contabil_filtrado_bytes,
        arquivo_contabil_geral=arquivo_contabil_geral_bytes,
        nome_origem=arquivo_origem.filename or "origem.xlsx",
        nome_contabil_filtrado=arquivo_contabil_filtrado.filename or "contabil_filtrado.xlsx",
        nome_contabil_geral=arquivo_contabil_geral.filename or "contabil_geral.xlsx"
    )

    return EfetivarConciliacaoResponse(
        id=conciliacao.id,
        message="Conciliacao efetivada com sucesso",
        status=StatusConciliacao.EFETIVADA,
        data_efetivacao=conciliacao.data_efetivacao
    )


@router.get("/efetivadas", response_model=ListaConciliacoesEfetivadas)
async def listar_conciliacoes_efetivadas(
    empresa_id: int = Query(..., description="ID da empresa (obrigatorio)"),
    ano: int = Query(..., ge=2000, le=2100, description="Ano do periodo (obrigatorio)"),
    mes: int = Query(..., ge=1, le=12, description="Mes do periodo 1-12 (obrigatorio)"),
    skip: int = Query(0, ge=0, description="Registros a pular"),
    limit: int = Query(50, ge=1, le=100, description="Maximo de registros"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Lista todas as conciliacoes efetivadas para uma empresa/periodo.

    Filtros obrigatorios:
    - empresa_id: ID da empresa
    - ano: Ano do periodo
    - mes: Mes do periodo (1-12)
    """
    # Validar acesso a empresa
    if not current_user.is_admin and current_user.empresa_id != empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem acesso a esta empresa"
        )

    service = EfetivacaoService()
    items, total = service.listar_efetivadas(
        db=db,
        empresa_id=empresa_id,
        ano=ano,
        mes=mes,
        skip=skip,
        limit=limit
    )

    return ListaConciliacoesEfetivadas(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        has_more=(skip + len(items)) < total
    )


@router.get("/efetivadas/periodos", response_model=PeriodosDisponiveis)
async def listar_periodos_disponiveis(
    empresa_id: int = Query(..., description="ID da empresa"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Lista os periodos (ano/mes) que possuem ao menos uma conciliacao
    efetivada para a empresa. Usado para popular os filtros de ano/mes
    sem mostrar periodos sem nenhum fechamento.
    """
    # Validar acesso a empresa
    if not current_user.is_admin and current_user.empresa_id != empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem acesso a esta empresa"
        )

    service = EfetivacaoService()
    periodos = service.listar_periodos_disponiveis(db, empresa_id)

    return PeriodosDisponiveis(
        periodos=[PeriodoDisponivel(ano=ano, mes=mes) for ano, mes in periodos]
    )


@router.get("/contas-efetivadas", response_model=ContasEfetivadas)
async def listar_contas_efetivadas(
    empresa_id: int = Query(..., description="ID da empresa"),
    periodo: str = Query(..., description="Periodo no formato YYYY-MM"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Lista IDs das contas ja efetivadas para uma empresa/periodo.

    Usado para desabilitar contas na tela de selecao de conciliacao.
    """
    # Validar acesso a empresa
    if not current_user.is_admin and current_user.empresa_id != empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem acesso a esta empresa"
        )

    service = EfetivacaoService()
    contas = service.listar_contas_efetivadas(db, empresa_id, periodo)

    return ContasEfetivadas(contas_efetivadas=contas)


@router.get("/efetivadas/{conciliacao_id}", response_model=ConciliacaoEfetivadaDetalhe)
async def obter_detalhes_conciliacao(
    conciliacao_id: int,
    empresa_id: int = Query(..., description="ID da empresa"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Obtem detalhes completos de uma conciliacao efetivada.

    Retorna o resultado_json completo com todos os dados de analise,
    na mesma estrutura do resultado original do processamento.
    """
    # Validar acesso a empresa
    if not current_user.is_admin and current_user.empresa_id != empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem acesso a esta empresa"
        )

    service = EfetivacaoService()
    return service.obter_detalhes(db, conciliacao_id, empresa_id)


@router.get("/efetivadas/{conciliacao_id}/arquivos", response_model=list[ArquivoDownloadInfo])
async def listar_arquivos_conciliacao(
    conciliacao_id: int,
    empresa_id: int = Query(..., description="ID da empresa"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Lista todos os arquivos disponiveis para download de uma conciliacao.
    """
    # Validar acesso a empresa
    if not current_user.is_admin and current_user.empresa_id != empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem acesso a esta empresa"
        )

    service = EfetivacaoService()
    detalhes = service.obter_detalhes(db, conciliacao_id, empresa_id)

    arquivos = []
    caminhos = detalhes.caminhos_arquivos or {}

    for tipo, formatos in caminhos.items():
        if isinstance(formatos, dict):
            for formato, caminho in formatos.items():
                existe = storage.file_exists(caminho) if caminho else False
                tamanho = storage.get_file_size(caminho) if existe else None
                nome = caminho.rsplit("/", 1)[-1] if caminho else ""

                arquivos.append(ArquivoDownloadInfo(
                    tipo_arquivo=tipo,
                    formato=formato,
                    nome_arquivo=nome,
                    caminho_arquivo=caminho,
                    tamanho_bytes=tamanho,
                    existe=existe
                ))

    return arquivos


@router.get("/efetivadas/{conciliacao_id}/arquivos/{tipo_arquivo}/{formato}")
async def download_arquivo(
    conciliacao_id: int,
    tipo_arquivo: str,
    formato: str,
    empresa_id: int = Query(..., description="ID da empresa"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Download de um arquivo de uma conciliacao efetivada.

    tipo_arquivo:
    - origem: Dados de origem (financeiro)
    - contabil_filtrado: Dados contabeis filtrados
    - contabil_geral: Dados contabeis gerais (razao)
    - relatorio: Relatorio final

    formato:
    - original: Arquivo original como foi enviado
    - normalizado: Dados normalizados pelo sistema
    - json: Apenas para relatorio
    """
    # Validar acesso a empresa
    if not current_user.is_admin and current_user.empresa_id != empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem acesso a esta empresa"
        )

    valid_tipos = ["origem", "contabil_filtrado", "contabil_geral", "relatorio", "extrato", "razao", "kardex"]
    if tipo_arquivo not in valid_tipos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"tipo_arquivo deve ser um de: {valid_tipos}"
        )

    valid_formatos = ["original", "normalizado", "json"]
    if formato not in valid_formatos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"formato deve ser um de: {valid_formatos}"
        )

    service = EfetivacaoService()
    file_key = service.obter_arquivo(db, conciliacao_id, tipo_arquivo, formato, empresa_id)

    filename = file_key.rsplit("/", 1)[-1]
    content = storage.download_bytes(file_key)

    # Arquivos "originais" de conciliacoes vindas direto do Protheus (sem upload manual)
    # sao salvos como JSON puro (ex: finr130_protheus.json) - nao ha planilha real por
    # tras. Para o usuario conseguir abrir no Excel, convertemos para .xlsx aqui.
    if formato == "original" and file_key.endswith(".json") and tipo_arquivo != "relatorio":
        registros = json.loads(content)
        if isinstance(registros, dict):
            registros = registros.get("registros", [])
        df = pd.DataFrame(registros)
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False)
        content = buffer.getvalue()
        filename = filename.rsplit(".", 1)[0] + ".xlsx"
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif file_key.endswith(".xlsx"):
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif file_key.endswith(".xls"):
        media_type = "application/vnd.ms-excel"
    elif file_key.endswith(".csv"):
        media_type = "text/csv"
    elif file_key.endswith(".json"):
        media_type = "application/json"
    else:
        media_type = "application/octet-stream"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.delete("/efetivadas/{conciliacao_id}", status_code=204)
async def excluir_conciliacao(
    conciliacao_id: int,
    empresa_id: int = Query(..., description="ID da empresa"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Exclui uma conciliacao efetivada.

    **REQUER PERMISSAO DE ADMINISTRADOR**

    Esta operacao:
    - Remove o registro do banco de dados
    - Remove os arquivos do sistema de arquivos
    - Registra a acao no audit log
    """
    # Validar acesso a empresa
    if not current_user.is_admin and current_user.empresa_id != empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem acesso a esta empresa"
        )

    service = EfetivacaoService()
    service.excluir(db, conciliacao_id, empresa_id, current_user)

    # Retorna 204 No Content
    return None
