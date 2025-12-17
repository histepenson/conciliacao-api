"""
Agente de Conciliação usando AGNO (agnai.chat)
"""

import json
import requests
from typing import Dict, List, Any
import pandas as pd
from io import BytesIO


class AgenteConciliacaoAGNO:
    """
    Agente de conciliação que usa AGNO (agnai.chat) como backend.
    """
    
    def __init__(self, agno_api_url: str, agno_api_key: str, agent_id: str):
        """
        Inicializa o agente com configurações do AGNO.
        
        Args:
            agno_api_url: URL da API do AGNO (ex: https://api.agnai.chat/v1)
            agno_api_key: API key do AGNO
            agent_id: ID do agente criado no AGNO
        """
        self.api_url = agno_api_url
        self.api_key = agno_api_key
        self.agent_id = agent_id
        self.headers = {
            "Authorization": f"Bearer {agno_api_key}",
            "Content-Type": "application/json"
        }
    
    def processar_arquivos_excel(
        self, 
        arquivo_origem: bytes,
        arquivo_destino: bytes, 
        arquivo_lancamentos: bytes
    ) -> Dict[str, Any]:
        """
        Processa arquivos Excel e retorna análise de conciliação usando AGNO.
        
        Args:
            arquivo_origem: Bytes do arquivo Excel origem
            arquivo_destino: Bytes do arquivo Excel destino  
            arquivo_lancamentos: Bytes do arquivo Excel de lançamentos
            
        Returns:
            Dict com resultado da análise
        """
        
        # Lê os arquivos Excel
        df_origem = pd.read_excel(BytesIO(arquivo_origem))
        df_destino = pd.read_excel(BytesIO(arquivo_destino))
        df_lancamentos = pd.read_excel(BytesIO(arquivo_lancamentos))
        
        # Converte para formato legível
        dados_origem = self._dataframe_to_text(df_origem, "ARQUIVO ORIGEM")
        dados_destino = self._dataframe_to_text(df_destino, "ARQUIVO DESTINO (CONTABILIDADE)")
        dados_lancamentos = self._dataframe_to_text(df_lancamentos, "LANÇAMENTOS CONTÁBEIS")
        
        # Monta mensagem para o agente AGNO
        mensagem_usuario = f"""Realize a conciliação contábil dos seguintes dados:

{dados_origem}

{dados_destino}

{dados_lancamentos}

Analise criteriosamente e retorne APENAS o JSON de resposta conforme especificado."""

        # Chama API do AGNO
        try:
            resultado = self._chamar_agente_agno(mensagem_usuario)
            return resultado
        except Exception as e:
            print(f"Erro ao chamar AGNO: {e}")
            return self._resposta_erro(str(e))
    
    def _chamar_agente_agno(self, mensagem: str) -> Dict[str, Any]:
        """
        Faz chamada à API do AGNO.
        
        Args:
            mensagem: Mensagem do usuário
            
        Returns:
            Dict com resposta parseada
        """
        
        # Payload para AGNO API
        payload = {
            "agent_id": self.agent_id,
            "message": mensagem,
            "stream": False,
            "temperature": 0.2,
            "max_tokens": 8000
        }
        
        # Faz requisição
        response = requests.post(
            f"{self.api_url}/chat/completions",
            headers=self.headers,
            json=payload,
            timeout=120  # 2 minutos timeout
        )
        
        response.raise_for_status()
        
        # Parse da resposta
        dados_resposta = response.json()
        
        # Extrai texto da resposta (estrutura pode variar por implementação AGNO)
        texto_resposta = self._extrair_texto_resposta(dados_resposta)
        
        # Parse do JSON
        resultado = self._parse_json_resposta(texto_resposta)
        
        return resultado
    
    def _extrair_texto_resposta(self, dados: Dict) -> str:
        """
        Extrai texto da resposta do AGNO (adaptar conforme estrutura real).
        
        Args:
            dados: Dict com resposta da API
            
        Returns:
            Texto da resposta
        """
        # Adaptação para diferentes estruturas possíveis
        if "choices" in dados:
            return dados["choices"][0]["message"]["content"]
        elif "response" in dados:
            return dados["response"]
        elif "message" in dados:
            return dados["message"]
        else:
            return json.dumps(dados)
    
    def _parse_json_resposta(self, texto: str) -> Dict[str, Any]:
        """
        Faz parse do JSON da resposta, tratando possíveis erros.
        
        Args:
            texto: Texto contendo JSON
            
        Returns:
            Dict parseado
        """
        import re
        
        # Remove markdown code blocks se houver
        texto = re.sub(r'```json\s*', '', texto)
        texto = re.sub(r'```\s*', '', texto)
        texto = texto.strip()
        
        try:
            # Tenta parse direto
            return json.loads(texto)
        except json.JSONDecodeError:
            # Tenta encontrar JSON no texto
            match = re.search(r'\{.*\}', texto, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except:
                    pass
            
            # Se falhar, retorna erro estruturado
            return self._resposta_erro("Erro ao fazer parse da resposta JSON")
    
    def _dataframe_to_text(self, df: pd.DataFrame, titulo: str) -> str:
        """
        Converte DataFrame para texto formatado.
        
        Args:
            df: DataFrame pandas
            titulo: Título do conjunto de dados
            
        Returns:
            String formatada
        """
        linhas = [
            f"═══════════════════════════════════════",
            f"📄 {titulo}",
            f"═══════════════════════════════════════",
            f"",
            f"Total de registros: {len(df)}",
            f"",
            f"Estrutura:",
            f"Colunas: {', '.join(df.columns.tolist())}",
            f"",
            f"Primeiras 10 linhas:",
            df.head(10).to_string(index=False),
            f"",
            f"Estatísticas (colunas numéricas):"
        ]
        
        # Adiciona estatísticas de colunas numéricas
        colunas_numericas = df.select_dtypes(include=['number']).columns
        for col in colunas_numericas:
            total = df[col].sum()
            media = df[col].mean()
            linhas.append(f"  {col}: Total = {total:.2f}, Média = {media:.2f}")
        
        linhas.append("")
        linhas.append("Dados completos:")
        linhas.append(df.to_string(index=False))
        linhas.append("")
        
        return "\n".join(linhas)
    
    def _resposta_erro(self, mensagem_erro: str) -> Dict[str, Any]:
        """
        Retorna estrutura de erro padronizada.
        
        Args:
            mensagem_erro: Mensagem de erro
            
        Returns:
            Dict com estrutura de erro
        """
        return {
            "resumo": {
                "total_origem": 0.0,
                "total_destino": 0.0,
                "diferenca": 0.0,
                "situacao": "Erro no processamento",
                "percentual_divergencia": 0.0
            },
            "diferencas_origem_maior": [],
            "diferencas_contabilidade_maior": [],
            "observacoes": [f"Erro: {mensagem_erro}"]
        }


# Exemplo de uso
if __name__ == "__main__":
    # Configuração do AGNO
    AGNO_API_URL = "https://api.agnai.chat/v1"  # URL da API do AGNO
    AGNO_API_KEY = "sua-api-key-agno"
    AGENT_ID = "seu-agent-id"  # ID do agente criado no AGNO
    
    # Inicializa o agente
    agente = AgenteConciliacaoAGNO(
        agno_api_url=AGNO_API_URL,
        agno_api_key=AGNO_API_KEY,
        agent_id=AGENT_ID
    )
    
    # Processa arquivos (exemplo)
    with open("origem.xlsx", "rb") as f1, \
         open("destino.xlsx", "rb") as f2, \
         open("lancamentos.xlsx", "rb") as f3:
        
        resultado = agente.processar_arquivos_excel(
            arquivo_origem=f1.read(),
            arquivo_destino=f2.read(),
            arquivo_lancamentos=f3.read()
        )
    
    # Exibe resultado
    print(json.dumps(resultado, indent=2, ensure_ascii=False))