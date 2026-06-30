import json as _json
import logging
from typing import Any
from fastapi import HTTPException

import httpx

from core.protheus_http import protheus_async_client, protheus_get

logger = logging.getLogger(__name__)

_PARAMS_MATR900 = [
    "data_ini", "data_fim", "page", "pageSize",
    "produto_de", "produto_ate",
    "tipo_de", "tipo_ate",
    "grupo_de", "grupo_ate",
    "conta_de", "conta_ate",
    "armazem", "documento_por", "moeda", "ordem",
    "lista_sem_movimento", "lista_transferencia", "considera_filiais",
    "tipo_custo",
]


class Matr900Service:
    """Proxy/adaptador para o ZMATR900API do Protheus."""

    def __init__(self, protheus_base_url: str, user: str = "", password: str = "", tenant_id: str = "", rest_prefix: str = "rest"):
        self.endpoint = protheus_base_url.rstrip("/") + f"/{rest_prefix.strip('/')}/zmatr900api/api/v1/matr900"
        self.auth = (user, password) if user else None
        self.tenant_id = tenant_id

    async def buscar_pagina(self, params: dict[str, Any], *, client: httpx.AsyncClient | None = None) -> dict[str, Any]:
        query = self._montar_query(params)
        query["page"] = int(query.get("page") or 1)
        headers = {"tenantId": self.tenant_id} if self.tenant_id else {}

        async def _do(c: httpx.AsyncClient) -> dict[str, Any]:
            resp = await protheus_get(c, self.endpoint, params=query, headers=headers, logger=logger, operation=f"MATR900 pagina {query['page']}")
            data = self._decode_response(resp.content)
            total_pages = int(data.get("total_pages") or data.get("totalPages") or query["page"] or 1)
            logger.info("MATR900 -> pagina %s/%s  pageSize=%s  endpoint=%s  tenant=%s", query["page"], total_pages, query["pageSize"], self.endpoint, self.tenant_id)
            return data

        if client is not None:
            return await _do(client)
        async with protheus_async_client(auth=self.auth) as c:
            return await _do(c)

    async def buscar_kardex(self, params: dict[str, Any]) -> dict[str, Any]:
        query = self._montar_query(params)

        all_linhas: list[dict] = []
        parametros: dict[str, Any] = {}
        total_pages = 1
        current_page = 1
        has_more = True

        headers = {"tenantId": self.tenant_id} if self.tenant_id else {}

        logger.info(
            "MATR900 iniciando busca | endpoint=%s tenant=%s | params=%s",
            self.endpoint, self.tenant_id,
            {k: v for k, v in query.items() if k not in ("page",)},
        )

        async with protheus_async_client(auth=self.auth) as client:
            while has_more:
                query["page"] = current_page
                logger.info(
                    "MATR900 -> pagina %s/%s  pageSize=%s  endpoint=%s  tenant=%s",
                    current_page, total_pages, query["pageSize"], self.endpoint, self.tenant_id,
                )
                resp = await protheus_get(
                    client,
                    self.endpoint,
                    params=query,
                    headers=headers,
                    logger=logger,
                    operation=f"MATR900 pagina {current_page}",
                )
                logger.info(
                    "MATR900 <- pagina %s | HTTP %s | bytes=%s",
                    current_page, resp.status_code, len(resp.content),
                )

                data = self._decode_response(resp.content)

                parametros = data.get("parametros", {})
                total_pages = int(data.get("total_pages") or total_pages or 1)
                has_more = bool(data.get("hasMore", current_page < total_pages))
                linhas_pagina = data.get("linhas", [])
                all_linhas.extend(linhas_pagina)
                logger.info(
                    "MATR900 pagina %s/%s | registros nesta pagina=%s | total acumulado=%s",
                    current_page, total_pages, len(linhas_pagina), len(all_linhas),
                )
                current_page += 1

        logger.info("MATR900 concluido | total_registros=%s", len(all_linhas))
        return {
            "parametros": parametros,
            "total_registros": len(all_linhas),
            "linhas": all_linhas,
        }

    async def buscar_como_registros(self, params: dict[str, Any]) -> list[dict]:
        resultado = await self.buscar_kardex(params)
        return resultado["linhas"]

    async def buscar_como_registros_pagina(self, params: dict[str, Any], *, client: httpx.AsyncClient | None = None) -> dict[str, Any]:
        resultado = await self.buscar_pagina(params, client=client)
        linhas = resultado.get("linhas", [])
        return {**resultado, "registros": linhas, "total": len(linhas)}

    def _montar_query(self, params: dict[str, Any]) -> dict[str, Any]:
        page_size = int(params.get("pageSize") or 5000)
        query = {k: v for k, v in params.items() if k in _PARAMS_MATR900 and v is not None}
        query["pageSize"] = page_size
        query.setdefault("documento_por", "D")
        query.setdefault("moeda", "1")
        query.setdefault("ordem", "1")
        query.setdefault("lista_sem_movimento", "2")
        query.setdefault("lista_transferencia", "1")
        query.setdefault("considera_filiais", "2")
        query.setdefault("tipo_custo", "1")
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
            logger.error("MATR900 erro do Protheus: [%s] %s", status, mensagem)
            raise HTTPException(status_code=status, detail=mensagem)

        return data
