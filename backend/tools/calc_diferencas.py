import pandas as pd
from datetime import datetime
from openpyxl import load_workbook


def calcular_diferencas(df_financeiro: pd.DataFrame, df_contabilidade: pd.DataFrame, 
                       salvar_arquivo: bool = True, caminho_saida: str = None) -> dict:
    """
    Calcula diferenças entre Financeiro e Contabilidade (em ambas direções).
    
    Parâmetros:
    -----------
    df_financeiro : pd.DataFrame
        DataFrame normalizado do financeiro (colunas: codigo, cliente, valor)
    df_contabilidade : pd.DataFrame
        DataFrame normalizado da contabilidade (colunas: codigo, cliente, valor)
    salvar_arquivo : bool
        Se True, salva resultado em arquivo Excel
    caminho_saida : str
        Caminho para salvar o arquivo (padrão: diferencas_YYYYMMDD_HHMMSS.xlsx)
    
    Retorna:
    --------
    dict contendo:
        - 'df_completo': DataFrame com todas as diferenças
        - 'resumo': Estatísticas das diferenças
        - 'caminho_arquivo': Caminho do arquivo salvo (se salvar_arquivo=True)
    """
    
    print("📊 Calculando diferenças...")
    
    # Padronizar nomes das colunas
    df_fin = df_financeiro.copy()
    df_cont = df_contabilidade.copy()
    
    # Garantir que as colunas existem
    if 'codigo' not in df_fin.columns or 'valor' not in df_fin.columns:
        raise ValueError("df_financeiro deve ter colunas 'codigo' e 'valor'")
    if 'codigo' not in df_cont.columns or 'valor' not in df_cont.columns:
        raise ValueError("df_contabilidade deve ter colunas 'codigo' e 'valor'")
    
    # Fazer merge completo (outer join) para pegar todos os códigos
    df_merge = pd.merge(
        df_fin[['codigo', 'cliente', 'valor']],
        df_cont[['codigo', 'cliente', 'valor']],
        on='codigo',
        how='outer',
        suffixes=('_fin', '_cont')
    )
    
    # Preencher valores NaN com 0
    df_merge['valor_fin'] = df_merge['valor_fin'].fillna(0)
    df_merge['valor_cont'] = df_merge['valor_cont'].fillna(0)
    
    # Usar cliente do financeiro, se não existir usar da contabilidade
    df_merge['cliente'] = df_merge['cliente_fin'].fillna(df_merge['cliente_cont'])
    
    # Calcular diferença: Contabilidade - Financeiro
    df_merge['diferenca'] = df_merge['valor_cont'] - df_merge['valor_fin']
    df_merge['diferenca_abs'] = df_merge['diferenca'].abs()
    
    # Calcular percentual de diferença
    df_merge['diferenca_perc'] = 0.0
    mask = df_merge['valor_fin'] != 0
    df_merge.loc[mask, 'diferenca_perc'] = (
        (df_merge.loc[mask, 'diferenca'] / df_merge.loc[mask, 'valor_fin']) * 100
    )
    
    # Classificar origem dos registros
    df_merge['origem'] = 'Ambos'
    df_merge.loc[df_merge['valor_fin'] == 0, 'origem'] = 'Só Contabilidade'
    df_merge.loc[df_merge['valor_cont'] == 0, 'origem'] = 'Só Financeiro'
    
    # Classificar tipo de diferença
    df_merge['tipo_diferenca'] = 'Sem diferença'
    df_merge.loc[df_merge['diferenca'] > 0, 'tipo_diferenca'] = 'Contabilidade > Financeiro'
    df_merge.loc[df_merge['diferenca'] < 0, 'tipo_diferenca'] = 'Financeiro > Contabilidade'
    df_merge.loc[df_merge['origem'] != 'Ambos', 'tipo_diferenca'] = 'Exclusivo'
    
    # Selecionar e ordenar colunas finais
    df_resultado = df_merge[[
        'codigo',
        'cliente',
        'valor_fin',
        'valor_cont',
        'diferenca',
        'diferenca_abs',
        'diferenca_perc',
        'origem',
        'tipo_diferenca'
    ]].copy()
    
    # Renomear para melhor visualização
    df_resultado.columns = [
        'Código',
        'Cliente',
        'Valor Financeiro',
        'Valor Contabilidade',
        'Diferença',
        'Diferença Absoluta',
        'Diferença %',
        'Origem',
        'Tipo Diferença'
    ]
    
    # Ordenar por diferença absoluta (maiores primeiro)
    df_resultado = df_resultado.sort_values('Diferença Absoluta', ascending=False)
    
    # Calcular resumo
    resumo = {
        'total_registros': len(df_resultado),
        'registros_ambos': len(df_resultado[df_resultado['Origem'] == 'Ambos']),
        'registros_so_financeiro': len(df_resultado[df_resultado['Origem'] == 'Só Financeiro']),
        'registros_so_contabilidade': len(df_resultado[df_resultado['Origem'] == 'Só Contabilidade']),
        'registros_com_diferenca': len(df_resultado[df_resultado['Diferença Absoluta'] > 0.01]),
        'registros_sem_diferenca': len(df_resultado[df_resultado['Diferença Absoluta'] <= 0.01]),
        'diferenca_total': df_resultado['Diferença'].sum(),
        'diferenca_absoluta_total': df_resultado['Diferença Absoluta'].sum(),
        'maior_diferenca': df_resultado['Diferença Absoluta'].max(),
        'valor_total_financeiro': df_resultado['Valor Financeiro'].sum(),
        'valor_total_contabilidade': df_resultado['Valor Contabilidade'].sum()
    }
    
    print(f"   ✓ Total de registros analisados: {resumo['total_registros']}")
    print(f"   ✓ Registros com diferença: {resumo['registros_com_diferenca']}")
    print(f"   ✓ Diferença total: R$ {resumo['diferenca_total']:,.2f}")
    
    # Salvar arquivo se solicitado
    caminho_arquivo = None
    if salvar_arquivo:
        if caminho_saida is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            caminho_arquivo = f"diferencas_{timestamp}.xlsx"
        else:
            caminho_arquivo = caminho_saida
        
        # Criar arquivo Excel com múltiplas abas
        print(f"\n💾 Salvando arquivo: {caminho_arquivo}")
        
        with pd.ExcelWriter(caminho_arquivo, engine='openpyxl') as writer:
            # Aba 1: Todas as diferenças
            df_resultado.to_excel(writer, sheet_name='Todas Diferenças', index=False)
            
            # Aba 2: Apenas com diferenças significativas
            df_com_dif = df_resultado[df_resultado['Diferença Absoluta'] > 0.01].copy()
            df_com_dif.to_excel(writer, sheet_name='Com Diferenças', index=False)
            
            # Aba 3: Apenas no Financeiro
            df_so_fin = df_resultado[df_resultado['Origem'] == 'Só Financeiro'].copy()
            if len(df_so_fin) > 0:
                df_so_fin.to_excel(writer, sheet_name='Só Financeiro', index=False)
            
            # Aba 4: Apenas na Contabilidade
            df_so_cont = df_resultado[df_resultado['Origem'] == 'Só Contabilidade'].copy()
            if len(df_so_cont) > 0:
                df_so_cont.to_excel(writer, sheet_name='Só Contabilidade', index=False)
            
            # Aba 5: Resumo
            df_resumo = pd.DataFrame([resumo]).T
            df_resumo.columns = ['Valor']
            df_resumo.index.name = 'Métrica'
            df_resumo.to_excel(writer, sheet_name='Resumo')
        
        # Aplicar formatação
        _formatar_arquivo_excel(caminho_arquivo)
        
        print(f"   ✓ Arquivo salvo com {len(df_resultado)} registros")
        print(f"   ✓ Abas criadas: Todas Diferenças, Com Diferenças, Só Financeiro, Só Contabilidade, Resumo")
    
    return {
        'df_completo': df_resultado,
        'resumo': resumo,
        'caminho_arquivo': caminho_arquivo
    }


