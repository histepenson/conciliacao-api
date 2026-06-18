"""
Servico de Conciliacao de Impostos.

Compara, para uma unica conta contabil de imposto, os lancamentos a debito do
razao contabil (CT2RAZCT5) contra uma coluna de valor do SFT (Entradas Fiscais)
escolhida pelo usuario - ex: Valor ICMS, Valor PIS, Valor COFINS, Valor IPI.

O matching e feito nota a nota via CT2_KEY, reaproveitando a mesma logica usada
na Pre-Conferencia (tools/fiscal/match_ct2_sft.py).
"""

import logging
from typing import Dict, Any

from schemas.conciliacao_impostos_schema import RequestConciliacaoImpostos
from tools.fiscal.match_ct2_sft import match_ct2_sft

logger = logging.getLogger(__name__)

# Colunas de imposto disponiveis no SFT para o usuario escolher, por conta contabil.
COLUNAS_IMPOSTO_SFT = {
    "valicm": "Valor ICMS",
    "valipi": "Valor IPI",
    "valpis": "Valor PIS",
    "valcof": "Valor COFINS",
    "icmsret": "ICMS Retido",
    "difal": "Difal ICMS",
}


def _classificar_tipo_mov(registro: Dict[str, Any]) -> str:
    """
    Classifica um registro do SFT como "ENTRADA" ou "SAIDA".

    Usa o campo "tipo_mov" do registro se ja vier preenchido (alguns layouts
    manuais ja trazem essa coluna); caso contrario, deriva pelo primeiro
    digito do CFOP (1/2/3 = Entrada, 5/6/7 = Saida - convencao fiscal padrao).
    """
    valor = str(registro.get("tipo_mov") or "").strip().upper()
    if valor in ("ENTRADA", "E", "1"):
        return "ENTRADA"
    if valor in ("SAIDA", "SAÍDA", "S", "2"):
        return "SAIDA"

    cfop = str(registro.get("cfop") or "").strip()
    if cfop[:1] in ("1", "2", "3"):
        return "ENTRADA"
    if cfop[:1] in ("5", "6", "7"):
        return "SAIDA"
    return ""


