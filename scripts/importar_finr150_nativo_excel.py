"""
Importa um FINR150.xlsx ja no layout NATIVO de upload manual (colunas
"Codigo-Nome do Fornecedor", "Prf-Numero Parcela", etc. - o mesmo que
scripts/padronizar_finr150_rimaq.py gera) como carga Protheus "manual" tipo
FINR150, no schema TRANSFORMADO (dados_json com chaves snake_case, igual ao
que services/finr150_service.py::_titulos_para_registros produz).

Diferente de scripts/importar_finr150_rimaq_carga.py (que le o export bruto
combinado e monta "fornecedor-loja-nome"), este script LE O ARQUIVO JA
SEPARADO POR EMPRESA e retira a loja do codigo do fornecedor:
"26929186-0151-CLEBER SILVA..." -> "26929186--CLEBER SILVA..." (loja vazia).

Por que remover a loja: tools/financeiro/base.py::normalizar_codigo_cliente
faz split("-", n=2) em BASE-LOJA-NOME; com loja preenchida o codigo final vira
"F" + base + loja (ex: F269291860151), que nao bate com o item do CTBR140
manual (que nao tem loja, ex: "F26929186"). Usar "BASE--NOME" (loja vazia
entre os dois hifens) preserva o parser (3 segmentos) mas gera codigo final
so com a base: "F26929186".

Usa a MESMA data_base/sem parametros extras da carga original, entao
gravar_carga_manual() substitui a carga anterior automaticamente
(idempotente - ver scripts/importar_carga_manual.py).

Uso:
    python scripts/importar_finr150_nativo_excel.py \\
        --empresa-id 14 --data-base 20260531 \\
        --excel "C:\\...\\FINR150_RIMAVE.xlsx"
"""
import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.importar_carga_manual import gravar_carga_manual


def _s(v) -> str:
    if pd.isna(v):
        return ""
    return str(v).strip()


def _num(v) -> float:
    if pd.isna(v):
        return 0.0
    return float(v)


def _data_iso(v) -> str:
    if pd.isna(v):
        return ""
    ts = pd.to_datetime(v, errors="coerce")
    if pd.isna(ts):
        return ""
    return ts.strftime("%Y-%m-%d")


def _codigo_sem_loja(codigo_nome: str) -> str:
    """"BASE-LOJA-NOME" -> "BASE--NOME" (loja removida, mas com o segmento vazio
    preservado para nao quebrar o parser BASE-LOJA-NOME de normalizar_codigo_cliente)."""
    partes = codigo_nome.split("-", 2)
    if len(partes) < 3:
        # Sem loja identificavel (ja veio "BASE-NOME" ou so "BASE") - devolve como esta.
        return codigo_nome
    base, _loja, nome = partes
    return f"{base.strip()}--{nome.strip()}"


def carregar_registros(caminho: str) -> list[dict]:
    df = pd.read_excel(caminho, header=0)
    registros = []
    for _, row in df.iterrows():
        registros.append({
            "codigo_nome_do_fornecedor": _codigo_sem_loja(_s(row["Codigo-Nome do Fornecedor"])),
            "prf_numero_parcela": _s(row["Prf-Numero Parcela"]).replace("-", ""),
            "tp": _s(row["Tp"]),
            "natureza": _s(row["Natureza"]),
            "data_de_emissao": _data_iso(row["Data de Emissao"]),
            "vencto_real": _data_iso(row["Vencto Real"]),
            "tit_vencidos_valor_corrigido": _num(row["Tit Vencidos Valor corrigido"]),
            "titulos_a_vencer_valor_nominal": _num(row["Titulos a vencer Valor nominal"]),
            "dias_atraso": _num(row["Dias Atraso"]),
            "historico": _s(row["Historico(Vencidos+Vencer)"]),
        })
    return registros


def main():
    parser = argparse.ArgumentParser(description="Importa FINR150.xlsx nativo (ja separado por empresa) como carga FINR150, sem loja no codigo do fornecedor")
    parser.add_argument("--empresa-id", type=int, required=True)
    parser.add_argument("--data-base", required=True, help="YYYYMMDD")
    parser.add_argument("--excel", required=True)
    args = parser.parse_args()

    registros = carregar_registros(args.excel)
    print(f"{args.excel}: {len(registros)} registros")

    resultado = gravar_carga_manual(
        empresa_id=args.empresa_id,
        tipo_relatorio="FINR150",
        data_base=args.data_base,
        registros=registros,
    )
    print(resultado)


if __name__ == "__main__":
    main()
