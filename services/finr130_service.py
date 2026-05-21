import json as _json
import logging
from typing import Any

from core.protheus_http import protheus_async_client, protheus_get

logger = logging.getLogger(__name__)

_PARAMS_FINR130 = [
    "data_base", "page", "pageSize",
    "cliente_de", "cliente_ate", "prefixo_de", "prefixo_ate",
    "num_de", "num_ate", "banco_de", "banco_ate",
    "vencto_de", "vencto_ate", "natureza_de", "natureza_ate",
    "emissao_de", "emissao_ate", "moeda", "provisorios",
    "reajuste_vencto", "tit_descontados", "saldo_retroativo",
    "consid_filiais", "filial_de", "filial_ate",
    "loja_de", "loja_ate", "adiantamentos",
    "dtcontab_de", "dtcontab_ate", "outras_moedas",
    "tipos_incluir", "tipos_excluir", "abatimentos",
    "fluxo_caixa", "comp_saldo_por", "emissao_futura",
    "taxa_moeda", "considera_data",
]


class FinR130Service:
    """Proxy/adaptador para o ZFINR130API do Protheus."""

    def __init__(self, protheus_base_url: str, user: str = "", password: str = "", tenant_id: str = "", rest_prefix: str = "rest"):
        self.endpoint = protheus_base_url.rstrip("/") + f"/{rest_prefix.strip('/')}/zfinr130api/api/v1/finr130"
        self.auth = (user, password) if user else None
        self.tenant_id = tenant_id  # "02,0201"

    async def buscar_pagina(self, params: dict[str, Any]) -> dict[str, Any]:
        """Chama uma pagina do ZFINR130API sem consolidar o resultado inteiro."""
        query = {k: v for k, v in params.items() if k in _PARAMS_FINR130 and v is not None}
        query["page"] = int(query.get("page") or 1)
        query["pageSize"] = int(query.get("pageSize") or 5000)
        headers = {"tenantId": self.tenant_id} if self.tenant_id else {}

        async with protheus_async_client(auth=self.auth) as client:
            resp = await protheus_get(
                client,
                self.endpoint,
                params=query,
                headers=headers,
                logger=logger,
                operation=f"FINR130 pagina {query['page']}",
            )
            data = _decode_json_response(resp.content)
            total_pages = int(data.get("totalPages") or data.get("total_pages") or query["page"] or 1)
            logger.info(
                "FINR130 -> pagina %s/%s  pageSize=%s  endpoint=%s  tenant=%s",
                query["page"], total_pages, query["pageSize"], self.endpoint, self.tenant_id,
            )
            return data

    async def buscar_como_registros_pagina(self, params: dict[str, Any]) -> dict[str, Any]:
        resultado = await self.buscar_pagina(params)
        titulos = resultado.get("titulos", [])
        total_pages = int(resultado.get("totalPages") or resultado.get("total_pages") or 1)
        page = int(params.get("page") or 1)
        return {
            "registros": titulos,
            "total": len(titulos),
            "total_pages": total_pages,
            "page": page,
            "hasMore": bool(resultado.get("hasMore", page < total_pages)),
        }

    async def buscar_todos_titulos(self, params: dict[str, Any]) -> dict[str, Any]:
        """Chama o ZFINR130API paginando automaticamente e retorna todos os titulos."""
        page_size = int(params.get("pageSize", 5000))
        query = {k: v for k, v in params.items() if k in _PARAMS_FINR130 and v is not None}
        query["pageSize"] = page_size

        all_titulos: list[dict] = []
        parametros: dict = {}
        current_page = 1
        total_pages = 1
        has_more = True

        headers = {"tenantId": self.tenant_id} if self.tenant_id else {}

        async with protheus_async_client(auth=self.auth) as client:
            while has_more:
                query["page"] = current_page
                logger.info("FINR130 -> pagina %s/%s  pageSize=%s  endpoint=%s  tenant=%s", current_page, total_pages, query["pageSize"], self.endpoint, self.tenant_id)

                resp = await protheus_get(
                    client,
                    self.endpoint,
                    params=query,
                    headers=headers,
                    logger=logger,
                    operation=f"FINR130 pagina {current_page}",
                )

                data = _decode_json_response(resp.content)
                parametros = data.get("parametros", {})
                total_pages = int(data.get("totalPages") or total_pages or 1)
                has_more = bool(data.get("hasMore", current_page < total_pages))
                all_titulos.extend(data.get("titulos", []))
                current_page += 1

        return {
            "parametros": parametros,
            "total_registros": len(all_titulos),
            "titulos": all_titulos,
        }


def _decode_json_response(raw: bytes) -> dict[str, Any]:
    # Protheus retorna Windows-1252 (CP1252) por padrao.
    try:
        return _json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError:
        return _json.loads(raw.decode("windows-1252"))
