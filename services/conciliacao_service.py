import logging
import re
from datetime import datetime
from typing import Optional

import pandas as pd

from schemas.conciliacao_schema import RequestConciliacao
from services.analise_diferencas_service import AnaliseDiferencasService
from services.ctbr480_service import Ctbr480Service
from core.config import settings
from core.protheus import ProtheusConfig
from tools.calc_diferencas import calcular_diferencas
from tools.contabilidade import normalizar_planilha_contabilidade
from tools.financeiro import (
    normalizar_planilha_financeira,
    normalizar_planilha_financeira_detalhada,
)
from tools.financeiro.factory import (
    get_processador_por_nome,
    TipoFinanceiro,
    validar_layout_planilha,
)
from tools.financeiro.base import corrigir_header_titulo
from tools.mappers import map_origem_maior

logger = logging.getLogger(__name__)


class ConciliacaoService:

    # ==================================================
    # VALIDACAO
    # ==================================================
    def validar_dados(self, request: RequestConciliacao) -> tuple[bool, str]:
        if not request.base_origem or not request.base_origem.registros:
            return False, "Base de origem vazia"

        if not request.base_contabil_filtrada or not request.base_contabil_filtrada.registros:
            return False, "Base contabil filtrada vazia"

        # base_contabil_geral pode vir vazia (conta sem lancamentos no periodo --
        # nesse caso ainda e' possivel fazer o comparativo de saldos, so' fica
        # sem a analise detalhada por linha de razao) ou quando ctbr480_params
        # esta preenchido (busca automatica no Protheus, resolvida em executar_async).

        if not request.parametros or not request.parametros.get("data_base"):
            return False, "Data-base nao informada"

        return True, ""

    def _filtrar_razao_por_conta(self, df_razao: pd.DataFrame, conta_contabil: str) -> pd.DataFrame:
        """Filtra o razao pela conta contabil sendo conciliada, se a coluna existir."""
        if df_razao.empty:
            return df_razao

        colunas_candidatas = ["conta_contabil", "Conta Contabil", "conta"]
        coluna_conta: Optional[str] = next((c for c in colunas_candidatas if c in df_razao.columns), None)

        if not coluna_conta:
            logger.info("[ANALISE DETALHADA] Coluna de conta nao encontrada no razao; usando razao completo")
            return df_razao

        df_filtrado = df_razao[df_razao[coluna_conta].astype(str) == str(conta_contabil)].copy()
        logger.info(
            "[ANALISE DETALHADA] Razao filtrado por conta %s: %s -> %s registros",
            conta_contabil,
            len(df_razao),
            len(df_filtrado),
        )
        return df_filtrado

    def _formatar_resumo_analise(self, total: int, conciliados: int) -> dict:
        divergentes = int(total - conciliados)
        percentual = (conciliados / total * 100) if total else 0.0
        return {
            "total_registros": int(total),
            "total": int(total),
            "conciliados": int(conciliados),
            "divergentes": int(divergentes),
            "percentual_conciliacao": round(percentual, 2),
            "percentual": round(percentual, 2),
        }

    def _mes_analise_from_parametros(self, parametros: dict) -> Optional[str]:
        """Retorna mes_analise (YYYYMM) dos parametros ou deriva de data_base."""
        mes = parametros.get("mes_analise")
        if mes:
            return str(mes).strip()
        data_base = str(parametros.get("data_base", "")).strip()
        if len(data_base) >= 6:
            return data_base[:6]
        return None

    def _filtrar_financeiro_por_mes(
        self, df_detalhado: pd.DataFrame, mes_analise: str
    ) -> pd.DataFrame:
        """
        Filtra registros pelo mes/ano de data_emissao e agrega por codigo.
        Retorna DataFrame com colunas: codigo, cliente, valor.
        """
        if df_detalhado is None or df_detalhado.empty:
            return pd.DataFrame(columns=["codigo", "cliente", "valor"])

        if "data_emissao" not in df_detalhado.columns:
            logger.warning("[MES] Coluna data_emissao ausente; usando financeiro completo")
            return df_detalhado

        try:
            ano = int(mes_analise[:4])
            mes = int(mes_analise[4:6])
        except (ValueError, TypeError, IndexError):
            logger.warning("[MES] mes_analise invalido: %s", mes_analise)
            return df_detalhado

        datas = pd.to_datetime(df_detalhado["data_emissao"], errors="coerce")
        mask = (datas.dt.month == mes) & (datas.dt.year == ano)
        df_filtrado = df_detalhado[mask].copy()

        logger.info(
            "[MES] Filtro emissao %s/%s: %s/%s registros",
            mes, ano, len(df_filtrado), len(df_detalhado),
        )

        if df_filtrado.empty:
            return pd.DataFrame(columns=["codigo", "cliente", "valor"])

        return df_filtrado.groupby("codigo", as_index=False).agg(
            cliente=("cliente", "first"),
            valor=("valor", "sum"),
        )

    def _gerar_resumo_analise_fallback(self, df_completo: pd.DataFrame) -> dict:
        """Gera resumo da analise diretamente do df_completo, sem depender da analise detalhada."""
        if df_completo is None or df_completo.empty:
            return self._formatar_resumo_analise(total=0, conciliados=0)

        dif_abs = pd.to_numeric(df_completo.get("Diferenca Absoluta"), errors="coerce").fillna(0.0)
        conciliados = int((dif_abs <= 0.01).sum())
        total = int(len(df_completo))
        resumo = self._formatar_resumo_analise(total=total, conciliados=conciliados)
        logger.info("[ANALISE DETALHADA] Resumo fallback: %s", resumo)
        return resumo

    # ==================================================
    # BUSCA AUTOMATICA DO CTBR480 (RAZAO GERAL)
    # ==================================================
    async def _buscar_razao_geral_protheus(
        self, request: RequestConciliacao, config: ProtheusConfig
    ) -> list[dict]:
        """
        Se base_contabil_geral.ctbr480_params estiver preenchido, busca o razao
        contabil diretamente do Protheus via ZCTBR480API e retorna os registros.
        Caso contrario, retorna os registros ja presentes em base_contabil_geral.registros.
        """
        geral = request.base_contabil_geral
        if not geral:
            return []

        params = geral.ctbr480_params
        if not params:
            return geral.registros

        logger.info(" base_contabil_geral.ctbr480_params detectado -- buscando CTBR480 do Protheus")
        protheus_url = params.protheus_url or config.url
        if not protheus_url:
            raise ValueError(
                "CTBR480 automatico requer URL do Protheus configurada na empresa."
            )

        service = Ctbr480Service(
            protheus_base_url=protheus_url,
            user=config.user,
            password=config.password,
            tenant_id=config.tenant,
            rest_prefix=config.rest_prefix,
        )
        query = {
            "data_fim": params.data_fim,
            "data_ini": params.data_ini,
            "item_de": params.item_de,
            "item_ate": params.item_ate,
            "conta_de": params.conta_de,
            "conta_ate": params.conta_ate,
            "custo_de": params.custo_de,
            "custo_ate": params.custo_ate,
            "clvl_de": params.clvl_de,
            "clvl_ate": params.clvl_ate,
            "moeda": params.moeda,
            "saldo": params.saldo,
            "vlr_zerado": params.vlr_zerado,
            "consid_filiais": params.consid_filiais,
            "filial_de": params.filial_de,
            "filial_ate": params.filial_ate,
        }
        registros = await service.buscar_como_registros(query)
        logger.info(" CTBR480 Protheus: %s lancamentos recebidos", len(registros))
        return registros

    # ==================================================
    # EXECUCAO ASSINCRONA (suporta ctbr480_params)
    # ==================================================
    async def executar_async(self, request: RequestConciliacao, config: ProtheusConfig) -> dict:
        """
        Versao assincrona do executar() com suporte a busca automatica do CTBR480.
        Quando base_contabil_geral.ctbr480_params estiver preenchido, busca o razao
        diretamente do Protheus antes de executar a conciliacao.
        """
        # Injeta registros do Protheus se ctbr480_params estiver presente
        if request.base_contabil_geral and request.base_contabil_geral.ctbr480_params:
            registros = await self._buscar_razao_geral_protheus(request, config)
            request.base_contabil_geral.registros = registros

        return self.executar(request)

    # ==================================================
    # EXECUCAO PRINCIPAL
    # ==================================================
    def executar(self, request: RequestConciliacao) -> dict:
        """
        Retorna dict para compatibilidade com o frontend.
        """
        logger.info(" Executando conciliacao contabil")

        # ==========================
        # 1 NORMALIZAR FINANCEIRO
        # ==========================
        df_financeiro_raw = pd.DataFrame(request.base_origem.registros)
        logger.info(" Registros origem recebidos: %s", len(df_financeiro_raw))

        # Corrigir header caso o arquivo tenha linha de titulo (ex: "Titulos a Pagar")
        df_financeiro_raw = corrigir_header_titulo(df_financeiro_raw)
        logger.info(" Registros apos corrigir header: %s colunas: %s", len(df_financeiro_raw), list(df_financeiro_raw.columns)[:5])

        # Detectar tipo financeiro (contas_receber ou contas_pagar)
        tipo_financeiro = request.parametros.get("tipo_financeiro", "contas_receber")
        # Tambem verificar no base_origem.tipo para retrocompatibilidade
        if hasattr(request.base_origem, "tipo") and request.base_origem.tipo:
            tipo_financeiro = request.base_origem.tipo
        logger.info(" Tipo financeiro: %s", tipo_financeiro)

        # Validar layout do arquivo financeiro ANTES de processar
        validacao_layout = validar_layout_planilha(df_financeiro_raw, tipo_financeiro)
        if not validacao_layout.valido:
            logger.error(" Layout invalido: %s", validacao_layout.mensagem)
            raise ValueError(
                f"Layout do arquivo financeiro invalido: {validacao_layout.mensagem} "
                f"Colunas encontradas no arquivo: {validacao_layout.colunas_arquivo}"
            )

        if validacao_layout.avisos:
            for aviso in validacao_layout.avisos:
                logger.warning(" %s", aviso)

        # Usar o processador apropriado via factory
        try:
            processador = get_processador_por_nome(tipo_financeiro)
            financeiro_norm = processador.normalizar(df_financeiro_raw)
            financeiro_detalhado = processador.normalizar_detalhado(df_financeiro_raw)
            logger.info(" %s normalizado via factory: %s registros", tipo_financeiro.upper(), len(financeiro_norm))
        except ValueError as e:
            # Se for erro de layout, propagar com mensagem clara
            if "coluna" in str(e).lower() or "encontrada" in str(e).lower():
                raise ValueError(f"Erro no layout do arquivo financeiro: {str(e)}")
            # Fallback para o metodo legado (contas a receber) se tipo nao reconhecido
            logger.warning(" Tipo '%s' nao reconhecido, usando processador padrao (contas_receber)", tipo_financeiro)
            financeiro_norm = normalizar_planilha_financeira(df_financeiro_raw)
            financeiro_detalhado = normalizar_planilha_financeira_detalhada(df_financeiro_raw)
            logger.info(" Financeiro normalizado (legado): %s registros", len(financeiro_norm))

        # ==========================
        # 1.5 FILTRAR EMISSAO DO MES
        # ==========================
        mes_analise = self._mes_analise_from_parametros(request.parametros or {})
        df_fin_mes: Optional[pd.DataFrame] = None
        if mes_analise:
            df_fin_mes = self._filtrar_financeiro_por_mes(financeiro_detalhado, mes_analise)
            logger.info(
                "[MES] df_fin_mes: %s codigos, valor total: %.2f",
                len(df_fin_mes),
                float(df_fin_mes["valor"].sum()) if not df_fin_mes.empty else 0.0,
            )

        # ==========================
        # 2 NORMALIZAR CONTABILIDADE
        # ==========================
        df_contabil_raw = pd.DataFrame(request.base_contabil_filtrada.registros)
        logger.info(" Registros contabeis recebidos: %s", len(df_contabil_raw))

        contabil_norm = normalizar_planilha_contabilidade(df_contabil_raw)
        logger.info(" Contabilidade normalizada: %s registros", len(contabil_norm))

        # ==========================
        # 3 CALCULAR DIFERENCAS
        # ==========================
        resultado = calcular_diferencas(
            df_financeiro=financeiro_norm,
            df_contabilidade=contabil_norm,
            salvar_arquivo=False,
        )

        resumo_calc = resultado["resumo"]
        df_completo = resultado["df_completo"]

        logger.info(" Resumo calculado: %s", resumo_calc)
        logger.info(" Colunas do df_completo: %s", df_completo.columns.tolist())

        # ==========================
        # 4 FILTRAR DIFERENCAS
        # ==========================
        df_origem_maior = df_completo[
            df_completo["Tipo Diferenca"] == "Financeiro > Contabilidade"
        ].copy()

        df_contabil_maior = df_completo[
            df_completo["Tipo Diferenca"] == "Contabilidade > Financeiro"
        ].copy()

        logger.info(" Diferencas Origem > Contabil: %s", len(df_origem_maior))
        logger.info(" Diferencas Contabil > Origem: %s", len(df_contabil_maior))

        # ==========================
        # 5 MAPEAR DIFERENCAS (SCHEMA)
        # ==========================
        diferencas_origem_maior = []
        for row_dict in df_origem_maior.to_dict("records"):
            try:
                mapped = map_origem_maior(row_dict)
                diferencas_origem_maior.append(mapped)
            except Exception as exc:
                logger.error(" Erro ao mapear origem_maior: %s", exc)
                logger.error("   Row problematico: %s", row_dict)

        diferencas_contabilidade_maior = []
        conta_contabil = request.base_contabil_filtrada.conta_contabil
        for row_dict in df_contabil_maior.to_dict("records"):
            try:
                diferencas_contabilidade_maior.append(
                    {
                        "identificador": str(row_dict.get("Codigo", "")).strip(),
                        "data": None,
                        "valor": float(row_dict.get("Diferenca", 0) or 0),
                        "conta_contabil": conta_contabil,
                        "historico": "Valor maior na Contabilidade",
                        "existe_origem": False,
                        "verificacoes_realizadas": ["Comparacao por codigo"],
                        "situacao": "DIVERGENTE",
                    }
                )
            except Exception as exc:
                logger.error(" Erro ao mapear contabil_maior: %s", exc)
                logger.error("   Row problematico: %s", row_dict)

        logger.info(
            " Mapeados: %s origem_maior, %s contabil_maior",
            len(diferencas_origem_maior),
            len(diferencas_contabilidade_maior),
        )

        # ==========================
        # 6 RESUMO (FORMATO FRONTEND)
        # ==========================
        total_origem = float(resumo_calc.get("valor_total_financeiro", 0) or 0)
        total_destino = float(resumo_calc.get("valor_total_contabilidade", 0) or 0)
        diferenca = abs(total_destino) - abs(total_origem)

        percentual_divergencia = abs(diferenca) / abs(total_origem) * 100 if total_origem else 0.0

        situacao = "CONCILIADO" if abs(diferenca) <= 0.01 else "DIVERGENTE"

        resumo = {
            "total_origem": round(total_origem, 2),
            "total_destino": round(total_destino, 2),
            "diferenca": round(diferenca, 2),
            "situacao": situacao,
            "percentual_divergencia": round(percentual_divergencia, 2),
            "quantidade_registros_origem": int(resumo_calc.get("registros_so_financeiro", 0) or 0),
            "quantidade_registros_destino": int(resumo_calc.get("registros_so_contabilidade", 0) or 0),
            "data_processamento": datetime.now().isoformat(),
        }

        logger.info(" Resumo final: %s", resumo)

        # ==========================
        # 7 ANALISE DETALHADA (RESTAURO)
        # ==========================
        analise_detalhada = []
        analise_profunda_contabil = []
        resumo_analise = self._gerar_resumo_analise_fallback(df_completo)
        try:
            df_razao_geral = pd.DataFrame(request.base_contabil_geral.registros)
            df_razao_geral = corrigir_header_titulo(df_razao_geral)
            df_razao_filtrado = self._filtrar_razao_por_conta(df_razao_geral, conta_contabil)

            analise_service = AnaliseDiferencasService()
            # Usa financeiro filtrado pelo mes de emissao para comparar com CTBR480
            # (que ja contem apenas o mes de analise); se nao houver filtro, usa o completo
            df_fin_para_analise = (
                df_fin_mes
                if (df_fin_mes is not None and not df_fin_mes.empty)
                else financeiro_norm
            )

            # Mapa de saldo anterior por codigo (item do CTBR140) para o grid de Lancamentos Razao
            saldo_ant_map: dict[str, float] = {}
            for reg in (request.base_contabil_filtrada.registros or []):
                codigo_raw = str(reg.get("Codigo", "")).strip()
                codigo_norm = re.sub(r"\s+", "", codigo_raw)
                saldo_ant_val = reg.get("Saldo anterior")
                if codigo_norm and saldo_ant_val is not None:
                    try:
                        saldo_ant_map[codigo_norm] = float(saldo_ant_val)
                    except (ValueError, TypeError):
                        pass

            analise_detalhada = analise_service.processar_analise_detalhada(
                df_financeiro=df_fin_para_analise,
                df_contabilidade_filtrada=contabil_norm,
                df_razao_contabil=df_razao_filtrado,
                df_financeiro_detalhado=financeiro_detalhado,
                df_razao_geral=df_razao_geral,
                conta_contabil=conta_contabil,
                data_base=request.parametros.get("data_base"),
                saldo_ant_map=saldo_ant_map if saldo_ant_map else None,
            )

            if analise_detalhada:
                resumo_analise = analise_service.gerar_resumo_analise(analise_detalhada)
            else:
                # Mesmo sem analise, manter resumo coerente com o total calculado
                resumo_analise = self._formatar_resumo_analise(total=len(df_completo), conciliados=0)

            # ==========================
            # 7.1 ANALISE PROFUNDA SO_CONTABILIDADE
            # ==========================
            # DEBUG: Verificar tipos de diferenca disponiveis
            tipos_encontrados = set(a.get("tipo_diferenca") for a in analise_detalhada)
            logger.info(" Tipos de diferenca encontrados: %s", tipos_encontrados)

            registros_so_contabilidade = [
                a for a in analise_detalhada
                if a.get("tipo_diferenca") == "SO_CONTABILIDADE"
            ]
            logger.info(" Registros SO_CONTABILIDADE encontrados: %s", len(registros_so_contabilidade))

            if registros_so_contabilidade:
                logger.info(
                    " Iniciando analise profunda de %s registros SO_CONTABILIDADE",
                    len(registros_so_contabilidade)
                )
                analise_profunda_contabil = analise_service.analisar_so_contabilidade_profundo(
                    registros_so_contabilidade=registros_so_contabilidade,
                    df_razao_geral=df_razao_geral,  # Usa razao geral COMPLETO para buscar origens
                    conta_analisada=conta_contabil,
                )
                logger.info(" Analise profunda concluida: %s registros", len(analise_profunda_contabil))

        except Exception as exc:
            logger.error(" Falha ao gerar analise detalhada: %s", exc, exc_info=True)

        # ==========================
        # 8 RETORNO FINAL (DICT)
        # ==========================
        analise_movimentos_mes: Optional[dict] = None
        if mes_analise and df_fin_mes is not None:
            analise_movimentos_mes = {
                "mes": mes_analise,
                "codigos_financeiro_mes": int(len(df_fin_mes)),
                "valor_financeiro_mes": round(float(df_fin_mes["valor"].sum()) if not df_fin_mes.empty else 0.0, 2),
                "codigos_financeiro_total": int(len(financeiro_norm)),
                "valor_financeiro_total": round(float(financeiro_norm["valor"].sum()), 2),
                "codigos_excluidos_outros_periodos": int(len(financeiro_norm)) - int(len(df_fin_mes)),
            }

        retorno = {
            "resumo": resumo,
            "diferencas_origem_maior": diferencas_origem_maior,
            "diferencas_contabilidade_maior": diferencas_contabilidade_maior,
            "analise_detalhada": analise_detalhada,
            "resumo_analise": resumo_analise,
            "analise_profunda_contabil": analise_profunda_contabil,
            "analise_movimentos_mes": analise_movimentos_mes,
            "observacoes": [
                f"Total de {len(diferencas_origem_maior)} registros onde origem > contabilidade",
                f"Total de {len(diferencas_contabilidade_maior)} registros onde contabilidade > origem",
                f"Percentual de divergencia: {percentual_divergencia:.2f}%",
                f"Total de {len(analise_profunda_contabil)} registros SO_CONTABILIDADE analisados em profundidade",
            ],
            "alertas": [
                " Verificar diferencas significativas"
                if abs(diferenca) > 1000
                else " Diferencas dentro do esperado"
            ],
        }

        logger.info(" Conciliacao executada com sucesso")
        logger.info(
            " Retorno final com %s origem_maior, %s contabil_maior, %s analise_detalhada, %s analise_profunda",
            len(diferencas_origem_maior),
            len(diferencas_contabilidade_maior),
            len(analise_detalhada),
            len(analise_profunda_contabil),
        )

        return retorno

