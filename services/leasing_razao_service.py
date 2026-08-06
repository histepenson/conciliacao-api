# services/leasing_razao_service.py
"""
Persistencia generica do lado "razao" da Conferencia LEASING: grava um
DataFrame ja normalizado (services/estrategias/bbc/leasing_razao_contabil.py)
como um novo LeasingLoteImportacao + N LeasingRazaoContabil.
"""
from typing import List, Optional

import pandas as pd
from sqlalchemy.orm import Session

from models.leasing_lote_importacao import LeasingLoteImportacao
from models.leasing_razao_contabil import LeasingRazaoContabil

CAMPOS_RAZAO = [
    "dt_lanc_contabil", "conta_contabil", "nome_conta_contabil",
    "historico_padrao", "historico", "conta_contra", "nome_conta_contra",
    "valor_debito", "valor_credito",
]


def _sanitizar_nan(dados: dict) -> dict:
    """
    df.to_dict("records") pode devolver `float('nan')` (nao `None`) para
    celulas vazias em colunas de texto -- o pandas 3.x usa NaN como
    sentinela de nulo mesmo em colunas inferidas como "str". Isso quebra
    o bind de tipo do SQLAlchemy num INSERT em lote (tenta gravar a
    string NaN numa coluna de outra linha por causa da inferencia de
    tipo por coluna do insertmanyvalues). Troca por None antes de montar
    o objeto ORM.
    """
    return {k: (None if isinstance(v, float) and pd.isna(v) else v) for k, v in dados.items()}


def registrar_lote_razao(
    db: Session,
    empresa_id: int,
    nome_arquivo: str,
    usuario_id: Optional[int],
    df: pd.DataFrame,
) -> dict:
    lote = LeasingLoteImportacao(
        empresa_id=empresa_id,
        tipo_relatorio="RAZAO",
        nome_arquivo=nome_arquivo,
        usuario_id=usuario_id,
        qtd_linhas=len(df),
        status="concluido",
    )
    db.add(lote)
    db.flush()

    registros = df.to_dict("records")
    linhas: List[LeasingRazaoContabil] = [
        LeasingRazaoContabil(
            empresa_id=empresa_id,
            lote_importacao_id=lote.id,
            **_sanitizar_nan({campo: row.get(campo) for campo in CAMPOS_RAZAO}),
        )
        for row in registros
    ]
    db.add_all(linhas)
    db.commit()

    total_debito = float(df["valor_debito"].fillna(0).sum())
    total_credito = float(df["valor_credito"].fillna(0).sum())

    return {
        "lote_id": lote.id,
        "tipo_relatorio": "RAZAO",
        "nome_arquivo": nome_arquivo,
        "total_linhas": len(df),
        "total_debito": total_debito,
        "total_credito": total_credito,
        "valor_total": total_debito,
    }
