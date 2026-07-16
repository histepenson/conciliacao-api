"""
Importa o export nativo do CTBR140 (Balancete de Conta/Item) do Protheus no
layout "Item Conta" com TODAS as contas contabeis no mesmo arquivo/aba
(diferente de scripts/importar_ctbr140_excel.py, que espera um arquivo ja
filtrado para uma unica conta).

Layout esperado (2 linhas de titulo antes do header real):
    Linha 1: "Item Conta" (titulo da aba, ignorado)
    Linha 2 (header): Codigo, Descricao, Codigo, Descricao, Saldo anterior,
        Debito, Credito, Movimento do periodo, Saldo atual
    - 1o par Codigo/Descricao = conta contabil (ex: "1.1.1.02.0011")
    - 2o par Codigo/Descricao = item da conta (cliente/fornecedor, com
      prefixo C/F, ex: "C00001300")
    - Saldo anterior / Saldo atual: numero BR com sufixo D (positivo) ou
      C (negativo) - mesma convencao de tools/balancete.py

Gera UMA carga CTBR140 por conta contabil encontrada no arquivo (grava
conta_de/conta_ate nos parametros para casar com o filtro de cache do
dialog CTBR140 do frontend - ver services/protheus_carga_service.py:316-338).

Uso:
    python scripts/importar_ctbr140_balancete_item.py \\
        --empresa-id 13 --data-base 20260531 \\
        --excel "C:\\...\\Qualicaps - CTBR140  05.2026.xlsx"
"""
import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.importar_carga_manual import gravar_carga_manual
from tools.balancete import normalizar_codigo_conta, parse_numero_balancete


def _detectar_linha_header(caminho: str, sheet_name) -> int:
    bruto = pd.read_excel(caminho, sheet_name=sheet_name, header=None, nrows=5)
    for i, row in bruto.iterrows():
        valores = [str(v).strip().lower() for v in row.tolist()]
        if valores.count("codigo") >= 2 and "descricao" in valores:
            return i
    raise SystemExit(f"Nao foi possivel localizar a linha de header (Codigo/Descricao) nas primeiras 5 linhas: {bruto.values.tolist()}")


def carregar_registros_por_conta(caminho: str, sheet_name=0) -> dict[str, dict]:
    header_row = _detectar_linha_header(caminho, sheet_name)
    df = pd.read_excel(caminho, sheet_name=sheet_name, header=header_row)
    df.columns = [str(c).strip() for c in df.columns]

    colunas = list(df.columns)
    idx_codigo = [i for i, c in enumerate(colunas) if c == "Codigo" or c.startswith("Codigo.")]
    idx_descricao = [i for i, c in enumerate(colunas) if c == "Descricao" or c.startswith("Descricao.")]
    if len(idx_codigo) < 2 or len(idx_descricao) < 2:
        raise SystemExit(f"Esperava 2 colunas 'Codigo' e 2 'Descricao' (conta + item). Colunas encontradas: {colunas}")

    col_conta_codigo = colunas[idx_codigo[0]]
    col_item_codigo = colunas[idx_codigo[1]]
    col_conta_descricao = colunas[idx_descricao[0]]
    col_item_descricao = colunas[idx_descricao[1]]

    if "Saldo atual" not in colunas:
        raise SystemExit(f"Coluna 'Saldo atual' nao encontrada. Colunas: {colunas}")
    col_saldo_anterior = "Saldo anterior" if "Saldo anterior" in colunas else None

    contas: dict[str, dict] = {}
    for _, row in df.iterrows():
        conta_raw = str(row[col_conta_codigo] or "").strip()
        conta_normalizada = normalizar_codigo_conta(conta_raw)
        if not conta_normalizada:
            continue

        item_codigo = str(row[col_item_codigo] or "").strip()
        if not item_codigo:
            continue

        registro = {
            "Codigo": item_codigo,
            "Descricao": str(row[col_item_descricao] or "").strip(),
            "Saldo atual": parse_numero_balancete(row["Saldo atual"]),
            "Saldo anterior": parse_numero_balancete(row[col_saldo_anterior]) if col_saldo_anterior else 0.0,
        }

        if conta_normalizada not in contas:
            contas[conta_normalizada] = {
                "conta_raw": conta_raw,
                "descricao": str(row[col_conta_descricao] or "").strip(),
                "registros": [],
            }
        contas[conta_normalizada]["registros"].append(registro)

    return contas


def main():
    parser = argparse.ArgumentParser(description="Importa CTBR140 (Balancete de Conta/Item, todas as contas) como cargas CTBR140, uma por conta")
    parser.add_argument("--empresa-id", type=int, required=True)
    parser.add_argument("--data-base", required=True, help="YYYYMMDD")
    parser.add_argument("--excel", required=True)
    parser.add_argument("--sheet", default=0, help="Nome ou indice da aba (default: primeira)")
    args = parser.parse_args()

    contas = carregar_registros_por_conta(args.excel, args.sheet)
    print(f"{args.excel}: {len(contas)} contas encontradas")

    for conta_normalizada, dados in sorted(contas.items()):
        registros = dados["registros"]
        resultado = gravar_carga_manual(
            empresa_id=args.empresa_id,
            tipo_relatorio="CTBR140",
            data_base=args.data_base,
            registros=registros,
            parametros_extra={
                "conta_contabil": conta_normalizada,
                "conta_de": conta_normalizada,
                "conta_ate": conta_normalizada,
                "data_fim": args.data_base,
            },
        )
        print(f"  conta {conta_normalizada} ({dados['descricao']}): {len(registros)} registros -> carga_id={resultado['carga_id']}")


if __name__ == "__main__":
    main()
