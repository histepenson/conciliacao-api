import json as _json
import logging
from typing import Any
from fastapi import HTTPException

from core.protheus_http import protheus_async_client, protheus_get

logger = logging.getLogger(__name__)

_PARAMS_CTBR400 = [
    "data_ini", "data_fim", "page", "pageSize",
    "conta_de", "conta_ate",
    "custo_de", "custo_ate",
    "item_de", "item_ate",
    "clvl_de", "clvl_ate",
    "moeda", "saldo", "set_of_books",
    "imprime_custo", "imprime_item", "imprime_clvl",
    "tipo_rel", "salta_linha", "moeda_desc",
    "consid_filiais", "filial_de", "filial_ate",
]


class Ctbr400Service:
    """Proxy/adaptador para o ZCTBR400API do Protheus."""

    def __init__(self, protheus_base_url: str, user: str = "", password: str = "", tenant_id: str = "", rest_prefix: str = "rest"):
        self.endpoint = protheus_base_url.rstrip("/") + f"/{rest_prefix.strip('/')}/zctbr400api/api/v1/ctbr400"
        self.auth = (user, password) if user else None
        self.tenant_id = tenant_id

    async def buscar_pagina(self, params: dict[str, Any]) -> dict[str, Any]:
        query = self._montar_query(params)
        query["page"] = int(query.get("page") or 1)
        headers = {"tenantId": self.tenant_id} if self.tenant_id else {}

        async with protheus_async_client(auth=self.auth) as client:
            resp = await protheus_get(
                client,
                self.endpoint,
                params=query,
                headers=headers,
                logger=logger,
                operation=f"CTBR400 pagina {query['page']}",
            )
            return self._decode_response(resp.content)

    async def buscar_razao(self, params: dict[str, Any]) -> dict[str, Any]:
        query = self._montar_query(params)

        all_linhas: list[dict] = []
        parametros: dict[str, Any] = {}
        total_pages = 1
        current_page = 1
        has_more = True

        headers = {"tenantId": self.tenant_id} if self.tenant_id else {}

        async with protheus_async_client(auth=self.auth) as client:
            while has_more:
                query["page"] = current_page
                logger.info(
                    "CTBR400 -> pagina %s/%s endpoint=%s tenant=%s",
                    current_page,
                    total_pages,
                    self.endpoint,
                    self.tenant_id,
                )
                resp = await protheus_get(
                    client,
                    self.endpoint,
                    params=query,
                    headers=headers,
                    logger=logger,
                    operation=f"CTBR400 pagina {current_page}",
                )

                data = self._decode_response(resp.content)

                parametros = data.get("parametros", {})
                total_pages = int(data.get("total_pages") or total_pages or 1)
                has_more = bool(data.get("hasMore", current_page < total_pages))
                all_linhas.extend(data.get("linhas", []))
                current_page += 1

        return {
            "parametros": parametros,
            "total_registros": len(all_linhas),
            "linhas": all_linhas,
        }

    async def buscar_como_registros(self, params: dict[str, Any]) -> list[dict]:
        resultado = await self.buscar_razao(params)
        return resultado["linhas"]

    async def buscar_como_registros_pagina(self, params: dict[str, Any]) -> dict[str, Any]:
        resultado = await self.buscar_pagina(params)
        linhas = resultado.get("linhas", [])
        return {**resultado, "registros": linhas, "total": len(linhas)}

    def _montar_query(self, params: dict[str, Any]) -> dict[str, Any]:
        page_size = int(params.get("pageSize") or 500)
        query = {k: v for k, v in params.items() if k in _PARAMS_CTBR400 and v is not None}
        query["pageSize"] = page_size
        query.setdefault("tipo_rel", "1")
        query.setdefault("moeda", "01")
        query.setdefault("saldo", "1")
        return query

    def _decode_response(self, raw: bytes) -> dict[str, Any]:
        if not raw:
            raise HTTPException(status_code=502, detail="Protheus retornou resposta vazia")

        try:
            data = _json.loads(raw.decode("utf-8"))
        except UnicodeDecodeError:
            data = _json.loads(raw.decode("windows-1252"))

        if data.get("erro"):
            status = int(data.get("status", 400))
            mensagem = data.get("mensagem", "Erro ao consultar Protheus")
            raise HTTPException(status_code=status, detail=mensagem)

        return data