class ConciliacaoImpostosService:
    """Servico para processar conciliacao de impostos."""

    def validar_dados(self, request: RequestConciliacaoImpostos) -> tuple[bool, str]:
        if not request.base_sft or not request.base_sft.registros:
            return False, "Base do SFT vazia"

        if not request.base_razao or not request.base_razao.registros:
            return False, "Base do razao contabil vazia"

        if not request.parametros or not request.parametros.data_base:
            return False, "Data-base nao informada"

        campo = request.parametros.campo_imposto
        if not campo or campo not in COLUNAS_IMPOSTO_SFT:
            opcoes = ", ".join(COLUNAS_IMPOSTO_SFT.keys())
            return False, f"campo_imposto invalido: '{campo}'. Use um de: {opcoes}"

        return True, ""

    def executar(self, request: RequestConciliacaoImpostos) -> Dict[str, Any]:
        """
        Executa a conciliacao de impostos.

        Fluxo:
        1. Filtra o razao pela conta contabil da tela e mantem so lancamentos a debito.
        2. Casa cada lancamento de debito com uma nota do SFT via CT2_KEY, comparando
           contra a coluna de imposto escolhida.
        3. Monta resumo (totais e diferenca) e lista os itens sem correspondencia.
        """
        conta_contabil = request.base_razao.conta_contabil
        campo_imposto = request.parametros.campo_imposto

        logger.info("=" * 50)
        logger.info(f"CONCILIACAO DE IMPOSTOS - INICIO - conta={conta_contabil} campo={campo_imposto}")
        logger.info("=" * 50)

        # ==========================
        # 1. FILTRAR RAZAO (conta + debito/credito)
        # ==========================
        tipo_mov_filtro = (request.parametros.tipo_mov or "").strip().upper()

        # Nota de Entrada gera lancamento a debito (ex: imposto a recuperar);
        # nota de Saida gera lancamento a credito (ex: imposto a recolher).
        coluna_razao = "credito" if tipo_mov_filtro == "SAIDA" else "debito"
        coluna_razao_label = "Credito" if coluna_razao == "credito" else "Debito"

        razao_raw = request.base_razao.registros
        razao_da_conta = [
            r for r in razao_raw
            if str(r.get("conta") or "").strip() == conta_contabil.strip()
        ]
        razao_filtrado = [
            r for r in razao_da_conta
            if round(float(r.get(coluna_razao) or 0), 2) > 0
        ]
        logger.info(f"[1/2] Razao: {len(razao_raw)} lancamentos recebidos, {len(razao_filtrado)} a {coluna_razao} da conta {conta_contabil}")

        # Totais de debito/credito da conta, independente da coluna usada no matching
        # -- exibidos sempre no resumo para o usuario ver os dois lados.
        total_debito_conta = round(sum(float(r.get("debito") or 0) for r in razao_da_conta), 2)
        total_credito_conta = round(sum(float(r.get("credito") or 0) for r in razao_da_conta), 2)

        sft_raw = request.base_sft.registros
        logger.info(f"      SFT: {len(sft_raw)} registros recebidos")

        # ICMS: soma "Valor ICMS" + "Vlr ICMS Com" (icmscom) -- o ICMS proprio
        # cobrado na nota pode vir parte em "valicm" e parte em "icmscom"
        # (operacoes com substituicao/complemento), e a coluna escolhida pelo
        # usuario deve refletir o total do imposto, nao so uma das parcelas.
        if campo_imposto == "valicm":
            sft_raw = [
                {**r, "valicm": round(float(r.get("valicm") or 0) + float(r.get("icmscom") or 0), 2)}
                for r in sft_raw
            ]

        if tipo_mov_filtro in ("ENTRADA", "SAIDA"):
            sft_raw = [r for r in sft_raw if _classificar_tipo_mov(r) == tipo_mov_filtro]
            logger.info(f"      SFT filtrado por Tipo Mov={tipo_mov_filtro}: {len(sft_raw)} registros")

        # ==========================
        # 2. MATCHING via CT2_KEY
        # ==========================
        logger.info("[2/2] Casando lancamentos via CT2_KEY")
        razao_resultado, sft_resultado = match_ct2_sft(
            razao_filtrado, sft_raw, campo_valor_sft=campo_imposto, campo_valor_ct2=coluna_razao
        )

        total_lancamento_razao = round(sum(float(r.get(coluna_razao) or 0) for r in razao_resultado), 2)
        total_sft = round(sum(float(s.get(campo_imposto) or 0) for s in sft_resultado), 2)
        diferenca = round(total_lancamento_razao - total_sft, 2)
        situacao = "CONCILIADO" if abs(diferenca) <= 0.01 else "DIVERGENTE"

        # Lancamentos individuais (mesmo padrao da grid de razao da conciliacao
        # financeira/contas a pagar: um lancamento por linha, sem agrupar).
        diferencas_so_razao = [r for r in razao_resultado if not r["matched"]]
        diferencas_so_sft = self._agrupar_sft(
            [
                s for s in sft_resultado
                if not s["matched"] and round(float(s.get(campo_imposto) or 0), 2) != 0
            ],
            campo_imposto,
        )
        qtd_matched = sum(1 for r in razao_resultado if r["matched"])

        resumo = {
            "campo_imposto": campo_imposto,
            "campo_imposto_label": COLUNAS_IMPOSTO_SFT.get(campo_imposto, campo_imposto),
            "tipo_mov": tipo_mov_filtro,
            "coluna_razao": coluna_razao,
            "coluna_razao_label": coluna_razao_label,
            "total_lancamento_razao": total_lancamento_razao,
            "total_debito_razao": total_debito_conta,
            "total_credito_razao": total_credito_conta,
            "total_sft": total_sft,
            "diferenca": diferenca,
            "situacao": situacao,
            "qtd_lancamentos_razao": len(razao_resultado),
            "qtd_registros_sft": len(sft_resultado),
            "qtd_matched": qtd_matched,
            "qtd_so_razao": len(diferencas_so_razao),
            "qtd_so_sft": len(diferencas_so_sft),
        }

        resposta = {
            "resumo": resumo,
            "diferencas_so_razao": diferencas_so_razao,
            "diferencas_so_sft": diferencas_so_sft,
            "observacoes": [
                f"Conciliacao de impostos da conta {conta_contabil}",
                f"Coluna SFT considerada: {COLUNAS_IMPOSTO_SFT.get(campo_imposto, campo_imposto)}",
                f"Coluna do Razao considerada: {coluna_razao_label}",
                f"Data-base: {request.parametros.data_base}",
                *([f"SFT filtrado por Tipo Mov: {'Entrada' if tipo_mov_filtro == 'ENTRADA' else 'Saida'}"] if tipo_mov_filtro in ("ENTRADA", "SAIDA") else []),
            ],
            "alertas": self._gerar_alertas(resumo),
        }

        logger.info("=" * 50)
        logger.info(f"CONCILIACAO DE IMPOSTOS - {situacao} - diferenca={diferenca}")
        logger.info("=" * 50)

        return resposta

    def _agrupar_sft(self, registros: list, campo_imposto: str) -> list:
        """Aglutina notas do SFT sem correspondencia por (filial, nf, fornecedor)."""
        grupos: Dict[tuple, list] = {}
        for s in registros:
            filial = str(s.get("filial") or "").strip()
            nf = str(s.get("nf") or "").strip()
            cliefor = str(s.get("cliefor") or "").strip()
            grupos.setdefault((filial, nf, cliefor), []).append(s)

        agrupados = []
        for (filial, nf, cliefor), itens in grupos.items():
            agrupados.append({
                "filial": filial,
                "nf": nf,
                "cliefor": cliefor,
                campo_imposto: round(sum(float(i.get(campo_imposto) or 0) for i in itens), 2),
                "qtd_itens": len(itens),
            })

        return agrupados

    def _gerar_alertas(self, resumo: Dict[str, Any]) -> list:
        alertas = []

        if abs(resumo["diferenca"]) > 0.01:
            alertas.append(f"Diferenca entre razao e SFT: R$ {resumo['diferenca']:,.2f}")

        if resumo["qtd_so_razao"] > 0:
            alertas.append(f"{resumo['qtd_so_razao']} lancamento(s) do razao sem correspondencia no SFT")

        if resumo["qtd_so_sft"] > 0:
            alertas.append(f"{resumo['qtd_so_sft']} registro(s) do SFT sem correspondencia no razao")

        if not alertas:
            alertas.append("Conciliacao OK - razao e SFT conferem")

        return alertas
