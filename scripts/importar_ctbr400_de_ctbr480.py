"""
Deriva carga(s) CTBR400 (razao filtrado por conta bancaria) a partir de uma
carga CTBR480 (razao geral, todas as contas) ja importada - mesmo schema,
apenas filtrando por conta_contabil. Usado quando o CT2 completo ja foi
gravado como CTBR480 e so falta disponibilizar o recorte por conta para a
tela de Conciliacao Bancaria (que busca cache do tipo CTBR400).

Uso:
    python scripts/importar_ctbr400_de_ctbr480.py \\
        --empresa-id 13 --ctbr480-carga-id 227 --data-base 20260430 \\
        --conta 111020001 111020010 111020011
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db import SessionLocal
from models.protheus_carga import ProtheusCargaRegistro
from scripts.importar_carga_manual import gravar_carga_manual


def main():
    parser = argparse.ArgumentParser(description="Gera cargas CTBR400 (por conta) a partir de uma carga CTBR480")
    parser.add_argument("--empresa-id", type=int, required=True)
    parser.add_argument("--ctbr480-carga-id", type=int, required=True)
    parser.add_argument("--data-base", required=True, help="YYYYMMDD")
    parser.add_argument("--conta", nargs="+", required=True, help="Uma ou mais contas contabeis a extrair")
    args = parser.parse_args()

    db = SessionLocal()
    rows = (
        db.query(ProtheusCargaRegistro)
        .filter(ProtheusCargaRegistro.carga_id == args.ctbr480_carga_id)
        .all()
    )
    print(f"Carga CTBR480 {args.ctbr480_carga_id}: {len(rows)} registros totais")
    db.close()

    for conta in args.conta:
        registros = [r.dados_json for r in rows if str(r.dados_json.get("conta") or "").strip() == conta]
        print(f"Conta {conta}: {len(registros)} registros")
        if not registros:
            print(f"  aviso: nenhum registro encontrado para conta {conta}, pulando")
            continue
        resultado = gravar_carga_manual(
            empresa_id=args.empresa_id,
            tipo_relatorio="CTBR400",
            data_base=args.data_base,
            registros=registros,
            parametros_extra={"conta_de": conta, "conta_ate": conta},
        )
        print(resultado)


if __name__ == "__main__":
    main()
