import json as _json
import logging
from typing import Any

import httpx

from core.protheus_http import protheus_async_client, protheus_get
from core.situacoes_folha import SituacaoConferenciaFolha

logger = logging.getLogger(__name__)

# Registry: slug -> path do wsmethod (protheus/ZFOLPAGAPI.prw) e filtros manuais aceitos.
# Nao parametriza o SQL em si - cada situacao continua com sua propria regra
# de negocio no .prw, isso so mapeia slug -> endpoint HTTP.
_SITUACOES: dict[SituacaoConferenciaFolha, dict[str, Any]] = {
    SituacaoConferenciaFolha.EMPRESTIMO_FUNCIONARIO: {"path": "emprestimo-funcionario", "params": ["vencto"]},
    SituacaoConferenciaFolha.ADIANTAMENTO_FERIAS: {"path": "adiantamento-ferias", "params": ["baixa_de", "baixa_ate", "historico_competencia", "datarq"]},
    SituacaoConferenciaFolha.ADIANTAMENTO_RESCISAO: {"path": "adiant-rescisao", "params": ["baixa_de", "baixa_ate", "historico_competencia"]},
    SituacaoConferenciaFolha.FGTS: {"path": "fgts", "params": ["vencto"]},
    SituacaoConferenciaFolha.IRRF: {"path": "irrf", "params": ["datpgt_maior_que", "datarq_de", "datarq_ate", "emissao_de", "emissao_ate"]},
    SituacaoConferenciaFolha.INSS: {"path": "inss", "params": ["vencto"]},
    SituacaoConferenciaFolha.FGTS_RESCISORIO: {"path": "fgts-rescisorio", "params": ["baixa_de", "baixa_ate", "historico_competencia"]},
    SituacaoConferenciaFolha.CONTRIBUICAO_ASSISTENCIAL: {"path": "contribuicao-assistencial", "params": ["vencto"]},
    SituacaoConferenciaFolha.SALARIO: {"path": "salario", "params": ["baixa_de", "baixa_ate"]},
    SituacaoConferenciaFolha.FERIAS_A_PAGAR: {"path": "ferias-a-pagar", "params": ["datarq"]},
    SituacaoConferenciaFolha.PENSAO_ALIMENTICIA: {"path": "pensao-alimenticia", "params": ["baixa_de", "baixa_ate"]},
    SituacaoConferenciaFolha.PLR: {"path": "plr", "params": []},
}


class FolhaPagamentoService:
    """Proxy para o ZFOLPAGAPI (Conferencia Folha) do Protheus."""

    def __init__(self, protheus_base_url: str, user: str = "", password: str = "", tenant_id: str = "", rest_prefix: str = "rest"):
        self._base = protheus_base_url.rstrip("/") + f"/{rest_prefix.strip('/')}/zfolpagapi/api/v1/folhapag"
        self.auth = (user, password) if user else None
        self.tenant_id = tenant_id

    async def buscar_situacao(self, situacao: SituacaoConferenciaFolha, params: dict[str, Any]) -> dict[str, Any]:
        cfg = _SITUACOES[situacao]
        query = {k: v for k, v in params.items() if k in cfg["params"] and v is not None}
        headers = {"tenantId": self.tenant_id} if self.tenant_id else {}
        endpoint = f"{self._base}/{cfg['path']}"

        async with protheus_async_client(auth=self.auth) as client:
            resp = await protheus_get(
                client, endpoint, params=query, headers=headers, logger=logger,
                operation=f"ZFOLPAGAPI/{cfg['path']}",
            )
            return _decode_json_response(resp.content)


def _decode_json_response(raw: bytes) -> dict[str, Any]:
    try:
        return _json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError:
        return _json.loads(raw.decode("windows-1252"))
