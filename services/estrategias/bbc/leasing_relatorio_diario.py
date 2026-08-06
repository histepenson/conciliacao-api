# services/estrategias/bbc/leasing_relatorio_diario.py
"""
Parser exclusivo da BBC para os relatorios impressos "Movimentacao Diaria"
do Protheus (RL323E_v1 / RL117E_v1) usados na Conferencia LEASING:
Cancelamento de Contrato, Contratos 2 e 6, Contratos 4.

Layout do arquivo (Excel "impresso", nao tabular): bloco de cabecalho,
depois N blocos repetidos "Relatorio de <X>:" -> linha de header de
colunas -> linhas de detalhe (uma por lancamento) -> uma linha de
SUBTOTAL por natureza (LCTO numerico, DT.LANC vazio, HISTORICO na
coluna 2 em vez da 5, contas DB/CR combinadas na coluna 5 como texto
"DB:<conta> - <desc>\nCR:<conta> - <desc>").

Usamos as linhas de SUBTOTAL como base da Conferencia LEASING -- ja vem
no valor agregado por natureza que bate com o razao contabil, sem
precisar re-somar as linhas de detalhe.

Isolado aqui (fora de qualquer service generico) porque esse layout de
relatorio e essa regra de extracao sao exclusivos da BBC.
"""
import re
from typing import BinaryIO, List, Tuple, Union

import pandas as pd

_RE_BLOCO_TITULO = re.compile(r"^Relat[oó]rio de (.+):\s*$", re.IGNORECASE)
_RE_DB = re.compile(r"DB:\s*(\S+)\s*-\s*(.*?)(?:\r?\n|$)", re.IGNORECASE)
_RE_CR = re.compile(r"CR:\s*(\S+)\s*-\s*(.*?)(?:\r?\n|$)", re.IGNORECASE)

COLUNAS_RESULTADO = [
    "relatorio", "lcto", "natureza_codigo", "natureza_descricao",
    "conta_debito", "conta_credito", "valor",
]


def _split_natureza(texto: str) -> Tuple[str, str]:
    texto = (texto or "").strip()
    if " - " in texto:
        codigo, descricao = texto.split(" - ", 1)
        return codigo.strip(), re.sub(r"\s+", " ", descricao.strip())
    return texto, ""


def _extrair_contas(texto: str) -> Tuple[str, str]:
    texto = str(texto or "")
    m_db = _RE_DB.search(texto)
    m_cr = _RE_CR.search(texto)
    conta_debito = m_db.group(1).strip() if m_db else None
    conta_credito = m_cr.group(1).strip() if m_cr else None
    return conta_debito, conta_credito


def parsear_relatorio_diario(arquivo: Union[bytes, BinaryIO]) -> pd.DataFrame:
    """
    Le um relatorio "Movimentacao Diaria" (Cancelamento, Contratos 2 e 6
    ou Contratos 4) e retorna um DataFrame com uma linha por SUBTOTAL de
    natureza encontrado, colunas: COLUNAS_RESULTADO.

    Levanta ValueError se o arquivo nao tiver o layout esperado (nenhuma
    linha de subtotal reconhecida).
    """
    df_raw = pd.read_excel(arquivo, header=None)

    linhas: List[dict] = []
    relatorio_atual = None

    for row in df_raw.itertuples(index=False, name=None):
        col0 = row[0] if len(row) > 0 else None
        col1 = row[1] if len(row) > 1 else None
        col2 = row[2] if len(row) > 2 else None
        col5 = row[5] if len(row) > 5 else None
        col9 = row[9] if len(row) > 9 else None

        if isinstance(col0, str):
            m = _RE_BLOCO_TITULO.match(col0.strip())
            if m:
                relatorio_atual = m.group(1).strip()
            continue

        # Linha de subtotal: LCTO numerico, DT.LANC vazio, HISTORICO na
        # coluna 2 (nao na 5, como nas linhas de detalhe), contas DB/CR
        # combinadas como texto na coluna 5.
        if (
            isinstance(col0, (int, float))
            and pd.notna(col0)
            and pd.isna(col1)
            and isinstance(col2, str)
            and col2.strip()
            and isinstance(col5, str)
            and "DB:" in col5
        ):
            natureza_codigo, natureza_descricao = _split_natureza(col2)
            conta_debito, conta_credito = _extrair_contas(col5)
            linhas.append({
                "relatorio": relatorio_atual,
                "lcto": str(int(col0)),
                "natureza_codigo": natureza_codigo,
                "natureza_descricao": natureza_descricao,
                "conta_debito": conta_debito,
                "conta_credito": conta_credito,
                "valor": float(col9) if pd.notna(col9) else 0.0,
            })

    if not linhas:
        raise ValueError(
            "Nenhuma linha de subtotal por natureza foi encontrada. Verifique se o "
            "arquivo e um relatorio 'Movimentacao Diaria' exportado do Protheus."
        )

    return pd.DataFrame(linhas, columns=COLUNAS_RESULTADO)