def _formatar_arquivo_excel(caminho_arquivo: str):
    """Aplica formatação ao arquivo Excel gerado"""
    
    wb = load_workbook(caminho_arquivo)
    
    # Formatar cada aba
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        
        if sheet_name == 'Resumo':
            continue
        
        # Encontrar colunas de valor
        header = [cell.value for cell in ws[1]]
        
        for idx, col_name in enumerate(header, 1):
            if col_name in ['Valor Financeiro', 'Valor Contabilidade', 'Diferença', 
                           'Diferença Absoluta']:
                # Aplicar formato de moeda
                for row in range(2, ws.max_row + 1):
                    cell = ws.cell(row=row, column=idx)
                    cell.number_format = 'R$ #,##0.00;[RED]-R$ #,##0.00'
            
            elif col_name == 'Diferença %':
                # Aplicar formato de percentual
                for row in range(2, ws.max_row + 1):
                    cell = ws.cell(row=row, column=idx)
                    cell.number_format = '0.00%'
        
        # Ajustar largura das colunas
        ws.column_dimensions['A'].width = 12  # Código
        ws.column_dimensions['B'].width = 35  # Cliente
        ws.column_dimensions['C'].width = 18  # Valor Financeiro
        ws.column_dimensions['D'].width = 20  # Valor Contabilidade
        ws.column_dimensions['E'].width = 15  # Diferença
        ws.column_dimensions['F'].width = 18  # Diferença Absoluta
        ws.column_dimensions['G'].width = 12  # Diferença %
        ws.column_dimensions['H'].width = 18  # Origem
        ws.column_dimensions['I'].width = 25  # Tipo Diferença
    
    wb.save(caminho_arquivo)
