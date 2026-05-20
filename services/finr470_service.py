import json as _json
import logging
from typing import Any
from fastapi import HTTPException

from core.protheus_http import protheus_async_client, protheus_get

logger = logging.getLogger(__name__)

_PARAMS_FINR470 = [
    "banco", "agencia", "conta",
    "data_ini", "data_fim",
    "moeda", "situacao", "linhas_pagina",
    "taxa_moeda", "saldo_compart", "todas_filiais", "data_conv_saldo",
    "page", "pageSize",
]


class FinR470Service:
    """Proxy/adaptador para o ZFIN470API do Protheus."""

    def __init__(self, protheus_base_url: str, user: str = "", password: str = "", tenant_id: str = "", rest_prefix: str = "rest"):
        self.endpoint = protheus_base_url.rstrip("/") + f"/{rest_prefix.strip('/')}/zfin470api/api/v1/finr470"
        self.auth = (user, password) if user else None
        self.tenant_id = tenant_id

    async def buscar_extrato(self, params: dict[str, Any]) -> dict[str, Any]:
        page_size = int(params.get("pageSize") or 500)
        query = {k: v for k, v in params.items() if k in _PARAMS_FINR470 and v is not None}
        query["pageSize"] = page_size
        query.setdefault("moeda", 1)

        all_registros: list[dict] = []
        parametros: dict = {}
        banco: dict = {}
        totais: dict = {}
        current_page = 1
        total_pages = 1

        headers = {"tenantId": self.tenant_id} if self.tenant_id else {}

        async with protheus_async_client(auth=self.auth) as client:
            while current_page <= total_pages:
                query["page"] = current_page
                logger.info(
                    "FINR470 -> pagina %s/%s  pageSize=%s  endpoint=%s  tenant=%s",
                    current_page, total_pages, query["pageSize"], self.endpoint, self.tenant_id,
                )
                resp = await protheus_get(
                    client,
                    self.endpoint,
                    params=query,
                    headers=headers,
                    logger=logger,
                    operation=f"FINR470 pagina {current_page}",
                )

                raw = resp.content
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

                parametros = data.get("parametros", {})
                banco = data.get("banco", {})
                totais = data.get("totais", {})
                total_pages = int(data.get("total_pages", 1))
                all_registros.extend(data.get("registros", data.get("movimentos", [])))
                current_page += 1

        return {
            "parametros": parametros,
            "banco": banco,
            "totais": totais,
            "total_registros": len(all_registros),
            "registros": all_registros,
        }

    async def buscar_pagina(self, params: dict[str, Any]) -> dict[str, Any]:
        page = int(params.get("page") or 1)
        page_size = int(params.get("pageSize") or 2000)
        query = {k: v for k, v in params.items() if k in _PARAMS_FINR470 and v is not None}
        query["page"] = page
        query["pageSize"] = page_size
        query.setdefault("moeda", 1)

        headers = {"tenantId": self.tenant_id} if self.tenant_id else {}

        async with protheus_async_client(auth=self.auth) as client:
            resp = await protheus_get(
                client,
                self.endpoint,
                params=query,
                headers=headers,
                logger=logger,
                operation=f"FINR470 pagina {page}",
            )

        raw = resp.content
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

        total_pages = int(data.get("total_pages", page))
        registros = data.get("registros", data.get("movimentos", []))
        logger.info(
            "FINR470 -> pagina %s/%s  pageSize=%s  endpoint=%s  tenant=%s",
            page, total_pages, page_size, self.endpoint, self.tenant_id,
        )
        return {
            "parametros": data.get("parametros", {}),
            "banco": data.get("banco", {}),
            "totais": data.get("totais", {}),
            "total_registros": int(data.get("total_registros", len(registros))),
            "total_pages": total_pages,
            "page": page,
            "pageSize": page_size,
            "hasMore": bool(data.get("hasMore", page < total_pages)),
            "registros": registros,
        }

    async def buscar_como_registros(self, params: dict[str, Any]) -> list[dict]:
        """
        Retorna o extrato no formato esperado por `base_extrato.registros`.

        Cada registro preserva os nomes de colunas usados pelo normalizador do
        backend: `data`, `documento`, `prefixo_titulo`, `entradas`, `saidas`,
        `saldo_atual`, `descricao`.
        """
        resultado = await self.buscar_extrato(params)
        return resultado["registros"]

    async def buscar_como_registros_pagina(self, params: dict[str, Any]) -> dict[str, Any]:
        resultado = await self.buscar_pagina(params)
        registros = resultado["registros"]
        return {
            "registros": registros,
            "total": resultado.get("total_registros", len(registros)),
            "total_pages": resultado.get("total_pages", 1),
            "page": resultado.get("page", 1),
            "pageSize": resultado.get("pageSize", len(registros)),
            "hasMore": resultado.get("hasMore", False),
        }
