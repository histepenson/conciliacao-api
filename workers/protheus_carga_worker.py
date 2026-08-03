import asyncio
import logging
from typing import Any, AsyncGenerator, Optional

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
from services.sn3_service import Sn3Service
from services.sn4_service import Sn4Service
from services.croms051_service import Croms051Service
from services.protheus_carga_service import marcar_concluido, marcar_erro, marcar_processando
from services.lancamento_padrao_service import upsert_de_carga as lp_upsert_de_carga

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

_PAGE_SIZE = 5000
_PAGE_SIZE_POR_TIPO: dict[str, int] = {
    "CTBR140": 3000,
    "CT2RAZCT5": 8000,
}
_INSERT_CHUNK_SIZE = 1000
_MAX_PARALLEL_PAGES = 5  # paginas simultâneas por carga


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

        todos_registros = await _buscar_todas_paginas(carga, config, params)

        # Verificar cancelamento antes de gravar
        db.refresh(carga)
        if carga.status == "cancelado":
            logger.info("Carga Protheus %s cancelada antes de gravar", carga.id)
            print(f"[PROTHEUS_CARGA] cancelada carga_id={carga.id}", flush=True)
            return

        total = len(todos_registros)
        rows = [
            {"carga_id": carga.id, "sequencia": i + 1, "dados_json": r}
            for i, r in enumerate(todos_registros)
        ]
        for start in range(0, len(rows), _INSERT_CHUNK_SIZE):
            db.execute(pg_insert(ProtheusCargaRegistro), rows[start:start + _INSERT_CHUNK_SIZE])

        carga.total_registros = total
        db.commit()
        logger.info("Carga Protheus %s: %s registros gravados", carga.id, total)
        print(f"[PROTHEUS_CARGA] gravados {total} registros carga_id={carga.id}", flush=True)

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


async def _buscar_todas_paginas(
    carga: ProtheusCarga,
    config: Any,
    params: dict[str, Any],
) -> list[dict]:
    """Busca todas as páginas do Protheus em paralelo (até _MAX_PARALLEL_PAGES simultâneas)."""
    tipo = carga.tipo_relatorio.upper()
    service_args = (config.url, config.user, config.password, config.tenant, config.rest_prefix)

    services = {
        "FINR130": FinR130Service, "FINR150": FinR150Service,
        "CTBR140": Ctbr140Service, "CTBR400": Ctbr400Service,
        "CTBR480": Ctbr480Service, "FINR470": FinR470Service,
        "MATR900": Matr900Service, "SFTENT": SftEntService,
        "CT2RAZCT5": Ct2RazCt5Service,
        "SN3": Sn3Service, "SN4": Sn4Service,
        "CROMS051": Croms051Service,
    }
    if tipo not in services:
        raise RuntimeError(f"Relatorio {carga.tipo_relatorio} nao suportado")

    def make_service():
        return services[tipo](*service_args)

    async def _buscar_pagina(page: int) -> list[dict]:
        p = dict(params)
        p["page"] = page
        print(f"[PROTHEUS_CARGA] buscando pagina={page} relatorio={tipo} carga_id={carga.id}", flush=True)
        svc = make_service()
        if tipo == "FINR130":
            resultado = await svc.buscar_pagina(p)
            return resultado.get("titulos", []), resultado
        else:
            resultado = await svc.buscar_como_registros_pagina(p)
            return resultado.get("registros", []), resultado

    # Busca página 1 para descobrir total_pages
    registros_p1, resultado_p1 = await _buscar_pagina(1)
    total_pages = int(resultado_p1.get("total_pages") or resultado_p1.get("totalPages") or 1)
    has_more = bool(resultado_p1.get("hasMore", 1 < total_pages))

    todos = list(registros_p1)

    if not has_more or total_pages <= 1:
        return todos

    # Busca páginas restantes em lotes paralelos
    semaphore = asyncio.Semaphore(_MAX_PARALLEL_PAGES)
    pages_restantes = list(range(2, total_pages + 1))

    async def _buscar_com_semaphore(page: int) -> tuple[int, list[dict]]:
        async with semaphore:
            regs, _ = await _buscar_pagina(page)
            return page, regs

    resultados = await asyncio.gather(*[_buscar_com_semaphore(p) for p in pages_restantes])

    # Ordenar por página para manter sequência correta
    for _, regs in sorted(resultados, key=lambda x: x[0]):
        todos.extend(regs)

    return todos


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
        "SN3":       Sn3Service,
        "SN4":       Sn4Service,
        "CROMS051":  Croms051Service,
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
