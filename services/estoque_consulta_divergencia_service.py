"""
Consulta pontual do Kardex (MATR900) ou do Razao Contabil (CTBR400) para
diagnosticar um lancamento sem correspondencia na Conciliacao de Estoque.

Decodifica o CT2_KEY (pelo layout_campos cadastrado do LP, ver
models/lancamento_padrao.py::LancamentoPadraoCt2Layout) e busca no lado
oposto SEM restringir conta contabil (conta_de/conta_ate omitidos) -- se
achar o movimento/lancamento, ele so' esta' classificado em outra conta
contabil (nao e' divergencia real); se nao achar, confirma que
genuinamente nao ha' correspondencia nesse periodo (ver caso real: produto
MUC3060, LP 650, Rivema -- confirmado ausente do Kardex em qualquer conta).
"""

import logging

import pandas as pd

from core.data_base import parse_ano_mes
from tools.estoque.calc_diferencas_estoque import (
    _decodificar_ct2_key_por_layout,
    _chave_ct2_decodificada_por_layout,
    _chave_kardex_por_layout,
)
from tools.estoque.kardex import normalizar_kardex
from tools.estoque.razao_estoque import normalizar_razao_estoque
from services.lancamento_padrao_ct2_service import obter_mapa_layout_campos, obter_mapa_sequencias_credito_imposto
from services.empresa_configuracao_service import obter_valor
from core.particularidades import ChaveParticularidade
from services.matr900_service import Matr900Service
from services.ctbr400_service import Ctbr400Service
from services.ct2raz_ct5_service import Ct2RazCt5Service

logger = logging.getLogger(__name__)


class RazaoCt2RazCt5Adapter:
    """Faz o Ct2RazCt5Service responder como o Ctbr400Service pra consulta de
    divergencia (buscar_como_registros = todas as paginas). Usado so' pelas
    empresas com a particularidade estoque_razao_ct2razct5 (razao da
    conciliacao de estoque via CT2RAZCT5). O Ct2RazCt5Service em si nao muda."""

    def __init__(self, svc: Ct2RazCt5Service):
        self._svc = svc

    async def buscar_como_registros(self, params: dict) -> list[dict]:
        linhas: list[dict] = []
        pagina = 1
        while True:
            resp = await self._svc.buscar_como_registros_pagina({**params, "page": pagina})
            linhas.extend(resp.get("registros", []))
            if not resp.get("hasMore"):
                break
            pagina += 1
        return linhas


async def consultar_divergencia_kardex(
    db,
    empresa_id: int,
    ct2_lp: str,
    ct2_key: str,
    data_ini: str,
    data_fim: str,
    matr900_service: Matr900Service,
) -> dict:
    mapa_layout = obter_mapa_layout_campos(db, empresa_id)
    layout_campos = mapa_layout.get(str(ct2_lp or "").strip())
    if not layout_campos:
        return {"encontrado": False, "motivo": "lp_sem_layout_cadastrado"}

    decoded = _decodificar_ct2_key_por_layout(ct2_key, layout_campos)
    if not decoded or "produto" not in decoded or not decoded["produto"]:
        return {"encontrado": False, "motivo": "nao_decodificou"}

    campos_ordem = [c["campo"] for c in layout_campos]
    chave_alvo = _chave_ct2_decodificada_por_layout(decoded, campos_ordem)

    query = {
        "data_ini": data_ini,
        "data_fim": data_fim,
        "produto_de": decoded["produto"],
        "produto_ate": decoded["produto"],
        "considera_filiais": "2",  # todas as filiais -- nao restringir aqui tambem
        # conta_de/conta_ate OMITIDOS DE PROPOSITO: busca em todas as contas
    }

    logger.info(
        "[CONSULTAR DIVERGENCIA] empresa_id=%s ct2_lp=%s produto=%s periodo=%s-%s",
        empresa_id, ct2_lp, decoded["produto"], data_ini, data_fim,
    )

    registros = await matr900_service.buscar_como_registros(query)
    if not registros:
        return {"encontrado": False, "motivo": "sem_movimento_fisico"}
    df_kardex = normalizar_kardex(pd.DataFrame(registros))

    for _, linha in df_kardex.iterrows():
        chave_linha = _chave_kardex_por_layout(linha, campos_ordem)
        if chave_linha == chave_alvo:
            return {
                "encontrado": True,
                "conta_contabil": linha.get("conta_contabil") or "",
                "documento": linha.get("doc") or linha.get("documento_numero") or "",
                "produto": linha.get("codigo_produto") or "",
                "descricao": linha.get("descricao") or "",
            }

    return {"encontrado": False, "motivo": "sem_movimento_fisico"}


