"""
Importa um export bruto da tabela CT2 do Protheus (planilha "CT2 MM.AAAA.xlsx",
gerada direto do banco, sem passar pela API REST) como DUAS cargas Protheus
"manuais" - CTBR480 e CT2RAZCT5 - cobrindo TODAS as contas contabeis de uma vez.

Usado para empresas sem acesso a API do Protheus (feature "Dados Locais",
ver Empresa.dados_locais). Como o razao filtra por conta dentro de cada
servico (ConciliacaoService._filtrar_razao_por_conta,
ConciliacaoImpostosService.executar), uma unica carga com todas as contas
atende qualquer tela/conta sem precisar reimportar a cada conta nova.

Layout esperado da planilha (header na 3a linha, ou seja, header=2 no pandas):
Filial, Data Lcto, Numero Lote, Sub Lote, Numero Doc, Numero Linha, Tipo Lcto,
Cta Debito, Cta Credito, Valor, Hist Lanc, Item Conta D, Item Conta C,
Cod Cl Val D, Cod Cl Val C, Lanc Padrao, ...

Tipo Lcto encontrados no export:
- "Debito"  -> 1 perna: Cta Debito preenchida, Valor a debito
- "Credito" -> 1 perna: Cta Credito preenchida, Valor a credito
- "Partida Dobrada" -> 1 linha com as DUAS pernas (Cta Debito E Cta Credito
  preenchidas) -> explode em 2 registros de saida
- "Cont.Hist" (ou qualquer linha sem nenhuma conta preenchida) -> descartada
  (so texto adicional do historico, sem valor)

ct2_key (CT2RAZCT5) vem direto da coluna "Key" do export quando presente -
e' o CT2_KEY real do Protheus, unico por lancamento (distingue corretamente
fornecedores diferentes que compartilham o mesmo numero de NF, o que e'
comum). So' quando "Key" vem vazia/curta demais o script cai no fallback:
tenta extrair serie/NF do texto do historico (padrao Protheus tipo
"NF.001/000164716") e cruza com um SFTENT ja importado (mesma empresa) para
descobrir o fornecedor - e, se a NF for compartilhada por mais de um
fornecedor no SFT, desambigua comparando o valor do lancamento contra a
coluna de imposto correspondente (PIS/COFINS/ICMS/IPI) de cada candidato.
Quando nada disso resolve, fica em branco e o matching cai no fallback
global por valor (tools/fiscal/match_ct2_sft.py).

Uso:
    python scripts/importar_ct2_completo.py \\
        --empresa-id 13 --excel "C:\\...\\CT2 12.2025.xlsx" --data-base 20251231

    # informando explicitamente a carga SFTENT a usar no cruzamento do ct2_key
    python scripts/importar_ct2_completo.py \\
        --empresa-id 13 --excel "C:\\...\\CT2 12.2025.xlsx" --data-base 20251231 \\
        --sft-carga-id 163
"""
import argparse
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db import SessionLocal
from models.protheus_carga import ProtheusCarga, ProtheusCargaRegistro
from scripts.importar_carga_manual import gravar_carga_manual

PAT_NF = re.compile(r"NF[.\s]+([A-Za-z0-9]+)\s*/\s*(\d+)")


def _limpar_conta(serie: pd.Series) -> pd.Series:
    # fillna("") ANTES do astype(str): em pandas 2.x, astype(str) numa coluna
    # float com NaN produz um valor ainda nulo (dtype "str" nullable), nao a
    # string "nan" - bool(NaN) e True, o que faria linhas sem conta vazarem
    # como se tivessem conta. fillna("") elimina isso na origem.
    return serie.fillna("").astype(str).str.strip().str.replace(r"\.0$", "", regex=True)


_CAMPOS_IMPOSTO_SFT = ("valpis", "valcof", "valicm", "icmscom", "valipi", "icmsret", "difal", "valcont")


