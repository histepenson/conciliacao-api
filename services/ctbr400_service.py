import json as _json
import logging
from typing import Any

import httpx

from core.protheus_http import protheus_async_client, protheus_get

logger = logging.getLogger(__name__)

_PARAMS_CTBR400 = [
    "data_ini", "data_fim", "page", "pageSize",
    "conta_de", "conta_ate",
    "item_de", "item_ate",
    "clvl_de", "clvl_ate",
    "custo_de", "custo_ate",
    "moeda", "saldo",
    "vlr_zerado",
    "consid_filiais", "filial_de", "filial_ate",
]


class Ctbr400Service:
    """Proxy para ZCT2RAZAPI — razao contabil via SQL direto em CT2."""

    def __init__(self, protheus_base_url: str, user: str = "", password: str = "", tenant_id: str = "", rest_prefix: str = "rest"):
        self.endpoint = protheus_base_url.rstrip("/") + f"/{rest_prefix.strip('/')}/zct2razapi/api/v1/ct2raz"
        self.auth = (user, password) if user else None
        self.tenant_id = tenant_id

    async def buscar_pagina(self, params: dict[str, Any], *, client: httpx.AsyncClient | None = None) -> dict[str, Any]:
        query = self._montar_query(params)
        query["page"] = int(query.get("page") or 1)
        headers = {"tenantId": self.tenant_id} if self.tenant_id else {}

        async def _do(c: httpx.AsyncClient) -> dict[str, Any]:
            resp = await protheus_get(c, self.endpoint, params=query, headers=headers, logger=logger, operation=f"CTBR400(CT2) pagina {query['page']}")
            data = _decode_response(resp.content)
            total_pages = int(data.get("total_pages") or data.get("totalPages") or query["page"] or 1)
            logger.info("CTBR400(CT2) -> pagina %s/%s  pageSize=%s  endpoint=%s", query["page"], total_pages, query["pageSize"], self.endpoint)
            return data

        if client is not None:
            return await _do(client)
        async with protheus_async_client(auth=self.auth) as c:
            return await _do(c)

    async def buscar_razao(self, params: dict[str, Any]) -> dict[str, Any]:
        query = self._montar_query(params)
        all_linhas: list[dict] = []
        current_page = 1
        total_pages = 1
        has_more = True
        headers = {"tenantId": self.tenant_id} if self.tenant_id else {}

        async with protheus_async_client(auth=self.auth) as client:
            while has_more:
                query["page"] = current_page
                resp = await protheus_get(client, self.endpoint, params=query, headers=headers, logger=logger, operation=f"CTBR400(CT2) pagina {current_page}")
                data = _decode_response(resp.content)
                total_pages = int(data.get("total_pages") or total_pages or 1)
                has_more = bool(data.get("hasMore", current_page < total_pages))
                all_linhas.extend(data.get("linhas", []))
                current_page += 1

        return {"total_registros": len(all_linhas), "linhas": all_linhas}

    async def buscar_como_registros(self, params: dict[str, Any]) -> list[dict]:
        resultado = await self.buscar_razao(params)
        return resultado["linhas"]

    async def buscar_como_registros_pagina(self, params: dict[str, Any], *, client: httpx.AsyncClient | None = None) -> dict[str, Any]:
        resultado = await self.buscar_pagina(params, client=client)
        linhas = resultado.get("linhas", [])
        return {**resultado, "registros": linhas, "total": len(linhas)}

    def _montar_query(self, params: dict[str, Any]) -> dict[str, Any]:
        page_size = int(params.get("pageSize") or 5000)
        query = {k: v for k, v in params.items() if k in _PARAMS_CTBR400 and v is not None}
        query["pageSize"] = page_size
        query.setdefault("moeda", "01")
        return query

    def _decode_response(self, raw: bytes) -> dict[str, Any]:
        return _decode_response(raw)


def _decode_response(raw: bytes) -> dict[str, Any]:
    if not raw:
        from fastapi import HTTPException
        raise HTTPException(status_code=502, detail="Protheus retornou resposta vazia")
    try:
        data = _json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError:
        data = _json.loads(raw.decode("windows-1252"))

    if data.get("erro"):
        from fastapi import HTTPException
        status = int(data.get("status", 400))
        mensagem = data.get("mensagem", "Erro ao consultar Protheus")
        raise HTTPException(status_code=status, detail=mensagem)

    return data
