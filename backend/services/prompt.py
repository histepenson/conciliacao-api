"""
Módulo de Prompts para Agente de Conciliação Contábil
Sistema modular de construção de prompts por categorias
"""

# =============================================================================
# CATEGORIA: IDENTIDADE E PAPEL
# =============================================================================

IDENTIDADE = """# AGENTE DE CONCILIAÇÃO CONTÁBIL

Você é um especialista em conciliação contábil com profundo conhecimento em análise de dados contábil e financeiro."""


# =============================================================================
# CATEGORIA: OBJETIVO PRINCIPAL
# =============================================================================

OBJETIVO = """## OBJETIVO
Comparar 3 conjuntos de dados (Origem, Destino (relatório contabil apenas da conta contabil), Lançamentos (todos lançamentos contabil de todas as contas)) e identificar diferenças precisamente."""


# =============================================================================
# CATEGORIA: PROCESSO DE ANÁLISE
# =============================================================================

PROCESSO_ANALISE_TOTAIS = """## PROCESSO

1. **Análise de Totais**
   - Calcule total Origem
   - Calcule total Destino
   - Calcule diferença"""

PROCESSO_ORIGEM_MAIOR = """
2. **Se Origem > Destino**
   Para cada registro divergente:
   - Busque nos Lançamentos por: ID, Valor+Data, Histórico
   - Se encontrou: "Contabilizado em conta diferente" ou "Parcialmente"
   - Se não encontrou: "Não contabilizado\""""

PROCESSO_DESTINO_MAIOR = """
3. **Se Destino > Origem**
   Para cada registro excedente:
   - Localize nos Lançamentos
   - Classifique: "Sem origem", "Duplicado" ou "Indevido\""""

# Processo completo (soma das partes)
PROCESSO = PROCESSO_ANALISE_TOTAIS + PROCESSO_ORIGEM_MAIOR + PROCESSO_DESTINO_MAIOR


# =============================================================================
# CATEGORIA: FORMATO DE SAÍDA
# =============================================================================

FORMATO_SAIDA = """## FORMATO DE SAÍDA

Retorne APENAS JSON válido:

{
  "resumo": {
    "total_origem": 0.00,
    "total_destino": 0.00,
    "diferenca": 0.00,
    "situacao": "Conciliado" ou "Divergente",
    "percentual_divergencia": 0.00
  },
  "diferencas_origem_maior": [
    {
      "identificador": "string",
      "data": "DD/MM/AAAA",
      "valor": 0.00,
      "encontrado_lancamentos": true/false,
      "conta_contabil": "string ou null",
      "historico": "string ou null",
      "situacao": "string"
    }
  ],
  "diferencas_contabilidade_maior": [
    {
      "identificador": "string",
      "data": "DD/MM/AAAA",
      "valor": 0.00,
      "conta_contabil": "string",
      "existe_origem": true/false,
      "historico": "string",
      "situacao": "string"
    }
  ],
  "observacoes": ["string"]
}"""


# =============================================================================
# CATEGORIA: REGRAS CRÍTICAS
# =============================================================================

REGRAS_PROIBIDAS = """## REGRAS CRÍTICAS

❌ PROIBIDO:
- Inventar dados
- Assumir sem evidência
- Texto fora do JSON"""

REGRAS_OBRIGATORIAS = """
✅ OBRIGATÓRIO:
- JSON válido sempre
- 2 casas decimais
- Datas DD/MM/AAAA
- Justificar diferenças"""

# Regras completas (soma das partes)
REGRAS = REGRAS_PROIBIDAS + REGRAS_OBRIGATORIAS


# =============================================================================
# CATEGORIA: MATCHING E PRIORIDADES
# =============================================================================

MATCHING = """## MATCHING (prioridade)
1. Identificador único
2. Valor + Data exata
3. Valor + Data ±3 dias
4. Histórico"""


# =============================================================================
# CATEGORIA: COMPORTAMENTO ESPERADO
# =============================================================================

COMPORTAMENTO = """
Seja técnico, preciso e use linguagem contábil profissional."""


# =============================================================================
# CATEGORIA: CLASSIFICAÇÕES VÁLIDAS
# =============================================================================

CLASSIFICACOES_ORIGEM_MAIOR = """## CLASSIFICAÇÕES VÁLIDAS

### Para diferencas_origem_maior:
- "Não contabilizado"
- "Contabilizado em conta diferente"
- "Contabilizado parcialmente\""""

CLASSIFICACOES_DESTINO_MAIOR = """
### Para diferencas_contabilidade_maior:
- "Lançamento sem origem"
- "Lançamento duplicado"
- "Lançamento indevido\""""

# Classificações completas (soma das partes)
CLASSIFICACOES = CLASSIFICACOES_ORIGEM_MAIOR + CLASSIFICACOES_DESTINO_MAIOR


# =============================================================================
# CATEGORIA: EXEMPLOS (OPCIONAL)
# =============================================================================

EXEMPLOS = """## EXEMPLOS

### Exemplo 1: Origem Maior
```json
{
  "identificador": "NF-12345",
  "valor": 1000.00,
  "encontrado_lancamentos": true,
  "conta_contabil": "1.1.1.02.001",
  "situacao": "Contabilizado em conta diferente"
}
```

### Exemplo 2: Destino Maior
```json
{
  "identificador": "LC-789",
  "valor": 500.00,
  "existe_origem": false,
  "situacao": "Lançamento sem origem"
}
```"""


# =============================================================================
# MONTAGEM FINAL DO PROMPT
# =============================================================================

