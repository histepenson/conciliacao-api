"""
Service para efetivacao de conciliacao de estoque.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_

from core.data_base import parse_ano_mes
from models import Conciliacao, PlanoDeContas, Empresa
from schemas.efetivacao_schema import StatusConciliacao
from middleware.auth import CurrentUser
from services.file_storage_service import FileStorageService

logger = logging.getLogger(__name__)


class ConciliacaoEstoqueEfetivacaoService:
    """Service para efetivar conciliacao de estoque."""

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
    ) -> Conciliacao | None:
        return db.query(Conciliacao).filter(
            and_(
                Conciliacao.empresa_id == empresa_id,
                Conciliacao.periodo == periodo,
                Conciliacao.conta_contabil_id == conta_contabil_id,
                Conciliacao.status == StatusConciliacao.EFETIVADA.value
            )
        ).first()

    def _validate_no_divergencias(self, resultado: Dict[str, Any], permite_divergente: bool = False) -> None:
        resumo = resultado.get("resumo", {})
        situacao = resumo.get("situacao", "DIVERGENTE")
        qtd_divergentes = resumo.get("qtd_divergentes", 1)
        if (situacao != "CONCILIADO" or int(qtd_divergentes) > 0) and not permite_divergente:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nao e possivel efetivar: conciliacao de estoque divergente"
            )

    def efetivar(
        self,
        db: Session,
        empresa_id: int,
        conta_contabil_id: int,
        data_base: str,
        resultado: Dict[str, Any],
        current_user: CurrentUser,
        arquivo_kardex: Optional[bytes] = None,
        arquivo_razao: Optional[bytes] = None,
        nome_kardex: str = "kardex.xlsx",
        nome_razao: str = "razao.xlsx"
    ) -> Conciliacao:
        periodo = self._normalize_periodo(data_base)

        existing = self._check_already_efetivada(db, empresa_id, periodo, conta_contabil_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Conciliacao de estoque ja efetivada em {existing.data_efetivacao}"
            )

        # Consultar parametro da empresa
        empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
        permite_divergente = empresa.permite_efetivar_divergente if empresa else False

        self._validate_no_divergencias(resultado, permite_divergente)

        conta = db.query(PlanoDeContas).filter(PlanoDeContas.id == conta_contabil_id).first()
        if not conta:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta contabil nao encontrada")

        resumo = resultado.get("resumo", {})
        saldo = float(resumo.get("dif_total", 0) or 0)

        # Ao efetivar, situacao e sempre CONCILIADO
        resultado_para_salvar = {**resultado}
        resultado_para_salvar["resumo"] = {**resumo, "situacao": "CONCILIADO"}

        now = datetime.now(timezone.utc)

        # Salvar arquivos no volume
        ano, mes = self._parse_periodo(data_base)
        caminhos_arquivos = self.file_storage.save_stock_files(
            empresa_id=empresa_id,
            ano=ano,
            mes=mes,
            conta_contabil=conta.conta_contabil,
            resultado=resultado_para_salvar,
            arquivo_kardex=arquivo_kardex,
            arquivo_razao=arquivo_razao,
            nome_kardex=nome_kardex,
            nome_razao=nome_razao
        )

        conciliacao = Conciliacao(
            empresa_id=empresa_id,
            conta_contabil_id=conta_contabil_id,
            periodo=periodo,
            saldo=saldo,
            status=StatusConciliacao.EFETIVADA.value,
            tipo_conciliacao="estoque",
            usuario_responsavel_id=current_user.user_id,
            data_efetivacao=now,
            resultado_json=resultado_para_salvar,
            caminhos_arquivos=caminhos_arquivos
        )

        db.add(conciliacao)
        db.commit()
        db.refresh(conciliacao)

        logger.info(f"Conciliacao de estoque {conciliacao.id} efetivada por usuario {current_user.user_id}")
        return conciliacao
