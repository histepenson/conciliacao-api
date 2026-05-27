"""
Importa lançamentos padrão (CT5) de um arquivo Excel para a tabela ct5_referencia.

Uso:
    python scripts/importar_ct5_referencia.py --arquivo Downloads/ctba090.xlsx --empresa-id 1

O script:
  - Lê o xlsx (colunas: Filial, Lcto Padrao, Chave Busca, Ordem Busca, Descricao, Alias Arq)
  - Para alias SD1 e SF1 calcula campo_nf='FT_NFISCAL', nf_posicao_ini=10, nf_tamanho=9
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

# Posição e tamanho da NF dentro do CT2_KEY para LPs de SD1/SF1:
# Estrutura do CT2_KEY: D1_FILIAL(2) + D1_DOC(9) + ...
# + FILIAL(2) = pos 1-2
# + DOC(9)    = pos 3-11  ← NF aqui
NF_POSICAO_INI = 3
NF_TAMANHO = 9


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
        raise ValueError(f"Colunas ausentes no arquivo: {missing}\nColunas encontradas: {header}")

    idx = {c: header.index(c) for c in expected}

    registros = []
    for i, row in enumerate(rows[1:], start=2):
        lp = str(row[idx["Lcto Padrao"]]).strip() if row[idx["Lcto Padrao"]] is not None else ""
        if not lp:
            continue

        alias = str(row[idx["Alias Arq"]]).strip() if row[idx["Alias Arq"]] else ""
        tem_nf = alias in ALIASES_COM_NF

        registros.append({
            "filial":        str(row[idx["Filial"]]).split("-")[0].strip() if row[idx["Filial"]] else None,
            "lp_codigo":     lp,
            "chave_busca":   str(row[idx["Chave Busca"]]).strip() if row[idx["Chave Busca"]] else None,
            "ordem_busca":   str(row[idx["Ordem Busca"]]).strip() if row[idx["Ordem Busca"]] is not None else None,
            "descricao":     str(row[idx["Descricao"]]).strip() if row[idx["Descricao"]] else None,
            "alias_arq":     alias or None,
            "campo_nf":      "FT_NFISCAL" if tem_nf else None,
            "nf_posicao_ini": NF_POSICAO_INI if tem_nf else None,
            "nf_tamanho":    NF_TAMANHO if tem_nf else None,
        })

    return registros


def importar(empresa_id: int, arquivo: str, dry_run: bool = False):
    registros = parse_xlsx(arquivo)
    print(f"Lidos {len(registros)} lançamentos padrão do arquivo.")

    nf_count = sum(1 for r in registros if r["campo_nf"])
    print(f"  Com mapeamento de NF (SD1/SF1): {nf_count}")
    print(f"  Sem mapeamento de NF:           {len(registros) - nf_count}")

    if dry_run:
        print("\n[DRY RUN] Nenhuma alteração gravada.")
        for r in registros[:5]:
            print(" ", r)
        print("  ...")
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
            filial        = EXCLUDED.filial,
            chave_busca   = EXCLUDED.chave_busca,
            ordem_busca   = EXCLUDED.ordem_busca,
            descricao     = EXCLUDED.descricao,
            alias_arq     = EXCLUDED.alias_arq,
            campo_nf      = EXCLUDED.campo_nf,
            nf_posicao_ini = EXCLUDED.nf_posicao_ini,
            nf_tamanho    = EXCLUDED.nf_tamanho,
            updated_at    = now()
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
