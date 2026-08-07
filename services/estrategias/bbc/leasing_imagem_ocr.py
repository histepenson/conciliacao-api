# services/estrategias/bbc/leasing_imagem_ocr.py
"""
Extracao via IA de visao (Claude) dos relatorios "Movimentacao Diaria" da
BBC quando chegam como captura de tela (print) em vez de arquivo Excel --
mesmo layout impresso do Protheus que leasing_relatorio_diario.py le de
um .xlsx, so que aqui a fonte e' uma ou mais imagens.

Isolado aqui (exclusivo BBC) porque o layout esperado na imagem (blocos
"Relatorio de X:", linha de subtotal por natureza com texto
"DB:<conta> - <desc>\nCR:<conta> - <desc>") e' o mesmo formato descrito
em leasing_relatorio_diario.py -- so' muda a fonte (imagem em vez de
planilha).
"""
import base64
from typing import List, Tuple

import anthropic
import pandas as pd

from core.config import settings

MODELO = "claude-sonnet-5"

COLUNAS_RESULTADO = [
    "relatorio", "lcto", "natureza_codigo", "natureza_descricao",
    "conta_debito", "conta_credito", "valor",
]

_FERRAMENTA_EXTRACAO = {
    "name": "registrar_naturezas_extraidas",
    "description": "Registra as linhas de SUBTOTAL por natureza encontradas no relatorio.",
    "input_schema": {
        "type": "object",
        "properties": {
            "linhas": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "relatorio": {"type": "string", "description": "Titulo do bloco, ex: 'Apropriacao de receita'"},
                        "lcto": {"type": "string", "description": "Numero do LCTO da linha de subtotal"},
                        "natureza_codigo": {"type": "string", "description": "Codigo da natureza, ex: N202, A300"},
                        "natureza_descricao": {"type": "string", "description": "Descricao da natureza"},
                        "conta_debito": {"type": "string", "description": "Conta contabil apos 'DB:'"},
                        "conta_credito": {"type": "string", "description": "Conta contabil apos 'CR:'"},
                        "valor": {"type": "number", "description": "Valor total da linha de subtotal"},
                    },
                    "required": ["natureza_codigo", "valor"],
                },
            }
        },
        "required": ["linhas"],
    },
}

_PROMPT_SISTEMA = """Voce esta lendo capturas de tela de um relatorio Protheus \
"Movimentacao Diaria" (BBC - leasing). O relatorio tem blocos, cada um comecando \
com um titulo "Relatorio de <X>:", seguido de uma tabela com colunas LCTO, DT. LANC, \
NR. OPERACAO, CLIENTE, DT. MOV., HISTORICO, DEBITA, CREDITA, VLR. LCTO.

Cada bloco tem VARIAS linhas de detalhe (uma por lancamento, com data preenchida) \
e, ao final de cada grupo de mesma natureza, UMA linha de SUBTOTAL: essa linha NAO \
tem DT.LANC/CLIENTE/DT.MOV preenchidos, a coluna HISTORICO mostra "<CODIGO> - <DESCRICAO>" \
(ex: "N202 - APROP JR RAP") e as colunas de conta mostram um texto tipo \
"DB:<conta> - <descricao da conta>\\nCR:<conta> - <descricao da conta>".

Extraia APENAS as linhas de SUBTOTAL (nao as linhas de detalhe individuais). Para \
cada uma, retorne: o titulo do bloco (relatorio), o LCTO, o codigo da natureza, a \
descricao da natureza, a conta de debito, a conta de credito e o valor total. Se \
as imagens forem capturas sequenciais do mesmo relatorio (paginas diferentes), \
combine tudo num unico resultado, sem duplicar linhas que aparecam repetidas em \
capturas sobrepostas. Use a ferramenta fornecida para registrar o resultado."""


def extrair_naturezas_de_imagens(imagens: List[Tuple[bytes, str]]) -> pd.DataFrame:
    """
    imagens: lista de (conteudo_bytes, media_type), ex: [(b"...", "image/png"), ...]
    Retorna DataFrame no mesmo formato de parsear_relatorio_diario
    (COLUNAS_RESULTADO), pronto pra services.leasing_movimentacao_service.registrar_lote.
    """
    if not settings.ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY nao configurada. Fale com o administrador do sistema.")
    if not imagens:
        raise ValueError("Nenhuma imagem enviada.")

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    content = [
        {
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": base64.b64encode(dados).decode("utf-8")},
        }
        for dados, media_type in imagens
    ]
    content.append({
        "type": "text",
        "text": "Extraia as linhas de subtotal por natureza de todas as imagens acima "
                "(podem ser capturas/paginas diferentes do mesmo relatorio).",
    })

    try:
        resposta = client.messages.create(
            model=MODELO,
            max_tokens=4096,
            system=_PROMPT_SISTEMA,
            tools=[_FERRAMENTA_EXTRACAO],
            tool_choice={"type": "tool", "name": "registrar_naturezas_extraidas"},
            messages=[{"role": "user", "content": content}],
        )
    except anthropic.APIError as e:
        raise ValueError(f"Erro ao chamar a IA de extracao: {e}")

    bloco_ferramenta = next((b for b in resposta.content if b.type == "tool_use"), None)
    if not bloco_ferramenta:
        raise ValueError("A IA nao conseguiu extrair nenhuma linha das imagens enviadas.")

    linhas = bloco_ferramenta.input.get("linhas", [])
    if not linhas:
        raise ValueError("A IA nao encontrou nenhuma linha de subtotal por natureza nas imagens enviadas.")

    df = pd.DataFrame(linhas)
    for coluna in COLUNAS_RESULTADO:
        if coluna not in df.columns:
            df[coluna] = None
    return df[COLUNAS_RESULTADO]
