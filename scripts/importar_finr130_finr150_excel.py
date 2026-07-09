"""
Importa os exports nativos dos relatorios FINR130 (Titulos a receber) e
FINR150 (Titulos a pagar) do Protheus, exatamente no layout que o usuario
baixa manualmente (mesmo formato aceito hoje no upload manual do frontend),
como cargas Protheus "manuais" para empresas sem acesso a API REST.

Layout esperado (aba com header na 2a linha, header=1 no pandas):
- FINR130: "Codigo-Lj-Nome do Cliente", "Prf-Numero Parcela", "TP", "Natureza",
  "Data de Emissao", "Vencto Titulo", "Vencto Real", "Bco St", "Valor Original",
  "Tit Vencidos Valor Atual", "Tit Vencidos Valor Corrigido",
  "Titulos a Vencer Valor Atual", "Num Banco", "Vlr.juros ou permanencia",
  "Dias Atraso", "Historico"
- FINR150: "Codigo-Nome do Fornecedor", "Prf-Numero Parcela", "Tp", "Natureza",
  "Data de Emissao", "Data de Vencto", "Vencto Real", "Valor Original",
  "Tit Vencidos Valor nominal", "Tit Vencidos Valor corrigido",
  "Titulos a vencer Valor nominal", "Porta- dor", "Vlr.juros ou permanencia",
  "Dias Atraso", "Historico(Vencidos+Vencer)"

Os nomes de coluna sao normalizados com a MESMA funcao normalizar_nome_colunas
usada no upload manual (tools/financeiro/base.py), entao o resultado e'
identico ao de um upload manual real - tools/financeiro/contas_receber.py e
contas_pagar.py ja reconhecem esses nomes de coluna nativamente.

Uso:
    python scripts/importar_finr130_finr150_excel.py \\
        --empresa-id 13 --data-base 20260430 \\
        --finr130 "C:\\...\\FIN130.xlsx" --finr150 "C:\\...\\FIN150.xlsx"
"""
import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.financeiro.base import normalizar_nome_colunas
from scripts.importar_carga_manual import gravar_carga_manual


def _valor(v):
    if pd.isna(v):
        return None
    return float(v)


def _data_iso(v):
    if pd.isna(v):
        return None
    ts = pd.to_datetime(v, errors="coerce")
    if pd.isna(ts):
        return None
    return ts.strftime("%Y-%m-%d")


_COLUNAS_DATA = {"data_de_emissao", "vencto_titulo", "vencto_real", "data_de_vencto"}
_COLUNAS_VALOR = {
    "valor_original",
    "tit_vencidos_valor_atual",
    "tit_vencidos_valor_corrigido",
    "titulos_a_vencer_valor_atual",
    "tit_vencidos_valor_nominal",
    "titulos_a_vencer_valor_nominal",
    "vlr_juros_ou_permanencia",
    "dias_atraso",
}


def carregar_registros(caminho: str, sheet_name: str) -> list[dict]:
    df = pd.read_excel(caminho, sheet_name=sheet_name, header=1)
    df = normalizar_nome_colunas(df)

    registros = []
    for _, row in df.iterrows():
        registro = {}
        for col, val in row.items():
            if col in _COLUNAS_DATA:
                registro[col] = _data_iso(val)
            elif col in _COLUNAS_VALOR:
                registro[col] = _valor(val)
            elif pd.isna(val):
                registro[col] = None
            else:
                registro[col] = str(val).strip()
        registros.append(registro)
    return registros


def main():
    parser = argparse.ArgumentParser(description="Importa FIN130.xlsx/FIN150.xlsx como cargas FINR130/FINR150")
    parser.add_argument("--empresa-id", type=int, required=True)
    parser.add_argument("--data-base", required=True, help="YYYYMMDD")
    parser.add_argument("--finr130", help="Caminho do FIN130.xlsx")
    parser.add_argument("--finr150", help="Caminho do FIN150.xlsx")
    args = parser.parse_args()

    if not args.finr130 and not args.finr150:
        parser.error("Informe pelo menos --finr130 ou --finr150")

    if args.finr130:
        registros = carregar_registros(args.finr130, "2-Titulos a receber")
        print(f"FINR130: {len(registros)} registros lidos de {args.finr130}")
        resultado = gravar_carga_manual(
            empresa_id=args.empresa_id,
            tipo_relatorio="FINR130",
            data_base=args.data_base,
            registros=registros,
        )
        print(resultado)

    if args.finr150:
        registros = carregar_registros(args.finr150, "2-Titulos a pagar")
        print(f"FINR150: {len(registros)} registros lidos de {args.finr150}")
        resultado = gravar_carga_manual(
            empresa_id=args.empresa_id,
            tipo_relatorio="FINR150",
            data_base=args.data_base,
            registros=registros,
        )
        print(resultado)


if __name__ == "__main__":
    main()
