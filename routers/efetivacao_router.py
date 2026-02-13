"""
Router para endpoints de efetivação de conciliações.
"""
import logging
import json
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from db import get_db
from middleware.auth import get_current_user, CurrentUser
from schemas.efetivacao_schema import (
    EfetivarConciliacaoRequest,
    EfetivarConciliacaoResponse,
    ConciliacaoEfetivadaDetalhe,
    ListaConciliacoesEfetivadas,
    ContasEfetivadas,
    ValidacaoEfetivacaoResponse,
    ArquivoDownloadInfo,
    StatusConciliacao,
)
from services.efetivacao_service import EfetivacaoService

router = APIRouter(prefix="/conciliacoes", tags=["Efetivação"])
logger = logging.getLogger(__name__)


@router.post("/efetivar", response_model=EfetivarConciliacaoResponse, status_code=201)
async def efetivar_conciliacao(
    dados: str = Form(..., description="JSON com dados da conciliação"),
    arquivo_origem: UploadFile = File(..., description="Arquivo Excel original de origem"),
    arquivo_contabil_filtrado: UploadFile = File(..., description="Arquivo Excel contábil filtrado"),
    arquivo_contabil_geral: UploadFile = File(..., description="Arquivo Excel contábil geral (razão)"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Efetiva uma conciliação.

    Requisitos:
    - Não deve haver divergências (situação deve ser CONCILIADO)
    - Período não pode ter sido efetivado anteriormente

    Esta operação:
    1. Valida o resultado da conciliação
    2. Salva arquivos originais e normalizados em estrutura hierárquica
    3. Cria registros no banco de dados
    4. É irreversível (somente admin pode excluir)
    """
    logger.info(f"Efetivando conciliação - usuário: {current_user.user_id}")

    # Parse dos dados JSON
    try:
        request_data = json.loads(dados)
        request = EfetivarConciliacaoRequest(**request_data)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"JSON inválido: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dados inválidos: {str(e)}"
        )

    # Validar acesso à empresa
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
        message="Conciliação efetivada com sucesso",
        status=StatusConciliacao.EFETIVADA,
        data_efetivacao=conciliacao.data_efetivacao
    )


@router.get("/efetivadas", response_model=ListaConciliacoesEfetivadas)
async def listar_conciliacoes_efetivadas(
    empresa_id: int = Query(..., description="ID da empresa (obrigatório)"),
    ano: int = Query(..., ge=2000, le=2100, description="Ano do período (obrigatório)"),
    mes: int = Query(..., ge=1, le=12, description="Mês do período 1-12 (obrigatório)"),
    skip: int = Query(0, ge=0, description="Registros a pular"),
    limit: int = Query(50, ge=1, le=100, description="Máximo de registros"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Lista todas as conciliações efetivadas para uma empresa/período.

    Filtros obrigatórios:
    - empresa_id: ID da empresa
    - ano: Ano do período
    - mes: Mês do período (1-12)
    """
    # Validar acesso à empresa
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


@router.get("/contas-efetivadas", response_model=ContasEfetivadas)
async def listar_contas_efetivadas(
    empresa_id: int = Query(..., description="ID da empresa"),
    periodo: str = Query(..., description="Período no formato YYYY-MM"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Lista IDs das contas já efetivadas para uma empresa/período.

    Usado para desabilitar contas na tela de seleção de conciliação.
    """
    # Validar acesso à empresa
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
    Obtém detalhes completos de uma conciliação efetivada.

    Retorna o resultado_json completo com todos os dados de análise,
    na mesma estrutura do resultado original do processamento.
    """
    # Validar acesso à empresa
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
    Lista todos os arquivos disponíveis para download de uma conciliação.
    """
    # Validar acesso à empresa
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
                existe = os.path.exists(caminho) if caminho else False
                tamanho = os.path.getsize(caminho) if existe else None
                nome = os.path.basename(caminho) if caminho else ""

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
    Download de um arquivo de uma conciliação efetivada.

    tipo_arquivo:
    - origem: Dados de origem (financeiro)
    - contabil_filtrado: Dados contábeis filtrados
    - contabil_geral: Dados contábeis gerais (razão)
    - relatorio: Relatório final

    formato:
    - original: Arquivo original como foi enviado
    - normalizado: Dados normalizados pelo sistema
    - json: Apenas para relatorio
    """
    # Validar acesso à empresa
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
    file_path = service.obter_arquivo(db, conciliacao_id, tipo_arquivo, formato, empresa_id)

    # Determinar media type
    if file_path.endswith(".xlsx"):
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif file_path.endswith(".json"):
        media_type = "application/json"
    else:
        media_type = "application/octet-stream"

    filename = os.path.basename(file_path)

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=media_type
    )


@router.delete("/efetivadas/{conciliacao_id}", status_code=204)
async def excluir_conciliacao(
    conciliacao_id: int,
    empresa_id: int = Query(..., description="ID da empresa"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Exclui uma conciliação efetivada.

    **REQUER PERMISSÃO DE ADMINISTRADOR**

    Esta operação:
    - Remove o registro do banco de dados
    - Remove os arquivos do sistema de arquivos
    - Registra a ação no audit log
    """
    # Validar acesso à empresa
    if not current_user.is_admin and current_user.empresa_id != empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem acesso a esta empresa"
        )

    service = EfetivacaoService()
    service.excluir(db, conciliacao_id, empresa_id, current_user)

    # Retorna 204 No Content
    return None
