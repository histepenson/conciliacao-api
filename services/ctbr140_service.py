import json as _json
import logging
from typing import Any

from core.protheus_http import protheus_async_client, protheus_get

logger = logging.getLogger(__name__)

_PARAMS_CTBR140 = [
    "data_ini", "data_fim", "page", "pageSize",
    "conta_de", "conta_ate", "item_de", "item_ate",
    "tipo_balancete", "set_of_books", "vlr_zerado", "moeda",
    "tp_lanc", "imp_mov", "divide_por",
    "sld_ant_lp", "data_lp",
    "consid_filiais", "filial_de", "filial_ate",
]


class Ctbr140Service:
    """
    Proxy/adaptador para o ZCTBR140API do Protheus.

    Busca o Balancete de Conta/Item (CTBR140) diretamente do Protheus via REST,
    paginando automaticamente, e entrega os dados prontos para normalizacao.
    """

    def __init__(self, protheus_base_url: str, user: str = "", password: str = "", tenant_id: str = "", rest_prefix: str = "rest"):
        self.endpoint = protheus_base_url.rstrip("/") + f"/{rest_prefix.strip('/')}/zctbr140api/api/v1/ctbr140"
        self.auth = (user, password) if user else None
        self.tenant_id = tenant_id  # "02,0201"

    async def buscar_balancete(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Chama o ZCTBR140API paginando automaticamente.
        Retorna todas as linhas consolidadas.
        """
        page_size = int(params.get("pageSize") or 200)
        query = {k: v for k, v in params.items() if k in _PARAMS_CTBR140 and v is not None}
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
                    "CTBR140 -> pagina %s/%s  endpoint=%s  tenant=%s",
                    current_page, total_pages, self.endpoint, self.tenant_id,
                )
                resp = await protheus_get(
                    client,
                    self.endpoint,
                    params=query,
                    headers=headers,
                    logger=logger,
                    operation=f"CTBR140 pagina {current_page}",
                )

                # Protheus retorna Windows-1252 (CP1252) por padrao.
                # Tenta UTF-8 primeiro; se falhar, usa windows-1252.
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
        Busca o balancete e transforma para o formato de registros esperado por
        normalizar_planilha_contabilidade:

            [{"Codigo": <item_code>, "Descricao": <desc_item>, "Saldo atual": <valor>}]

        Logica de sinal do "Saldo atual":
        - normal_cta = "1" (debito-normal):  valor =  saldo_atu  (positivo = saldo devedor)
        - normal_cta = "2" (credito-normal): valor = -saldo_atu  (inverte para positivo = saldo credor)

        Isso replica o comportamento de ValorCTB no relatorio, que exibe o saldo
        sempre na direcao normal da conta (positivo = saldo esperado).
        Clientes com saldo inverso aparecem como negativo, preservando a informacao.
        """
        resultado = await self.buscar_balancete(params)
        return [self._linha_para_registro(linha) for linha in resultado["linhas"]]

    @staticmethod
    def _linha_para_registro(linha: dict) -> dict:
        normal_cta = str(linha.get("normal_cta") or "1").strip()
        saldo_atu = float(linha.get("saldo_atu") or 0)

        # Conta credito-normal (passivo, receita, contas a pagar):
        # saldo_atu negativo = creditos > debitos = saldo na direcao certa.
        # Invertemos para que o valor fique positivo, igual ao que o relatorio exibe.
        value = -saldo_atu if normal_cta == "2" else saldo_atu

        return {
            "Codigo": linha.get("item", ""),         # CT2_ITEM -> codigo do item/CC
            "Descricao": linha.get("desc_item", ""), # Descricao do item
            "Saldo atual": value,                    # Valor na direcao normal da conta
        }
