import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.protheus import resolve_protheus_config
from db import get_db
from middleware.tenant import EmpresaContext, get_empresa_context, resolve_empresa_id
from schemas.analise_ia import AnalisarDivergenciaBody
from services import analise_ia_service
from services.ct2_lancamento_service import buscar_lancamento_contabil_de_titulo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/analise-ia", tags=["Analise IA"])

# Janela de busca na CT2 a partir da data de emissao do titulo -- cobre o
# caso de a baixa/contabilizacao ter ocorrido depois da emissao.
_JANELA_BUSCA_CT2_DIAS = 60


async def _enriquecer_titulos_com_ct2(
    body: AnalisarDivergenciaBody, context: EmpresaContext, db: Session
) -> None:
    """
    Para o dominio financeiro, busca na CT2 (contabil) onde cada titulo sem
    correspondencia foi efetivamente lancado, e anexa o resultado em
    `lancamentos_financeiro_detalhes` -- assim a IA pode explicar quando o
    titulo nao "sumiu", apenas caiu em outra conta contabil.

    So' roda para titulos que tem a chave CT2 disponivel (carga automatica
    via Protheus); upload manual de Excel nao tem FILIAL/LOJA separados e
    fica sem essa enriquecimento.
    """
    if body.dominio != "financeiro":
        return

    try:
        empresa_id = resolve_empresa_id(context, body.contexto.get("empresa_id"))
        protheus = resolve_protheus_config(empresa_id, db)
    except Exception:
        logger.warning("[ANALISE_IA] Nao foi possivel resolver config Protheus para busca na CT2", exc_info=True)
        return

    conta_analisada = str(body.contexto.get("conta_contabil") or "").strip()
    logger.info(
        "[ANALISE_IA] Iniciando enriquecimento CT2: empresa_id=%s conta_analisada=%s itens=%s",
        empresa_id, conta_analisada, len(body.registros_nao_conciliados_a),
    )

    for item in body.registros_nao_conciliados_a:
        # SO_FINANCEIRO popula lancamentos_financeiro_detalhes; outros tipos
        # (ex.: DIVERGENTE_VALOR) populam registros_match_financeiro -- mesmo
        # fallback que o frontend ja usa pra montar a grid "Lancamentos Financeiro".
        titulos = item.get("lancamentos_financeiro_detalhes") or item.get("registros_match_financeiro") or []
        codigo = item.get("codigo_fornecedor") or item.get("codigo") or "?"
        logger.info("[ANALISE_IA] codigo=%s: %s titulo(s) candidatos", codigo, len(titulos))

        for titulo in titulos:
            filial = titulo.get("ct2_filial")
            cliente_fornecedor = titulo.get("ct2_cliente_fornecedor")
            loja = titulo.get("ct2_loja")
            numero = titulo.get("ct2_numero")
            tipo_titulo = titulo.get("tipo_titulo")
            data_emissao = titulo.get("data_emissao") or titulo.get("data_lancamento")

            campos_faltando = [
                nome for nome, valor in (
                    ("ct2_filial", filial), ("ct2_cliente_fornecedor", cliente_fornecedor),
                    ("ct2_loja", loja), ("ct2_numero", numero),
                    ("tipo_titulo", tipo_titulo), ("data_emissao", data_emissao),
                ) if not valor
            ]
            if campos_faltando:
                logger.info(
                    "[ANALISE_IA] codigo=%s titulo pulado (campos ausentes: %s) -- titulo=%s",
                    codigo, campos_faltando, titulo,
                )
                continue

            try:
                dt_emissao = datetime.strptime(data_emissao, "%d/%m/%Y")
            except ValueError:
                logger.warning(
                    "[ANALISE_IA] codigo=%s titulo pulado: data_emissao=%r fora do formato dd/mm/aaaa",
                    codigo, data_emissao,
                )
                continue

            data_ini = dt_emissao.strftime("%Y%m%d")
            data_fim = (dt_emissao + timedelta(days=_JANELA_BUSCA_CT2_DIAS)).strftime("%Y%m%d")

            try:
                resultado = await buscar_lancamento_contabil_de_titulo(
                    protheus_url=protheus.url,
                    protheus_user=protheus.user,
                    protheus_password=protheus.password,
                    tenant_id=protheus.tenant,
                    rest_prefix=protheus.rest_prefix,
                    filial=filial,
                    cliente_fornecedor=cliente_fornecedor,
                    loja=loja,
                    num=numero,
                    tipo=tipo_titulo,
                    prefixo=titulo.get("ct2_prefixo") or "",
                    parcela=titulo.get("parcela") or "",
                    data_ini=data_ini,
                    data_fim=data_fim,
                    conta_contabil_analisada=conta_analisada,
                )
                titulo["ct2_lancamento"] = resultado
                logger.info(
                    "[ANALISE_IA] codigo=%s numero=%s -> encontrado=%s contas=%s",
                    codigo, numero, resultado.get("encontrado"), resultado.get("contas_encontradas"),
                )
            except Exception:
                logger.exception(
                    "[ANALISE_IA] codigo=%s Falha ao buscar lancamento contabil na CT2 para titulo numero=%s",
                    codigo, numero,
                )


@router.post(
    "/divergencia",
    summary="Analisar com IA: diagnostico generico de divergencia (financeiro/bancario/estoque)",
    description=(
        "Reencaminha os registros nao-conciliados (ja calculados pela conciliacao) para o "
        "servico smartconciliacoes_ia diagnosticar a causa raiz e gerar uma explicacao. "
        "Para o dominio financeiro, antes de reencaminhar busca na razão contábil se os "
        "titulos sem correspondencia foram lancados em outra conta contabil."
    ),
)
async def post_divergencia(
    body: AnalisarDivergenciaBody,
    context: EmpresaContext = Depends(get_empresa_context),
    db: Session = Depends(get_db),
):
    await _enriquecer_titulos_com_ct2(body, context, db)
    payload = body.model_dump()
    payload["config"] = {}
    payload["candidatos_brutos_b"] = []
    payload["gerar_explicacao_ia"] = True
    payload["empresa_id"] = resolve_empresa_id(context, body.contexto.get("empresa_id"))
    return analise_ia_service.chamar_diagnostico(payload)
