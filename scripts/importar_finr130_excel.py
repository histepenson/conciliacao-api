"""
Importa o export nativo do FINR130 (Titulos a Receber) do Protheus, no layout
que a GENIX baixa manualmente (aba com titulo na 1a linha + header na 2a),
como carga Protheus "manual" tipo FINR130 - schema RAW (dados_json com as
mesmas colunas do arquivo, snake_case, sem nenhuma transformacao - ver skill
importar-csv-protheus, secao FINR130).

Layout esperado (aba "2-Titulos a receber" ou similar, header na 2a linha):
    Codigo-Lj-Nome do Cliente, Prf-Numero Parcela, TP, Natureza,
    Data de Emissao, Vencto Titulo, Vencto Real, Bco St, Valor Original,
    Tit Vencidos Valor Atual, Tit Vencidos Valor Corrigido,
    Titulos a Vencer Valor Atual, Num Banco, Vlr.juros ou permanencia,
    Dias Atraso, Historico, (Vencidos+Vencer)

A aba "EXPORTACOES" (quando presente) e' apenas um recorte dos clientes de
exportacao ja incluidos na aba principal - NAO deve ser somada (duplicaria
titulos).

Uso:
    python scripts/importar_finr130_excel.py \\
        --empresa-id 13 --data-base 20260531 \\
        --excel "C:\\...\\finr130.xlsx" --sheet "2-Titulos a receber"
"""
import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.importar_carga_manual import gravar_carga_manual
from tools.balancete import normalizar_nome_colunas

_COLUNAS_DATA = {"vencto_real", "vencto_titulo", "data_de_emissao"}
_COLUNAS_NUMERICAS = {
    "valor_original",
    "tit_vencidos_valor_atual",
    "tit_vencidos_valor_corrigido",
    "titulos_a_vencer_valor_atual",
    "dias_atraso",
}


def _detectar_linha_header(caminho: str, sheet_name) -> int:
    bruto = pd.read_excel(caminho, sheet_name=sheet_name, header=None, nrows=5)
    for i, row in bruto.iterrows():
        valores = [str(v).strip().lower() for v in row.tolist()]
        if any("codigo" in v and "cliente" in v for v in valores):
            return i
    raise SystemExit(f"Nao foi possivel localizar a linha de header (Codigo...Cliente) nas primeiras 5 linhas: {bruto.values.tolist()}")


def _valor_data(v):
    if pd.isna(v):
        return None
    ts = pd.to_datetime(v, errors="coerce")
    if pd.isna(ts):
        return None
    return ts.strftime("%Y-%m-%d")


def carregar_registros(caminho: str, sheet_name) -> list[dict]:
    header_row = _detectar_linha_header(caminho, sheet_name)
    df = pd.read_excel(caminho, sheet_name=sheet_name, header=header_row)
    df = df.dropna(how="all")
    df = normalizar_nome_colunas(df)

    registros = []
    for _, row in df.iterrows():
        registro = {}
        for col_norm in df.columns:
            v = row[col_norm]
            if pd.isna(v):
                registro[col_norm] = None
            elif col_norm in _COLUNAS_DATA:
                registro[col_norm] = _valor_data(v)
            elif col_norm in _COLUNAS_NUMERICAS:
                registro[col_norm] = float(v)
            else:
                s = str(v).strip()
                registro[col_norm] = s if s else None
        if not registro.get("codigo_lj_nome_do_cliente"):
            continue
        registros.append(registro)
    return registros


def main():
    parser = argparse.ArgumentParser(description="Importa FINR130.xlsx (Titulos a Receber, layout nativo GENIX) como carga FINR130")
    parser.add_argument("--empresa-id", type=int, required=True)
    parser.add_argument("--data-base", required=True, help="YYYYMMDD")
    parser.add_argument("--excel", required=True)
    parser.add_argument("--sheet", default="2-Titulos a receber", help="Nome ou indice da aba com os titulos (default: '2-Titulos a receber')")
    args = parser.parse_args()

    registros = carregar_registros(args.excel, args.sheet)
    print(f"{args.excel} [{args.sheet}]: {len(registros)} registros")

    resultado = gravar_carga_manual(
        empresa_id=args.empresa_id,
        tipo_relatorio="FINR130",
        data_base=args.data_base,
        registros=registros,
    )
    print(resultado)


if __name__ == "__main__":
    main()
