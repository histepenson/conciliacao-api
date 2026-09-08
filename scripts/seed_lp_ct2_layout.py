"""
Popula lancamento_padrao_ct2_layout com o mapeamento LP -> familia de
formula de CT2_KEY, usado no matching exato da Conciliacao de Estoque
(ver tools/estoque/calc_diferencas_estoque.py::_matching_por_ct2_key).

Esse mapeamento nao da pra descobrir automaticamente (nao e' um campo
consultavel no Protheus) -- vem de analise manual da configuracao de
Lancamento Padrao da empresa. Os LPs abaixo sao os que a empresa piloto
(assumido empresa_id=5 -- ajustar via --empresa-id se for outra) informou.

Uso:
    python scripts/seed_lp_ct2_layout.py --empresa-id 5
    python scripts/seed_lp_ct2_layout.py --empresa-id 5 --dry-run
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.dialects.postgresql import insert as pg_insert

from db import SessionLocal
from models.lancamento_padrao import LancamentoPadraoCt2Layout

# lp_codigo -> (tipo_chave, descricao)
LPS_PADRAO = {
    "681": ("COMPRA", "D1_FILIAL+DOC+SERIE+FORNECE+LOJA+COD+ITEM"),
    "641": ("COMPRA", "FILIAL+DOC+SERIE+FORNECE+LOJA+COD+ITEM"),
    "678": ("VENDA", "FILIAL+DOC+SERIE+CLIENTE+LOJA+COD+ITEM"),
    "670": ("ESTOQUE", "FILIAL+COD+LOCAL+DTOS(EMISSAO)+NUMSEQ"),
    "668": ("ESTOQUE", "FILIAL+COD+LOCAL+DTOS(EMISSAO)+NUMSEQ"),
    "672": ("ESTOQUE", "FILIAL+COD+LOCAL+DTOS(EMISSAO)+NUMSEQ"),
    "666": ("ESTOQUE", "FILIAL+COD+LOCAL+DTOS(EMISSAO)+NUMSEQ"),
}


def main():
    parser = argparse.ArgumentParser(description="Seed de lancamento_padrao_ct2_layout")
    parser.add_argument("--empresa-id", type=int, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        for lp_codigo, (tipo_chave, descricao) in LPS_PADRAO.items():
            print(f"LP {lp_codigo} -> {tipo_chave} ({descricao})")
            if args.dry_run:
                continue

            stmt = pg_insert(LancamentoPadraoCt2Layout).values(
                empresa_id=args.empresa_id,
                lp_codigo=lp_codigo,
                tipo_chave=tipo_chave,
                descricao=descricao,
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_lp_ct2_layout_empresa_codigo",
                set_={"tipo_chave": tipo_chave, "descricao": descricao},
            )
            db.execute(stmt)

        if args.dry_run:
            print("(dry-run, nada gravado)")
        else:
            db.commit()
            print(f"OK - {len(LPS_PADRAO)} LPs gravados para empresa_id={args.empresa_id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