def carregar_lookup_cliefor(db, empresa_id: int, sft_carga_id: int | None) -> dict:
    """
    (filial, nf) -> lista de candidatos {"cliefor", "valpis", "valcof", ...}.

    Numero de NF nao e' unico entre fornecedores diferentes (duas notas "345"
    de fornecedores distintos sao comuns) - por isso cada (filial, nf) pode
    ter mais de um cliefor candidato. Quando houver mais de um, a escolha do
    cliefor correto e' feita por valor em _resolver_ct2_key (nao da' pra
    decidir aqui, sem o valor do lancamento do CT2).
    """
    if sft_carga_id is None:
        carga = (
            db.query(ProtheusCarga)
            .filter(
                ProtheusCarga.empresa_id == empresa_id,
                ProtheusCarga.tipo_relatorio == "SFTENT",
                ProtheusCarga.status == "concluido",
            )
            .order_by(ProtheusCarga.created_at.desc())
            .first()
        )
        sft_carga_id = carga.id if carga else None

    if sft_carga_id is None:
        print("Aviso: nenhuma carga SFTENT encontrada - ct2_key ficara vazio para todos os registros.")
        return {}

    rows = db.query(ProtheusCargaRegistro).filter(ProtheusCargaRegistro.carga_id == sft_carga_id).all()
    agregados: dict = {}
    for r in rows:
        d = r.dados_json
        filial = str(d.get("filial") or "").strip().zfill(4)
        nf = str(d.get("nf") or "").strip().zfill(9)
        cliefor = str(d.get("cliefor") or "").strip().zfill(6)
        if not filial or not nf:
            continue
        soma = agregados.setdefault((filial, nf, cliefor), dict.fromkeys(_CAMPOS_IMPOSTO_SFT, 0.0))
        for campo in _CAMPOS_IMPOSTO_SFT:
            soma[campo] += float(d.get(campo) or 0)

    lookup: dict = {}
    for (filial, nf, cliefor), somas in agregados.items():
        candidato = {"cliefor": cliefor, **{c: round(v, 2) for c, v in somas.items()}}
        lookup.setdefault((filial, nf), []).append(candidato)
    print(f"Lookup SFT (carga {sft_carga_id}): {len(lookup)} pares (filial, nf), "
          f"{sum(1 for v in lookup.values() if len(v) > 1)} com mais de um cliefor (NF duplicada entre fornecedores)")
    return lookup


def _campos_base(row, lado: str) -> dict:
    data_lcto = row.get("Data Lcto")
    data_str = data_lcto.strftime("%d/%m/%Y") if pd.notna(data_lcto) else ""

    lote = str(row.get("Numero Lote") or "").strip()
    sublote = str(row.get("Sub Lote") or "").strip()
    doc = str(row.get("Numero Doc") or "").strip()
    linha = str(row.get("Numero Linha") or "").strip()

    col_item = "Item Conta D" if lado == "debito" else "Item Conta C"
    col_clval = "Cod Cl Val D" if lado == "debito" else "Cod Cl Val C"

    item_conta = row.get(col_item)
    item_conta = "" if pd.isna(item_conta) else str(item_conta).strip()

    cod_cl_val = row.get(col_clval)
    cod_cl_val = "" if pd.isna(cod_cl_val) else str(cod_cl_val).strip().replace(".0", "")

    lanc_padrao = row.get("Lanc Padrao")
    ct2_lp = "" if pd.isna(lanc_padrao) else str(lanc_padrao).strip().replace(".0", "").zfill(6)

    valor = round(float(row.get("Valor") or 0), 2)
    conta = row["Cta Debito"] if lado == "debito" else row["Cta Credito"]
    xpartida = row["Cta Credito"] if lado == "debito" else row["Cta Debito"]

    return {
        "data": data_str,
        "lote_sub_doc_linha": f"{lote}{sublote}{doc}{linha}",
        "historico": str(row.get("Hist Lanc") or "").strip(),
        "xpartida": xpartida or "",
        "c_custo": "",
        "item_conta": item_conta,
        "cod_cl_val": cod_cl_val,
        "debito": valor if lado == "debito" else 0.0,
        "credito": valor if lado == "credito" else 0.0,
        "saldo_atual": 0.0,
        "conta": conta,
        "_ct2_lp": ct2_lp,
    }


def _detectar_campo_imposto(historico: str) -> str | None:
    """
    Identifica, pelo texto do historico do CT2, qual coluna do SFT comparar
    para desambiguar o cliefor quando uma NF e' compartilhada por mais de um
    fornecedor. "RET" de PIS/COFINS/CSLL/IRRF e' retencao na fonte (servicos)
    - nao existe coluna equivalente no SFT (Livro Fiscal de mercadoria), por
    isso fica sem campo (None) e a desambiguacao por valor nao e' possivel.
    """
    h = historico.upper()
    if "DIFAL" in h:
        return "difal"
    if "ICMS" in h and "RET" in h:
        return "icmsret"
    if "ICMS" in h:
        return "valicm"
    if "IPI" in h:
        return "valipi"
    if "COFINS" in h and "RET" not in h:
        return "valcof"
    if "PIS" in h and "RET" not in h:
        return "valpis"
    return None


