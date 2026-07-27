"""
Padroniza o export bruto de FINR150 (Titulos a pagar) de UMA UNICA empresa
(sem mistura de filiais/empresas, diferente de scripts/padronizar_finr150_rimaq.py
que separa 2 empresas) no layout nativo aceito pelo upload manual de FINR150
(tools/financeiro/contas_pagar.py):

    Codigo-Nome do Fornecedor, Prf-Numero Parcela, Tp, Natureza,
    Data de Emissao, Data de Vencto, Vencto Real, Valor Original,
    Tit Vencidos Valor nominal, Tit Vencidos Valor corrigido,
    Titulos a vencer Valor nominal, Portador,
    Vlr.juros ou permanencia, Dias Atraso, Historico(Vencidos+Vencer)

O valor usado (Valor Original / Tit Vencidos) e a coluna "Saldo" do titulo
(saldo em aberto), nao o Vlr.Titulo original nem o Saldo liquido, pois e o
que reflete o que ainda esta pendente de pagamento para fins de conciliacao.

Uso:
    python scripts/padronizar_finr150_bruto.py "C:\\...\\FINR150.xlsx"
"""
import argparse
import os

import pandas as pd

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


def carregar_padronizado(caminho: str) -> pd.DataFrame:
    bruto = pd.read_excel(caminho, header=0, dtype=str)
    bruto.columns = range(len(bruto.columns))
    # 0 Dados do fornecedor | 1 Filial | 2 Prefixo | 3 No. Titulo | 4 Parcela
    # 5 Tipo | 6 Fornecedor | 7 Loja | 8 Dados da natureza | 9 DT Emissao
    # 10 Vencimento | 11 Vencto Real | 12 Vlr.Titulo | 13 Saldo | 14 Acrescimo
    # 15 Decrescimo | 16 Valores acessorios | 17 Abatimentos | 18 Juros
    # 19 Razao social | 20 CPF/CNPJ | 21 Saldo liquido | 22 Atraso
    # 23 DT Baixa | 24 Historico | 25 Portador | 26 No do Cheque

    bruto = bruto[bruto[1].notna()].copy()

    fornecedor = _s(bruto[6])
    loja = _s(bruto[7])
    razao_social = _s(bruto[19])
    codigo_nome = fornecedor + "-" + loja + "-" + razao_social

    prefixo = _s(bruto[2])
    no_titulo = _s(bruto[3])
    parcela = _s(bruto[4])
    prf_numero_parcela = prefixo + "-" + no_titulo + "-" + parcela

    saldo = pd.to_numeric(bruto[13], errors="coerce").fillna(0.0)
    atraso = pd.to_numeric(bruto[22], errors="coerce").fillna(0.0)
    # dias > 0 -> vencido; caso contrario (dias <= 0) -> a vencer (mesma regra
    # de services/finr150_service.py::_titulos_para_registros).
    vencido = saldo.where(atraso > 0, 0.0)
    a_vencer = saldo.where(atraso <= 0, 0.0)

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
    })

    filiais = sorted(set(_s(bruto[1])))
    if len(filiais) > 1:
        print(f"AVISO: arquivo tem mais de uma filial ({filiais}) - todas serao gravadas juntas no mesmo arquivo de saida")

    return saida


def main():
    parser = argparse.ArgumentParser(description="Padroniza FINR150.xlsx bruto (uma unica empresa) no layout nativo de upload manual")
    parser.add_argument("arquivo", help="Caminho do FINR150.xlsx bruto")
    parser.add_argument("--saida", default=None, help="Caminho do arquivo de saida (default: FINR150_padronizado.xlsx na mesma pasta)")
    args = parser.parse_args()

    saida_path = args.saida or os.path.join(os.path.dirname(args.arquivo), "FINR150_padronizado.xlsx")
    df = carregar_padronizado(args.arquivo)
    df.to_excel(saida_path, index=False, sheet_name="Titulos a Pagar")
    print(f"{len(df)} titulos | soma Valor Original = {df['Valor Original'].sum():,.2f} -> {saida_path}")


if __name__ == "__main__":
    main()
