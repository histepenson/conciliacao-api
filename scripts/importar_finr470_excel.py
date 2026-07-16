"""
Importa exports nativos do relatorio FINR470 (Extrato Bancario) do Protheus,
no layout que o usuario baixa manualmente, como carga Protheus "manual" para
empresas sem acesso a API REST (ver skill importar-csv-protheus).

Layout esperado (header na 2a linha, header=1 no pandas):
BANCO, AGENCIA, CONTA, SALDO INICIAL, DATA, OPERACAO, DOCUMENTO,
PREFIXO/TITULO, ENTRADAS, SAIDAS, SALDO ATUAL, CONCILIADOS, DESCRICAO, ...

Os nomes de coluna sao normalizados com a MESMA funcao normalizar_nome_colunas
usada em tools/banco/extrato_bancario.py, entao o resultado e' reconhecido
nativamente por normalizar_extrato_bancario (mesmo caminho de um upload
manual real).

Aceita varios arquivos para o MESMO banco/conta (ex: extrato "normal" +
extrato de "aplicacao automatica" que sao o mesmo numero de conta no banco,
so exportados em relatorios separados) - os registros de todos os arquivos
sao concatenados em uma unica carga.

Uso:
    python scripts/importar_finr470_excel.py \\
        --empresa-id 13 --data-base 20260430 \\
        --banco 341 --agencia 0001 --conta 440008 \\
        --excel "C:\\...\\Banco Itau  04.2026.xlsx"

    python scripts/importar_finr470_excel.py \\
        --empresa-id 13 --data-base 20260430 \\
        --banco 752 --agencia 0001 --conta 99999 \\
        --excel "C:\\...\\Aplicacao Banco Itau  04.2026.xlsx" "C:\\...\\Aplicacao Banco Santander 04.2026.xlsx"
"""
import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.banco.extrato_bancario import normalizar_nome_colunas
from scripts.importar_carga_manual import gravar_carga_manual

_COLUNAS_DATA = {"data"}
_COLUNAS_VALOR = {"saldo_inicial", "entradas", "saidas", "saldo_atual"}


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


def carregar_registros(caminho: str) -> list[dict]:
    df = pd.read_excel(caminho, header=1)
    df = normalizar_nome_colunas(df)
    df = df[df["data"].notna()].copy()

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
    parser = argparse.ArgumentParser(description="Importa extrato(s) FINR470.xlsx como carga FINR470")
    parser.add_argument("--empresa-id", type=int, required=True)
    parser.add_argument("--data-base", required=True, help="YYYYMMDD")
    parser.add_argument("--banco", required=True)
    parser.add_argument("--agencia", required=True)
    parser.add_argument("--conta", required=True)
    parser.add_argument("--excel", nargs="+", required=True, help="Um ou mais arquivos .xlsx do mesmo banco/conta")
    args = parser.parse_args()

    registros = []
    for caminho in args.excel:
        regs = carregar_registros(caminho)
        print(f"{caminho}: {len(regs)} registros")
        registros.extend(regs)

    resultado = gravar_carga_manual(
        empresa_id=args.empresa_id,
        tipo_relatorio="FINR470",
        data_base=args.data_base,
        registros=registros,
        parametros_extra={"banco": args.banco, "agencia": args.agencia, "conta": args.conta},
    )
    print(f"FINR470 total: {len(registros)} registros")
    print(resultado)


if __name__ == "__main__":
    main()
