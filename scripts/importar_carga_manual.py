"""
Grava uma carga Protheus "manual" (sem chamar a API do Protheus) como se ela
tivesse sido concluida via fila RQ normal — usado para empresas sem acesso a
API do Protheus, cujos dados chegam apenas em CSV/Excel.

Este script NAO faz nenhuma normalizacao de CSV. Ele recebe uma lista de
registros JA no formato exato que cada tipo_relatorio grava em
protheus_carga_registro.dados_json (ver skill
".claude/skills/importar-csv-protheus/SKILL.md" para o schema de cada tipo
e as regras de mapeamento a partir do CSV bruto).

Uso:
    python scripts/importar_carga_manual.py \
        --empresa-id 7 --tipo FINR130 --data-base 20260601 \
        --registros-json /tmp/finr130_registros.json

    python scripts/importar_carga_manual.py --listar-empresas
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.dialects.postgresql import insert as pg_insert

from db import SessionLocal
from models.empresa import Empresa
from models.protheus_carga import ProtheusCarga, ProtheusCargaRegistro
from services import protheus_carga_service as pcs
from services.lancamento_padrao_service import upsert_de_carga as lp_upsert_de_carga

_INSERT_CHUNK_SIZE = 1000


def listar_empresas() -> None:
    db = SessionLocal()
    try:
        empresas = db.query(Empresa).order_by(Empresa.nome).all()
        print(f"{'id':<5} {'nome':<40} {'cnpj':<20} status")
        for e in empresas:
            print(f"{e.id:<5} {e.nome:<40} {e.cnpj:<20} {'ativo' if e.status else 'inativo'}")
    finally:
        db.close()


def gravar_carga_manual(
    empresa_id: int,
    tipo_relatorio: str,
    data_base: str,
    registros: list[dict],
    parametros_extra: dict | None = None,
) -> dict:
    """
    Cria (ou reaproveita) uma ProtheusCarga e grava `registros` em
    ProtheusCargaRegistro com status='concluido', exatamente como o worker
    faz apos consultar a API do Protheus.
    """
    db = SessionLocal()
    try:
        tipo = pcs.normalizar_tipo_relatorio(tipo_relatorio)
        data_base = pcs.validar_data_base(data_base)

        empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
        if not empresa:
            raise SystemExit(f"Empresa id={empresa_id} nao encontrada")

        parametros = dict(parametros_extra or {})
        parametros["data_base"] = parametros.get("data_base") or data_base
        parametros.setdefault("importacao_manual", True)
        parametros.setdefault("fonte", "csv")
        parametros_hash = pcs.calcular_parametros_hash(parametros)

        filtro = [
            ProtheusCarga.empresa_id == empresa_id,
            ProtheusCarga.tipo_relatorio == tipo,
            ProtheusCarga.data_base == data_base,
            ProtheusCarga.parametros_hash == parametros_hash,
        ]
        carga = db.query(ProtheusCarga).filter(*filtro).order_by(ProtheusCarga.created_at.desc()).first()

        if carga:
            db.query(ProtheusCargaRegistro).filter(ProtheusCargaRegistro.carga_id == carga.id).delete()
            carga.status = "processando"
            carga.erro = None
            carga.total_registros = 0
            db.commit()
        else:
            carga = ProtheusCarga(
                empresa_id=empresa_id,
                tipo_relatorio=tipo,
                data_base=data_base,
                parametros_hash=parametros_hash,
                parametros_json=parametros,
                status="processando",
            )
            db.add(carga)
            db.commit()
            db.refresh(carga)

        pcs.marcar_processando(db, carga)

        rows = [
            {"carga_id": carga.id, "sequencia": i + 1, "dados_json": r}
            for i, r in enumerate(registros)
        ]
        for start in range(0, len(rows), _INSERT_CHUNK_SIZE):
            db.execute(pg_insert(ProtheusCargaRegistro), rows[start:start + _INSERT_CHUNK_SIZE])
        db.commit()

        total = len(registros)
        pcs.marcar_concluido(db, carga, total)

        novos_lp = 0
        if tipo == "CT2RAZCT5":
            novos_lp = lp_upsert_de_carga(db, empresa_id, registros)

        return {
            "carga_id": carga.id,
            "empresa_id": empresa_id,
            "empresa_nome": empresa.nome,
            "tipo_relatorio": tipo,
            "data_base": data_base,
            "total_registros": total,
            "novos_lancamentos_padrao": novos_lp,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Grava carga Protheus manual (importacao via CSV) no banco")
    parser.add_argument("--listar-empresas", action="store_true", help="Lista empresas cadastradas e sai")
    parser.add_argument("--empresa-id", type=int, help="ID da empresa (tenant)")
    parser.add_argument("--tipo", help="Tipo de relatorio: FINR130, FINR150, FINR470, SFTENT, CT2RAZCT5, etc.")
    parser.add_argument("--data-base", help="Data base no formato YYYYMMDD")
    parser.add_argument("--registros-json", help="Caminho de um arquivo JSON contendo a lista de registros normalizados")
    parser.add_argument("--parametros-json", help="JSON inline com parametros extras (opcional)")
    args = parser.parse_args()

    if args.listar_empresas:
        listar_empresas()
        return

    if not (args.empresa_id and args.tipo and args.data_base and args.registros_json):
        parser.error("--empresa-id, --tipo, --data-base e --registros-json sao obrigatorios (ou use --listar-empresas)")

    with open(args.registros_json, "r", encoding="utf-8") as f:
        registros = json.load(f)
    if not isinstance(registros, list):
        raise SystemExit("O arquivo --registros-json deve conter uma lista JSON de objetos")

    parametros_extra = json.loads(args.parametros_json) if args.parametros_json else None

    resultado = gravar_carga_manual(
        empresa_id=args.empresa_id,
        tipo_relatorio=args.tipo,
        data_base=args.data_base,
        registros=registros,
        parametros_extra=parametros_extra,
    )
    print(json.dumps(resultado, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
