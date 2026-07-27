"""
Importa exports nativos do relatorio CTBR140 (Balancete de Conta/Item) do
Protheus, no layout que o usuario baixa manualmente, como carga Protheus
"manual" tipo CTBR140 para empresas sem acesso a API REST (ver skill
importar-csv-protheus).

Layout esperado (header na 1a linha):
Codigo do Item Contabil, Descricao do Item, Saldo Anterior, Saldo Atual

- Codigo do Item Contabil: codigo do cliente/fornecedor com prefixo C/F
  (ex: "C01425787", "F00062851") - mesmo padrao usado por FINR130/150.
- Saldo Anterior / Saldo Atual: numericos, JA com o sinal correto (positivo/
  negativo) no sentido normal da conta - diferente do Balancete.xlsx (por
  conta), este export do CTBR140 (por item) nao usa sufixo D/C.

O tipo CTBR140 grava no formato TRANSFORMADO (identico ao que
Ctbr140Service._linha_para_registro produz a partir da API):
    {"Codigo": ..., "Descricao": ..., "Saldo atual": ..., "Saldo anterior": ...}
Chaves com essa grafia exata (nao snake_case) porque
services/conciliacao_service.py:414-420 le "Codigo" e "Saldo anterior"
direto do dict, sem passar pelo normalizador flexivel de
tools/contabilidade.py.

Uso:
    python scripts/importar_ctbr140_excel.py \\
        --empresa-id 14 --data-base 20260531 \\
        --excel "C:\\...\\CTBR140_RIMAVE.xlsx"
"""
import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.importar_carga_manual import gravar_carga_manual

_MAPA_COLUNAS = {
    "Codigo": ["Codigo do Item Contabil", "Código do Item Contábil", "Codigo", "Código"],
    "Descricao": ["Descricao do Item", "Descrição do Item", "Descricao", "Descrição"],
    "Saldo anterior": ["Saldo Anterior"],
    "Saldo atual": ["Saldo Atual"],
}


def _valor(v) -> float:
    if pd.isna(v):
        return 0.0
    return float(v)


def carregar_registros(caminho: str) -> list[dict]:
    df = pd.read_excel(caminho, header=0)

    coluna_por_campo = {}
    for campo, aliases in _MAPA_COLUNAS.items():
        for alias in aliases:
            if alias in df.columns:
                coluna_por_campo[campo] = alias
                break

    faltando = [c for c in ("Codigo", "Saldo atual") if c not in coluna_por_campo]
    if faltando:
        raise SystemExit(f"Colunas obrigatorias nao encontradas no Excel: {faltando}. Colunas presentes: {list(df.columns)}")

    registros = []
    for _, row in df.iterrows():
        codigo_raw = row[coluna_por_campo["Codigo"]]
        if pd.isna(codigo_raw):
            continue
        codigo = str(codigo_raw).strip()
        if not codigo:
            continue
        registro = {
            "Codigo": codigo,
            "Descricao": str(row[coluna_por_campo["Descricao"]] or "").strip() if "Descricao" in coluna_por_campo else "",
            "Saldo atual": _valor(row[coluna_por_campo["Saldo atual"]]),
            "Saldo anterior": _valor(row[coluna_por_campo["Saldo anterior"]]) if "Saldo anterior" in coluna_por_campo else 0.0,
        }
        registros.append(registro)
    return registros


def main():
    parser = argparse.ArgumentParser(description="Importa CTBR140.xlsx (Balancete de Conta/Item) como carga CTBR140")
    parser.add_argument("--empresa-id", type=int, required=True)
    parser.add_argument("--data-base", required=True, help="YYYYMMDD")
    parser.add_argument("--conta", required=True, help="Conta contabil a que este balancete se refere (ex: 1127040001) - grava conta_de/conta_ate nos parametros da carga para bater com o filtro de cache do dialog CTBR140 do frontend")
    parser.add_argument("--excel", required=True)
    args = parser.parse_args()

    registros = carregar_registros(args.excel)
    print(f"{args.excel}: {len(registros)} registros")

    resultado = gravar_carga_manual(
        empresa_id=args.empresa_id,
        tipo_relatorio="CTBR140",
        data_base=args.data_base,
        registros=registros,
        parametros_extra={
            "conta_contabil": args.conta,
            "conta_de": args.conta,
            "conta_ate": args.conta,
            "data_fim": args.data_base,
        },
    )
    print(resultado)


if __name__ == "__main__":
    main()
