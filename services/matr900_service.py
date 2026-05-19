import httpx
import json as _json
import logging
from typing import Any
from fastapi import HTTPException

logger = logging.getLogger(__name__)

_PARAMS_MATR900 = [
    "data_ini", "data_fim", "page", "pageSize",
    "produto_de", "produto_ate",
    "tipo_de", "tipo_ate",
    "grupo_de", "grupo_ate",
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

    async def buscar_kardex(self, params: dict[str, Any]) -> dict[str, Any]:
        page_size = int(params.get("pageSize") or 500)
        query = {k: v for k, v in params.items() if k in _PARAMS_MATR900 and v is not None}
        query["pageSize"] = page_size
        query.setdefault("documento_por", "D")
        query.setdefault("moeda", "1")
        query.setdefault("ordem", "1")
        query.setdefault("lista_sem_movimento", "2")
        query.setdefault("lista_transferencia", "1")
        query.setdefault("considera_filiais", "2")
        query.setdefault("tipo_custo", "1")

        all_linhas: list[dict] = []
        parametros: dict[str, Any] = {}
        total_pages = 1
        current_page = 1

        headers = {"tenantId": self.tenant_id} if self.tenant_id else {}

        logger.info(
            "MATR900 iniciando busca | endpoint=%s tenant=%s | params=%s",
            self.endpoint, self.tenant_id,
            {k: v for k, v in query.items() if k not in ("page",)},
        )

        async with httpx.AsyncClient(verify=False, timeout=600.0, auth=self.auth) as client:
            while current_page <= total_pages:
                query["page"] = current_page
                url_completa = str(client.build_request("GET", self.endpoint, params=query).url)
                logger.info(
                    "MATR900 -> pagina %s/%s | URL: %s",
                    current_page, total_pages, url_completa,
                )
                resp = await client.get(self.endpoint, params=query, headers=headers)
                logger.info(
                    "MATR900 <- pagina %s | HTTP %s | bytes=%s",
                    current_page, resp.status_code, len(resp.content),
                )
                resp.raise_for_status()

                raw = resp.content
                if not raw:
                    logger.error("MATR900 resposta vazia na pagina %s", current_page)
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

                parametros = data.get("parametros", {})
                total_pages = int(data.get("total_pages", 1))
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
