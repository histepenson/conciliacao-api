import json as _json
import logging
from typing import Any

from core.protheus_http import protheus_async_client, protheus_get

logger = logging.getLogger(__name__)

_PARAMS_CTBR480 = [
    "data_ini", "data_fim", "page", "pageSize",
    "item_de", "item_ate",
    "conta_de", "conta_ate",
    "custo_de", "custo_ate",
    "clvl_de", "clvl_ate",
    "moeda", "saldo", "set_of_books",
    "vlr_zerado",
    "consid_filiais", "filial_de", "filial_ate",
    "analitico", "contas_sem_mov",
    "imprime_custo", "imprime_clvl", "totaliza_conta",
]


class Ctbr480Service:
    """
    Proxy/adaptador para o ZCTBR480API do Protheus.

    Busca o RazAo ContAbil por Item (CTBR480) diretamente do Protheus via REST,
    paginando automaticamente, e entrega os dados prontos para o sistema de
    conciliaAAo (base_contabil_geral).

    Campos retornados por lancamento (espelham as colunas do Excel CTBR480):
        data, lote_sub_doc_linha, historico, xpartida, c_custo,
        item_conta, cod_cl_val, debito, credito, saldo_atual,
        conta, desc_item, desc_conta, normal_item, normal_cta
    """

    def __init__(self, protheus_base_url: str, user: str = "", password: str = "", tenant_id: str = "", rest_prefix: str = "rest"):
        self.endpoint = protheus_base_url.rstrip("/") + f"/{rest_prefix.strip('/')}/zctbr480api/api/v1/ctbr480"
        self.auth = (user, password) if user else None
        self.tenant_id = tenant_id  # ex: "02,0201"

    async def buscar_razao(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Chama o ZCTBR480API paginando automaticamente.
        Retorna todos os lanAamentos consolidados com saldo_atual acumulado.
        """
        page_size = int(params.get("pageSize") or 500)
        query = {k: v for k, v in params.items() if k in _PARAMS_CTBR480 and v is not None}
        query["pageSize"] = page_size

        all_linhas: list[dict] = []
        parametros: dict = {}
        current_page = 1
        total_pages = 1

        headers = {"tenantId": self.tenant_id} if self.tenant_id else {}

        async with protheus_async_client(auth=self.auth) as client:
            while current_page <= total_pages:
                query["page"] = current_page
                logger.info(
                    "CTBR480 a' pAgina %s/%s  endpoint=%s  tenant=%s",
                    current_page, total_pages, self.endpoint, self.tenant_id,
                )
                resp = await protheus_get(
                    client,
                    self.endpoint,
                    params=query,
                    headers=headers,
                    logger=logger,
                    operation=f"CTBR480 pagina {current_page}",
                )

                raw = resp.content
                try:
                    data = _json.loads(raw.decode("utf-8"))
                except UnicodeDecodeError:
                    data = _json.loads(raw.decode("windows-1252"))

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
        """
        Busca o razAo contAbil e retorna os registros no formato esperado pela
        conciliaAAo (base_contabil_geral.registros).

        Cada registro mantA(c)m os nomes de coluna do Excel CTBR480, pois o
        analise_diferencas_service.py jA conhece e normaliza esses nomes:
            data, lote_sub_doc_linha, historico, xpartida, c_custo,
            item_conta, cod_cl_val, debito, credito, saldo_atual,
            conta, desc_item, desc_conta, normal_item, normal_cta
        """
        resultado = await self.buscar_razao(params)
        return resultado["linhas"]

