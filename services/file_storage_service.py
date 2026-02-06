"""
Service para gerenciamento de armazenamento de arquivos de conciliação.

Estrutura de diretórios:
{STORAGE_DIR}/empresa_{id}/{ano}/{mes}/{tipo}/{conta_contabil}/
  ├── originais/
  │   ├── origem.xlsx
  │   ├── contabil_filtrado.xlsx
  │   └── contabil_geral.xlsx
  ├── normalizados/
  │   ├── origem.xlsx
  │   ├── contabil_filtrado.xlsx
  │   └── contabil_geral.xlsx
  └── relatorio/
      └── resultado.json

Tipos: banco, receber, pagar
"""
import os
import json
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Any, BinaryIO

import pandas as pd

logger = logging.getLogger(__name__)

# Diretório base - usa env var STORAGE_DIR, default "data"
UPLOAD_BASE_DIR = Path(os.environ.get("STORAGE_DIR", "data"))


class FileStorageService:
    """Service para armazenamento hierárquico de arquivos de conciliação."""

    @staticmethod
    def _ensure_directory(path: Path) -> None:
        """Cria diretório se não existir."""
        path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _generate_timestamp() -> str:
        """Gera string de timestamp para nomes de arquivo."""
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    @staticmethod
    def _sanitize_conta(conta_contabil: str) -> str:
        """Sanitiza código da conta para uso em path de arquivo."""
        return conta_contabil.replace(".", "_").replace("/", "_").replace("\\", "_").replace(" ", "_")

    def get_base_path(
        self,
        empresa_id: int,
        ano: int,
        mes: int,
        conta_contabil: str,
        tipo_conciliacao: str = "receber"
    ) -> Path:
        """
        Retorna o path base para arquivos de uma conciliação.

        Args:
            empresa_id: ID da empresa
            ano: Ano do período
            mes: Mês do período (1-12)
            conta_contabil: Código da conta contábil
            tipo_conciliacao: banco, receber ou pagar

        Returns:
            Path base: {STORAGE_DIR}/empresa_{id}/{ano}/{mes:02d}/{tipo}/{conta}/
        """
        sanitized_conta = self._sanitize_conta(conta_contabil)
        return UPLOAD_BASE_DIR / f"empresa_{empresa_id}" / str(ano) / f"{mes:02d}" / tipo_conciliacao / sanitized_conta

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
            Caminho completo do arquivo salvo
        """
        base_path = self.get_base_path(empresa_id, ano, mes, conta_contabil, tipo_conciliacao)
        originais_path = base_path / "originais"
        self._ensure_directory(originais_path)

        extensao = Path(nome_original).suffix or ".xlsx"
        filename = f"{tipo_arquivo}{extensao}"
        file_path = originais_path / filename

        with open(file_path, 'wb') as f:
            f.write(file_content)

        logger.info(f"Arquivo original salvo: {file_path}")
        return str(file_path)

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
            Caminho completo do arquivo salvo
        """
        base_path = self.get_base_path(empresa_id, ano, mes, conta_contabil, tipo_conciliacao)
        normalizados_path = base_path / "normalizados"
        self._ensure_directory(normalizados_path)

        filename = f"{tipo_arquivo}.xlsx"
        file_path = normalizados_path / filename

        df.to_excel(str(file_path), index=False)
        logger.info(f"DataFrame normalizado salvo: {file_path}")

        return str(file_path)

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
        Salva resultado da conciliação como JSON.

        Returns:
            Caminho completo do arquivo salvo
        """
        base_path = self.get_base_path(empresa_id, ano, mes, conta_contabil, tipo_conciliacao)
        relatorio_path = base_path / "relatorio"
        self._ensure_directory(relatorio_path)

        filename = "resultado.json"
        file_path = relatorio_path / filename

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"Resultado JSON salvo: {file_path}")
        return str(file_path)

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
        # Tipo de conciliação
        tipo_conciliacao: str = "receber"
    ) -> Dict[str, Dict[str, str]]:
        """
        Salva todos os arquivos de uma conciliação contábil (receber/pagar).

        Returns:
            Dicionário com estrutura:
            {
                "origem": {"original": "path", "normalizado": "path"},
                "contabil_filtrado": {"original": "path", "normalizado": "path"},
                "contabil_geral": {"original": "path", "normalizado": "path"},
                "relatorio": {"json": "path"}
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

        logger.info(f"Todos os arquivos salvos para empresa {empresa_id}, período {ano}-{mes:02d}, conta {conta_contabil}, tipo {tipo_conciliacao}")
        return caminhos

    def save_bank_files(
        self,
        empresa_id: int,
        ano: int,
        mes: int,
        conta_contabil: str,
        resultado: Dict[str, Any]
    ) -> Dict[str, Dict[str, str]]:
        """
        Salva arquivos de conciliação bancária (apenas resultado JSON).

        Returns:
            Dicionário com estrutura:
            {
                "relatorio": {"json": "path"}
            }
        """
        caminhos = {"relatorio": {}}

        caminhos["relatorio"]["json"] = self.save_json_result(
            resultado, empresa_id, ano, mes, conta_contabil, "banco"
        )

        logger.info(f"Arquivos bancários salvos para empresa {empresa_id}, período {ano}-{mes:02d}, conta {conta_contabil}")
        return caminhos

    def file_exists(self, file_path: str) -> bool:
        """Verifica se um arquivo existe."""
        return Path(file_path).exists()

    def get_file_size(self, file_path: str) -> Optional[int]:
        """Retorna o tamanho do arquivo em bytes."""
        path = Path(file_path)
        if path.exists():
            return path.stat().st_size
        return None

    def delete_reconciliation_files(
        self,
        empresa_id: int,
        ano: int,
        mes: int,
        conta_contabil: str,
        tipo_conciliacao: str = "receber"
    ) -> bool:
        """
        Remove todos os arquivos de uma conciliação.

        Returns:
            True se removido com sucesso, False caso contrário
        """
        base_path = self.get_base_path(empresa_id, ano, mes, conta_contabil, tipo_conciliacao)

        if base_path.exists():
            try:
                shutil.rmtree(base_path)
                logger.info(f"Arquivos removidos: {base_path}")
                return True
            except Exception as e:
                logger.error(f"Erro ao remover arquivos: {e}")
                return False
        return True

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
        Obtém o caminho de um arquivo específico.

        Args:
            tipo_arquivo: origem, contabil_filtrado, contabil_geral, relatorio
            formato: original, normalizado, json
            tipo_conciliacao: banco, receber, pagar

        Returns:
            Caminho do arquivo ou None se não existir
        """
        base_path = self.get_base_path(empresa_id, ano, mes, conta_contabil, tipo_conciliacao)

        if tipo_arquivo == "relatorio":
            relatorio_path = base_path / "relatorio"
            if relatorio_path.exists():
                json_files = list(relatorio_path.glob("*.json"))
                if json_files:
                    return str(max(json_files, key=os.path.getmtime))
            return None

        if formato == "original":
            file_path = base_path / "originais" / f"{tipo_arquivo}.xlsx"
        elif formato == "normalizado":
            file_path = base_path / "normalizados" / f"{tipo_arquivo}.xlsx"
        else:
            return None

        return str(file_path) if file_path.exists() else None
