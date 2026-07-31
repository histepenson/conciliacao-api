# services/estrategias/rancheiro/croms051_tratativas.py
"""
Tratativas exclusivas do relatorio CROMS051 (Conta Corrente Desconto) da
Rancheiro. Isolado aqui (fora de services/croms051_service.py, que e o proxy
generico do ZCROMS051API) porque essas regras so existem para esse relatorio.

Regras (aplicadas linha a linha, apos o relatorio inteiro ja ter sido
montado pelo Protheus):
  1) Linhas com desconto_pago = True (DESC PAGO = SIM): se valor_associacao
     != 0 e valor = 0, copia valor_associacao para valor; se valor != 0 e
     valor_associacao = 0, copia valor para valor_associacao; se as duas
     colunas tem valor (mesmo divergentes), nao altera.
  2) Linhas com origem = SOPAG: mesma regra do item 1.
  3) Coluna "diferenca" = valor_associacao - valor (calculada apos as
     tratativas 1 e 2), inserida entre "valor" e "valor_associacao".
"""
from typing import Any


def agrupar_croms051_por_cliente(registros_tratados: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Agrega os registros do CROMS051 (ja tratados por aplicar_tratativas_croms051)
    por cliente/loja, somando o saldo (valor - valor_associacao) de cada linha e
    descartando as demais ~20 colunas do relatorio bruto (modalidade, vendedor,
    historico, acordo, etc.).

    Usado para reduzir a carga (centenas de milhares de linhas de transacao) a
    um resumo por cliente (poucos milhares de linhas) antes de sair do backend
    -- so' o saldo liquido por cliente importa para o abatimento em
    abate_croms051.py::_calcular_abatimento_por_codigo.
    """
    agregados: dict[tuple[str, str], dict[str, Any]] = {}

    for linha in registros_tratados:
        base = str(linha.get("codigo_cliente", "")).strip()
        loja = str(linha.get("loja", "")).strip()
        if not base:
            continue
        chave = (base, loja)
        item = agregados.get(chave)
        if item is None:
            item = {
                "codigo_cliente": base,
                "loja": loja,
                "cliente": str(linha.get("cliente", "")).strip(),
                "saldo": 0.0,
            }
            agregados[chave] = item
        valor = float(linha.get("valor") or 0)
        valor_associacao = float(linha.get("valor_associacao") or 0)
        item["saldo"] += valor - valor_associacao

    resultado = list(agregados.values())
    for item in resultado:
        item["saldo"] = round(item["saldo"], 2)

    return resultado


def aplicar_tratativas_croms051(registros: list[dict[str, Any]]) -> list[dict[str, Any]]:
    resultado: list[dict[str, Any]] = []

    for linha in registros:
        valor = float(linha.get("valor") or 0)
        valor_associacao = float(linha.get("valor_associacao") or 0)
        desconto_pago = bool(linha.get("desconto_pago"))
        origem = str(linha.get("origem") or "").strip().upper()

        if desconto_pago or origem == "SOPAG":
            if valor_associacao != 0 and valor == 0:
                valor = valor_associacao
            elif valor != 0 and valor_associacao == 0:
                valor_associacao = valor

        valor = round(valor, 2)
        valor_associacao = round(valor_associacao, 2)
        diferenca = round(valor_associacao - valor, 2)

        nova_linha: dict[str, Any] = {}
        for chave, valor_original in linha.items():
            if chave == "valor":
                nova_linha["valor"] = valor
                nova_linha["diferenca"] = diferenca
            elif chave == "valor_associacao":
                nova_linha["valor_associacao"] = valor_associacao
            else:
                nova_linha[chave] = valor_original
        resultado.append(nova_linha)

    return resultado
