"""
Mappers para converter dados do DataFrame para formato JSON/dict
Compativel com as colunas retornadas por calcular_diferencas
"""

def map_origem_maior(row):
    """
    Mapeia registros onde Origem > Contabilidade
    Row vem com as colunas:
    - Codigo
    - Cliente
    - Valor Financeiro
    - Valor Contabilidade
    - Diferenca
    - Tipo Diferenca
    """
    return {
        "cnpj": str(row.get("Codigo", "")).strip() if row.get("Codigo") else None,
        "nome": str(row.get("Cliente", "")).strip() if row.get("Cliente") else None,
        "valor_origem": float(row.get("Valor Financeiro", 0)),
        "valor_contabil": float(row.get("Valor Contabilidade", 0)),
        "diferenca": float(row.get("Diferenca", 0)),
        "prazo": classificar_prazo(row.get("Codigo")),  # Classificar por codigo
        "tipo_diferenca": "Origem Maior"
    }


def map_contabilidade_maior(df, conta_contabil):
    return [
        {
            "identificador": row["Codigo"],
            "data": None,
            "valor": row["Diferenca"],
            "conta_contabil": conta_contabil,
            "historico": "Valor maior na Contabilidade"
        }
        for _, row in df.iterrows()
    ]



def classificar_prazo(codigo):
    """
    Classifica o prazo baseado no codigo (CNPJ).
    Regra: CNPJs comecados com digitos menores sao Curto Prazo, maiores sao Longo Prazo.
    Voce pode ajustar essa logica conforme sua necessidade.
    """
    if not codigo:
        return "Nao Classificado"
    
    codigo_str = str(codigo).strip()
    
    # Logica simples: se o codigo tem menos de 11 digitos, e Curto Prazo
    # Ajuste conforme sua regra de negocio
    if len(codigo_str) < 11:
        return "Curto"
    
    # Exemplo alternativo: baseado no primeiro digito do CNPJ
    # primeiro_digito = int(codigo_str[0]) if codigo_str and codigo_str[0].isdigit() else 5
    # return "Curto" if primeiro_digito < 5 else "Longo"
    
    return "Longo"


def map_registro_conciliado(row):
    """
    Mapeia registros que bateram perfeitamente
    """
    return {
        "cnpj": str(row.get("Codigo", "")).strip() if row.get("Codigo") else None,
        "nome": str(row.get("Cliente", "")).strip() if row.get("Cliente") else None,
        "valor": float(row.get("Valor Financeiro", 0)),
        "prazo": classificar_prazo(row.get("Codigo")),
        "tipo_diferenca": "Conciliado"
    }