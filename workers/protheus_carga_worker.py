import asyncio
import logging
from typing import Any

from db import SessionLocal
from core.protheus import resolve_protheus_config
from models.protheus_carga import ProtheusCarga, ProtheusCargaRegistro
from services.ctbr140_service import Ctbr140Service
from services.ctbr400_service import Ctbr400Service
from services.ctbr480_service import Ctbr480Service
from services.finr130_service import FinR130Service
from services.finr150_service import FinR150Service
from services.finr470_service import FinR470Service
from services.matr900_service import Matr900Service
from services.protheus_carga_service import marcar_concluido, marcar_erro, marcar_processando

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def executar_carga_protheus(carga_id: int) -> None:
    print(f"[PROTHEUS_CARGA] job recebido carga_id={carga_id}", flush=True)
    asyncio.run(_executar_carga_protheus(carga_id))


async def _executar_carga_protheus(carga_id: int) -> None:
    print(f"[PROTHEUS_CARGA] abrindo sessao banco carga_id={carga_id}", flush=True)
    db = SessionLocal()
    try:
        print(f"[PROTHEUS_CARGA] buscando carga no banco carga_id={carga_id}", flush=True)
        carga = db.query(ProtheusCarga).filter(ProtheusCarga.id == carga_id).first()
        if not carga:
            raise RuntimeError(f"Carga Protheus {carga_id} nao encontrada")

        if carga.status in {"concluido", "cancelado"}:
            logger.info("Carga Protheus %s ja esta em status final (%s), ignorando", carga.id, carga.status)
            print(f"[PROTHEUS_CARGA] status final {carga.status}, ignorando carga_id={carga.id}", flush=True)
            return

        print(f"[PROTHEUS_CARGA] marcando processando carga_id={carga.id}", flush=True)
        marcar_processando(db, carga)
        logger.info(
            "Carga Protheus %s iniciada: relatorio=%s empresa=%s data_base=%s",
            carga.id,
            carga.tipo_relatorio,
            carga.empresa_id,
            carga.data_base,
        )

        print(f"[PROTHEUS_CARGA] chamando Protheus carga_id={carga.id} relatorio={carga.tipo_relatorio}", flush=True)
        registros = await _buscar_registros(carga, db)

        print(f"[PROTHEUS_CARGA] gravando {len(registros)} registros carga_id={carga.id}", flush=True)
        db.query(ProtheusCargaRegistro).filter(ProtheusCargaRegistro.carga_id == carga.id).delete()
        db.bulk_save_objects(
            [
                ProtheusCargaRegistro(carga_id=carga.id, sequencia=index + 1, dados_json=registro)
                for index, registro in enumerate(registros)
            ]
        )
        marcar_concluido(db, carga, len(registros))
        logger.info("Carga Protheus %s concluida com %s registros", carga.id, len(registros))
        print(f"[PROTHEUS_CARGA] concluida carga_id={carga.id} total={len(registros)}", flush=True)
    except Exception as exc:
        print(f"[PROTHEUS_CARGA] erro carga_id={carga_id}: {exc}", flush=True)
        db.rollback()
        carga = db.query(ProtheusCarga).filter(ProtheusCarga.id == carga_id).first()
        if carga:
            marcar_erro(db, carga, str(exc))
        logger.exception("Carga Protheus %s falhou", carga_id)
        raise
    finally:
        db.close()


async def _buscar_registros(carga: ProtheusCarga, db) -> list[dict[str, Any]]:
    print(f"[PROTHEUS_CARGA] resolvendo config Protheus empresa_id={carga.empresa_id}", flush=True)
    config = resolve_protheus_config(carga.empresa_id, db)
    params = dict(carga.parametros_json or {})
    params["data_base"] = params.get("data_base") or carga.data_base

    service_args = (config.url, config.user, config.password, config.tenant, config.rest_prefix)
    tipo = carga.tipo_relatorio.upper()
    print(f"[PROTHEUS_CARGA] config resolvida relatorio={tipo} tenant={config.tenant}", flush=True)

    if tipo == "FINR130":
        resultado = await FinR130Service(*service_args).buscar_todos_titulos(params)
        return list(resultado.get("titulos", []))
    if tipo == "FINR150":
        return await FinR150Service(*service_args).buscar_como_registros(params)
    if tipo == "CTBR140":
        return await Ctbr140Service(*service_args).buscar_como_registros(params)
    if tipo == "CTBR400":
        return await Ctbr400Service(*service_args).buscar_como_registros(params)
    if tipo == "CTBR480":
        return await Ctbr480Service(*service_args).buscar_como_registros(params)
    if tipo == "FINR470":
        return await FinR470Service(*service_args).buscar_como_registros(params)
    if tipo == "MATR900":
        return await Matr900Service(*service_args).buscar_como_registros(params)

    raise RuntimeError(f"Relatorio {carga.tipo_relatorio} nao suportado")
