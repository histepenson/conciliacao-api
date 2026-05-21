import asyncio
import logging
from typing import Any, AsyncGenerator

from sqlalchemy.dialects.postgresql import insert as pg_insert

from db import SessionLocal
from core.protheus import resolve_protheus_config
from core.protheus_http import protheus_async_client
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

_PAGE_SIZE = 5000
_COMMIT_A_CADA = 5


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
            carga.id, carga.tipo_relatorio, carga.empresa_id, carga.data_base,
        )

        config = resolve_protheus_config(carga.empresa_id, db)
        params = dict(carga.parametros_json or {})
        params["data_base"] = params.get("data_base") or carga.data_base
        params.setdefault("pageSize", _PAGE_SIZE)

        db.query(ProtheusCargaRegistro).filter(ProtheusCargaRegistro.carga_id == carga.id).delete()
        db.commit()

        total = 0
        sequencia = 1
        paginas_sem_commit = 0
        buffer_insert: list[dict] = []

        async for registros_pagina in _iterar_paginas(carga, config, params):
            if not registros_pagina:
                continue

            buffer_insert.extend(
                {"carga_id": carga.id, "sequencia": sequencia + i, "dados_json": r}
                for i, r in enumerate(registros_pagina)
            )
            sequencia += len(registros_pagina)
            total += len(registros_pagina)
            paginas_sem_commit += 1

            if paginas_sem_commit >= _COMMIT_A_CADA:
                db.execute(pg_insert(ProtheusCargaRegistro), buffer_insert)
                carga.total_registros = total
                db.commit()
                buffer_insert = []
                paginas_sem_commit = 0
                logger.info("Carga Protheus %s: %s registros gravados", carga.id, total)
                print(f"[PROTHEUS_CARGA] gravados {total} registros carga_id={carga.id}", flush=True)

        if buffer_insert:
            db.execute(pg_insert(ProtheusCargaRegistro), buffer_insert)
            db.commit()

        marcar_concluido(db, carga, total)
        logger.info("Carga Protheus %s concluida com %s registros", carga.id, total)
        print(f"[PROTHEUS_CARGA] concluida carga_id={carga.id} total={total}", flush=True)

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


async def _iterar_paginas(
    carga: ProtheusCarga,
    config: Any,
    params: dict[str, Any],
) -> AsyncGenerator[list[dict], None]:
    service_args = (config.url, config.user, config.password, config.tenant, config.rest_prefix)
    tipo = carga.tipo_relatorio.upper()

    services = {
        "FINR130": FinR130Service,
        "FINR150": FinR150Service,
        "CTBR140": Ctbr140Service,
        "CTBR400": Ctbr400Service,
        "CTBR480": Ctbr480Service,
        "FINR470": FinR470Service,
        "MATR900": Matr900Service,
    }

    if tipo not in services:
        raise RuntimeError(f"Relatorio {carga.tipo_relatorio} nao suportado")

    service = services[tipo](*service_args)
    page = 1
    auth = (config.user, config.password) if config.user else None

    async with protheus_async_client(auth=auth) as client:
        while True:
            p = dict(params)
            p["page"] = page
            print(f"[PROTHEUS_CARGA] buscando pagina={page} relatorio={tipo} carga_id={carga.id}", flush=True)
            resultado = await service.buscar_como_registros_pagina(p, client=client)
            registros = resultado.get("registros", [])
            yield registros
            total_pages = int(resultado.get("total_pages") or resultado.get("totalPages") or 1)
            has_more = bool(resultado.get("hasMore", page < total_pages))
            if not has_more:
                break
            page += 1
