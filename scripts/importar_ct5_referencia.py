"""
Importa lançamentos padrão (CT5) de um arquivo Excel para a tabela ct5_referencia.

Uso:
    python scripts/importar_ct5_referencia.py --arquivo Downloads/ctba090.xlsx --empresa-id 1
    python scripts/importar_ct5_referencia.py --arquivo Downloads/ctba090.xlsx --empresa-id 1 --dry-run

O script:
  - Lê o xlsx (colunas: Filial, Lcto Padrao, Chave Busca, Ordem Busca, Descricao, Alias Arq)
  - Para alias SD1 e SF1: parseia a chave busca para calcular a posição do campo NF (D1_DOC/F1_DOC)
    dentro do CT2_KEY, baseado nos tamanhos conhecidos dos campos Protheus
  - Faz upsert (INSERT ... ON CONFLICT DO UPDATE) para ser idempotente
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import openpyxl
from sqlalchemy import text
from db import SessionLocal


ALIASES_COM_NF = {"SD1", "SF1"}

# Campo NF por alias
CAMPO_NF_POR_ALIAS = {
    "SD1": "D1_DOC",
    "SF1": "F1_DOC",
}

# Tamanhos padrão dos campos Protheus (baseado no dicionário SX3)
TAMANHOS_CAMPO = {
    # SD1 - Itens das notas de entrada
    "D1_FILIAL":  2,
    "D1_DOC":     9,
    "D1_SERIE":   3,
    "D1_FORNECE": 6,
    "D1_LOJA":    2,
    "D1_TIPO":    2,
    "D1_COD":    15,
    "D1_ITEM":    4,
    "D1_SEQUEN":  4,
    # SF1 - Cabeçalho das notas de entrada
    "F1_FILIAL":  2,
    "F1_DOC":     9,
    "F1_SERIE":   3,
    "F1_FORNECE": 6,
    "F1_LOJA":    2,
    "F1_TIPO":    2,
    "F1_SEQUEN":  4,
    # SE1 - Contas a receber
    "E1_FILIAL":  2,
    "E1_CLIENTE": 6,
    "E1_LOJA":    2,
    "E1_PREFIXO": 3,
    "E1_NUM":     9,
    "E1_PARCELA": 2,
    "E1_TIPO":    3,
    # SE2 - Contas a pagar
    "E2_FILIAL":  2,
    "E2_FORNECE": 6,
    "E2_LOJA":    2,
    "E2_PREFIXO": 3,
    "E2_NUM":     9,
    "E2_PARCELA": 2,
    "E2_TIPO":    3,
}


def calcular_posicao_nf(chave_busca: str, alias: str) -> tuple[int | None, int | None, list[str]]:
    """
    Parseia a fórmula da chave busca e retorna (posicao_ini, tamanho, avisos).

    posicao_ini: posição 1-based do campo NF dentro do CT2_KEY
    tamanho: tamanho do campo NF
    avisos: campos cujo tamanho não foi encontrado no dicionário
    """
    campo_nf = CAMPO_NF_POR_ALIAS.get(alias)
    if not campo_nf:
        return None, None, []

    campos = [c.strip() for c in chave_busca.split("+") if c.strip()]
    avisos = []
    posicao = 1

    for campo in campos:
        tamanho = TAMANHOS_CAMPO.get(campo)
        if tamanho is None:
            avisos.append(campo)
            # Não é possível calcular posição com campo desconhecido antes do NF
            if campo == campo_nf:
                break
            return None, None, avisos

        if campo == campo_nf:
            return posicao, tamanho, avisos

        posicao += tamanho

    return None, None, avisos


def parse_xlsx(arquivo: str):
    wb = openpyxl.load_workbook(arquivo)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ValueError("Arquivo vazio")

    header = [str(c).strip() if c else "" for c in rows[0]]
    expected = {"Filial", "Lcto Padrao", "Chave Busca", "Ordem Busca", "Descricao", "Alias Arq"}
    missing = expected - set(header)
    if missing:
        raise ValueError(f"Colunas ausentes: {missing}\nEncontradas: {header}")

    idx = {c: header.index(c) for c in expected}
    registros = []
    todos_avisos = []

    for i, row in enumerate(rows[1:], start=2):
        lp = str(row[idx["Lcto Padrao"]]).strip() if row[idx["Lcto Padrao"]] is not None else ""
        if not lp:
            continue

        alias = str(row[idx["Alias Arq"]]).strip() if row[idx["Alias Arq"]] else ""
        chave = str(row[idx["Chave Busca"]]).strip() if row[idx["Chave Busca"]] else ""
        tem_nf = alias in ALIASES_COM_NF

        nf_pos, nf_tam, avisos = (None, None, [])
        if tem_nf and chave:
            nf_pos, nf_tam, avisos = calcular_posicao_nf(chave, alias)
            if avisos:
                todos_avisos.append(f"  LP {lp} ({alias}): campos sem tamanho definido: {avisos}")
            if tem_nf and nf_pos is None:
                todos_avisos.append(f"  LP {lp} ({alias}): não foi possível calcular posição do NF")

        filial_raw = row[idx["Filial"]]
        filial = str(filial_raw).split("-")[0].strip() if filial_raw else None

        registros.append({
            "filial":         filial,
            "lp_codigo":      lp,
            "chave_busca":    chave or None,
            "ordem_busca":    str(row[idx["Ordem Busca"]]).strip() if row[idx["Ordem Busca"]] is not None else None,
            "descricao":      str(row[idx["Descricao"]]).strip() if row[idx["Descricao"]] else None,
            "alias_arq":      alias or None,
            "campo_nf":       "FT_NFISCAL" if tem_nf and nf_pos else None,
            "nf_posicao_ini": nf_pos,
            "nf_tamanho":     nf_tam,
        })

    return registros, todos_avisos


def importar(empresa_id: int, arquivo: str, dry_run: bool = False):
    registros, avisos = parse_xlsx(arquivo)
    print(f"Lidos {len(registros)} lançamentos padrão do arquivo.")

    nf_mapeados = sum(1 for r in registros if r["nf_posicao_ini"])
    print(f"  Com posição NF calculada (SD1/SF1): {nf_mapeados}")
    print(f"  Sem mapeamento de NF:               {len(registros) - nf_mapeados}")

    if avisos:
        print(f"\nAvisos ({len(avisos)}):")
        for a in avisos:
            print(a)

    # Mostrar resumo dos LPs com NF
    print("\nLP | Alias | Pos NF | Tam | Descrição")
    print("-" * 70)
    for r in registros:
        if r["nf_posicao_ini"]:
            print(f"  {r['lp_codigo']:<8} {r['alias_arq']:<6} pos={r['nf_posicao_ini']:<4} tam={r['nf_tamanho']}  {(r['descricao'] or '')[:40]}")

    if dry_run:
        print("\n[DRY RUN] Nenhuma alteração gravada.")
        return

    upsert_sql = text("""
        INSERT INTO concilia.ct5_referencia
            (empresa_id, filial, lp_codigo, chave_busca, ordem_busca,
             descricao, alias_arq, campo_nf, nf_posicao_ini, nf_tamanho,
             created_at, updated_at)
        VALUES
            (:empresa_id, :filial, :lp_codigo, :chave_busca, :ordem_busca,
             :descricao, :alias_arq, :campo_nf, :nf_posicao_ini, :nf_tamanho,
             now(), now())
        ON CONFLICT (empresa_id, lp_codigo)
        DO UPDATE SET
            filial         = EXCLUDED.filial,
            chave_busca    = EXCLUDED.chave_busca,
            ordem_busca    = EXCLUDED.ordem_busca,
            descricao      = EXCLUDED.descricao,
            alias_arq      = EXCLUDED.alias_arq,
            campo_nf       = EXCLUDED.campo_nf,
            nf_posicao_ini = EXCLUDED.nf_posicao_ini,
            nf_tamanho     = EXCLUDED.nf_tamanho,
            updated_at     = now()
    """)

    db = SessionLocal()
    try:
        for reg in registros:
            db.execute(upsert_sql, {"empresa_id": empresa_id, **reg})
        db.commit()
        print(f"\nImportados/atualizados {len(registros)} registros para empresa_id={empresa_id}.")
    except Exception as e:
        db.rollback()
        print(f"ERRO: {e}")
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Importa CT5 de xlsx para ct5_referencia")
    parser.add_argument("--arquivo", required=True, help="Caminho do arquivo xlsx")
    parser.add_argument("--empresa-id", type=int, required=True, help="ID da empresa no banco")
    parser.add_argument("--dry-run", action="store_true", help="Apenas mostra os dados, não grava")
    args = parser.parse_args()

    if not os.path.isfile(args.arquivo):
        print(f"Arquivo não encontrado: {args.arquivo}")
        sys.exit(1)

    importar(args.empresa_id, args.arquivo, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
