import asyncio
import logging
from typing import Any, AsyncGenerator

from sqlalchemy.dialects.postgresql import insert as pg_insert

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
from services.sft_ent_service import SftEntService
from services.ct2raz_ct5_service import Ct2RazCt5Service
from services.protheus_carga_service import marcar_concluido, marcar_erro, marcar_processando
from services.lancamento_padrao_service import upsert_de_carga as lp_upsert_de_carga

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

_PAGE_SIZE = 5000
_PAGE_SIZE_POR_TIPO: dict[str, int] = {
    "CTBR140": 3000,
}
_INSERT_CHUNK_SIZE = 1000


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
        tipo_upper = (carga.tipo_relatorio or "").upper()
        params.setdefault("pageSize", _PAGE_SIZE_POR_TIPO.get(tipo_upper, _PAGE_SIZE))

        db.query(ProtheusCargaRegistro).filter(ProtheusCargaRegistro.carga_id == carga.id).delete()
        db.commit()

        total = 0
        sequencia = 1

        async for registros_pagina in _iterar_paginas(carga, config, params):
            if not registros_pagina:
                continue

            rows = [
                {"carga_id": carga.id, "sequencia": sequencia + i, "dados_json": r}
                for i, r in enumerate(registros_pagina)
            ]
            sequencia += len(registros_pagina)
            total += len(registros_pagina)

            for start in range(0, len(rows), _INSERT_CHUNK_SIZE):
                db.execute(pg_insert(ProtheusCargaRegistro), rows[start:start + _INSERT_CHUNK_SIZE])

            carga.total_registros = total
            db.commit()
            logger.info("Carga Protheus %s: %s registros gravados", carga.id, total)
            print(f"[PROTHEUS_CARGA] gravados {total} registros carga_id={carga.id}", flush=True)

            db.refresh(carga)
            if carga.status == "cancelado":
                logger.info("Carga Protheus %s cancelada durante processamento", carga.id)
                print(f"[PROTHEUS_CARGA] cancelada carga_id={carga.id}", flush=True)
                db.query(ProtheusCargaRegistro).filter(ProtheusCargaRegistro.carga_id == carga.id).delete()
                carga.total_registros = 0
                db.commit()
                return

        marcar_concluido(db, carga, total)
        logger.info("Carga Protheus %s concluida com %s registros", carga.id, total)
        print(f"[PROTHEUS_CARGA] concluida carga_id={carga.id} total={total}", flush=True)

        if tipo_upper == "CT2RAZCT5":
            try:
                registros_all = (
                    db.query(ProtheusCargaRegistro)
                    .filter_by(carga_id=carga.id)
                    .all()
                )
                lp_upsert_de_carga(db, carga.empresa_id, [r.dados_json for r in registros_all])
                print(f"[PROTHEUS_CARGA] lancamentos_padrao atualizados empresa={carga.empresa_id}", flush=True)
            except Exception as exc_lp:
                logger.warning("Falha ao popular lancamentos_padrao carga=%s: %s", carga.id, exc_lp)

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
        "SFTENT":    SftEntService,
        "CT2RAZCT5": Ct2RazCt5Service,
    }

    if tipo not in services:
        raise RuntimeError(f"Relatorio {carga.tipo_relatorio} nao suportado")

    service = services[tipo](*service_args)
    page = 1

    while True:
        p = dict(params)
        p["page"] = page
        print(f"[PROTHEUS_CARGA] buscando pagina={page} relatorio={tipo} carga_id={carga.id}", flush=True)
        if tipo == "FINR130":
            resultado = await service.buscar_pagina(p)
            registros = resultado.get("titulos", [])
        else:
            resultado = await service.buscar_como_registros_pagina(p)
            registros = resultado.get("registros", [])

        yield registros
        total_pages = int(resultado.get("total_pages") or resultado.get("totalPages") or 1)
        has_more = bool(resultado.get("hasMore", page < total_pages))
        if not has_more:
            break
        page += 1
