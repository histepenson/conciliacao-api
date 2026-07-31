# services/estrategias/rancheiro/abate_croms051.py
"""
Particularidade exclusiva da Rancheiro: abater o CROMS051 (Conta Corrente
Desconto) do saldo financeiro na Conciliacao de Clientes.

Isolado aqui (fora de services/conciliacao_service.py) para que o service
generico nunca precise saber que essa regra existe - ela so entra em jogo
quando o router escolhe ConciliacaoServiceRancheiro (empresa com a chave
tem_croms051 habilitada em empresa_configuracao).
"""
from typing import Optional

import pandas as pd

from schemas.conciliacao_schema import RequestConciliacao
from services.conciliacao_service import ConciliacaoService
from tools.financeiro.base import formatar_codigo


def _calcular_abatimento_por_codigo(registros: list[dict]) -> dict[str, float]:
    """
    Agrupa as linhas do CROMS051 por codigo de cliente (C+base+loja) e soma o
    saldo (valor - valor_associacao).

    Aceita tanto linhas brutas ja tratadas por aplicar_tratativas_croms051
    (com "valor"/"valor_associacao") quanto linhas ja agregadas por cliente
    via agrupar_croms051_por_cliente (com "saldo" direto) -- usado quando a
    carga tem centenas de milhares de linhas e o resumo por cliente e' buscado
    pronto do backend em vez de recalculado a partir do bruto.

    Nas linhas tratadas (DESC PAGO = SIM ou origem SOPAG), valor e
    valor_associacao ja foram igualados, entao o saldo fica zerado e nao
    afeta o abatimento - esses descontos ja foram pagos no financeiro. Nas
    demais linhas, o saldo reflete o desconto ainda pendente, que deve ser
    abatido do financeiro.
    """
    abatimento: dict[str, float] = {}
    for linha in registros:
        base = str(linha.get("codigo_cliente", "")).strip()
        loja = str(linha.get("loja", "")).strip()
        if not base:
            continue
        codigo = formatar_codigo(base, loja, prefixo="C")
        if "saldo" in linha:
            saldo = float(linha.get("saldo") or 0)
        else:
            valor = float(linha.get("valor") or 0)
            valor_associacao = float(linha.get("valor_associacao") or 0)
            saldo = valor - valor_associacao
        abatimento[codigo] = abatimento.get(codigo, 0.0) + saldo
    return abatimento


def _aplicar_abatimento(df: pd.DataFrame, abatimento: dict[str, float]) -> pd.DataFrame:
    if df.empty or not abatimento:
        return df
    df = df.copy()
    df["valor"] = df["valor"] - df["codigo"].map(abatimento).fillna(0)
    return df


class ConciliacaoServiceRancheiro(ConciliacaoService):
    """Variante da Conciliacao de Clientes exclusiva da Rancheiro."""

    def _aplicar_ajuste_financeiro(
        self,
        request: RequestConciliacao,
        financeiro_norm: pd.DataFrame,
        df_fin_mes: Optional[pd.DataFrame],
    ) -> tuple[pd.DataFrame, Optional[pd.DataFrame]]:
        if not request.base_croms051 or not request.base_croms051.registros:
            return financeiro_norm, df_fin_mes

        abatimento = _calcular_abatimento_por_codigo(request.base_croms051.registros)
        financeiro_norm = _aplicar_abatimento(financeiro_norm, abatimento)
        if df_fin_mes is not None and not df_fin_mes.empty:
            df_fin_mes = _aplicar_abatimento(df_fin_mes, abatimento)

        return financeiro_norm, df_fin_mes
