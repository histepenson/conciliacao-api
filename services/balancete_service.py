"""
Service para importacao e consulta de Balancete Contabil.

O balancete e importado uma vez por periodo (mes) e cobre todas as contas do
plano de contas da empresa de uma vez. As telas de conciliacao (banco, estoque,
financeira) leem o registro da conta sendo conciliada para exibir saldo
anterior/atual no cabecalho e validar o calculo do periodo.
"""

import logging
from datetime import date
from typing import Any

import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from core.data_base import parse_ano_mes
from models.balancete import BalanceteConta
from models.planodecontas import PlanoDeContas
from tools.balancete import normalizar_balancete, normalizar_codigo_conta

logger = logging.getLogger(__name__)


def _primeiro_dia_mes_de_data_base(data_base: str) -> date:
    """Converte data-base (DD/MM/YYYY, MM/YYYY ou YYYYMMDD) para o primeiro dia do mes."""
    ano, mes = parse_ano_mes(data_base)
    return date(ano, mes, 1)


def importar_balancete(
    db: Session,
    empresa_id: int,
    data_base: str,
    df_raw: pd.DataFrame,
) -> dict[str, Any]:
    """Normaliza o balancete e faz upsert por conta para o periodo informado."""
    periodo = _primeiro_dia_mes_de_data_base(data_base)

    df_norm = normalizar_balancete(df_raw)
    if df_norm.empty:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhuma linha valida encontrada no balancete (coluna 'Conta' vazia em todas as linhas).",
        )

    contas_plano = {
        normalizar_codigo_conta(c.conta_contabil): c.id
        for c in db.query(PlanoDeContas).filter(PlanoDeContas.empresa_id == empresa_id).all()
    }

    existentes = {
        b.conta_codigo_normalizado: b
        for b in db.query(BalanceteConta).filter(
            BalanceteConta.empresa_id == empresa_id,
            BalanceteConta.periodo == periodo,
        ).all()
    }

    contas_casadas = 0
    contas_nao_encontradas: list[str] = []

    for row in df_norm.to_dict("records"):
        conta_norm = row["conta_normalizada"]
        conta_contabil_id = contas_plano.get(conta_norm)
        if conta_contabil_id:
            contas_casadas += 1
        else:
            contas_nao_encontradas.append(row["conta_raw"])

        registro = existentes.get(conta_norm)
        if registro is None:
            registro = BalanceteConta(
                empresa_id=empresa_id,
                periodo=periodo,
                conta_codigo_normalizado=conta_norm,
            )
            db.add(registro)
            existentes[conta_norm] = registro

        registro.conta_contabil_id = conta_contabil_id
        registro.conta_codigo_raw = row["conta_raw"]
        registro.descricao = row["descricao"]
        registro.saldo_anterior = row["saldo_anterior"]
        registro.debito = row["debito"]
        registro.credito = row["credito"]
        registro.mov_periodo = row["mov_periodo"]
        registro.saldo_atual = row["saldo_atual"]

    db.commit()

    resultado = {
        "periodo": periodo.isoformat(),
        "total_linhas": len(df_norm),
        "contas_casadas": contas_casadas,
        "contas_nao_encontradas": contas_nao_encontradas,
    }
    logger.info("[BALANCETE] Importacao empresa=%s periodo=%s: %s", empresa_id, periodo, resultado)
    return resultado


def obter_balancete_conta(
    db: Session,
    empresa_id: int,
    conta_contabil_id: int,
    data_base: str,
) -> BalanceteConta | None:
    """Retorna o registro do balancete para a conta+periodo, se existir."""
    periodo = _primeiro_dia_mes_de_data_base(data_base)
    return db.query(BalanceteConta).filter(
        BalanceteConta.empresa_id == empresa_id,
        BalanceteConta.conta_contabil_id == conta_contabil_id,
        BalanceteConta.periodo == periodo,
    ).first()


def validar_saldo_calculado(
    db: Session,
    empresa_id: int | None,
    conta_contabil_id: int | None,
    data_base: str,
    movimentos_periodo: float,
    saldo_final_origem: float | None = None,
) -> dict[str, Any] | None:
    """
    Compara saldo_anterior (balancete) + movimentos_periodo (calculado a partir dos
    arquivos conciliados) com o saldo_atual do balancete importado.

    Se `saldo_final_origem` for informado (saldo atual que vem no final do proprio
    relatorio de origem, ex: extrato bancario FINR470) e ele bater com o saldo_atual
    do balancete, a conciliacao tambem e' considerada OK -- mesmo que o calculado
    (saldo_anterior + movimentos_periodo) nao bata. O relatorio de origem fechando
    no mesmo saldo do balancete e' por si so um sinal valido de que o periodo
    concilia, independente de eventuais divergencias internas dos lancamentos.

    Retorna None quando nao ha empresa/conta informada ou nao ha balancete
    importado para a conta+periodo (nao bloqueia o processamento, e informativo).
    """
    if not empresa_id or not conta_contabil_id:
        return None

    balancete = obter_balancete_conta(db, empresa_id, conta_contabil_id, data_base)
    if not balancete:
        return None

    saldo_anterior = float(balancete.saldo_anterior)
    saldo_atual = float(balancete.saldo_atual)
    saldo_calculado = saldo_anterior + movimentos_periodo
    diferenca = saldo_atual - saldo_calculado

    bate_calculado = abs(diferenca) <= 0.01
    bate_origem = (
        saldo_final_origem is not None
        and abs(saldo_atual - float(saldo_final_origem)) <= 0.01
    )

    return {
        "balancete_saldo_anterior": round(saldo_anterior, 2),
        "balancete_saldo_atual": round(saldo_atual, 2),
        "saldo_calculado_balancete": round(saldo_calculado, 2),
        "diferenca_balancete": round(diferenca, 2),
        "saldo_final_origem": round(float(saldo_final_origem), 2) if saldo_final_origem is not None else None,
        "balancete_bate_origem": bate_origem,
        "balancete_bate": bate_calculado or bate_origem,
    }
