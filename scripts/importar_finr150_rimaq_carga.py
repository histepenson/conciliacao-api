"""
Importa o export bruto de FINR150 (Titulos a pagar) do cliente RIMAQ - que
traz 2 empresas misturadas no mesmo arquivo, identificadas pela coluna
"Filial" (prefixo 01 = RIMAVE, 02 = RIVEMA) - como 2 cargas Protheus
"manuais" (uma por empresa), no schema TRANSFORMADO que
services/finr150_service.py::_titulos_para_registros gera e que o worker
grava em protheus_carga_registro.dados_json.

O valor usado (saldo em aberto) e' o Saldo do titulo, nao o Vlr.Titulo
original, pois e' o que reflete o que ainda esta pendente de pagamento.

Uso:
    python scripts/importar_finr150_rimaq_carga.py \\
        "C:\\...\\FINR150.xlsx" --data-base 20260531 \\
        --empresa-rimave 14 --empresa-rivema 15
"""
import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.importar_carga_manual import gravar_carga_manual

EMPRESAS = {"01": "RIMAVE", "02": "RIVEMA"}


def _s(serie: pd.Series) -> pd.Series:
    return serie.fillna("").astype(str).str.strip()


def _data_iso(serie: pd.Series) -> pd.Series:
    return pd.to_datetime(serie, errors="coerce").dt.strftime("%Y-%m-%d").fillna("")


def carregar_registros_por_empresa(caminho: str) -> dict[str, list[dict]]:
    bruto = pd.read_excel(caminho, header=0, dtype=str)
    bruto.columns = range(len(bruto.columns))
    # 0 Dados do fornecedor | 1 Filial | 2 Prefixo | 3 No. Titulo | 4 Parcela
    # 5 Tipo | 6 Fornecedor | 7 Loja | 8 Dados da natureza | 9 DT Emissao
    # 10 Vencimento | 11 Vencto Real | 12 Vlr.Titulo | 13 Saldo | 14 Acrescimo
    # 15 Decrescimo | 16 Valores acessorios | 17 Abatimentos | 18 Juros
    # 19 Razao social | 20 CPF/CNPJ | 21 Saldo liquido | 22 Atraso
    # 23 DT Baixa | 24 Historico | 25 Portador | 26 No do Cheque
    bruto = bruto[bruto[1].notna()].copy()
    bruto["filial_empresa"] = bruto[1].astype(str).str.strip().str[:2]

    codigo_nome = _s(bruto[6]) + "-" + _s(bruto[7]) + "-" + _s(bruto[19])
    prf_numero_parcela = _s(bruto[2]) + _s(bruto[3]) + _s(bruto[4])

    saldo = pd.to_numeric(bruto[21], errors="coerce").fillna(0.0)
    dias = pd.to_numeric(bruto[22], errors="coerce").fillna(0.0)
    # Mesma regra de services/finr150_service.py::_titulos_para_registros:
    # dias > 0 -> vencido; caso contrario (dias <= 0) -> a vencer.
    vencido = saldo.where(dias > 0, 0.0)
    a_vencer = saldo.where(dias <= 0, 0.0)

    registros_df = pd.DataFrame({
        "codigo_nome_do_fornecedor": codigo_nome,
        "tit_vencidos_valor_corrigido": vencido,
        "titulos_a_vencer_valor_nominal": a_vencer,
        "vencto_real": _data_iso(bruto[11]),
        "data_de_emissao": _data_iso(bruto[9]),
        "prf_numero_parcela": prf_numero_parcela,
        "dias_atraso": dias,
        "tp": _s(bruto[5]),
        "natureza": _s(bruto[8]),
        "historico": _s(bruto[24]),
        "_filial_empresa": bruto["filial_empresa"],
    })

    resultado = {}
    for codigo, nome in EMPRESAS.items():
        parte = registros_df[registros_df["_filial_empresa"] == codigo].drop(columns=["_filial_empresa"])
        resultado[nome] = parte.to_dict(orient="records")

    nao_mapeadas = sorted(set(registros_df["_filial_empresa"]) - set(EMPRESAS))
    if nao_mapeadas:
        print(f"AVISO: filiais nao mapeadas para nenhuma empresa: {nao_mapeadas}")

    return resultado


def main():
    parser = argparse.ArgumentParser(description="Importa FINR150.xlsx (RIMAQ) como carga manual para RIMAVE e RIVEMA")
    parser.add_argument("arquivo", help="Caminho do FINR150.xlsx bruto")
    parser.add_argument("--data-base", required=True, help="YYYYMMDD")
    parser.add_argument("--empresa-rimave", type=int, required=True)
    parser.add_argument("--empresa-rivema", type=int, required=True)
    args = parser.parse_args()

    registros = carregar_registros_por_empresa(args.arquivo)
    ids = {"RIMAVE": args.empresa_rimave, "RIVEMA": args.empresa_rivema}

    for nome, empresa_id in ids.items():
        regs = registros[nome]
        print(f"{nome}: {len(regs)} titulos a gravar (empresa_id={empresa_id})")
        resultado = gravar_carga_manual(
            empresa_id=empresa_id,
            tipo_relatorio="FINR150",
            data_base=args.data_base,
            registros=regs,
        )
        print(f"  -> {resultado}")


if __name__ == "__main__":
    main()