def construir_prompt_completo(
    incluir_identidade: bool = True,
    incluir_objetivo: bool = True,
    incluir_processo: bool = True,
    incluir_formato_saida: bool = True,
    incluir_regras: bool = True,
    incluir_matching: bool = True,
    incluir_comportamento: bool = True,
    incluir_classificacoes: bool = False,
    incluir_exemplos: bool = False
) -> str:
    """
    Constrói o prompt completo a partir das categorias selecionadas.
    
    Args:
        incluir_identidade: Incluir seção de identidade
        incluir_objetivo: Incluir seção de objetivo
        incluir_processo: Incluir seção de processo
        incluir_formato_saida: Incluir seção de formato de saída
        incluir_regras: Incluir seção de regras
        incluir_matching: Incluir seção de matching
        incluir_comportamento: Incluir seção de comportamento
        incluir_classificacoes: Incluir seção de classificações (opcional)
        incluir_exemplos: Incluir seção de exemplos (opcional)
        
    Returns:
        String com prompt completo
    """
    
    secoes = []
    
    if incluir_identidade:
        secoes.append(IDENTIDADE)
    
    if incluir_objetivo:
        secoes.append(OBJETIVO)
    
    if incluir_processo:
        secoes.append(PROCESSO)
    
    if incluir_formato_saida:
        secoes.append(FORMATO_SAIDA)
    
    if incluir_regras:
        secoes.append(REGRAS)
    
    if incluir_matching:
        secoes.append(MATCHING)
    
    if incluir_classificacoes:
        secoes.append(CLASSIFICACOES)
    
    if incluir_comportamento:
        secoes.append(COMPORTAMENTO)
    
    if incluir_exemplos:
        secoes.append(EXEMPLOS)
    
    # Junta todas as seções com dupla quebra de linha
    return "\n\n".join(secoes)


# =============================================================================
# PROMPT PADRÃO (TODAS AS SEÇÕES PRINCIPAIS)
# =============================================================================

SYSTEM_PROMPT_PADRAO = construir_prompt_completo(
    incluir_identidade=True,
    incluir_objetivo=True,
    incluir_processo=True,
    incluir_formato_saida=True,
    incluir_regras=True,
    incluir_matching=True,
    incluir_comportamento=True,
    incluir_classificacoes=False,  # Opcional, já está implícito no processo
    incluir_exemplos=False          # Opcional, para não poluir o prompt
)


# =============================================================================
# PROMPT SIMPLIFICADO (VERSÃO REDUZIDA)
# =============================================================================

SYSTEM_PROMPT_SIMPLIFICADO = construir_prompt_completo(
    incluir_identidade=True,
    incluir_objetivo=True,
    incluir_processo=True,
    incluir_formato_saida=True,
    incluir_regras=True,
    incluir_matching=False,
    incluir_comportamento=True,
    incluir_classificacoes=False,
    incluir_exemplos=False
)


# =============================================================================
# PROMPT COMPLETO (COM TUDO)
# =============================================================================

SYSTEM_PROMPT_COMPLETO = construir_prompt_completo(
    incluir_identidade=True,
    incluir_objetivo=True,
    incluir_processo=True,
    incluir_formato_saida=True,
    incluir_regras=True,
    incluir_matching=True,
    incluir_comportamento=True,
    incluir_classificacoes=True,
    incluir_exemplos=True
)


# =============================================================================
# FUNÇÃO DE ACESSO PRINCIPAL
# =============================================================================

def obter_system_prompt(versao: str = "padrao") -> str:
    """
    Retorna o system prompt na versão especificada.
    
    Args:
        versao: Versão do prompt desejada
                - "padrao": Versão padrão (recomendado)
                - "simplificado": Versão reduzida
                - "completo": Versão com todas as seções
                - "custom": Chame construir_prompt_completo() diretamente
                
    Returns:
        String com o system prompt
    """
    
    versoes = {
        "padrao": SYSTEM_PROMPT_PADRAO,
        "simplificado": SYSTEM_PROMPT_SIMPLIFICADO,
        "completo": SYSTEM_PROMPT_COMPLETO
    }
    
    if versao not in versoes:
        raise ValueError(f"Versão '{versao}' não encontrada. Use: {list(versoes.keys())}")
    
    return versoes[versao]


# =============================================================================
# UTILITÁRIOS
# =============================================================================

def listar_categorias() -> list:
    """Retorna lista de todas as categorias disponíveis."""
    return [
        "IDENTIDADE",
        "OBJETIVO",
        "PROCESSO",
        "FORMATO_SAIDA",
        "REGRAS",
        "MATCHING",
        "COMPORTAMENTO",
        "CLASSIFICACOES",
        "EXEMPLOS"
    ]


def obter_categoria(nome_categoria: str) -> str:
    """
    Retorna o conteúdo de uma categoria específica.
    
    Args:
        nome_categoria: Nome da categoria (use listar_categorias() para ver opções)
        
    Returns:
        String com conteúdo da categoria
    """
    
    categorias = {
        "IDENTIDADE": IDENTIDADE,
        "OBJETIVO": OBJETIVO,
        "PROCESSO": PROCESSO,
        "FORMATO_SAIDA": FORMATO_SAIDA,
        "REGRAS": REGRAS,
        "MATCHING": MATCHING,
        "COMPORTAMENTO": COMPORTAMENTO,
        "CLASSIFICACOES": CLASSIFICACOES,
        "EXEMPLOS": EXEMPLOS
    }
    
    if nome_categoria not in categorias:
        raise ValueError(f"Categoria '{nome_categoria}' não encontrada. Use listar_categorias()")
    
    return categorias[nome_categoria]