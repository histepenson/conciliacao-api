"""
Importa o export nativo do FINR130 (Titulos a Receber) da GENIX no MESMO
schema "legado" (estilo API Protheus bruta) usado na carga de 31/12/2025
(carga_id=162) - NAO o schema "nativo"/snake-case de colunas do Excel usado
em scripts/importar_finr130_finr150_excel.py.

Por que o schema legado e nao o nativo: o frontend
(C:\\conciliacao-app\\src\\pages\\Conciliacoes.jsx::mapFinr130ParaReceber)
espera os campos brutos da API Protheus (item.cliente, item.loja,
item.nome_cliente, item.saldo_na_data, item.prefixo, item.numero,
item.tipo, item.parcela, item.filial, item.banco, item.dias_vencidos,
item.prazo, item.codigo_cli) e nao reconhece o schema nativo (que so e'
valido quando o backend processa o registro diretamente, sem passar pelo
mapeamento do frontend) - usar o schema nativo faz quase todos os campos
mapeados virarem `undefined` no frontend e sumirem no JSON (JSON.stringify
remove chaves undefined), gerando "Layout invalido: Colunas obrigatorias
nao encontradas: Valor".

Campos derivados de "Codigo-Lj-Nome do Cliente" (BASE-LOJA-NOME, split em
3 partes) e de "Prf-Numero Parcela" (PREFIXO-NUMERO-PARCELA, split em 3
partes) - mesma logica usada no export bruto do Protheus.

Uso:
    python scripts/importar_finr130_legado_excel.py \\
        --empresa-id 13 --data-base 20260531 \\
        --excel "C:\\...\\finr130.xlsx"
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


def _data_yyyymmdd(v) -> str:
    if pd.isna(v):
        return ""
    ts = pd.to_datetime(v, errors="coerce")
    if pd.isna(ts):
        return ""
    return ts.strftime("%Y%m%d")


def _split3(valor: str) -> tuple[str, str, str]:
    partes = [p.strip() for p in valor.split("-", 2)]
    while len(partes) < 3:
        partes.append("")
    return partes[0], partes[1], partes[2]


def _detectar_linha_header(caminho: str, sheet_name) -> int:
    bruto = pd.read_excel(caminho, sheet_name=sheet_name, header=None, nrows=5)
    for i, row in bruto.iterrows():
        valores = [str(v).strip().lower() for v in row.tolist()]
        if any("codigo" in v and "cliente" in v for v in valores):
            return i
    raise SystemExit(f"Nao foi possivel localizar a linha de header nas primeiras 5 linhas: {bruto.values.tolist()}")


def carregar_registros(caminho: str, sheet_name: str) -> list[dict]:
    header_row = _detectar_linha_header(caminho, sheet_name)
    df = pd.read_excel(caminho, sheet_name=sheet_name, header=header_row)
    df = df.dropna(how="all")

    registros = []
    for _, row in df.iterrows():
        codigo_lj_nome = _s(row["Codigo-Lj-Nome do Cliente"])
        if not codigo_lj_nome:
            continue
        cliente, loja, nome_cliente = _split3(codigo_lj_nome)

        prf_numero_parcela = _s(row["Prf-Numero Parcela"])
        prefixo, numero, parcela = _split3(prf_numero_parcela)

        tit_vencidos = _num(row["Tit Vencidos Valor Atual"])
        titulos_a_vencer = _num(row["Titulos a Vencer Valor Atual"])
        dias_atraso = _num(row["Dias Atraso"])
        num_banco_raw = row["Num Banco"]

        registros.append({
            "filial": "01",
            "cliente": cliente,
            "loja": loja,
            "nome_cliente": nome_cliente,
            "codigo_cli": f"C{cliente}{loja}",
            "prefixo": prefixo,
            "numero": numero,
            "parcela": parcela,
            "tipo": _s(row["TP"]),
            "natureza": _s(row["Natureza"]),
            "emissao": _data_yyyymmdd(row["Data de Emissao"]),
            "vencto": _data_yyyymmdd(row["Vencto Titulo"]),
            "vencto_real": _data_yyyymmdd(row["Vencto Real"]),
            "banco": _s(row["Bco St"]),
            "situacao": "",
            "numero_banco": "" if pd.isna(num_banco_raw) else str(int(num_banco_raw)),
            "valor_original": _num(row["Valor Original"]),
            "saldo_na_data": tit_vencidos + titulos_a_vencer,
            "saldo_atual": tit_vencidos + titulos_a_vencer,
            "juros": _num(row["Vlr.juros ou permanencia"]),
            "moeda": 1,
            "historico": _s(row["Historico"]),
            "dias_vencidos": dias_atraso,
            "prazo": "VENCIDO" if dias_atraso > 0 else "A VENCER",
        })
    return registros


def main():
    parser = argparse.ArgumentParser(description="Importa FINR130.xlsx (GENIX) no schema legado (mesmo padrao da carga de 31/12/2025)")
    parser.add_argument("--empresa-id", type=int, required=True)
    parser.add_argument("--data-base", required=True, help="YYYYMMDD")
    parser.add_argument("--excel", required=True)
    parser.add_argument("--sheet", default="2-Titulos a receber")
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
