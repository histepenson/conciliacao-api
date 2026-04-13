import httpx
import json as _json
import logging
from typing import Any
from fastapi import HTTPException

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

    def __init__(self, protheus_base_url: str, user: str = "", password: str = "", tenant_id: str = ""):
        self.endpoint = protheus_base_url.rstrip("/") + "/rest/zfin470api/api/v1/finr470"
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

        async with httpx.AsyncClient(verify=False, timeout=300.0, auth=self.auth) as client:
            while current_page <= total_pages:
                query["page"] = current_page
                logger.info(
                    "FINR470 -> pagina %s/%s  endpoint=%s  tenant=%s",
                    current_page, total_pages, self.endpoint, self.tenant_id,
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

    async def buscar_como_registros(self, params: dict[str, Any]) -> list[dict]:
        """
        Retorna o extrato no formato esperado por `base_extrato.registros`.

        Cada registro preserva os nomes de colunas usados pelo normalizador do
        backend: `data`, `documento`, `prefixo_titulo`, `entradas`, `saidas`,
        `saldo_atual`, `descricao`.
        """
        resultado = await self.buscar_extrato(params)
        return resultado["registros"]
