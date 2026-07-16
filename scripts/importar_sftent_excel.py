"""
Importa o export bruto da tabela SFT (Livro Fiscal de Entradas) do Protheus
como carga Protheus "manual" tipo SFTENT, para empresas sem acesso a API REST
(ver skill importar-csv-protheus). Usado na Pre-Conferencia (CT2 x SFT).

Layout esperado (header na 1a linha): Filial, Data Entrada, Data Emissao,
Doc. Fiscal, Serie NF, Cli/Forn., Codigo loja, Estado Ref, Cod. Fiscal,
Vlr Contabil, Valor IPI, Vlr ICMS Ret, Especie NF, Quantidade, Valor PIS,
Valor COFINS, CST Pis, Cod.BC Cred., ...

Mapeia para os campos que services/pre_conferencia_service.py le direto do
dados_json: filial, nf, cliefor, serie, cfop, valcont, entrada, emissao,
estado, especie, quant, valipi, icmsret, produto, cstpis, codbcc, valpis,
valcof. Campos opcionais nao presentes no export (tes, difal, icms base/aliq)
ficam de fora - a Pre-Conferencia so exige filial/nf/cliefor/cfop/valcont/entrada.

Uso:
    python scripts/importar_sftent_excel.py \\
        --empresa-id 13 --data-base 20260630 \\
        --excel "C:\\...\\SFT 04.2026.xlsx"
"""
import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.importar_carga_manual import gravar_carga_manual

# Cada campo pode ter mais de um nome possivel de coluna no Excel - o layout
# do export varia entre empresas/versoes do Protheus (ex.: "Doc. Fiscal" vs
# "Nota Fiscal", "Vlr Contábil" vs "Vlr Contab."). Usa o primeiro nome que
# existir na planilha.
_MAPA_COLUNAS = {
    "filial": ["Filial"],
    "entrada": ["Data Entrada"],
    "emissao": ["Data Emissão", "Data Emissao"],
    "nf": ["Doc. Fiscal", "Nota Fiscal"],
    "serie": ["Série NF", "Serie NF", "Serie"],
    "cliefor": ["Cli/Forn.", "Cli/For"],
    "estado": ["Estado Ref", "UF"],
    "cfop": ["Cod. Fiscal", "CFOP"],
    "valcont": ["Vlr Contábil", "Vlr Contab."],
    "valipi": ["Valor IPI", "Vlr. IPI", "Vlr IPI"],
    "valicm": ["Valor ICMS", "Vlr ICMS"],
    "icmsret": ["Vlr ICMS Ret"],
    "icmscom": ["Vlr ICMS Compl"],
    "difal": ["Vlr Difal"],
    "especie": ["Espécie NF", "Especie"],
    "quant": ["Quantidade", "Quant."],
    "produto": ["Cod. Produto", "Cod. Prod."],
    "valpis": ["Valor PIS"],
    "valcof": ["Valor COFINS"],
    "cstpis": ["CST Pis"],
    "codbcc": ["Cod.BC Cred."],
}

_COLUNAS_DATA = {"entrada", "emissao"}
_COLUNAS_VALOR = {"valcont", "valipi", "valicm", "icmsret", "icmscom", "difal", "quant", "valpis", "valcof"}
_COLUNAS_INT_STR = {"filial", "nf", "serie", "cliefor", "cfop", "cstpis", "codbcc"}


def _valor(v):
    if pd.isna(v):
        return 0.0
    return float(v)


def _data_br(v):
    if pd.isna(v):
        return ""
    ts = pd.to_datetime(v, errors="coerce")
    if pd.isna(ts):
        return str(v).strip()
    return ts.strftime("%d/%m/%Y")


def carregar_registros(caminho: str) -> list[dict]:
    df = pd.read_excel(caminho, header=0)

    # Resolve, para cada campo, qual coluna da planilha usar (primeiro alias
    # que existir no arquivo).
    coluna_por_campo = {}
    for campo, aliases in _MAPA_COLUNAS.items():
        for alias in aliases:
            if alias in df.columns:
                coluna_por_campo[campo] = alias
                break

    faltando = [campo for campo in ("filial", "nf", "cliefor", "cfop", "valcont", "entrada") if campo not in coluna_por_campo]
    if faltando:
        print(f"AVISO: colunas obrigatorias nao encontradas no Excel: {faltando}")

    registros = []
    for _, row in df.iterrows():
        registro = {}
        for campo, col in coluna_por_campo.items():
            val = row[col]
            if campo in _COLUNAS_DATA:
                registro[campo] = _data_br(val)
            elif campo in _COLUNAS_VALOR:
                registro[campo] = _valor(val)
            elif campo in _COLUNAS_INT_STR:
                registro[campo] = "" if pd.isna(val) else str(val).strip()
                if registro[campo].endswith(".0"):
                    registro[campo] = registro[campo][:-2]
            else:
                registro[campo] = "" if pd.isna(val) else str(val).strip()
        registros.append(registro)
    return registros


def main():
    parser = argparse.ArgumentParser(description="Importa SFT.xlsx como carga SFTENT")
    parser.add_argument("--empresa-id", type=int, required=True)
    parser.add_argument("--data-base", required=True, help="YYYYMMDD")
    parser.add_argument("--excel", required=True)
    args = parser.parse_args()

    registros = carregar_registros(args.excel)
    print(f"{args.excel}: {len(registros)} registros")

    resultado = gravar_carga_manual(
        empresa_id=args.empresa_id,
        tipo_relatorio="SFTENT",
        data_base=args.data_base,
        registros=registros,
    )
    print(resultado)


if __name__ == "__main__":
    main()
