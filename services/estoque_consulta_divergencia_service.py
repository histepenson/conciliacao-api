"""
Consulta pontual do Kardex (MATR900) para diagnosticar um lancamento
"Só Razão" sem correspondencia na Conciliacao de Estoque.

Decodifica o CT2_KEY do lancamento (pelo layout_campos cadastrado do LP,
ver models/lancamento_padrao.py::LancamentoPadraoCt2Layout) e busca no
Kardex SEM restringir conta contabil (conta_de/conta_ate omitidos) -- se
achar o movimento, o lancamento so' esta' classificado em outra conta
contabil (nao e' falta de estoque); se nao achar, o produto genuinamente
nao gerou movimento fisico nesse periodo (ver caso real: produto MUC3060,
LP 650, Rivema -- confirmado ausente do Kardex em qualquer conta).
"""

import logging

import pandas as pd

from tools.estoque.calc_diferencas_estoque import (
    _decodificar_ct2_key_por_layout,
    _chave_ct2_decodificada_por_layout,
    _chave_kardex_por_layout,
)
from tools.estoque.kardex import normalizar_kardex
from services.lancamento_padrao_ct2_service import obter_mapa_layout_campos
from services.matr900_service import Matr900Service

logger = logging.getLogger(__name__)


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
