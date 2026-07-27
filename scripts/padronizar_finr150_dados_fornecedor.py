"""
Padroniza um export bruto de FINR150 (Titulos a pagar) de UMA UNICA empresa
em que o fornecedor/loja/razao social vem tudo junto em texto livre na
coluna "Dados do fornecedor" (formato "FORNECEDOR/LOJA - RAZAO SOCIAL(APELIDO)",
ex: "36539715/0164 - HGC CONSTRUCAO E REFORMAS LTDA(HGC CONSTRUCAO E REFORMAS)"),
sem colunas separadas "Fornecedor"/"Loja"/"Razao social" (diferente do layout
tratado por scripts/padronizar_finr150_bruto.py e padronizar_finr150_rimaq.py).

Layout esperado (header na 1a linha, 25 colunas):
Dados do fornecedor, Filial, Prefixo, No. Titulo, Parcela, Tipo,
Dados da natureza, DT Emissao, Vencimento, Vencto Real, Natureza,
Vlr.Titulo, Saldo, Descricao, Acrescimo, Decrescimo, Valores acessorios,
Abatimentos, Juros, Saldo liquido, Atraso, DT Baixa, Historico, Portador,
No do Cheque

Gera o layout NATIVO de upload manual (mesmo que scripts/padronizar_finr150_bruto.py):
    Codigo-Nome do Fornecedor, Prf-Numero Parcela, Tp, Natureza,
    Data de Emissao, Data de Vencto, Vencto Real, Valor Original,
    Tit Vencidos Valor nominal, Tit Vencidos Valor corrigido,
    Titulos a vencer Valor nominal, Portador,
    Vlr.juros ou permanencia, Dias Atraso, Historico(Vencidos+Vencer)

Nao tem coluna "Portador" nesse layout - fica sempre vazia na saida.

O valor usado (Valor Original / Tit Vencidos) e a coluna "Saldo" do titulo
(saldo em aberto), nao o Vlr.Titulo original nem o Saldo liquido.

Uso:
    python scripts/padronizar_finr150_dados_fornecedor.py "C:\\...\\FINR150.xlsx"
"""
import argparse
import os
import re

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

_PAT_FORNECEDOR = re.compile(r"^(.*?)/(.*?)\s*-\s*(.*?)\(.*\)\s*$")


def _s(serie: pd.Series) -> pd.Series:
    return serie.fillna("").astype(str).str.strip()


def _extrair_codigo_nome(dados_fornecedor: str) -> str:
    """"FORNECEDOR/LOJA - RAZAO SOCIAL(APELIDO)" -> "FORNECEDOR-LOJA-RAZAO SOCIAL"
    (mesmo formato BASE-LOJA-NOME que scripts/importar_finr150_nativo_excel.py espera)."""
    texto = str(dados_fornecedor or "").strip()
    m = _PAT_FORNECEDOR.match(texto)
    if not m:
        return texto
    fornecedor, loja, razao_social = (g.strip() for g in m.groups())
    return f"{fornecedor}-{loja}-{razao_social}"


def carregar_padronizado(caminho: str) -> pd.DataFrame:
    bruto = pd.read_excel(caminho, header=0, dtype=str)
    bruto.columns = range(len(bruto.columns))
    # 0 Dados do fornecedor | 1 Filial | 2 Prefixo | 3 No. Titulo | 4 Parcela
    # 5 Tipo | 6 Dados da natureza | 7 DT Emissao | 8 Vencimento | 9 Vencto Real
    # 10 Natureza | 11 Vlr.Titulo | 12 Saldo | 13 Descricao | 14 Acrescimo
    # 15 Decrescimo | 16 Valores acessorios | 17 Abatimentos | 18 Juros
    # 19 Saldo liquido | 20 Atraso | 21 DT Baixa | 22 Historico | 23 Portador
    # 24 No do Cheque

    bruto = bruto[bruto[1].notna()].copy()

    codigo_nome = bruto[0].apply(_extrair_codigo_nome)

    prefixo = _s(bruto[2])
    no_titulo = _s(bruto[3])
    parcela = _s(bruto[4])
    prf_numero_parcela = prefixo + "-" + no_titulo + "-" + parcela

    saldo = pd.to_numeric(bruto[12], errors="coerce").fillna(0.0)
    atraso = pd.to_numeric(bruto[20], errors="coerce").fillna(0.0)
    # dias > 0 -> vencido; caso contrario (dias <= 0) -> a vencer (mesma regra
    # de services/finr150_service.py::_titulos_para_registros).
    vencido = saldo.where(atraso > 0, 0.0)
    a_vencer = saldo.where(atraso <= 0, 0.0)

    saida = pd.DataFrame({
        "Codigo-Nome do Fornecedor": codigo_nome,
        "Prf-Numero Parcela": prf_numero_parcela,
        "Tp": _s(bruto[5]),
        "Natureza": _s(bruto[6]),
        "Data de Emissao": pd.to_datetime(bruto[7], errors="coerce"),
        "Data de Vencto": pd.to_datetime(bruto[8], errors="coerce"),
        "Vencto Real": pd.to_datetime(bruto[9], errors="coerce"),
        "Valor Original": saldo,
        "Tit Vencidos Valor nominal": vencido,
        "Tit Vencidos Valor corrigido": vencido,
        "Titulos a vencer Valor nominal": a_vencer,
        "Portador": "",
        "Vlr.juros ou permanencia": pd.to_numeric(bruto[18], errors="coerce").fillna(0.0),
        "Dias Atraso": atraso,
        "Historico(Vencidos+Vencer)": _s(bruto[22]),
    })

    filiais = sorted(set(_s(bruto[1])))
    if len(filiais) > 1:
        print(f"AVISO: arquivo tem mais de uma filial ({filiais}) - todas serao gravadas juntas no mesmo arquivo de saida")

    return saida


def main():
    parser = argparse.ArgumentParser(description="Padroniza FINR150.xlsx bruto (fornecedor/loja/razao social em texto livre) no layout nativo de upload manual")
    parser.add_argument("arquivo", help="Caminho do FINR150.xlsx bruto")
    parser.add_argument("--saida", default=None, help="Caminho do arquivo de saida (default: FINR150_padronizado.xlsx na mesma pasta)")
    args = parser.parse_args()

    saida_path = args.saida or os.path.join(os.path.dirname(args.arquivo), "FINR150_padronizado.xlsx")
    df = carregar_padronizado(args.arquivo)
    df.to_excel(saida_path, index=False, sheet_name="Titulos a Pagar")
    print(f"{len(df)} titulos | soma Valor Original = {df['Valor Original'].sum():,.2f} -> {saida_path}")


if __name__ == "__main__":
    main()
