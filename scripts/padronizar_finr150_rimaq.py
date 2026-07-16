"""
Padroniza o export bruto de FINR150 (Titulos a pagar) do cliente RIMAQ -
que traz 2 empresas misturadas no mesmo arquivo, identificadas pela
coluna "Filial" (prefixo 01 = RIMAVE, 02 = RIVEMA) - em 2 arquivos
separados, no layout nativo aceito pelo upload manual de FINR150
(tools/financeiro/contas_pagar.py):

    Codigo-Nome do Fornecedor, Prf-Numero Parcela, Tp, Natureza,
    Data de Emissao, Data de Vencto, Vencto Real, Valor Original,
    Tit Vencidos Valor nominal, Tit Vencidos Valor corrigido,
    Titulos a vencer Valor nominal, Portador,
    Vlr.juros ou permanencia, Dias Atraso, Historico(Vencidos+Vencer)

O valor usado (Valor Original / Tit Vencidos) e o Saldo do titulo
(saldo em aberto), nao o Vlr.Titulo original, pois e o que reflete o
que ainda esta pendente de pagamento para fins de conciliacao.

Uso:
    python scripts/padronizar_finr150_rimaq.py "C:\\...\\FINR150.xlsx"
"""
import argparse
import os

import pandas as pd

EMPRESAS = {
    "01": "RIMAVE",
    "02": "RIVEMA",
}

COLUNAS_SAIDA = [
    "Codigo-Nome do Fornecedor",
    "Prf-Numero Parcela",
    "Tp",
    "Natureza",
    "Data de Emissao",
    "Data de Vencto",
    "Vencto Real",
    "Valor Original",
    "Tit Vencidos Valor nominal",
    "Tit Vencidos Valor corrigido",
    "Titulos a vencer Valor nominal",
    "Portador",
    "Vlr.juros ou permanencia",
    "Dias Atraso",
    "Historico(Vencidos+Vencer)",
]


def _s(serie: pd.Series) -> pd.Series:
    return serie.fillna("").astype(str).str.strip()


def carregar_padronizado(caminho: str) -> dict[str, pd.DataFrame]:
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

    fornecedor = _s(bruto[6])
    loja = _s(bruto[7])
    razao_social = _s(bruto[19])
    codigo_nome = fornecedor + "-" + loja + "-" + razao_social

    prefixo = _s(bruto[2])
    no_titulo = _s(bruto[3])
    parcela = _s(bruto[4])
    prf_numero_parcela = prefixo + "-" + no_titulo + "-" + parcela

    saldo = pd.to_numeric(bruto[21], errors="coerce").fillna(0.0)
    atraso = pd.to_numeric(bruto[22], errors="coerce").fillna(0.0)
    vencido = saldo.where(atraso >= 0, 0.0)
    a_vencer = saldo.where(atraso < 0, 0.0)

    saida = pd.DataFrame({
        "Codigo-Nome do Fornecedor": codigo_nome,
        "Prf-Numero Parcela": prf_numero_parcela,
        "Tp": _s(bruto[5]),
        "Natureza": _s(bruto[8]),
        "Data de Emissao": pd.to_datetime(bruto[9], errors="coerce"),
        "Data de Vencto": pd.to_datetime(bruto[10], errors="coerce"),
        "Vencto Real": pd.to_datetime(bruto[11], errors="coerce"),
        "Valor Original": saldo,
        "Tit Vencidos Valor nominal": vencido,
        "Tit Vencidos Valor corrigido": vencido,
        "Titulos a vencer Valor nominal": a_vencer,
        "Portador": _s(bruto[25]),
        "Vlr.juros ou permanencia": pd.to_numeric(bruto[18], errors="coerce").fillna(0.0),
        "Dias Atraso": atraso,
        "Historico(Vencidos+Vencer)": _s(bruto[24]),
        "_filial_empresa": bruto["filial_empresa"],
    })

    resultado = {}
    for codigo, nome in EMPRESAS.items():
        parte = saida[saida["_filial_empresa"] == codigo].drop(columns=["_filial_empresa"])
        resultado[nome] = parte.reset_index(drop=True)

    nao_mapeadas = sorted(set(saida["_filial_empresa"]) - set(EMPRESAS))
    if nao_mapeadas:
        print(f"AVISO: filiais nao mapeadas para nenhuma empresa: {nao_mapeadas}")

    return resultado


def main():
    parser = argparse.ArgumentParser(description="Padroniza FINR150.xlsx (RIMAQ) em 2 arquivos por empresa")
    parser.add_argument("arquivo", help="Caminho do FINR150.xlsx bruto")
    parser.add_argument("--saida-dir", default=None, help="Pasta de saida (default: mesma pasta do arquivo)")
    args = parser.parse_args()

    saida_dir = args.saida_dir or os.path.dirname(args.arquivo)
    partes = carregar_padronizado(args.arquivo)

    for nome_empresa, df in partes.items():
        caminho_saida = os.path.join(saida_dir, f"FINR150_{nome_empresa}.xlsx")
        df.to_excel(caminho_saida, index=False, sheet_name="Titulos a Pagar")
        print(
            f"{nome_empresa}: {len(df)} titulos | "
            f"soma Valor Original = {df['Valor Original'].sum():,.2f} -> {caminho_saida}"
        )


if __name__ == "__main__":
    main()
