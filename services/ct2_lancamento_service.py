"""
Busca de lancamentos contabeis na CT2 (razao contabil, modulo CTB) a partir da
chave de um titulo financeiro (SE1/SE2, modulo FIN), para descobrir em quais
contas contabeis esse titulo foi efetivamente lancado -- usado pela analise de
IA para identificar titulos que nao aparecem na conta analisada mas foram
contabilizados em outro lugar.

CT2 e' sempre a tabela contabil. O termo "financeiro" abaixo se refere apenas
a' ORIGEM do lancamento dentro da CT2: quando um titulo do Financeiro (SE1/
SE2) e' baixado/contabilizado, a rotina de contabilizacao automatica grava uma
linha na CT2 com um lote fixo (008850) -- e' esse lote que identificamos aqui,
nao uma tabela financeira separada.

Reaproveita o ZCT2RAZCT5 (ja em producao para CT2RAZ) filtrando por esse lote,
sem precisar de um novo endpoint no Protheus.
"""
import logging
from typing import Any, Optional

from services.ct2raz_ct5_service import Ct2RazCt5Service

logger = logging.getLogger(__name__)

# Lote que a rotina de contabilizacao automatica do Financeiro (baixa de
# titulos SE1/SE2) grava na CT2 -- identifica a ORIGEM do lancamento
# contabil, nao uma tabela financeira separada.
LOTE_CONTABILIZACAO_FINANCEIRO = "008850"

# Largura (em caracteres) de cada campo dentro do CT2_KEY para lancamentos
# originados da contabilizacao automatica de titulos (SE1/SE2), na ordem
# FILIAL+CLIENTE/FORNECEDOR+LOJA+PREFIXO+NUM+PARCELA+TIPO. Padrao de
# dicionario (SX3) do Protheus -- pode mudar por empresa/customizacao;
# ajustar aqui se um novo ambiente nao bater com esses tamanhos.
CT2_KEY_CAMPOS: list[tuple[str, int]] = [
    ("filial", 4),
    ("cliente_fornecedor", 6),
    ("loja", 2),
    ("prefixo", 3),
    ("num", 9),
    ("parcela", 3),
    ("tipo", 2),
]


def decompor_ct2_key(ct2_key: str) -> dict[str, str]:
    """Fatia o CT2_KEY nos campos de origem do titulo, na ordem de CT2_KEY_CAMPOS."""
    chave = ct2_key or ""
    campos: dict[str, str] = {}
    pos = 0
    for nome, largura in CT2_KEY_CAMPOS:
        campos[nome] = chave[pos:pos + largura].strip()
        pos += largura
    return campos


def normalizar_campo_ct2(valor: Any) -> str:
    return str(valor or "").strip().upper().lstrip("0") or "0"


async def buscar_lancamento_contabil_de_titulo(
    *,
    protheus_url: str,
    protheus_user: str,
    protheus_password: str,
    tenant_id: str,
    rest_prefix: str,
    filial: str,
    cliente_fornecedor: str,
    loja: str,
    num: str,
    tipo: str,
    data_ini: str,
    data_fim: str,
    conta_contabil_analisada: str = "",
    prefixo: str = "",
    parcela: str = "",
    lote: str = LOTE_CONTABILIZACAO_FINANCEIRO,
) -> dict[str, Any]:
    """
    Busca na CT2 (tabela contabil, lote da contabilizacao automatica de
    titulos) todos os lancamentos que correspondem ao titulo financeiro
    informado (chave SE1/SE2: FILIAL+CLIENTE/FORNECEDOR+LOJA+PREFIXO+NUM+
    PARCELA+TIPO), decodificando o CT2_KEY de cada linha retornada pelo
    ZCT2RAZCT5.

    data_ini/data_fim: range de busca no formato YYYYMMDD (CT2_DATA), deve
    cobrir a data provavel do lancamento contabil do titulo.

    Retorna as contas contabeis onde o titulo foi efetivamente lancado e se
    isso difere da conta_contabil_analisada informada.
    """
    service = Ct2RazCt5Service(
        protheus_base_url=protheus_url,
        user=protheus_user,
        password=protheus_password,
        tenant_id=tenant_id,
        rest_prefix=rest_prefix,
    )

    alvo: dict[str, str] = {
        "filial": normalizar_campo_ct2(filial),
        "cliente_fornecedor": normalizar_campo_ct2(cliente_fornecedor),
        "loja": normalizar_campo_ct2(loja),
        "num": normalizar_campo_ct2(num),
        "tipo": normalizar_campo_ct2(tipo),
    }
    if prefixo:
        alvo["prefixo"] = normalizar_campo_ct2(prefixo)
    if parcela:
        alvo["parcela"] = normalizar_campo_ct2(parcela)

    encontrados: list[dict[str, Any]] = []
    page = 1
    while True:
        resultado = await service.buscar_como_registros_pagina({
            "lote": lote,
            "data_ini": data_ini,
            "data_fim": data_fim,
            "page": page,
            "pageSize": 5000,
        })

        for linha in resultado.get("registros", []):
            ct2_key = linha.get("ct2_key", "")
            campos = decompor_ct2_key(ct2_key)
            logger.debug("[CT2_LANCAMENTO] ct2_key=%r campos=%s", ct2_key, campos)

            if any(normalizar_campo_ct2(campos.get(chave)) != valor for chave, valor in alvo.items()):
                continue

            encontrados.append({
                "conta": linha.get("conta", ""),
                "data": linha.get("data", ""),
                "debito": linha.get("debito", 0),
                "credito": linha.get("credito", 0),
                "historico": linha.get("historico", ""),
                "ct5_desc": linha.get("ct5_desc", ""),
                "lote_sub_doc_linha": linha.get("lote_sub_doc_linha", ""),
                "ct2_key": ct2_key,
            })

        if not resultado.get("hasMore"):
            break
        page += 1

    contas_encontradas = sorted({e["conta"] for e in encontrados if e["conta"]})
    conta_alvo = (conta_contabil_analisada or "").strip()
    contas_diferentes = [c for c in contas_encontradas if c != conta_alvo] if conta_alvo else contas_encontradas

    logger.info(
        "[CT2_LANCAMENTO] titulo filial=%s cliente/fornecedor=%s num=%s tipo=%s -> "
        "%d lancamento(s) em %s",
        filial, cliente_fornecedor, num, tipo, len(encontrados), contas_encontradas,
    )

    return {
        "encontrado": bool(encontrados),
        "contas_encontradas": contas_encontradas,
        "refletiu_em_outra_conta": bool(contas_diferentes),
        "contas_diferentes": contas_diferentes,
        "conta_analisada_presente": (conta_alvo in contas_encontradas) if conta_alvo else None,
        "lancamentos": encontrados,
    }
