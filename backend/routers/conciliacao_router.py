"""
Endpoint FastAPI para conciliação usando Framework AGNO
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
import os
from services.agente_conciliacao import AgenteConciliacaoAGNO

router = APIRouter(prefix="/conciliacao", tags=["Conciliação"])

# Configuração
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY não configurada!")

# Inicializa agente AGNO uma vez
agente = AgenteConciliacaoAGNO(anthropic_api_key=ANTHROPIC_API_KEY)


@router.post("/processar")
async def processar_conciliacao(
    arquivo_origem: UploadFile = File(..., description="Arquivo origem (Excel)"),
    arquivo_contabil: UploadFile = File(..., description="Arquivo destino contábil (Excel)"),
    arquivo_geral_contabilidade: UploadFile = File(..., description="Lançamentos contábeis (Excel)"),
    conta_contabil: str = Form(..., description="Conta contábil sendo conciliada"),
    data_base: str = Form(..., description="Data base da conciliação"),
    empresa_id: int = Form(..., description="ID da empresa")
):
    """
    Processa conciliação contábil usando agente AGNO framework.
    
    O agente AGNO orquestra todo o processamento:
    - Lê e analisa os 3 arquivos Excel
    - Compara totais entre origem e destino
    - Identifica diferenças
    - Rastreia cada divergência nos lançamentos
    - Classifica situações
    - Retorna JSON estruturado
    
    Returns:
        JSON com análise completa da conciliação
    """
    
    try:
        # Lê bytes dos arquivos
        bytes_origem = await arquivo_origem.read()
        bytes_contabil = await arquivo_contabil.read()
        bytes_lancamentos = await arquivo_geral_contabilidade.read()
        
        # Valida formato
        formatos_validos = [
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-excel'
        ]
        
        if (arquivo_origem.content_type not in formatos_validos or
            arquivo_contabil.content_type not in formatos_validos or
            arquivo_geral_contabilidade.content_type not in formatos_validos):
            raise HTTPException(
                status_code=400,
                detail="Todos os arquivos devem ser Excel (.xlsx ou .xls)"
            )
        
        # Processa com agente AGNO
        print(f"🤖 Iniciando processamento com agente AGNO...")
        print(f"   Conta: {conta_contabil}")
        print(f"   Data: {data_base}")
        print(f"   Empresa: {empresa_id}")
        
        resultado = agente.processar_arquivos_excel(
            arquivo_origem=bytes_origem,
            arquivo_destino=bytes_contabil,
            arquivo_lancamentos=bytes_lancamentos
        )
        
        print(f"✅ Processamento concluído!")
        
        # Adiciona metadados
        resultado["metadados"] = {
            "conta_contabil": conta_contabil,
            "data_base": data_base,
            "empresa_id": empresa_id,
            "arquivos": {
                "origem": arquivo_origem.filename,
                "contabil": arquivo_contabil.filename,
                "lancamentos": arquivo_geral_contabilidade.filename
            },
            "processado_por": "AGNO Framework Agent"
        }
        
        # Flags de diferenças
        tem_diferencas = (
            len(resultado.get("diferencas_origem_maior", [])) > 0 or
            len(resultado.get("diferencas_contabilidade_maior", [])) > 0
        )
        
        resultado["diferencas_encontradas"] = tem_diferencas
        resultado["total_diferencas"] = (
            len(resultado.get("diferencas_origem_maior", [])) +
            len(resultado.get("diferencas_contabilidade_maior", []))
        )
        
        print(f"   Diferenças encontradas: {tem_diferencas}")
        print(f"   Total de diferenças: {resultado['total_diferencas']}")
        
        return resultado
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Erro ao processar: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao processar conciliação: {str(e)}"
        )


@router.post("/efetivar")
async def efetivar_conciliacao(
    conta_contabil: str = Form(...),
    data_base: str = Form(...),
    empresa_id: int = Form(...),
    resultado: dict = Form(...)
):
    """
    Efetiva uma conciliação no banco de dados.
    
    Só permite efetivar se não houver diferenças.
    """
    
    try:
        # Valida se pode efetivar
        tem_diferencas = (
            resultado.get("diferencas_encontradas", False) or
            resultado.get("total_diferencas", 0) > 0
        )
        
        if tem_diferencas:
            raise HTTPException(
                status_code=400,
                detail="Não é possível efetivar! Existem diferenças no relatório."
            )
        
        # TODO: Implementar gravação no banco
        print(f"✅ Efetivando conciliação:")
        print(f"   Conta: {conta_contabil}")
        print(f"   Data: {data_base}")
        print(f"   Empresa: {empresa_id}")
        
        return {
            "success": True,
            "message": "Conciliação efetivada com sucesso",
            "conta_contabil": conta_contabil,
            "data_base": data_base,
            "processado_por": "AGNO Framework Agent"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao efetivar conciliação: {str(e)}"
        )


@router.get("/status")
async def verificar_status():
    """
    Verifica se o agente AGNO está configurado corretamente.
    """
    return {
        "status": "ok",
        "framework": "AGNO",
        "anthropic_api_configured": bool(ANTHROPIC_API_KEY),
        "agent_ready": True
    }