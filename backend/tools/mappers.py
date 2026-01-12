"""
Mappers para converter dados do DataFrame para formato JSON/dict
Compatível com as colunas retornadas por calcular_diferencas
"""

def map_origem_maior(row):
    """
    Mapeia registros onde Origem > Contabilidade
    Row vem com as colunas:
    - Código
    - Cliente
    - Valor Financeiro
    - Valor Contabilidade
    - Diferença
    - Tipo Diferença
    """
    return {
        "cnpj": str(row.get("Código", "")).strip() if row.get("Código") else None,
        "nome": str(row.get("Cliente", "")).strip() if row.get("Cliente") else None,
        "valor_origem": float(row.get("Valor Financeiro", 0)),
        "valor_contabil": float(row.get("Valor Contabilidade", 0)),
        "diferenca": float(row.get("Diferença", 0)),
        "prazo": classificar_prazo(row.get("Código")),  # Classificar por código
        "tipo_diferenca": "Origem Maior"
    }


def map_contabilidade_maior(df, conta_contabil):
    return [
        {
            "identificador": row["Código"],
            "data": None,
            "valor": row["Diferença"],
            "conta_contabil": conta_contabil,
            "historico": "Valor maior na Contabilidade"
        }
        for _, row in df.iterrows()
    ]



def classificar_prazo(codigo):
    """
    Classifica o prazo baseado no código (CNPJ).
    Regra: CNPJs começados com dígitos menores são Curto Prazo, maiores são Longo Prazo.
    Você pode ajustar essa lógica conforme sua necessidade.
    """
    if not codigo:
        return "Não Classificado"
    
    codigo_str = str(codigo).strip()
    
    # Lógica simples: se o código tem menos de 11 dígitos, é Curto Prazo
    # Ajuste conforme sua regra de negócio
    if len(codigo_str) < 11:
        return "Curto"
    
    # Exemplo alternativo: baseado no primeiro dígito do CNPJ
    # primeiro_digito = int(codigo_str[0]) if codigo_str and codigo_str[0].isdigit() else 5
    # return "Curto" if primeiro_digito < 5 else "Longo"
    
    return "Longo"


def map_registro_conciliado(row):
    """
    Mapeia registros que bateram perfeitamente
    """
    return {
        "cnpj": str(row.get("Código", "")).strip() if row.get("Código") else None,
        "nome": str(row.get("Cliente", "")).strip() if row.get("Cliente") else None,
        "valor": float(row.get("Valor Financeiro", 0)),
        "prazo": classificar_prazo(row.get("Código")),
        "tipo_diferenca": "Conciliado"
    }