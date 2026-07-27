"""
Importa um FINR150.xlsx ja no layout NATIVO de upload manual (colunas
"Codigo-Nome do Fornecedor", "Prf-Numero Parcela", etc. - o mesmo que
scripts/padronizar_finr150_rimaq.py gera) como carga Protheus "manual" tipo
FINR150, no schema TRANSFORMADO (dados_json com chaves snake_case, igual ao
que services/finr150_service.py::_titulos_para_registros produz).

Diferente de scripts/importar_finr150_rimaq_carga.py (que le o export bruto
combinado e monta "fornecedor-loja-nome"), este script LE O ARQUIVO JA
SEPARADO POR EMPRESA. Por padrao mantem a loja no codigo do fornecedor
(padrao oficial "C"/"F" + base + loja - ver memoria feedback_codigo_cli_com_loja).

Use --remover-loja APENAS quando o CTBR140 manual dessa empresa nao tiver
loja no item (ex.: RIVEMA), para nao quebrar o matching:
"26929186-0151-CLEBER SILVA..." -> "26929186--CLEBER SILVA..." (loja vazia).

Por que remover a loja (quando aplicavel): tools/financeiro/base.py::normalizar_codigo_cliente
faz split("-", n=2) em BASE-LOJA-NOME; com loja preenchida o codigo final vira
"F" + base + loja (ex: F269291860151), que nao bate com o item do CTBR140
manual (que nao tem loja, ex: "F26929186"). Usar "BASE--NOME" (loja vazia
entre os dois hifens) preserva o parser (3 segmentos) mas gera codigo final
so com a base: "F26929186". Empresa RIMAVE (mesmo cliente RIMAQ) usa o
padrao normal (mantem loja) - so RIVEMA precisa de --remover-loja.

Usa a MESMA data_base/sem parametros extras da carga original, entao
gravar_carga_manual() substitui a carga anterior automaticamente
(idempotente - ver scripts/importar_carga_manual.py).

Uso:
    python scripts/importar_finr150_nativo_excel.py \\
        --empresa-id 14 --data-base 20260531 \\
        --excel "C:\\...\\FINR150_RIMAVE.xlsx"

    python scripts/importar_finr150_nativo_excel.py \\
        --empresa-id 15 --data-base 20260531 --remover-loja \\
        --excel "C:\\...\\FINR150_RIVEMA.xlsx"
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


def _codigo_sem_loja(codigo_nome: str, truncar_base_8: bool = False) -> str:
    """"BASE-LOJA-NOME" -> "BASE--NOME" (loja removida, mas com o segmento vazio
    preservado para nao quebrar o parser BASE-LOJA-NOME de normalizar_codigo_cliente).

    truncar_base_8: caso especifico da RIVEMA, onde fornecedores pessoa fisica
    trazem a loja JA colada na base sem separador (ex: "016128058" = fornecedor
    "01612805" + loja "8"), entao o split("-") sozinho nao a remove - o CTBR140
    manual dessa empresa so tem 8 digitos por item (confirmado batendo valor:
    F01612805 no CTBR140 = soma exata dos titulos de "016128058" no FINR150).
    NAO usar para outras empresas sem confirmar o mesmo padrao no CTBR140 delas.
    """
    partes = codigo_nome.split("-", 2)
    if len(partes) < 3:
        # Sem loja identificavel (ja veio "BASE-NOME" ou so "BASE") - devolve como esta.
        return codigo_nome
    base, _loja, nome = partes
    base = base.strip()
    if truncar_base_8:
        base = base[:8]
    return f"{base}--{nome.strip()}"


def _sheet_titulos_a_pagar(caminho: str):
    """Alguns exports trazem varias abas (ex: PA, FORNECEDOR, NDF, OUTROS) alem
    da aba com os dados - sem indicar a aba, pd.read_excel pega a 1a (errado).
    Usa "Titulos a Pagar" (aba gerada por scripts/padronizar_finr150_*.py)
    quando existir; senao cai no default (1a aba)."""
    sheets = pd.ExcelFile(caminho).sheet_names
    return "Titulos a Pagar" if "Titulos a Pagar" in sheets else 0


def carregar_registros(caminho: str, remover_loja: bool, truncar_base_8: bool = False) -> list[dict]:
    df = pd.read_excel(caminho, header=0, sheet_name=_sheet_titulos_a_pagar(caminho))
    registros = []
    for _, row in df.iterrows():
        codigo_nome = _s(row["Codigo-Nome do Fornecedor"])
        if remover_loja:
            codigo_nome = _codigo_sem_loja(codigo_nome, truncar_base_8)
        registros.append({
            "codigo_nome_do_fornecedor": codigo_nome,
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
    parser.add_argument("--remover-loja", action="store_true", help="Zera a loja no codigo do fornecedor (usar so quando o CTBR140 manual dessa empresa nao tiver loja no item)")
    parser.add_argument("--truncar-base-8", action="store_true", help="Alem de remover a loja, trunca a base em 8 digitos (caso especifico da RIVEMA - ver docstring de _codigo_sem_loja)")
    args = parser.parse_args()

    registros = carregar_registros(args.excel, args.remover_loja, args.truncar_base_8)
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
