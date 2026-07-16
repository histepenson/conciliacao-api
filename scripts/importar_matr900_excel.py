"""
Importa o export nativo do MATR900 (Kardex de Estoque) do Protheus, no
layout de blocos por produto que o usuario baixa manualmente, como carga
Protheus "manual" tipo MATR900 - schema RAW (chaves em Title Case, mesmo
formato que protheus/ZMATR900API.prw grava - ver skill importar-csv-protheus,
secao MATR900).

Layout esperado (sheet unica, sem header tabular - blocos repetidos):
    Dt.Ref: .../Hora: .../Emissao: ... (3 linhas de cabecalho do relatorio, ignoradas)
    OPERACAO DATA | ARM. | TES | C.F | DOCUMENTO NUMERO | ... (linha de titulo das colunas, ignorada)
    Codigo: <cod>  Descricao: <desc>  Um: <um>  Tipo: <tipo>  Grupo: <grupo>
        Custo Medio: <n>  Qtd. Saldo: <n>  Vlr.Total Saldo: <n>
    POSICAO IPI: <ncm>  ENDERECO: <end>
    <linhas de movimento: data, arm, tes, cf, documento, entradas qtd/custo,
     custo medio movimento, saidas qtd/custo, saldo qtd/valor, cli/for/cc/op/os>
    QTD. NA SEGUNDA UM: <n>   (fim do bloco do produto)
    (repete Codigo: ... para o proximo produto)

Cada linha de MOVIMENTO vira um registro, replicando os campos do produto
(Codigo/Descricao/Um/Tipo/Grupo/Custo Medio/Qtd Saldo/Vlr Total Saldo) e da
posicao (Posicao IPI/Endereco) do bloco atual - mesmo formato "flat" que o
worker grava a partir da API (uma linha por movimento).

Uso:
    python scripts/importar_matr900_excel.py \\
        --empresa-id 13 --data-base 20260531 \\
        --excel "C:\\...\\Qualicaps - MATR900 KARDEX - 05.2026.xlsx"
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


def carregar_registros(caminho: str, sheet_name=0) -> list[dict]:
    df = pd.read_excel(caminho, sheet_name=sheet_name, header=None)

    registros = []
    produto = None
    posicao_ipi = ""
    endereco = ""

    for _, row in df.iterrows():
        v0 = row[0]

        if isinstance(v0, str):
            s = v0.strip()
            if s.startswith("Codigo:"):
                produto = {
                    "Codigo": _s(row[1]),
                    "Descricao": _s(row[3]),
                    "UM": _s(row[5]),
                    "Tipo": _s(row[7]),
                    "Grupo": _s(row[9]),
                    "Custo Medio": _num(row[11]),
                    "Qtd Saldo": _num(row[13]),
                    "Vlr Total Saldo": _num(row[15]),
                }
                posicao_ipi = ""
                endereco = ""
            elif s.startswith("POSICAO IPI"):
                posicao_ipi = _s(row[1])
                endereco = _s(row[3])
            # demais linhas de string (Dt.Ref/Hora/Emissao/titulo de colunas/
            # "QTD. NA SEGUNDA UM") sao apenas ignoradas.
            continue

        # Linha de movimento (Operacao Data e datetime)
        if produto is None:
            continue

        registro = dict(produto)
        registro.update({
            "Posicao IPI": posicao_ipi,
            "Endereco": endereco,
            "Operacao Data": v0.strftime("%d/%m/%Y"),
            "ARM": _s(row[1]),
            "TES": _s(row[2]),
            "CF": _s(row[3]),
            "Documento Numero": _s(row[4]),
            "Entradas Quantidade": _num(row[6]),
            "Entradas Custo Total": _num(row[8]),
            "Custo Medio do Movimento": _num(row[10]),
            "Saidas Quantidade": _num(row[12]),
            "Saidas Custo Total": _num(row[14]),
            "Saldo Quantidade": _num(row[16]),
            "Saldo Valor Total": _num(row[18]),
            "CLI/FOR/CC/PJ/OP/OS": _s(row[20]),
        })
        registros.append(registro)

    return registros


def main():
    parser = argparse.ArgumentParser(description="Importa MATR900 (Kardex, layout nativo por blocos) como carga MATR900")
    parser.add_argument("--empresa-id", type=int, required=True)
    parser.add_argument("--data-base", required=True, help="YYYYMMDD")
    parser.add_argument("--excel", required=True)
    parser.add_argument("--sheet", default=0, help="Nome ou indice da aba (default: primeira)")
    args = parser.parse_args()

    registros = carregar_registros(args.excel, args.sheet)
    produtos = {r["Codigo"] for r in registros}
    print(f"{args.excel}: {len(registros)} registros de movimento, {len(produtos)} produtos")

    ano_mes = f"{args.data_base[:4]}{args.data_base[4:6]}"
    data_ini = f"{ano_mes}01"

    resultado = gravar_carga_manual(
        empresa_id=args.empresa_id,
        tipo_relatorio="MATR900",
        data_base=args.data_base,
        registros=registros,
        parametros_extra={
            # Precisam bater com os defaults de buildInitialParams() em
            # Matr900ParamsDialog.jsx, senao o banner de cache nao aparece
            # (containment JSONB exige match exato desses campos - ver
            # memoria project_carga_manual_data_fim_obrigatorio).
            "data_ini": data_ini,
            "data_fim": args.data_base,
            "documento_por": "D",
            "moeda": "1",
            "ordem": "1",
            "lista_sem_movimento": "2",
            "lista_transferencia": "1",
            "considera_filiais": "2",
            "tipo_custo": "1",
        },
    )
    print(resultado)


if __name__ == "__main__":
    main()
