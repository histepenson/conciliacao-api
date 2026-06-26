"""
Backfill do campo `sequencia` em lancamento_padrao para empresas onde ele ficou
vazio - acontecia porque o ct2_sequen das cargas CT2RAZCT5 antigas vinha vazio
(campo adicionado depois ao ZCT2RAZCT5.prw) e upsert_de_carga nao tinha fallback
para extrair a sequencia de ct2_origem (corrigido em lancamento_padrao_service.py).

Reaproveita a ULTIMA carga CT2RAZCT5 concluida ja armazenada no banco para cada
empresa (nao busca nada novo no Protheus) e roda o upsert corrigido, que so
preenche `sequencia` onde estiver vazio - nao toca em nenhuma outra config
(cfops, colunas_sft, grupo, ativo) ja feita pelo usuario.

Uso:
    python scripts/backfill_sequencia_lp.py              # todas as empresas
    python scripts/backfill_sequencia_lp.py --empresa-id 13
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db import SessionLocal
from models.protheus_carga import ProtheusCarga, ProtheusCargaRegistro
from models.lancamento_padrao import LancamentoPadrao
from services.lancamento_padrao_service import upsert_de_carga


def empresas_com_lp_sem_sequencia(db, empresa_id: int | None) -> list[int]:
    query = db.query(LancamentoPadrao.empresa_id).filter(
        (LancamentoPadrao.sequencia.is_(None)) | (LancamentoPadrao.sequencia == "")
    )
    if empresa_id is not None:
        query = query.filter(LancamentoPadrao.empresa_id == empresa_id)
    return sorted({row[0] for row in query.distinct().all()})


def ultima_carga_ct2razct5(db, empresa_id: int) -> ProtheusCarga | None:
    return (
        db.query(ProtheusCarga)
        .filter(
            ProtheusCarga.empresa_id == empresa_id,
            ProtheusCarga.tipo_relatorio == "CT2RAZCT5",
            ProtheusCarga.status == "concluido",
        )
        .order_by(ProtheusCarga.finalizado_em.desc())
        .first()
    )


def main():
    parser = argparse.ArgumentParser(description="Backfill de lancamento_padrao.sequencia a partir da ultima carga CT2RAZCT5 em cache")
    parser.add_argument("--empresa-id", type=int, default=None, help="Restringe a uma empresa (default: todas com sequencia vazia)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        empresas = empresas_com_lp_sem_sequencia(db, args.empresa_id)
        if not empresas:
            print("Nenhuma empresa com lancamento_padrao.sequencia vazio encontrada.")
            return

        print(f"Empresas com sequencia vazia: {empresas}")
        for empresa_id in empresas:
            carga = ultima_carga_ct2razct5(db, empresa_id)
            if not carga:
                print(f"  empresa={empresa_id}: sem carga CT2RAZCT5 concluida em cache, pulando.")
                continue

            registros = (
                db.query(ProtheusCargaRegistro)
                .filter(ProtheusCargaRegistro.carga_id == carga.id)
                .all()
            )
            novos = upsert_de_carga(db, empresa_id, [r.dados_json for r in registros])
            print(f"  empresa={empresa_id}: carga={carga.id} ({len(registros)} registros) -> {novos} novos LPs, sequencia preenchida onde estava vazia")
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
