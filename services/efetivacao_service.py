"""
Service para efetivação de conciliações.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_

from models import Conciliacao, Empresa, PlanoDeContas, Usuario, AuditLog, AuditAction
from schemas.efetivacao_schema import (
    EfetivarConciliacaoRequest,
    ConciliacaoEfetivadaResumo,
    ConciliacaoEfetivadaDetalhe,
    StatusConciliacao,
    ValidacaoEfetivacaoResponse,
)
from services.file_storage_service import FileStorageService
from middleware.auth import CurrentUser

logger = logging.getLogger(__name__)


class EfetivacaoService:
    """Service para gerenciar efetivação de conciliações."""

    def __init__(self):
        self.file_storage = FileStorageService()

    def _parse_periodo(self, periodo: str) -> Tuple[int, int]:
        """
        Converte string de período para (ano, mes).

        Suporta formatos: "YYYY-MM" ou "MM/YYYY"
        """
        if "-" in periodo:
            parts = periodo.split("-")
            return int(parts[0]), int(parts[1])
        elif "/" in periodo:
            parts = periodo.split("/")
            return int(parts[1]), int(parts[0])
        else:
            raise ValueError(f"Formato de período inválido: {periodo}")

    def _normalize_periodo(self, periodo: str) -> str:
        """Normaliza período para formato YYYY-MM."""
        ano, mes = self._parse_periodo(periodo)
        return f"{ano}-{mes:02d}"

    def _validate_no_divergencias(self, resultado: Dict[str, Any]) -> ValidacaoEfetivacaoResponse:
        """Valida se não há divergências antes de efetivar."""
        resumo = resultado.get("resumo", {})
        situacao = resumo.get("situacao", "DIVERGENTE")
        diferenca = abs(resumo.get("diferenca", 0) or 0)

        diferencas_origem = len(resultado.get("diferencas_origem_maior", []))
        diferencas_contabil = len(resultado.get("diferencas_contabilidade_maior", []))
        total_divergencias = diferencas_origem + diferencas_contabil

        alertas = resultado.get("alertas", [])

        # Verifica se pode efetivar
        if situacao == "CONCILIADO" and total_divergencias == 0:
            return ValidacaoEfetivacaoResponse(
                pode_efetivar=True,
                motivo=None,
                divergencias=0,
                alertas=alertas
            )

        # Não pode efetivar
        motivos = []
        if situacao != "CONCILIADO":
            motivos.append(f"Situação atual: {situacao}, diferença de R$ {diferenca:.2f}")
        if total_divergencias > 0:
            motivos.append(f"{total_divergencias} divergências encontradas")

        return ValidacaoEfetivacaoResponse(
            pode_efetivar=False,
            motivo="; ".join(motivos),
            divergencias=total_divergencias,
            alertas=alertas
        )

    def _check_already_efetivada(
        self,
        db: Session,
        empresa_id: int,
        periodo: str,
        conta_contabil_id: int
    ) -> Optional[Conciliacao]:
        """Verifica se já existe conciliação efetivada para este período."""
        periodo_normalizado = self._normalize_periodo(periodo)
        return db.query(Conciliacao).filter(
            and_(
                Conciliacao.empresa_id == empresa_id,
                Conciliacao.periodo == periodo_normalizado,
                Conciliacao.conta_contabil_id == conta_contabil_id,
                Conciliacao.status == StatusConciliacao.EFETIVADA.value
            )
        ).first()

    def validar_efetivacao(
        self,
        db: Session,
        request: EfetivarConciliacaoRequest
    ) -> ValidacaoEfetivacaoResponse:
        """Valida se uma conciliação pode ser efetivada."""
        # Verifica se já foi efetivada
        existing = self._check_already_efetivada(
            db, request.empresa_id, request.periodo, request.conta_contabil_id
        )
        if existing:
            return ValidacaoEfetivacaoResponse(
                pode_efetivar=False,
                motivo=f"Conciliação já efetivada em {existing.data_efetivacao}",
                divergencias=0,
                alertas=["Período já possui conciliação efetivada"]
            )

        # Valida se não há divergências
        return self._validate_no_divergencias(request.resultado)

    def efetivar(
        self,
        db: Session,
        request: EfetivarConciliacaoRequest,
        current_user: CurrentUser,
        arquivo_origem: bytes,
        arquivo_contabil_filtrado: bytes,
        arquivo_contabil_geral: bytes,
        nome_origem: str,
        nome_contabil_filtrado: str,
        nome_contabil_geral: str
    ) -> Conciliacao:
        """
        Efetiva uma conciliação.

        Args:
            db: Sessão do banco de dados
            request: Dados da conciliação
            current_user: Usuário atual
            arquivo_origem: Bytes do arquivo original de origem
            arquivo_contabil_filtrado: Bytes do arquivo contábil filtrado
            arquivo_contabil_geral: Bytes do arquivo contábil geral
            nome_origem: Nome original do arquivo de origem
            nome_contabil_filtrado: Nome original do arquivo contábil filtrado
            nome_contabil_geral: Nome original do arquivo contábil geral

        Returns:
            Conciliação efetivada
        """
        # Validar
        validacao = self.validar_efetivacao(db, request)
        if not validacao.pode_efetivar:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Não é possível efetivar: {validacao.motivo}"
            )

        # Parse período
        ano, mes = self._parse_periodo(request.periodo)
        periodo_normalizado = self._normalize_periodo(request.periodo)

        # Verificar conta contábil
        conta = db.query(PlanoDeContas).filter(PlanoDeContas.id == request.conta_contabil_id).first()
        if not conta:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conta contábil não encontrada"
            )

        # Criar DataFrames a partir dos registros normalizados
        df_origem = pd.DataFrame(request.base_origem.get("registros", []))
        df_contabil_filtrado = pd.DataFrame(request.base_contabil_filtrada.get("registros", []))
        df_contabil_geral = pd.DataFrame(request.base_contabil_geral.get("registros", []))

        # Salvar arquivos
        caminhos = self.file_storage.save_all_reconciliation_files(
            empresa_id=request.empresa_id,
            ano=ano,
            mes=mes,
            conta_contabil=conta.conta_contabil,
            arquivo_origem=arquivo_origem,
            arquivo_contabil_filtrado=arquivo_contabil_filtrado,
            arquivo_contabil_geral=arquivo_contabil_geral,
            nome_origem=nome_origem,
            nome_contabil_filtrado=nome_contabil_filtrado,
            nome_contabil_geral=nome_contabil_geral,
            df_origem=df_origem,
            df_contabil_filtrado=df_contabil_filtrado,
            df_contabil_geral=df_contabil_geral,
            resultado=request.resultado,
            tipo_conciliacao=request.tipo_conciliacao
        )

        # Obter saldo do resultado
        resumo = request.resultado.get("resumo", {})
        saldo = resumo.get("diferenca", 0) or 0

        now = datetime.now(timezone.utc)

        # Criar registro de conciliação
        conciliacao = Conciliacao(
            empresa_id=request.empresa_id,
            conta_contabil_id=request.conta_contabil_id,
            periodo=periodo_normalizado,
            saldo=saldo,
            status=StatusConciliacao.EFETIVADA.value,
            usuario_responsavel_id=current_user.user_id,
            data_efetivacao=now,
            resultado_json=request.resultado,
            caminhos_arquivos=caminhos
        )

        db.add(conciliacao)
        db.commit()
        db.refresh(conciliacao)

        # Registrar no audit log
        try:
            audit = AuditLog(
                usuario_id=current_user.user_id,
                empresa_id=request.empresa_id,
                action=AuditAction.CREATE,
                entity_type="conciliacao",
                entity_id=conciliacao.id,
                new_values={
                    "status": StatusConciliacao.EFETIVADA.value,
                    "periodo": periodo_normalizado,
                    "conta_contabil_id": request.conta_contabil_id
                }
            )
            db.add(audit)
            db.commit()
        except Exception as e:
            logger.warning(f"Erro ao registrar audit log: {e}")

        logger.info(f"Conciliação {conciliacao.id} efetivada por usuário {current_user.user_id}")
        return conciliacao

    def listar_efetivadas(
        self,
        db: Session,
        empresa_id: int,
        ano: int,
        mes: int,
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[ConciliacaoEfetivadaResumo], int]:
        """
        Lista conciliações efetivadas para uma empresa/período.

        Args:
            db: Sessão do banco
            empresa_id: ID da empresa
            ano: Ano do período
            mes: Mês do período
            skip: Registros a pular
            limit: Limite de registros

        Returns:
            Tupla (lista de resumos, total)
        """
        periodo = f"{ano}-{mes:02d}"

        query = db.query(Conciliacao).filter(
            Conciliacao.empresa_id == empresa_id,
            Conciliacao.periodo == periodo,
            Conciliacao.status == StatusConciliacao.EFETIVADA.value
        )

        total = query.count()

        conciliacoes = query.order_by(
            Conciliacao.data_efetivacao.desc()
        ).offset(skip).limit(limit).all()

        # Mapear para schema de resposta
        items = []
        for c in conciliacoes:
            resumo_json = c.resultado_json.get("resumo", {}) if c.resultado_json else {}

            # Detectar tipo de conciliação
            resultado_json_full = c.resultado_json or {}
            tipo_conc = "banco" if "movimentos_por_dia" in resultado_json_full else "contabil"

            item = ConciliacaoEfetivadaResumo(
                id=c.id,
                empresa_id=c.empresa_id,
                empresa_nome=c.empresa.nome if c.empresa else None,
                conta_contabil_id=c.conta_contabil_id,
                conta_contabil_codigo=c.conta_contabil.conta_contabil if c.conta_contabil else None,
                conta_contabil_descricao=c.conta_contabil.descricao if c.conta_contabil else None,
                periodo=c.periodo,
                status=c.status,
                data_efetivacao=c.data_efetivacao,
                usuario_responsavel_id=c.usuario_responsavel_id,
                usuario_responsavel_nome=c.usuario_responsavel.nome if c.usuario_responsavel else None,
                total_origem=resumo_json.get("total_origem"),
                total_destino=resumo_json.get("total_destino"),
                diferenca=resumo_json.get("diferenca"),
                situacao=resumo_json.get("situacao"),
                tipo_conciliacao=tipo_conc,
                created_at=c.created_at,
                updated_at=c.updated_at
            )
            items.append(item)

        return items, total

    def obter_detalhes(
        self,
        db: Session,
        conciliacao_id: int,
        empresa_id: int
    ) -> ConciliacaoEfetivadaDetalhe:
        """Obtém detalhes completos de uma conciliação efetivada."""
        conciliacao = db.query(Conciliacao).filter(
            Conciliacao.id == conciliacao_id,
            Conciliacao.empresa_id == empresa_id,
            Conciliacao.status == StatusConciliacao.EFETIVADA.value
        ).first()

        if not conciliacao:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conciliação efetivada não encontrada"
            )

        resumo_json = conciliacao.resultado_json.get("resumo", {}) if conciliacao.resultado_json else {}

        # Detectar tipo de conciliação
        resultado_json_full = conciliacao.resultado_json or {}
        tipo_conc = "banco" if "movimentos_por_dia" in resultado_json_full else "contabil"

        return ConciliacaoEfetivadaDetalhe(
            id=conciliacao.id,
            empresa_id=conciliacao.empresa_id,
            empresa_nome=conciliacao.empresa.nome if conciliacao.empresa else None,
            conta_contabil_id=conciliacao.conta_contabil_id,
            conta_contabil_codigo=conciliacao.conta_contabil.conta_contabil if conciliacao.conta_contabil else None,
            conta_contabil_descricao=conciliacao.conta_contabil.descricao if conciliacao.conta_contabil else None,
            periodo=conciliacao.periodo,
            status=conciliacao.status,
            data_efetivacao=conciliacao.data_efetivacao,
            usuario_responsavel_id=conciliacao.usuario_responsavel_id,
            usuario_responsavel_nome=conciliacao.usuario_responsavel.nome if conciliacao.usuario_responsavel else None,
            total_origem=resumo_json.get("total_origem"),
            total_destino=resumo_json.get("total_destino"),
            diferenca=resumo_json.get("diferenca"),
            situacao=resumo_json.get("situacao"),
            tipo_conciliacao=tipo_conc,
            saldo=conciliacao.saldo,
            resultado_json=conciliacao.resultado_json,
            caminhos_arquivos=conciliacao.caminhos_arquivos,
            created_at=conciliacao.created_at,
            updated_at=conciliacao.updated_at
        )

    def listar_contas_efetivadas(
        self,
        db: Session,
        empresa_id: int,
        periodo: str
    ) -> List[int]:
        """
        Lista IDs das contas já efetivadas para uma empresa/período.

        Args:
            db: Sessão do banco
            empresa_id: ID da empresa
            periodo: Período no formato YYYY-MM

        Returns:
            Lista de IDs de contas contábeis já efetivadas
        """
        periodo_normalizado = self._normalize_periodo(periodo)

        contas = db.query(Conciliacao.conta_contabil_id).filter(
            Conciliacao.empresa_id == empresa_id,
            Conciliacao.periodo == periodo_normalizado,
            Conciliacao.status == StatusConciliacao.EFETIVADA.value
        ).all()

        return [c[0] for c in contas]

    def obter_arquivo(
        self,
        db: Session,
        conciliacao_id: int,
        tipo_arquivo: str,
        formato: str,
        empresa_id: int
    ) -> str:
        """
        Obtém caminho de arquivo para download.

        Args:
            db: Sessão do banco
            conciliacao_id: ID da conciliação
            tipo_arquivo: origem, contabil_filtrado, contabil_geral, relatorio
            formato: original, normalizado, json
            empresa_id: ID da empresa

        Returns:
            Caminho do arquivo
        """
        conciliacao = db.query(Conciliacao).filter(
            Conciliacao.id == conciliacao_id,
            Conciliacao.empresa_id == empresa_id,
            Conciliacao.status == StatusConciliacao.EFETIVADA.value
        ).first()

        if not conciliacao:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conciliação efetivada não encontrada"
            )

        caminhos = conciliacao.caminhos_arquivos or {}
        tipo_caminhos = caminhos.get(tipo_arquivo, {})
        caminho = tipo_caminhos.get(formato)

        if not caminho:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Arquivo do tipo '{tipo_arquivo}' formato '{formato}' não encontrado nos registros"
            )

        if not self.file_storage.file_exists(caminho):
            # Para relatorio/json, regenerar a partir do resultado_json do banco
            if tipo_arquivo == "relatorio" and formato == "json" and conciliacao.resultado_json:
                logger.info(f"Regenerando arquivo JSON para conciliação {conciliacao_id} a partir do banco")
                conta = db.query(PlanoDeContas).filter(
                    PlanoDeContas.id == conciliacao.conta_contabil_id
                ).first()
                conta_contabil = conta.conta_contabil if conta else "desconhecida"
                ano, mes = self._parse_periodo(conciliacao.periodo)
                # Detectar tipo para salvar no path correto
                resultado_full = conciliacao.resultado_json or {}
                tipo_conc = "banco" if "movimentos_por_dia" in resultado_full else "receber"
                caminho_regenerado = self.file_storage.save_json_result(
                    conciliacao.resultado_json, empresa_id, ano, mes, conta_contabil, tipo_conc
                )
                # Atualizar caminho no banco
                if not conciliacao.caminhos_arquivos:
                    conciliacao.caminhos_arquivos = {}
                if "relatorio" not in conciliacao.caminhos_arquivos:
                    conciliacao.caminhos_arquivos["relatorio"] = {}
                conciliacao.caminhos_arquivos["relatorio"]["json"] = caminho_regenerado
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(conciliacao, "caminhos_arquivos")
                db.commit()
                return caminho_regenerado

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Arquivo não encontrado no servidor. Os arquivos podem ter sido perdidos após um redeploy. O relatório JSON pode ser regenerado, mas os arquivos Excel originais precisam ser re-efetivados."
            )

        return caminho

    def excluir(
        self,
        db: Session,
        conciliacao_id: int,
        empresa_id: int,
        current_user: CurrentUser
    ) -> bool:
        """
        Exclui uma conciliação efetivada (apenas admin).

        Args:
            db: Sessão do banco
            conciliacao_id: ID da conciliação
            empresa_id: ID da empresa
            current_user: Usuário atual

        Returns:
            True se excluído com sucesso
        """
        # Verificar se é admin
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas administradores podem excluir conciliações"
            )

        conciliacao = db.query(Conciliacao).filter(
            Conciliacao.id == conciliacao_id,
            Conciliacao.empresa_id == empresa_id,
            Conciliacao.status == StatusConciliacao.EFETIVADA.value
        ).first()

        if not conciliacao:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conciliação efetivada não encontrada"
            )

        # Remover arquivos
        ano, mes = self._parse_periodo(conciliacao.periodo)
        conta_contabil = conciliacao.conta_contabil.conta_contabil if conciliacao.conta_contabil else ""

        # Detectar tipo para saber qual diretório remover
        resultado_full = conciliacao.resultado_json or {}
        tipo_conc = "banco" if "movimentos_por_dia" in resultado_full else "receber"

        self.file_storage.delete_reconciliation_files(
            empresa_id=empresa_id,
            ano=ano,
            mes=mes,
            conta_contabil=conta_contabil,
            tipo_conciliacao=tipo_conc
        )

        # Registrar no audit log antes de excluir
        try:
            audit = AuditLog(
                usuario_id=current_user.user_id,
                empresa_id=empresa_id,
                action=AuditAction.DELETE,
                entity_type="conciliacao",
                entity_id=conciliacao_id,
                old_values={
                    "status": conciliacao.status,
                    "periodo": conciliacao.periodo,
                    "conta_contabil_id": conciliacao.conta_contabil_id,
                    "data_efetivacao": str(conciliacao.data_efetivacao)
                }
            )
            db.add(audit)
        except Exception as e:
            logger.warning(f"Erro ao registrar audit log: {e}")

        # Excluir conciliação
        db.delete(conciliacao)
        db.commit()

        logger.info(f"Conciliação {conciliacao_id} excluída por usuário {current_user.user_id}")
        return True