async def consultar_divergencia_razao_contabil(
    db,
    empresa_id: int,
    kardex_registro: dict,
    data_ini: str,
    data_fim: str,
    ctbr400_service: Ctbr400Service,
) -> dict:
    """
    Inverso de consultar_divergencia_kardex: dado um lancamento "Só Kardex"
    (sem ct2_lp/ct2_key proprios -- sao conceitos do lado Razao), busca no
    Razao Contabil (CTBR400) SEM restringir conta contabil. Cada linha do
    razao retornada ja' traz seu proprio ct2_lp, entao o layout e' resolvido
    por linha (nao ha' um LP unico conhecido de antemao pro lado Kardex).
    """
    mapa_layout = obter_mapa_layout_campos(db, empresa_id)
    if not mapa_layout:
        return {"encontrado": False, "motivo": "nenhum_lp_com_layout_cadastrado"}

    produto = str(kardex_registro.get("codigo_produto") or "").strip()
    if not produto:
        return {"encontrado": False, "motivo": "produto_nao_informado"}

    query = {
        "data_ini": data_ini,
        "data_fim": data_fim,
        "item_de": produto,
        "item_ate": produto,
        "consid_filiais": "2",  # todas as filiais -- nao restringir aqui tambem
        # Todas as contas: o ZCT2RAZAPI exige conta_de/conta_ate (422 se vazios),
        # entao vai a faixa completa em vez de omitir -- mesma faixa que o
        # Ct2RazCt5Service usa por padrao.
        "conta_de": "0",
        "conta_ate": "zzzzzzzzzzzzz",
    }

    logger.info(
        "[CONSULTAR DIVERGENCIA RAZAO] empresa_id=%s produto=%s periodo=%s-%s",
        empresa_id, produto, data_ini, data_fim,
    )

    registros = await ctbr400_service.buscar_como_registros(query)
    if not registros:
        return {"encontrado": False, "motivo": "sem_lancamento_contabil"}

    ano_base, _mes = parse_ano_mes(data_fim)
    razao_ct2razct5 = bool(obter_valor(db, empresa_id, ChaveParticularidade.ESTOQUE_RAZAO_CT2RAZCT5.value))
    df_razao = normalizar_razao_estoque(
        pd.DataFrame(registros),
        ano_base=ano_base,
        mapa_lp_sequencias_credito=obter_mapa_sequencias_credito_imposto(db, empresa_id) if razao_ct2razct5 else None,
        historico_estrito=razao_ct2razct5,
    )

    campos_ordem_por_lp: dict[str, list] = {}
    chave_alvo_por_lp: dict[str, tuple] = {}

    for _, linha in df_razao.iterrows():
        lp = str(linha.get("ct2_lp") or "").strip()
        if not lp:
            continue

        if lp not in campos_ordem_por_lp:
            layout_campos = mapa_layout.get(lp)
            if not layout_campos:
                campos_ordem_por_lp[lp] = None
            else:
                campos_ordem = [c["campo"] for c in layout_campos]
                chave_alvo = _chave_kardex_por_layout(kardex_registro, campos_ordem)
                campos_ordem_por_lp[lp] = campos_ordem
                chave_alvo_por_lp[lp] = chave_alvo

        campos_ordem = campos_ordem_por_lp[lp]
        if not campos_ordem:
            continue

        chave_alvo = chave_alvo_por_lp.get(lp)
        if not chave_alvo or not all(chave_alvo):
            continue

        layout_campos = mapa_layout[lp]
        decoded = _decodificar_ct2_key_por_layout(linha.get("ct2_key"), layout_campos)
        if not decoded:
            continue
        chave_linha = _chave_ct2_decodificada_por_layout(decoded, campos_ordem)
        if chave_linha == chave_alvo:
            return {
                "encontrado": True,
                "conta_contabil": linha.get("conta_contabil") or "",
                "ct2_lp": lp,
                "historico": linha.get("historico") or "",
                "data_movimento": linha.get("data_movimento") or "",
                "debito": float(linha.get("debito") or 0),
                "credito": float(linha.get("credito") or 0),
            }

    return {"encontrado": False, "motivo": "sem_lancamento_contabil"}
