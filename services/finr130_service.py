import json as _json
import logging
from typing import Any

import httpx

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

    async def buscar_pagina(self, params: dict[str, Any], *, client: httpx.AsyncClient | None = None) -> dict[str, Any]:
        """Chama uma pagina do ZFINR130API sem consolidar o resultado inteiro."""
        query = {k: v for k, v in params.items() if k in _PARAMS_FINR130 and v is not None}
        query["page"] = int(query.get("page") or 1)
        query["pageSize"] = int(query.get("pageSize") or 5000)
        headers = {"tenantId": self.tenant_id} if self.tenant_id else {}

        async def _do(c: httpx.AsyncClient) -> dict[str, Any]:
            resp = await protheus_get(c, self.endpoint, params=query, headers=headers, logger=logger, operation=f"FINR130 pagina {query['page']}")
            data = _decode_json_response(resp.content)
            total_pages = int(data.get("totalPages") or data.get("total_pages") or query["page"] or 1)
            logger.info("FINR130 -> pagina %s/%s  pageSize=%s  endpoint=%s  tenant=%s", query["page"], total_pages, query["pageSize"], self.endpoint, self.tenant_id)
            return data

        if client is not None:
            return await _do(client)
        async with protheus_async_client(auth=self.auth) as c:
            return await _do(c)

    async def buscar_como_registros_pagina(self, params: dict[str, Any], *, client: httpx.AsyncClient | None = None) -> dict[str, Any]:
        """Retorna uma pagina do FINR130 ja no formato de base financeira."""
        resultado = await self.buscar_pagina(params, client=client)
        registros = _titulos_para_registros(resultado.get("titulos", []))
        total_pages = int(resultado.get("totalPages") or resultado.get("total_pages") or 1)
        page = int(params.get("page") or 1)
        return {
            "parametros": resultado.get("parametros", {}),
            "registros": registros,
            "total": len(registros),
            "totalPages": total_pages,
            "total_pages": total_pages,
            "page": page,
            "hasMore": bool(resultado.get("hasMore", page < total_pages)),
        }

    async def buscar_como_registros(self, params: dict[str, Any]) -> list[dict]:
        """
        Retorna os titulos no formato esperado por ProcessadorContasReceber.

        Colunas geradas:
          - codigo_lj_nome_do_cliente: "CLIENTE-LOJA-NOME" -> normalizado para C{base}{loja}
          - tit_vencidos_valor_corrigido: saldo_na_data quando dias_vencidos > 0
          - titulos_a_vencer_valor_atual: saldo_na_data quando dias_vencidos <= 0
          - vencto_real: data de vencimento real
          - dias_atraso: dias vencidos (negativo = a vencer)
          - tp: tipo do titulo (para filtro opcional)
        """
        resultado = await self.buscar_todos_titulos(params)
        return _titulos_para_registros(resultado["titulos"])

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


def _titulos_para_registros(titulos: list[dict]) -> list[dict]:
    registros = []
    for t in titulos:
        cliente = (t.get("cliente") or "").strip()
        loja = (t.get("loja") or "").strip()
        nome = (t.get("nome_cliente") or "").strip()
        saldo = t.get("saldo_na_data", 0) or 0
        dias = t.get("dias_vencidos", 0) or 0

        if dias > 0:
            vencido = saldo
            a_vencer = 0
        else:
            vencido = 0
            a_vencer = saldo

        prefixo = (t.get("prefixo") or "").strip()
        numero = (t.get("numero") or "").strip()
        parcela = (t.get("parcela") or "").strip()

        registro = {
            "codigo_lj_nome_do_cliente": f"{cliente}-{loja}-{nome}",
            "tit_vencidos_valor_corrigido": vencido,
            "titulos_a_vencer_valor_atual": a_vencer,
            "vencto_real": t.get("vencto_real", ""),
            "data_de_emissao": t.get("emissao", ""),
            "prf_numero": f"{prefixo}{numero}{parcela}",
            "dias_atraso": dias,
            "tp": t.get("tipo", ""),
            "natureza": t.get("natureza", ""),
            "historico": t.get("historico", ""),
        }

        # Quando a carga ja traz o codigo Protheus completo (cargas manuais via
        # planilha de empresas sem API, ex: GENIX), repassa para o normalizador
        # usar direto em vez de re-parsear o composto "codigo_lj_nome_do_cliente"
        if t.get("codigo_cli") and t.get("filial"):
            registro["codigo_cli"] = t["codigo_cli"]
            registro["filial"] = t["filial"]
            registro["loja"] = loja
            registro["nome_cliente"] = nome

        registros.append(registro)
    return registros
