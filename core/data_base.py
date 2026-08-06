"""
Parsing do parametro `data_base` usado nas telas de conciliacao.

Dois formatos convivem na aplicacao:
- DD/MM/YYYY (ou MM/YYYY): digitado nas telas de importacao/consulta de balancete.
- YYYYMMDD (sem separador): enviado pelas telas de conciliacao (financeira,
  bancaria, estoque, impostos) -- ver dateUtils.js::converterDataParaYYYYMMDD
  no frontend.

Use `parse_ano_mes` como ponto unico de conversao para nao duplicar essa regra.
"""
import re


def parse_ano_mes(data_base: str) -> tuple[int, int]:
    """Extrai (ano, mes) de uma data-base em DD/MM/YYYY, MM/YYYY ou YYYYMMDD."""
    valor = (data_base or "").strip()

    if re.fullmatch(r"\d{8}", valor):
        return int(valor[:4]), int(valor[4:6])

    partes = valor.split("/")
    if len(partes) == 3:
        _, mes, ano = partes
        return int(ano), int(mes)
    if len(partes) == 2:
        mes, ano = partes
        return int(ano), int(mes)

    raise ValueError(f"Formato de data_base invalido: {data_base}")
