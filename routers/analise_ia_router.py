from fastapi import APIRouter, Depends

from middleware.tenant import EmpresaContext, get_empresa_context
from schemas.analise_ia import AnalisarDivergenciaBody
from services import analise_ia_service

router = APIRouter(prefix="/v1/analise-ia", tags=["Analise IA"])


@router.post(
    "/divergencia",
    summary="Analisar com IA: diagnostico generico de divergencia (financeiro/bancario/estoque)",
    description=(
        "Reencaminha os registros nao-conciliados (ja calculados pela conciliacao) para o "
        "servico smartconciliacoes_ia diagnosticar a causa raiz e gerar uma explicacao. "
        "Rota stateless: nao consulta o banco, so' repassa o que o frontend ja tem."
    ),
)
def post_divergencia(
    body: AnalisarDivergenciaBody,
    context: EmpresaContext = Depends(get_empresa_context),
):
    payload = body.model_dump()
    payload["config"] = {}
    payload["candidatos_brutos_b"] = []
    payload["gerar_explicacao_ia"] = True
    return analise_ia_service.chamar_diagnostico(payload)
