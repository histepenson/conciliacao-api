import json as _json
import logging
from typing import Any

import httpx

from core.protheus_http import protheus_async_client, protheus_get

logger = logging.getLogger(__name__)

_PARAMS_CT2RAZ = [
    "data_ini", "data_fim", "page", "pageSize",
    "conta_de", "conta_ate",
    "item_de", "item_ate",
    "clvl_de", "clvl_ate",
    "custo_de", "custo_ate",
    "moeda", "saldo",
    "vlr_zerado",
    "consid_filiais", "filial_de", "filial_ate",
]


class Ct2RazService:
    """
    Proxy para ZCT2RAZAPI — razao contabil via SQL direto em CT2.

    Substitui Ctbr400Service e Ctbr480Service eliminando CTBGerRaz().
    Interface compativel: retorna linhas com os mesmos campos esperados
    pelo backend (data, lote_sub_doc_linha, historico, xpartida,
    item_conta, cod_cl_val, debito, credito, conta).
    """

    def __init__(
        self,
        protheus_base_url: str,
        user: str = "",
        password: str = "",
        tenant_id: str = "",
        rest_prefix: str = "rest",
    ):
        self.endpoint = (
            protheus_base_url.rstrip("/")
            + f"/{rest_prefix.strip('/')}/zct2razapi/api/v1/ct2raz"
        )
        self.auth = (user, password) if user else None
        self.tenant_id = tenant_id

    async def buscar_pagina(
        self,
        params: dict[str, Any],
        *,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        query = self._montar_query(params)
        query["page"] = int(query.get("page") or 1)
        headers = {"tenantId": self.tenant_id} if self.tenant_id else {}

        async def _do(c: httpx.AsyncClient) -> dict[str, Any]:
            resp = await protheus_get(
                c,
                self.endpoint,
                params=query,
                headers=headers,
                logger=logger,
                operation=f"CT2RAZ pagina {query['page']}",
            )
            data = _decode_response(resp.content)
            total_pages = int(
                data.get("total_pages") or data.get("totalPages") or query["page"] or 1
            )
            logger.info(
                "CT2RAZ -> pagina %s/%s  pageSize=%s  conta_de=%s  conta_ate=%s",
                query["page"],
                total_pages,
                query["pageSize"],
                query.get("conta_de", ""),
                query.get("conta_ate", ""),
            )
            return data

        if client is not None:
            return await _do(client)
        async with protheus_async_client(auth=self.auth) as c:
            return await _do(c)

    async def buscar_como_registros_pagina(
        self,
        params: dict[str, Any],
        *,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        resultado = await self.buscar_pagina(params, client=client)
        linhas = resultado.get("linhas", [])
        return {**resultado, "registros": linhas, "total": len(linhas)}

    def _montar_query(self, params: dict[str, Any]) -> dict[str, Any]:
        page_size = int(params.get("pageSize") or 5000)
        query = {k: v for k, v in params.items() if k in _PARAMS_CT2RAZ and v is not None}
        query["pageSize"] = page_size
        query.setdefault("moeda", "01")
        return query


def _decode_response(raw: bytes) -> dict[str, Any]:
    if not raw:
        from fastapi import HTTPException
        raise HTTPException(status_code=502, detail="Protheus retornou resposta vazia")
    try:
        return _json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError:
        return _json.loads(raw.decode("windows-1252"))
