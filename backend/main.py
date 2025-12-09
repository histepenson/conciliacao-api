"""
API Python para Conciliação com IA
Exemplo usando FastAPI
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from typing import Dict, Any
import os
from datetime import datetime
from tools.financeiro import normalizar_planilha_financeira
from tools.contabilidade import normalizar_planilha_contabilidade
from tools.calc_diferencas import calcular_diferencas


app = FastAPI(title="API Conciliação IA")


origins = [
    "https://conciliacao-app-production.up.railway.app",
    "http://localhost:3000",  # opcional p/ testes locais
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


UPLOAD_DIR = "/tmp/conciliacao"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def ler_arquivo(caminho: str) -> pd.DataFrame:
    if caminho.endswith('.csv'):
        return pd.read_csv(caminho)
    else:
        return pd.read_excel(caminho)


@app.get("/")
async def root():
    return {
        "message": "API Conciliação IA",
        "status": "online",
        "version": "1.0.0"
    }


@app.post("/api/conciliacao/processar")
async def processar_conciliacao(
    arquivo_origem: UploadFile = File(...),
    arquivo_contabil: UploadFile = File(...),
    arquivo_geral_contabilidade: UploadFile = File(...)
) -> Dict[str, Any]:

    try:
        print("\n\n========================= 🚀 INICIANDO PROCESSAMENTO =========================")

        print("📥 Arquivos recebidos:")
        print(f"   → Origem: {arquivo_origem.filename}")
        print(f"   → Contábil: {arquivo_contabil.filename}")
        print(f"   → Geral: {arquivo_geral_contabilidade.filename}")

        # Salvar arquivos
        origem_path = os.path.join(UPLOAD_DIR, arquivo_origem.filename)
        contabil_path = os.path.join(UPLOAD_DIR, arquivo_contabil.filename)
        geral_path = os.path.join(UPLOAD_DIR, arquivo_geral_contabilidade.filename)

        # escrita dos arquivos
        for file, path in [
            (arquivo_origem, origem_path),
            (arquivo_contabil, contabil_path),
            (arquivo_geral_contabilidade, geral_path),
        ]:
            content = await file.read()
            with open(path, "wb") as f:
                f.write(content)

        print("✅ Arquivos salvos!")

        # Lendo arquivos
        print("\n📊 Lendo planilhas...")
        df_origem = ler_arquivo(origem_path)
        df_contabil = ler_arquivo(contabil_path)
        df_geral = ler_arquivo(geral_path)

        print(f"   → Origem: {len(df_origem)} linhas")
        print(f"   → Contábil: {len(df_contabil)} linhas")
        print(f"   → Geral: {len(df_geral)} linhas")

        # ----------------------------------------------------------------------
        # NORMALIZAÇÕES
        # ----------------------------------------------------------------------
        print("\n🔄 Normalizando planilhas...")

        financeiro_nor = normalizar_planilha_financeira(df_origem)
        contabilidade_nor = normalizar_planilha_contabilidade(df_contabil)

        # VALIDAÇÃO – evita retornar None sem explodir erro
        if financeiro_nor is None:
            raise Exception("❌ ERRO: normalizar_planilha_financeira retornou None!")

        if contabilidade_nor is None:
            raise Exception("❌ ERRO: normalizar_planilha_contabilidade retornou None!")

        print(f"   → Financeiro normalizado: {len(financeiro_nor)} linhas")
        print(f"   → Contabilidade normalizada: {len(contabilidade_nor)} linhas")

        # ----------------------------------------------------------------------
        # CALCULAR DIFERENÇAS
        # ----------------------------------------------------------------------
        print("\n📊 Calculando diferenças...")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        arquivo_diferencas = os.path.join(UPLOAD_DIR, f"diferencas_{timestamp}.xlsx")

        resultado_diferencas = calcular_diferencas(
            financeiro_nor,
            contabilidade_nor,
            salvar_arquivo=True,
            caminho_saida=arquivo_diferencas,
        )

        print("📁 Diferenças calculadas e arquivo salvo!")

        # ----------------------------------------------------------------------
        # RESPOSTA FINAL
        # ----------------------------------------------------------------------
        resultado = {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "resumo": {
                "total_origem": len(df_origem),
                "total_contabil": len(df_contabil),
                "total_geral": len(df_geral),
                "financeiro_normalizado": len(financeiro_nor),
                "contabilidade_normalizada": len(contabilidade_nor),
                **resultado_diferencas["resumo"],
            },
            "diferencas": resultado_diferencas["df_completo"].to_dict("records"),
            "arquivo_diferencas": arquivo_diferencas,
            "arquivos_processados": [
                arquivo_origem.filename,
                arquivo_contabil.filename,
                arquivo_geral_contabilidade.filename,
            ],
        }

        print("\n✅ PROCESSAMENTO CONCLUÍDO COM SUCESSO!")
        print("===============================================================================\n\n")
        return resultado

    except Exception as e:
        print("\n🔥 ERRO CRÍTICO NO PROCESSAMENTO:")
        print(str(e))
        print("===============================================================================\n\n")
        raise HTTPException(status_code=500, detail=f"Erro ao processar: {str(e)}")
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)