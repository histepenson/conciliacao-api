"""
Service para efetivacao de conciliacao de impostos.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_

from core.data_base import parse_ano_mes
from models import Conciliacao, PlanoDeContas
from schemas.efetivacao_schema import StatusConciliacao
from middleware.auth import CurrentUser
from services.file_storage_service import FileStorageService

logger = logging.getLogger(__name__)


class ConciliacaoImpostosEfetivacaoService:
    """Service para efetivar conciliacao de impostos."""

    def __init__(self):
        self.file_storage = FileStorageService()

    def _parse_periodo(self, data_base: str) -> Tuple[int, int]:
        """Converte data-base (DD/MM/YYYY, MM/YYYY ou YYYYMMDD) para (ano, mes)."""
        return parse_ano_mes(data_base)

    def _normalize_periodo(self, data_base: str) -> str:
        ano, mes = self._parse_periodo(data_base)
        return f"{ano}-{mes:02d}"

    def _check_already_efetivada(
        self,
        db: Session,
        empresa_id: int,
        periodo: str,
        conta_contabil_id: int
    ) -> Optional[Conciliacao]:
        return db.query(Conciliacao).filter(
            and_(
                Conciliacao.empresa_id == empresa_id,
                Conciliacao.periodo == periodo,
                Conciliacao.conta_contabil_id == conta_contabil_id,
                Conciliacao.status == StatusConciliacao.EFETIVADA.value
            )
        ).first()

    def efetivar(
        self,
        db: Session,
        empresa_id: int,
        conta_contabil_id: int,
        data_base: str,
        campo_imposto: str,
        resultado: Dict[str, Any],
        current_user: CurrentUser,
        arquivo_sft: Optional[bytes] = None,
        arquivo_razao: Optional[bytes] = None,
        nome_sft: str = "sft.xlsx",
        nome_razao: str = "razao.xlsx"
    ) -> Conciliacao:
        periodo = self._normalize_periodo(data_base)

        existing = self._check_already_efetivada(db, empresa_id, periodo, conta_contabil_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Conciliacao ja efetivada em {existing.data_efetivacao}"
            )

        conta = db.query(PlanoDeContas).filter(PlanoDeContas.id == conta_contabil_id).first()
        if not conta:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta contabil nao encontrada")

        resumo = resultado.get("resumo", {})
        saldo = float(resumo.get("diferenca", 0) or 0)

        # Divergencias (NFs sem correspondencia) sao esperadas na conciliacao de
        # impostos e nao bloqueiam a efetivacao; mantem a situacao real calculada.
        resultado_para_salvar = resultado

        now = datetime.now(timezone.utc)

        ano, mes = self._parse_periodo(data_base)
        caminhos_arquivos = self.file_storage.save_imposto_files(
            empresa_id=empresa_id,
            ano=ano,
            mes=mes,
            conta_contabil=conta.conta_contabil,
            resultado=resultado_para_salvar,
            arquivo_sft=arquivo_sft,
            arquivo_razao=arquivo_razao,
            nome_sft=nome_sft,
            nome_razao=nome_razao
        )

        conciliacao = Conciliacao(
            empresa_id=empresa_id,
            conta_contabil_id=conta_contabil_id,
            periodo=periodo,
            saldo=saldo,
            status=StatusConciliacao.EFETIVADA.value,
            tipo_conciliacao="impostos",
            usuario_responsavel_id=current_user.user_id,
            data_efetivacao=now,
            resultado_json=resultado_para_salvar,
            caminhos_arquivos=caminhos_arquivos
        )

        db.add(conciliacao)
        db.commit()
        db.refresh(conciliacao)

        logger.info(f"Conciliacao de impostos {conciliacao.id} efetivada por usuario {current_user.user_id}")
        return conciliacao
