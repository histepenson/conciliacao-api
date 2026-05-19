import httpx
import json as _json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_PARAMS_FINR150 = [
    "data_base", "page", "pageSize",
    "fornecedor_de", "fornecedor_ate", "loja_de", "loja_ate",
    "prefixo_de", "prefixo_ate", "num_de", "num_ate",
    "banco_de", "banco_ate", "vencto_de", "vencto_ate",
    "natureza_de", "natureza_ate", "emissao_de", "emissao_ate",
    "moeda", "provisorios", "reajuste_vencto", "saldo_retroativo",
    "consid_filiais", "filial_de", "filial_ate",
    "adiantamentos", "dtcontab_de", "dtcontab_ate", "outras_moedas",
    "tipos_incluir", "tipos_excluir", "abatimentos",
    "fluxo_caixa", "comp_saldo_por", "emissao_futura",
    "taxa_moeda", "titulos_excluidos",
]


class FinR150Service:
    """Proxy/adaptador para o ZFINR150API do Protheus (Contas a Pagar)."""

    def __init__(self, protheus_base_url: str, user: str = "", password: str = "", tenant_id: str = "", rest_prefix: str = "rest"):
        self.endpoint = protheus_base_url.rstrip("/") + f"/{rest_prefix.strip('/')}/zfinr150api/api/v1/finr150"
        self.auth = (user, password) if user else None
        self.tenant_id = tenant_id

    async def buscar_todos_titulos(self, params: dict[str, Any]) -> dict[str, Any]:
        """Chama o ZFINR150API paginando automaticamente e retorna todos os titulos."""
        page_size = int(params.get("pageSize", 100))
        query = {k: v for k, v in params.items() if k in _PARAMS_FINR150 and v is not None}
        query["pageSize"] = page_size

        all_titulos: list[dict] = []
        parametros: dict = {}
        current_page = 1
        total_pages = 1

        headers = {"tenantId": self.tenant_id} if self.tenant_id else {}

        async with httpx.AsyncClient(verify=False, timeout=600.0, auth=self.auth) as client:
            while current_page <= total_pages:
                query["page"] = current_page
                logger.info("FINR150 -> pagina %s/%s  endpoint=%s  tenant=%s", current_page, total_pages, self.endpoint, self.tenant_id)

                resp = await client.get(self.endpoint, params=query, headers=headers)
                resp.raise_for_status()

                raw = resp.content
                try:
                    data = _json.loads(raw.decode("utf-8"))
                except UnicodeDecodeError:
                    data = _json.loads(raw.decode("windows-1252"))

                parametros = data.get("parametros", {})
                total_pages = data.get("totalPages", 1)
                all_titulos.extend(data.get("titulos", []))
                current_page += 1

        return {
            "parametros": parametros,
            "total_registros": len(all_titulos),
            "titulos": all_titulos,
        }

    async def buscar_como_registros(self, params: dict[str, Any]) -> list[dict]:
        """
        Retorna os titulos no formato esperado por ProcessadorContasPagar.

        Colunas geradas:
          - codigo_nome_do_fornecedor: "FORNECE-LOJA-NOME" -> normalizado para F{base}{loja}
          - tit_vencidos_valor_corrigido: saldo_na_data quando dias_vencidos > 0
          - titulos_a_vencer_valor_nominal: saldo_na_data quando dias_vencidos <= 0
          - vencto_real: data de vencimento real
          - dias_atraso: dias vencidos (negativo = a vencer)
          - tp: tipo do titulo (para filtro opcional)
        """
        resultado = await self.buscar_todos_titulos(params)
        registros = []
        for t in resultado["titulos"]:
            fornecedor = (t.get("fornecedor") or "").strip()
            loja = (t.get("loja") or "").strip()
            nome = (t.get("nome_fornecedor") or "").strip()
            saldo = t.get("saldo_na_data", 0) or 0
            dias = t.get("dias_vencidos", 0) or 0

            if dias > 0:
                vencido = saldo
                a_vencer = 0
            else:
                vencido = 0
                a_vencer = saldo

            registros.append({
                "codigo_nome_do_fornecedor": f"{fornecedor}-{loja}-{nome}",
                "tit_vencidos_valor_corrigido": vencido,
                "titulos_a_vencer_valor_nominal": a_vencer,
                "vencto_real": t.get("vencto_real", ""),
                "dias_atraso": dias,
                "tp": t.get("tipo", ""),
                "natureza": t.get("natureza", ""),
                "historico": t.get("historico", ""),
            })
        return registros