def _resolver_ct2_key(historico: str, filial_raw: str, valor: float, lookup_cliefor: dict, tolerancia: float = 0.10) -> str:
    m = PAT_NF.search(historico)
    if not m:
        return ""
    serie_raw, nf_raw = m.group(1), m.group(2)
    filial = str(filial_raw or "").strip().zfill(4)
    nf = nf_raw.strip().zfill(9)
    serie = serie_raw.strip().zfill(3) if serie_raw.isdigit() else serie_raw.strip().ljust(3, " ")[:3]

    candidatos = lookup_cliefor.get((filial, nf)) or []
    if not candidatos:
        return ""
    if len(candidatos) == 1:
        return f"{filial}{nf}{serie}{candidatos[0]['cliefor']}"

    # NF compartilhada por mais de um fornecedor - so resolve se conseguir
    # desambiguar por valor; senao, melhor deixar em branco (cai no fallback
    # por valor do matching) do que gravar um cliefor errado.
    campo = _detectar_campo_imposto(historico)
    if campo is None:
        return ""

    valor_abs = abs(round(valor, 2))
    batem = []
    for c in candidatos:
        soma = c.get(campo, 0.0)
        if abs(soma - valor_abs) <= tolerancia:
            batem.append(c)
        elif campo == "valicm":
            soma_com_icmscom = round(soma + c.get("icmscom", 0.0), 2)
            if abs(soma_com_icmscom - valor_abs) <= tolerancia:
                batem.append(c)

    if len(batem) == 1:
        return f"{filial}{nf}{serie}{batem[0]['cliefor']}"
    return ""


def construir_registros(df: pd.DataFrame, lookup_cliefor: dict) -> tuple[list[dict], list[dict]]:
    registros_ctbr480 = []
    registros_ct2razct5 = []

    for _, row in df.iterrows():
        tipo_lcto = str(row.get("Tipo Lcto") or "").strip()
        tem_debito = bool(row["Cta Debito"])
        tem_credito = bool(row["Cta Credito"])

        lados = []
        if tipo_lcto == "Partida Dobrada" and tem_debito and tem_credito:
            lados = ["debito", "credito"]
        elif tem_debito:
            lados = ["debito"]
        elif tem_credito:
            lados = ["credito"]
        else:
            continue  # Cont.Hist ou linha sem conta - descarta

        filial_raw = row.get("Filial")
        key_raw = str(row.get("Key") or "").strip()

        for lado in lados:
            base = _campos_base(row, lado)
            ct2_lp = base.pop("_ct2_lp")

            registros_ctbr480.append(dict(base))

            # CT2_KEY real do Protheus, quando o export trouxe a coluna "Key"
            # preenchida - e' a fonte mais confiavel (distingue corretamente
            # fornecedores diferentes que usam o mesmo numero de NF). So cai
            # no fallback por NF+valor (historico) quando vier vazia.
            if len(key_raw) >= 22:
                ct2_key = key_raw
            else:
                valor_lancamento = base["debito"] if lado == "debito" else base["credito"]
                ct2_key = _resolver_ct2_key(base["historico"], filial_raw, valor_lancamento, lookup_cliefor)
            registros_ct2razct5.append({
                **base,
                "ct2_key": ct2_key,
                "ct2_lp": ct2_lp,
                "ct2_origem": "",
                "ct2_itemc": "",
                "ct5_desc": "",
            })

    return registros_ctbr480, registros_ct2razct5


def main():
    parser = argparse.ArgumentParser(description="Importa CT2 bruto como cargas CTBR480 + CT2RAZCT5 (todas as contas)")
    parser.add_argument("--empresa-id", type=int, required=True)
    parser.add_argument("--excel", required=True, help="Caminho do arquivo CT2 MM.AAAA.xlsx")
    parser.add_argument("--data-base", required=True, help="YYYYMMDD")
    parser.add_argument("--sft-carga-id", type=int, default=None, help="Carga SFTENT a usar no cruzamento do ct2_key (default: ultima concluida da empresa)")
    args = parser.parse_args()

    db = SessionLocal()
    lookup_cliefor = carregar_lookup_cliefor(db, args.empresa_id, args.sft_carga_id)
    db.close()

    print(f"Lendo {args.excel} ...")
    df = pd.read_excel(args.excel, header=2)
    df["Cta Debito"] = _limpar_conta(df["Cta Debito"])
    df["Cta Credito"] = _limpar_conta(df["Cta Credito"])
    print(f"Total linhas no export: {len(df)}")

    registros_ctbr480, registros_ct2razct5 = construir_registros(df, lookup_cliefor)
    print(f"Registros CTBR480: {len(registros_ctbr480)}")
    print(f"Registros CT2RAZCT5: {len(registros_ct2razct5)} (com ct2_key: {sum(1 for r in registros_ct2razct5 if r['ct2_key'])})")

    contas_distintas = {r["conta"] for r in registros_ctbr480 if r["conta"]}
    print(f"Contas contabeis cobertas: {len(contas_distintas)}")

    for tipo, registros in (("CTBR480", registros_ctbr480), ("CT2RAZCT5", registros_ct2razct5)):
        resultado = gravar_carga_manual(
            empresa_id=args.empresa_id,
            tipo_relatorio=tipo,
            data_base=args.data_base,
            registros=registros,
        )
        print(f"{tipo}: {resultado}")


if __name__ == "__main__":
    main()
