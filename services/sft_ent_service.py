import json as _json
import logging
from typing import Any

import httpx

from core.protheus_http import protheus_async_client, protheus_get

logger = logging.getLogger(__name__)

_PARAMS_SFT = [
    "data_ini", "data_fim",
    "filial_de", "filial_ate",
    "cfop_inc", "cfop_exc",
    "tes_inc", "tes_exc",
    "page", "pageSize",
]


class SftEntService:
    """Proxy para ZSFTENTAPI — Livro Fiscal SFT via SQL direto."""

    def __init__(self, protheus_base_url: str, user: str = "", password: str = "", tenant_id: str = "", rest_prefix: str = "rest"):
        self.endpoint = protheus_base_url.rstrip("/") + f"/{rest_prefix.strip('/')}/zsftentapi/api/v1/sftent"
        self.auth = (user, password) if user else None
        self.tenant_id = tenant_id

    async def buscar_pagina(self, params: dict[str, Any], *, client: httpx.AsyncClient | None = None) -> dict[str, Any]:
        query = self._montar_query(params)
        query["page"] = int(query.get("page") or 1)
        headers = {"tenantId": self.tenant_id} if self.tenant_id else {}

        async def _do(c: httpx.AsyncClient) -> dict[str, Any]:
            resp = await protheus_get(c, self.endpoint, params=query, headers=headers, logger=logger, operation=f"SFTENT pagina {query['page']}")
            data = _decode_response(resp.content)
            total_pages = int(data.get("total_pages") or data.get("totalPages") or query["page"] or 1)
            logger.info("SFTENT -> pagina %s/%s  pageSize=%s  endpoint=%s", query["page"], total_pages, query["pageSize"], self.endpoint)
            return data

        if client is not None:
            return await _do(client)
        async with protheus_async_client(auth=self.auth) as c:
            return await _do(c)

    async def buscar_como_registros_pagina(self, params: dict[str, Any], *, client: httpx.AsyncClient | None = None) -> dict[str, Any]:
        """Compatível com o padrão do protheus_carga_worker (espera 'registros' na resposta)."""
        resultado = await self.buscar_pagina(params, client=client)
        linhas = resultado.get("linhas", [])
        total_pages = int(resultado.get("total_pages") or resultado.get("totalPages") or 1)
        current_page = int(params.get("page") or 1)
        return {
            **resultado,
            "registros": linhas,
            "total_pages": total_pages,
            "hasMore": bool(resultado.get("hasMore", current_page < total_pages)),
            "total": len(linhas),
        }

    async def buscar_entradas(self, params: dict[str, Any]) -> list[dict]:
        """Busca todas as páginas e retorna lista plana de registros SFT."""
        query = self._montar_query(params)
        all_linhas: list[dict] = []
        current_page = 1
        total_pages = 1
        has_more = True
        headers = {"tenantId": self.tenant_id} if self.tenant_id else {}

        async with protheus_async_client(auth=self.auth) as client:
            while has_more:
                query["page"] = current_page
                resp = await protheus_get(client, self.endpoint, params=query, headers=headers, logger=logger, operation=f"SFTENT pagina {current_page}")
                data = _decode_response(resp.content)
                total_pages = int(data.get("total_pages") or total_pages or 1)
                has_more = bool(data.get("hasMore", current_page < total_pages))
                all_linhas.extend(data.get("linhas", []))
                current_page += 1

        return all_linhas

    def _montar_query(self, params: dict[str, Any]) -> dict[str, Any]:
        page_size = int(params.get("pageSize") or 5000)
        query = {k: v for k, v in params.items() if k in _PARAMS_SFT and v is not None}
        query["pageSize"] = page_size
        filial_de  = str(query.get("filial_de")  or "").strip()
        filial_ate = str(query.get("filial_ate") or "").strip()
        # Normaliza valores "todo-z" digitados pelo usuário (ex: zzzzz, zzzz) para vazio
        # → ADVPL aplica o default correto "zzzzzzzzz" internamente
        if filial_ate and all(c.lower() == 'z' for c in filial_ate):
            filial_ate = ""
        query["filial_de"]  = filial_de
        query["filial_ate"] = filial_ate or "zzzzzzzzz"
        return query


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
