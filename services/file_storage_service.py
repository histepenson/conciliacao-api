"""
Service para gerenciamento de armazenamento de arquivos de conciliacao.

Estrutura de chaves no bucket S3:
empresa_{id}/{ano}/{mes}/{tipo}/{conta_contabil}/
  |-- originais/
  |   |-- origem.xlsx
  |   |-- contabil_filtrado.xlsx
  |   +-- contabil_geral.xlsx
  |-- normalizados/
  |   |-- origem.xlsx
  |   |-- contabil_filtrado.xlsx
  |   +-- contabil_geral.xlsx
  +-- relatorio/
      +-- resultado.json

Tipos: banco, receber, pagar
"""
import io
import json
import logging
from typing import Dict, Optional, Any

import pandas as pd

from core import storage

logger = logging.getLogger(__name__)


class FileStorageService:
    """Service para armazenamento hierarquico de arquivos de conciliacao no bucket S3."""

    @staticmethod
    def _sanitize_conta(conta_contabil: str) -> str:
        """Sanitiza codigo da conta para uso em chave de arquivo."""
        return conta_contabil.replace(".", "_").replace("/", "_").replace("\\", "_").replace(" ", "_")

    def get_base_path(
        self,
        empresa_id: int,
        ano: int,
        mes: int,
        conta_contabil: str,
        tipo_conciliacao: str = "receber"
    ) -> str:
        """
        Retorna o prefixo de chave base para arquivos de uma conciliacao.

        Returns:
            Prefixo: empresa_{id}/{ano}/{mes:02d}/{tipo}/{conta}
        """
        sanitized_conta = self._sanitize_conta(conta_contabil)
        return f"empresa_{empresa_id}/{ano}/{mes:02d}/{tipo_conciliacao}/{sanitized_conta}"

    def save_original_file(
        self,
        file_content: bytes,
        empresa_id: int,
        ano: int,
        mes: int,
        conta_contabil: str,
        tipo_arquivo: str,
        nome_original: str,
        tipo_conciliacao: str = "receber"
    ) -> str:
        """
        Salva arquivo original exatamente como foi enviado.

        Returns:
            Chave do arquivo salvo no bucket
        """
        base_path = self.get_base_path(empresa_id, ano, mes, conta_contabil, tipo_conciliacao)

        extensao = "." + nome_original.rsplit(".", 1)[-1] if "." in nome_original else ".xlsx"
        key = f"{base_path}/originais/{tipo_arquivo}{extensao}"

        storage.upload_bytes(key, file_content)

        logger.info(f"Arquivo original salvo: {key}")
        return key

    def save_dataframe_as_excel(
        self,
        df: pd.DataFrame,
        empresa_id: int,
        ano: int,
        mes: int,
        conta_contabil: str,
        tipo_arquivo: str,
        tipo_conciliacao: str = "receber"
    ) -> str:
        """
        Salva DataFrame normalizado como arquivo Excel.

        Returns:
            Chave do arquivo salvo no bucket
        """
        base_path = self.get_base_path(empresa_id, ano, mes, conta_contabil, tipo_conciliacao)
        key = f"{base_path}/normalizados/{tipo_arquivo}.xlsx"

        buffer = io.BytesIO()
        df.to_excel(buffer, index=False)
        storage.upload_bytes(key, buffer.getvalue())

        logger.info(f"DataFrame normalizado salvo: {key}")
        return key

    def save_json_result(
        self,
        data: Dict[str, Any],
        empresa_id: int,
        ano: int,
        mes: int,
        conta_contabil: str,
        tipo_conciliacao: str = "receber"
    ) -> str:
        """
        Salva resultado da conciliacao como JSON.

        Returns:
            Chave do arquivo salvo no bucket
        """
        base_path = self.get_base_path(empresa_id, ano, mes, conta_contabil, tipo_conciliacao)
        key = f"{base_path}/relatorio/resultado.json"

        content = json.dumps(data, ensure_ascii=False, indent=2, default=str).encode("utf-8")
        storage.upload_bytes(key, content)

        logger.info(f"Resultado JSON salvo: {key}")
        return key

    def save_all_reconciliation_files(
        self,
        empresa_id: int,
        ano: int,
        mes: int,
        conta_contabil: str,
        # Arquivos originais (bytes)
        arquivo_origem: bytes,
        arquivo_contabil_filtrado: bytes,
        arquivo_contabil_geral: bytes,
        nome_origem: str,
        nome_contabil_filtrado: str,
        nome_contabil_geral: str,
        # DataFrames normalizados
        df_origem: pd.DataFrame,
        df_contabil_filtrado: pd.DataFrame,
        df_contabil_geral: pd.DataFrame,
        # Resultado
        resultado: Dict[str, Any],
        # Tipo de conciliacao
        tipo_conciliacao: str = "receber"
    ) -> Dict[str, Dict[str, str]]:
        """
        Salva todos os arquivos de uma conciliacao contabil (receber/pagar).

        Returns:
            Dicionario com estrutura:
            {
                "origem": {"original": "chave", "normalizado": "chave"},
                "contabil_filtrado": {"original": "chave", "normalizado": "chave"},
                "contabil_geral": {"original": "chave", "normalizado": "chave"},
                "relatorio": {"json": "chave"}
            }
        """
        caminhos = {
            "origem": {},
            "contabil_filtrado": {},
            "contabil_geral": {},
            "relatorio": {}
        }

        # Salvar arquivos originais
        caminhos["origem"]["original"] = self.save_original_file(
            arquivo_origem, empresa_id, ano, mes, conta_contabil, "origem", nome_origem, tipo_conciliacao
        )
        caminhos["contabil_filtrado"]["original"] = self.save_original_file(
            arquivo_contabil_filtrado, empresa_id, ano, mes, conta_contabil, "contabil_filtrado", nome_contabil_filtrado, tipo_conciliacao
        )
        caminhos["contabil_geral"]["original"] = self.save_original_file(
            arquivo_contabil_geral, empresa_id, ano, mes, conta_contabil, "contabil_geral", nome_contabil_geral, tipo_conciliacao
        )

        # Salvar dados normalizados
        caminhos["origem"]["normalizado"] = self.save_dataframe_as_excel(
            df_origem, empresa_id, ano, mes, conta_contabil, "origem", tipo_conciliacao
        )
        caminhos["contabil_filtrado"]["normalizado"] = self.save_dataframe_as_excel(
            df_contabil_filtrado, empresa_id, ano, mes, conta_contabil, "contabil_filtrado", tipo_conciliacao
        )
        caminhos["contabil_geral"]["normalizado"] = self.save_dataframe_as_excel(
            df_contabil_geral, empresa_id, ano, mes, conta_contabil, "contabil_geral", tipo_conciliacao
        )

        # Salvar resultado JSON
        caminhos["relatorio"]["json"] = self.save_json_result(
            resultado, empresa_id, ano, mes, conta_contabil, tipo_conciliacao
        )

        logger.info(f"Todos os arquivos salvos para empresa {empresa_id}, periodo {ano}-{mes:02d}, conta {conta_contabil}, tipo {tipo_conciliacao}")
        return caminhos

    def save_bank_files(
        self,
        empresa_id: int,
        ano: int,
        mes: int,
        conta_contabil: str,
        resultado: Dict[str, Any],
        arquivo_extrato: bytes = None,
        arquivo_razao: bytes = None,
        nome_extrato: str = "extrato.xlsx",
        nome_razao: str = "razao.xlsx"
    ) -> Dict[str, Dict[str, str]]:
        """
        Salva arquivos de conciliacao bancaria (originais + resultado JSON).

        Returns:
            Dicionario com estrutura:
            {
                "extrato": {"original": "chave"},
                "razao": {"original": "chave"},
                "relatorio": {"json": "chave"}
            }
        """
        caminhos = {"relatorio": {}}

        if arquivo_extrato:
            caminhos["extrato"] = {}
            caminhos["extrato"]["original"] = self.save_original_file(
                arquivo_extrato, empresa_id, ano, mes, conta_contabil,
                "extrato", nome_extrato, "banco"
            )

        if arquivo_razao:
            caminhos["razao"] = {}
            caminhos["razao"]["original"] = self.save_original_file(
                arquivo_razao, empresa_id, ano, mes, conta_contabil,
                "razao", nome_razao, "banco"
            )

        caminhos["relatorio"]["json"] = self.save_json_result(
            resultado, empresa_id, ano, mes, conta_contabil, "banco"
        )

        logger.info(f"Arquivos bancarios salvos para empresa {empresa_id}, periodo {ano}-{mes:02d}, conta {conta_contabil}")
        return caminhos

    def save_stock_files(
        self,
        empresa_id: int,
        ano: int,
        mes: int,
        conta_contabil: str,
        resultado: Dict[str, Any],
        arquivo_kardex: bytes = None,
        arquivo_razao: bytes = None,
        nome_kardex: str = "kardex.xlsx",
        nome_razao: str = "razao.xlsx"
    ) -> Dict[str, Dict[str, str]]:
        """
        Salva arquivos de conciliacao de estoque (originais + resultado JSON).

        Returns:
            Dicionario com estrutura:
            {
                "kardex": {"original": "chave"},
                "razao": {"original": "chave"},
                "relatorio": {"json": "chave"}
            }
        """
        caminhos = {"relatorio": {}}

        if arquivo_kardex:
            caminhos["kardex"] = {}
            caminhos["kardex"]["original"] = self.save_original_file(
                arquivo_kardex, empresa_id, ano, mes, conta_contabil,
                "kardex", nome_kardex, "estoque"
            )

        if arquivo_razao:
            caminhos["razao"] = {}
            caminhos["razao"]["original"] = self.save_original_file(
                arquivo_razao, empresa_id, ano, mes, conta_contabil,
                "razao", nome_razao, "estoque"
            )

        caminhos["relatorio"]["json"] = self.save_json_result(
            resultado, empresa_id, ano, mes, conta_contabil, "estoque"
        )

        logger.info(f"Arquivos de estoque salvos para empresa {empresa_id}, periodo {ano}-{mes:02d}, conta {conta_contabil}")
        return caminhos

    def file_exists(self, file_path: str) -> bool:
        """Verifica se um arquivo existe no bucket."""
        return storage.file_exists(file_path)

    def get_file_size(self, file_path: str) -> Optional[int]:
        """Retorna o tamanho do arquivo em bytes."""
        return storage.get_file_size(file_path)

    def delete_reconciliation_files(
        self,
        empresa_id: int,
        ano: int,
        mes: int,
        conta_contabil: str,
        tipo_conciliacao: str = "receber"
    ) -> bool:
        """
        Remove todos os arquivos de uma conciliacao.

        Returns:
            True se removido com sucesso, False caso contrario
        """
        base_path = self.get_base_path(empresa_id, ano, mes, conta_contabil, tipo_conciliacao)

        try:
            storage.delete_prefix(f"{base_path}/")
            logger.info(f"Arquivos removidos: {base_path}/")
            return True
        except Exception as e:
            logger.error(f"Erro ao remover arquivos: {e}")
            return False

    def get_file_path(
        self,
        empresa_id: int,
        ano: int,
        mes: int,
        conta_contabil: str,
        tipo_arquivo: str,
        formato: str,
        tipo_conciliacao: str = "receber"
    ) -> Optional[str]:
        """
        Obtem a chave de um arquivo especifico.

        Args:
            tipo_arquivo: origem, contabil_filtrado, contabil_geral, relatorio
            formato: original, normalizado, json
            tipo_conciliacao: banco, receber, pagar

        Returns:
            Chave do arquivo ou None se nao existir
        """
        base_path = self.get_base_path(empresa_id, ano, mes, conta_contabil, tipo_conciliacao)

        if tipo_arquivo == "relatorio":
            key = f"{base_path}/relatorio/resultado.json"
            return key if storage.file_exists(key) else None

        if formato == "original":
            key = f"{base_path}/originais/{tipo_arquivo}.xlsx"
        elif formato == "normalizado":
            key = f"{base_path}/normalizados/{tipo_arquivo}.xlsx"
        else:
            return None

        return key if storage.file_exists(key) else None
