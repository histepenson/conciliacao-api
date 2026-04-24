import httpx
import json as _json
import logging
from typing import Any
from fastapi import HTTPException

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

    def __init__(self, protheus_base_url: str, user: str = "", password: str = "", tenant_id: str = ""):
        self.endpoint = protheus_base_url.rstrip("/") + "/rest/zctbr400api/api/v1/ctbr400"
        self.auth = (user, password) if user else None
        self.tenant_id = tenant_id

    async def buscar_razao(self, params: dict[str, Any]) -> dict[str, Any]:
        page_size = int(params.get("pageSize") or 500)
        query = {k: v for k, v in params.items() if k in _PARAMS_CTBR400 and v is not None}
        query["pageSize"] = page_size
        query.setdefault("tipo_rel", "1")
        query.setdefault("moeda", "01")
        query.setdefault("saldo", "1")

        all_linhas: list[dict] = []
        parametros: dict[str, Any] = {}
        total_pages = 1
        current_page = 1

        headers = {"tenantId": self.tenant_id} if self.tenant_id else {}

        async with httpx.AsyncClient(verify=False, timeout=300.0, auth=self.auth) as client:
            while current_page <= total_pages:
                query["page"] = current_page
                logger.info(
                    "CTBR400 -> pagina %s/%s endpoint=%s tenant=%s",
                    current_page,
                    total_pages,
                    self.endpoint,
                    self.tenant_id,
                )
                resp = await client.get(self.endpoint, params=query, headers=headers)
                resp.raise_for_status()

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
                total_pages = int(data.get("total_pages", 1))
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
