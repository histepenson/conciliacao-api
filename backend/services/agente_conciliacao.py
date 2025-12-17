"""
Agente de Conciliação Contábil usando Framework AGNO
"""
from prompt import obter_system_prompt
from agno import Agent, Runner
from anthropic import Anthropic
import pandas as pd
from io import BytesIO
from typing import Dict, Any, List
import json


class AgenteConciliacaoAGNO:
    """
    Agente de conciliação que usa framework AGNO para orquestrar o processamento.
    """
    
    def __init__(self, anthropic_api_key: str):
        """
        Inicializa o agente AGNO.
        
        Args:
            anthropic_api_key: API key da Anthropic
        """
        self.client = Anthropic(api_key=anthropic_api_key)
        self.agent = self._criar_agente()
        self.runner = Runner()
    
    def _criar_agente(self) -> Agent:
        """
        Cria e configura o agente AGNO com suas ferramentas e instruções.
        """
        
        # Instruções do sistema para o agente
        system_prompt = obter_system_prompt("completo")
        # Cria agente AGNO
        agent = Agent(
            name="Agente de Conciliação Contábil",
            model="claude-sonnet-4-20250514",
            instructions=system_prompt,
            tools=[
                self._tool_processar_excel,
                self._tool_calcular_totais,
                self._tool_identificar_diferencas,
                self._tool_buscar_nos_lancamentos
            ],
            temperature=0.2,
            max_tokens=8000
        )
        
        return agent
    
    def _tool_processar_excel(self, arquivo_bytes: bytes, tipo: str) -> Dict[str, Any]:
        """
        Ferramenta: Processa arquivo Excel e retorna DataFrame como dict.
        
        Args:
            arquivo_bytes: Bytes do arquivo Excel
            tipo: Tipo do arquivo (origem, destino, lancamentos)
            
        Returns:
            Dict com dados do arquivo
        """
        df = pd.read_excel(BytesIO(arquivo_bytes))
        
        return {
            "tipo": tipo,
            "total_registros": len(df),
            "colunas": df.columns.tolist(),
            "dados": df.to_dict(orient='records'),
            "estatisticas": self._calcular_estatisticas(df)
        }
    
    def _tool_calcular_totais(self, dados: List[Dict]) -> Dict[str, float]:
        """
        Ferramenta: Calcula totais dos valores.
        
        Args:
            dados: Lista de registros
            
        Returns:
            Dict com totais calculados
        """
        # Identifica coluna de valor
        coluna_valor = None
        if dados and len(dados) > 0:
            for key in dados[0].keys():
                if 'valor' in key.lower():
                    coluna_valor = key
                    break
        
        if not coluna_valor:
            return {"total": 0.0, "erro": "Coluna valor não encontrada"}
        
        total = sum(float(registro.get(coluna_valor, 0)) for registro in dados)
        
        return {
            "total": round(total, 2),
            "quantidade": len(dados),
            "coluna_usada": coluna_valor
        }
    
    def _tool_identificar_diferencas(
        self, 
        dados_origem: List[Dict], 
        dados_destino: List[Dict]
    ) -> Dict[str, Any]:
        """
        Ferramenta: Identifica diferenças entre origem e destino.
        
        Args:
            dados_origem: Registros da origem
            dados_destino: Registros do destino
            
        Returns:
            Dict com diferenças identificadas
        """
        # Converte para DataFrames
        df_origem = pd.DataFrame(dados_origem)
        df_destino = pd.DataFrame(dados_destino)
        
        # Identifica colunas de valor
        col_valor_origem = self._identificar_coluna_valor(df_origem)
        col_valor_destino = self._identificar_coluna_valor(df_destino)
        
        total_origem = df_origem[col_valor_origem].sum() if col_valor_origem else 0
        total_destino = df_destino[col_valor_destino].sum() if col_valor_destino else 0
        
        diferenca = total_origem - total_destino
        
        return {
            "total_origem": round(total_origem, 2),
            "total_destino": round(total_destino, 2),
            "diferenca": round(diferenca, 2),
            "situacao": "Conciliado" if abs(diferenca) < 0.01 else "Divergente"
        }
    
    def _tool_buscar_nos_lancamentos(
        self,
        registro: Dict,
        lancamentos: List[Dict],
        criterio: str = "identificador"
    ) -> Dict[str, Any]:
        """
        Ferramenta: Busca um registro específico nos lançamentos.
        
        Args:
            registro: Registro a buscar
            lancamentos: Lista de lançamentos
            criterio: Critério de busca (identificador, valor_data, historico)
            
        Returns:
            Dict com resultado da busca
        """
        df_lancamentos = pd.DataFrame(lancamentos)
        
        if criterio == "identificador":
            # Busca por ID
            identificador = registro.get('id') or registro.get('identificador')
            if identificador:
                match = df_lancamentos[
                    df_lancamentos.apply(
                        lambda row: str(identificador).upper() in str(row).upper(),
                        axis=1
                    )
                ]
                if not match.empty:
                    return {
                        "encontrado": True,
                        "registro": match.iloc[0].to_dict(),
                        "criterio_usado": "identificador"
                    }
        
        elif criterio == "valor_data":
            # Busca por valor e data
            valor = registro.get('valor')
            data = registro.get('data')
            
            col_valor_lanc = self._identificar_coluna_valor(df_lancamentos)
            col_data_lanc = self._identificar_coluna_data(df_lancamentos)
            
            if valor and data and col_valor_lanc and col_data_lanc:
                match = df_lancamentos[
                    (abs(df_lancamentos[col_valor_lanc] - valor) < 0.01) &
                    (df_lancamentos[col_data_lanc].astype(str) == str(data))
                ]
                if not match.empty:
                    return {
                        "encontrado": True,
                        "registro": match.iloc[0].to_dict(),
                        "criterio_usado": "valor_data"
                    }
        
        return {
            "encontrado": False,
            "registro": None,
            "criterio_usado": criterio
        }
    
    def _calcular_estatisticas(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calcula estatísticas básicas do DataFrame"""
        stats = {}
        
        # Colunas numéricas
        for col in df.select_dtypes(include=['number']).columns:
            stats[col] = {
                "total": float(df[col].sum()),
                "media": float(df[col].mean()),
                "min": float(df[col].min()),
                "max": float(df[col].max())
            }
        
        return stats
    
    def _identificar_coluna_valor(self, df: pd.DataFrame) -> str:
        """Identifica coluna de valor no DataFrame"""
        for col in df.columns:
            if 'valor' in col.lower():
                return col
        return None
    
    def _identificar_coluna_data(self, df: pd.DataFrame) -> str:
        """Identifica coluna de data no DataFrame"""
        for col in df.columns:
            if 'data' in col.lower():
                return col
        return None
    
    def processar_arquivos_excel(
        self,
        arquivo_origem: bytes,
        arquivo_destino: bytes,
        arquivo_lancamentos: bytes
    ) -> Dict[str, Any]:
        """
        Processa arquivos Excel usando o agente AGNO.
        
        Args:
            arquivo_origem: Bytes do arquivo origem
            arquivo_destino: Bytes do arquivo destino
            arquivo_lancamentos: Bytes do arquivo lançamentos
            
        Returns:
            Dict com resultado da conciliação
        """
        
        # Processa arquivos Excel
        dados_origem = self._tool_processar_excel(arquivo_origem, "origem")
        dados_destino = self._tool_processar_excel(arquivo_destino, "destino")
        dados_lancamentos = self._tool_processar_excel(arquivo_lancamentos, "lancamentos")
        
        # Monta contexto para o agente
        contexto = f"""
═══════════════════════════════════════
📄 ARQUIVO ORIGEM
═══════════════════════════════════════
Total de registros: {dados_origem['total_registros']}
Colunas: {', '.join(dados_origem['colunas'])}

Primeiros registros:
{json.dumps(dados_origem['dados'][:10], indent=2, ensure_ascii=False)}

═══════════════════════════════════════
📄 ARQUIVO DESTINO (Contabilidade)
═══════════════════════════════════════
Total de registros: {dados_destino['total_registros']}
Colunas: {', '.join(dados_destino['colunas'])}

Primeiros registros:
{json.dumps(dados_destino['dados'][:10], indent=2, ensure_ascii=False)}

═══════════════════════════════════════
📄 ARQUIVO LANÇAMENTOS
═══════════════════════════════════════
Total de registros: {dados_lancamentos['total_registros']}
Colunas: {', '.join(dados_lancamentos['colunas'])}

Primeiros registros:
{json.dumps(dados_lancamentos['dados'][:10], indent=2, ensure_ascii=False)}

═══════════════════════════════════════

Analise os dados acima e retorne o JSON de conciliação conforme especificado.
"""
        
        # Executa agente AGNO
        try:
            response = self.runner.run(
                agent=self.agent,
                messages=[{"role": "user", "content": contexto}]
            )
            
            # Extrai JSON da resposta
            resultado = self._extrair_json_resposta(response.content)
            
            return resultado
            
        except Exception as e:
            print(f"Erro ao executar agente: {e}")
            return self._resposta_erro(str(e))
    
    def _extrair_json_resposta(self, texto: str) -> Dict[str, Any]:
        """Extrai JSON da resposta do agente"""
        import re
        
        # Remove markdown
        texto = re.sub(r'```json\s*', '', texto)
        texto = re.sub(r'```\s*', '', texto)
        texto = texto.strip()
        
        try:
            return json.loads(texto)
        except json.JSONDecodeError:
            # Tenta encontrar JSON
            match = re.search(r'\{.*\}', texto, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except:
                    pass
            
            return self._resposta_erro("Erro ao fazer parse do JSON")
    
    def _resposta_erro(self, mensagem: str) -> Dict[str, Any]:
        """Retorna estrutura de erro"""
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
            "observacoes": [f"Erro: {mensagem}"]
        }