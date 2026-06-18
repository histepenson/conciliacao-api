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
        # 1. FILTRAR RAZAO (conta + debito)
        # ==========================
        razao_raw = request.base_razao.registros
        razao_debito = [
            r for r in razao_raw
            if str(r.get("conta") or "").strip() == conta_contabil.strip()
            and round(float(r.get("debito") or 0), 2) > 0
        ]
        logger.info(f"[1/2] Razao: {len(razao_raw)} lancamentos recebidos, {len(razao_debito)} a debito da conta {conta_contabil}")

        sft_raw = request.base_sft.registros
        logger.info(f"      SFT: {len(sft_raw)} registros recebidos")

        # ==========================
        # 2. MATCHING via CT2_KEY
        # ==========================
        logger.info("[2/2] Casando lancamentos via CT2_KEY")
        razao_resultado, sft_resultado = match_ct2_sft(
            razao_debito, sft_raw, campo_valor_sft=campo_imposto
        )

        total_debito_razao = round(sum(float(r.get("debito") or 0) for r in razao_resultado), 2)
        total_sft = round(sum(float(s.get(campo_imposto) or 0) for s in sft_resultado), 2)
        diferenca = round(total_debito_razao - total_sft, 2)
        situacao = "CONCILIADO" if abs(diferenca) <= 0.01 else "DIVERGENTE"

        diferencas_so_razao = self._agrupar_razao(
            [r for r in razao_resultado if not r["matched"]]
        )
        diferencas_so_sft = self._agrupar_sft(
            [s for s in sft_resultado if not s["matched"]], campo_imposto
        )
        qtd_matched = sum(1 for r in razao_resultado if r["matched"])

        resumo = {
            "campo_imposto": campo_imposto,
            "campo_imposto_label": COLUNAS_IMPOSTO_SFT.get(campo_imposto, campo_imposto),
            "total_debito_razao": total_debito_razao,
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
                f"Data-base: {request.parametros.data_base}",
            ],
            "alertas": self._gerar_alertas(resumo),
        }

        logger.info("=" * 50)
        logger.info(f"CONCILIACAO DE IMPOSTOS - {situacao} - diferenca={diferenca}")
        logger.info("=" * 50)

        return resposta

    @staticmethod
    def _extrair_chave_ct2(rec: Dict[str, Any]):
        key = str(rec.get("ct2_key") or "").strip()
        if len(key) < 22:
            return None
        return (key[0:4], key[4:13].strip(), key[16:22].strip())

    def _agrupar_razao(self, registros: list) -> list:
        """Aglutina lancamentos do razao sem correspondencia por (filial, nf, fornecedor)."""
        grupos: Dict[tuple, list] = {}
        sem_chave = []
        for r in registros:
            chave = self._extrair_chave_ct2(r)
            if chave is None:
                sem_chave.append(r)
                continue
            grupos.setdefault(chave, []).append(r)

        agrupados = []
        for (filial, nf, fornece), itens in grupos.items():
            agrupados.append({
                "filial": filial,
                "nf": nf,
                "cliefor": fornece,
                "historico": itens[0].get("historico"),
                "debito": round(sum(float(i.get("debito") or 0) for i in itens), 2),
                "qtd_lancamentos": len(itens),
                "ct2_key": itens[0].get("ct2_key"),
            })

        return agrupados + sem_chave

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
