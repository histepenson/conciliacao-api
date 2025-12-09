import pandas as pd
from datetime import datetime
import re
def normalizar_planilha_contabilidade(entrada):
    """
    Normaliza a planilha de contabilidade COM AGRUPAMENTO.
    
    Parâmetros:
    -----------
    entrada : str ou DataFrame
        Caminho do arquivo Excel ou DataFrame já carregado
    
    Retorna:
    --------
    DataFrame normalizado com colunas: codigo, cliente, valor (AGRUPADO)
    """
    
    # Carregar DataFrame
    if isinstance(entrada, pd.DataFrame):
        df = entrada.copy()
    elif isinstance(entrada, str):
        df = pd.read_excel(entrada)
    else:
        raise ValueError("entrada deve ser um caminho de arquivo ou DataFrame")
    
    # Processar
    df_normalizado = pd.DataFrame()
    df_normalizado['codigo'] = df['Codigo.1']
    df_normalizado['cliente'] = df['Descricao.1']
    df_normalizado['valor_bruto'] = df['Saldo atual']
    
    df_normalizado = df_normalizado[df_normalizado['codigo'].notna()].copy()
    df_normalizado = df_normalizado[df_normalizado['valor_bruto'].notna()].copy()
    
    def converter_valor(valor_str):
        if pd.isna(valor_str):
            return 0.0
        
        valor_str = str(valor_str).strip()
        valor_str = re.sub(r'\s*[DC]$', '', valor_str)
        valor_str = valor_str.replace('.', '').replace(',', '.')
        
        try:
            return float(valor_str)
        except:
            return 0.0
    
    df_normalizado['valor'] = df_normalizado['valor_bruto'].apply(converter_valor)
    
    # ⭐ AGLUTINAR POR CÓDIGO (somar valores) ⭐
    df_agrupado = df_normalizado.groupby(['codigo', 'cliente']).agg({
        'valor': 'sum'
    }).reset_index()
    
    return df_agrupado