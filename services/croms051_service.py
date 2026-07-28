import json as _json
import logging
from typing import Any
from fastapi import HTTPException

import httpx

from core.protheus_http import protheus_async_client, protheus_get
from services.estrategias.rancheiro.croms051_tratativas import aplicar_tratativas_croms051

logger = logging.getLogger(__name__)

_PARAMS_CROMS051 = [
    "cliente", "considera_data", "data_de", "data_ate",
    "modalidade_nova", "vendedor", "filiais",
    "page", "pageSize",
]


class Croms051Service:
    """Proxy/adaptador para o ZCROMS051API do Protheus (Conta Corrente Desconto)."""

    def __init__(self, protheus_base_url: str, user: str = "", password: str = "", tenant_id: str = "", rest_prefix: str = "rest"):
        self.endpoint = protheus_base_url.rstrip("/") + f"/{rest_prefix.strip('/')}/zcroms051api/api/v1/croms051"
        self.auth = (user, password) if user else None
        self.tenant_id = tenant_id

    async def buscar_extrato(self, params: dict[str, Any]) -> dict[str, Any]:
        page_size = int(params.get("pageSize") or 5000)
        query = {k: v for k, v in params.items() if k in _PARAMS_CROMS051 and v is not None}
        query["pageSize"] = page_size

        all_registros: list[dict] = []
        parametros: dict = {}
        current_page = 1
        total_pages = 1

        headers = {"tenantId": self.tenant_id} if self.tenant_id else {}

        async with protheus_async_client(auth=self.auth) as client:
            while current_page <= total_pages:
                query["page"] = current_page
                logger.info(
                    "CROMS051 -> pagina %s/%s  pageSize=%s  endpoint=%s  tenant=%s",
                    current_page, total_pages, query["pageSize"], self.endpoint, self.tenant_id,
                )
                resp = await protheus_get(
                    client,
                    self.endpoint,
                    params=query,
                    headers=headers,
                    logger=logger,
                    operation=f"CROMS051 pagina {current_page}",
                )

                raw = resp.content
                if not raw:
                    raise HTTPException(status_code=502, detail="Protheus retornou resposta vazia")

                try:
                    data = _json.loads(raw.decode("utf-8"))
                except UnicodeDecodeError:
                    data = _json.loads(raw.decode("windows-1252"))

                if data.get("error"):
                    raise HTTPException(status_code=422, detail=data.get("message", "Erro ao consultar Protheus"))

                parametros = data.get("parametros", {})
                total_pages = int(data.get("total_pages", 1))
                all_registros.extend(data.get("linhas", []))
                current_page += 1

        all_registros = aplicar_tratativas_croms051(all_registros)

        return {
            "parametros": parametros,
            "total_registros": len(all_registros),
            "registros": all_registros,
        }

    async def buscar_pagina(self, params: dict[str, Any], *, client: httpx.AsyncClient | None = None) -> dict[str, Any]:
        page = int(params.get("page") or 1)
        page_size = int(params.get("pageSize") or 5000)
        query = {k: v for k, v in params.items() if k in _PARAMS_CROMS051 and v is not None}
        query["page"] = page
        query["pageSize"] = page_size

        headers = {"tenantId": self.tenant_id} if self.tenant_id else {}

        async def _do(c: httpx.AsyncClient) -> httpx.Response:
            return await protheus_get(c, self.endpoint, params=query, headers=headers, logger=logger, operation=f"CROMS051 pagina {page}")

        if client is not None:
            resp = await _do(client)
        else:
            async with protheus_async_client(auth=self.auth) as c:
                resp = await _do(c)

        raw = resp.content
        if not raw:
            raise HTTPException(status_code=502, detail="Protheus retornou resposta vazia")

        try:
            data = _json.loads(raw.decode("utf-8"))
        except UnicodeDecodeError:
            data = _json.loads(raw.decode("windows-1252"))

        if data.get("error"):
            raise HTTPException(status_code=422, detail=data.get("message", "Erro ao consultar Protheus"))

        total_pages = int(data.get("total_pages", page))
        registros = aplicar_tratativas_croms051(data.get("linhas", []))
        logger.info(
            "CROMS051 -> pagina %s/%s  pageSize=%s  endpoint=%s  tenant=%s",
            page, total_pages, page_size, self.endpoint, self.tenant_id,
        )
        return {
            "parametros": data.get("parametros", {}),
            "total_registros": int(data.get("total_registros", len(registros))),
            "total_pages": total_pages,
            "page": page,
            "pageSize": page_size,
            "hasMore": bool(data.get("hasMore", page < total_pages)),
            "registros": registros,
        }

    async def buscar_como_registros(self, params: dict[str, Any]) -> list[dict]:
        resultado = await self.buscar_extrato(params)
        return resultado["registros"]

    async def buscar_como_registros_pagina(self, params: dict[str, Any], *, client: httpx.AsyncClient | None = None) -> dict[str, Any]:
        resultado = await self.buscar_pagina(params, client=client)
        registros = resultado["registros"]
        return {
            "registros": registros,
            "total": resultado.get("total_registros", len(registros)),
            "total_pages": resultado.get("total_pages", 1),
            "page": resultado.get("page", 1),
            "pageSize": resultado.get("pageSize", len(registros)),
            "hasMore": resultado.get("hasMore", False),
        }
