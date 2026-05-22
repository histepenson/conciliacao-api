import argparse
import logging

from db import SessionLocal
from models.protheus_carga import ProtheusCargaConfig
from services.protheus_carga_service import enfileirar_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Enfileira cargas automaticas do Protheus")
    parser.add_argument("--data-base", required=True, help="Data base no formato YYYYMMDD")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        configs = (
            db.query(ProtheusCargaConfig)
            .filter(
                ProtheusCargaConfig.ativo == True,
                ProtheusCargaConfig.atualizar_automatico == True,
            )
            .all()
        )
        for config in configs:
            carga, reutilizavel = enfileirar_config(db, config.empresa_id, config.id, data_base=args.data_base)
            logger.info(
                "Config %s enfileirada: carga=%s relatorio=%s reutilizavel=%s",
                config.id,
                carga.id,
                config.tipo_relatorio,
                reutilizavel,
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()
