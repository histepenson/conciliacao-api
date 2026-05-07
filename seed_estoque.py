"""
Seed de dados de estoque para testes.
Empresa: SÃO MIGUEL PARTICIPAÇÕES (id=1)
- 20 produtos agrícolas
- De-Para por 4 fornecedores reais
- 50 NF-e de entrada (com itens vinculados)
- 100 NF-e de saída (com itens vinculados)
- Saldos mensais (JanAbr 2026)
- Movimentações correspondentes
"""

import random
import string
from datetime import date, timedelta
from decimal import Decimal

from db import SessionLocal
from models.produto import Produto
from models.produto_fornecedor import ProdutoFornecedor, OperacaoConversao
from models.nfe import NfeEntrada, NfeEntradaItem, NfeSaida, NfeSaidaItem, StatusNfe
from models.estoque import EstoqueSaldo, EstoqueMovimentacao, TipoMovimentacao

random.seed(42)

EMPRESA_ID = 1
CNPJ_EMPRESA = "23828180000108"

# 
# CATÁLOGO DE PRODUTOS
# 
PRODUTOS_CATALOGO = [
    # (codigo_interno, descricao, ncm, unidade, cfop_saida, valor_unitario)
    ("SOJ001", "Soja em Graos",               "12010010", "SC",  "5101", Decimal("120.00")),
    ("SOJ002", "Sementes de Soja RR",          "12010090", "SC",  "5101", Decimal("185.00")),
    ("MIL001", "Milho em Graos",               "10059010", "SC",  "5101", Decimal("75.00")),
    ("MIL002", "Sementes de Milho Hibrido",    "10059090", "SC",  "5101", Decimal("250.00")),
    ("TRI001", "Trigo em Graos",               "10019900", "SC",  "5101", Decimal("90.00")),
    ("FER001", "Fertilizante NPK 20-05-20",    "31049000", "TON", "5101", Decimal("2100.00")),
    ("FER002", "Ureia 46% Granulada",          "31021000", "TON", "5101", Decimal("1850.00")),
    ("FER003", "MAP Fosfato Monoamonico",      "31053000", "TON", "5101", Decimal("3200.00")),
    ("FER004", "KCL Cloreto de Potassio",      "31042000", "TON", "5101", Decimal("1650.00")),
    ("FER005", "Calcario Dolomítico",          "25210000", "TON", "5101", Decimal("120.00")),
    ("DEF001", "Glifosato 480 g/L",            "29310099", "L",   "5101", Decimal("18.50")),
    ("DEF002", "Mancozeb 800 g/kg",            "29309099", "KG",  "5101", Decimal("32.00")),
    ("DEF003", "Azoxystrobin 250 g/L",         "29339999", "L",   "5101", Decimal("95.00")),
    ("DEF004", "Carbendazim 500 g/L",          "29332990", "L",   "5101", Decimal("42.00")),
    ("DEF005", "Thiamethoxam 250 g/L",         "29339999", "L",   "5101", Decimal("180.00")),
    ("DEF006", "Imidacloprid 700 g/L",         "29339999", "L",   "5101", Decimal("95.00")),
    ("INS001", "Inseticida Cipermetrina 200",  "29149990", "L",   "5101", Decimal("28.00")),
    ("HER001", "Herbicida Atrazina 500 g/L",   "29252100", "L",   "5101", Decimal("22.00")),
    ("INO001", "Inoculante para Soja",         "30021200", "L",   "5101", Decimal("45.00")),
    ("EMB001", "Saco Rafia 60kg",              "63053200", "UN",  "5102", Decimal("2.50")),
]

# 
# FORNECEDORES
# 
FORNECEDORES = [
    {
        "cnpj": "60397874000160",
        "razao": "BAYER S.A.",
        "produtos": ["DEF001", "DEF003", "DEF005", "INO001"],
        "prefixo_cod": "BAY-",
        "unidade": "L",
        "fator": Decimal("1.0000"),
        "operacao": OperacaoConversao.multiplicar,
    },
    {
        "cnpj": "55260534000190",
        "razao": "BASF S.A.",
        "produtos": ["DEF002", "DEF004", "DEF006", "HER001"],
        "prefixo_cod": "BASF",
        "unidade": "KG",
        "fator": Decimal("1.0000"),
        "operacao": OperacaoConversao.multiplicar,
    },
    {
        "cnpj": "33042403000175",
        "razao": "MOSAIC FERTILIZANTES S.A.",
        "produtos": ["FER001", "FER002", "FER003", "FER004", "FER005"],
        "prefixo_cod": "MOS",
        "unidade": "TON",
        "fator": Decimal("1.0000"),
        "operacao": OperacaoConversao.multiplicar,
    },
    {
        "cnpj": "04184766000160",
        "razao": "COOPERATIVA AGRICOLA LTDA",
        "produtos": ["SOJ001", "SOJ002", "MIL001", "MIL002", "TRI001", "EMB001", "INS001"],
        "prefixo_cod": "COOP",
        "unidade": "SC",
        "fator": Decimal("60.0000"),  # 1 SC = 60 kg
        "operacao": OperacaoConversao.multiplicar,
    },
]

# 
# CLIENTES (destinatários das saídas)
# 
CLIENTES = [
    ("34478592000177", "FAZENDA BOA VISTA LTDA"),
    ("12345678000195", "AGROPECUARIA CERRADO S.A."),
    ("98765432000100", "COOPERATIVA MATO GROSSO"),
    ("11223344000155", "COMERCIO AGRICOLA PANTANAL LTDA"),
    ("55667788000133", "DISTRIBUIDORA AGRO NORTE"),
    ("22334455000166", "ARMAZEM GERAL CENTRAL LTDA"),
    ("44556677000144", "TRANSPORTADORA AGRO BRASIL"),
    ("66778899000122", "GRUPO CEREALISTA OESTE"),
]


def gerar_chave(cnpj_emitente: str, data: date, numero: int, serie: str = "1") -> str:
    """Gera uma chave de acesso NF-e fictícia mas com 44 dígitos."""
    cuf = "51"  # MT
    aamm = data.strftime("%y%m")
    mod = "55"
    serie_fmt = serie.zfill(3)
    nnf = str(numero).zfill(9)
    tp_emis = "1"
    cnf = "".join(random.choices(string.digits, k=8))
    base = f"{cuf}{aamm}{cnpj_emitente}{mod}{serie_fmt}{nnf}{tp_emis}{cnf}"
    # dígito verificador simplificado (módulo 11)
    pesos = list(range(2, 10)) * 6
    soma = sum(int(b) * p for b, p in zip(reversed(base), pesos))
    resto = soma % 11
    cdv = 0 if resto < 2 else 11 - resto
    return base + str(cdv)


def data_aleatoria(inicio: date, fim: date) -> date:
    delta = (fim - inicio).days
    return inicio + timedelta(days=random.randint(0, delta))


def main():
    db = SessionLocal()
    try:
        print(" Iniciando seed de estoque...")

        #  1. PRODUTOS 
        print("\n Criando produtos...")
        produtos_map: dict[str, Produto] = {}

        for cod, desc, ncm, unid, _, _ in PRODUTOS_CATALOGO:
            p = Produto(
                empresa_id=EMPRESA_ID,
                codigo_interno=cod,
                descricao=desc,
                ncm=ncm,
                unidade_estoque=unid,
                ativo=True,
            )
            db.add(p)
            db.flush()
            produtos_map[cod] = p
            print(f"  + {cod}  {desc}")

        #  2. DE-PARA (ProdutoFornecedor) 
        print("\n Criando de-para (produto  fornecedor)...")
        depara_map: dict[str, list[str]] = {}  # codigo_interno  [codigo_forn]

        for forn in FORNECEDORES:
            for i, cod in enumerate(forn["produtos"]):
                if cod not in produtos_map:
                    continue
                prod = produtos_map[cod]
                cod_forn = f"{forn['prefixo_cod']}{str(i+1).zfill(4)}"
                pf = ProdutoFornecedor(
                    produto_id=prod.id,
                    empresa_id=EMPRESA_ID,
                    cnpj_fornecedor=forn["cnpj"],
                    razao_social_fornecedor=forn["razao"],
                    codigo_produto_fornecedor=cod_forn,
                    descricao_fornecedor=prod.descricao,
                    unidade_compra=forn["unidade"],
                    fator_conversao=forn["fator"],
                    operacao_conversao=forn["operacao"],
                    unidade_convertida=prod.unidade_estoque,
                )
                db.add(pf)
                depara_map.setdefault(cod, []).append((forn["cnpj"], cod_forn, forn["unidade"]))
                print(f"  + {forn['razao'][:30]:30s}  {cod} [{cod_forn}]")

        db.flush()

        #  3. NF-e ENTRADA (50) 
        print("\n Criando 50 NF-e de entrada...")
        data_ini = date(2026, 1, 2)
        data_fim = date(2026, 4, 30)

        saldo_estoque: dict[str, Decimal] = {cod: Decimal("0") for cod in produtos_map}

        for num in range(1, 51):
            forn_info = random.choice(FORNECEDORES)
            data_emissao = data_aleatoria(data_ini, data_fim)
            data_auth = data_emissao + timedelta(days=random.randint(0, 2))
            chave = gerar_chave(forn_info["cnpj"], data_emissao, num)
            serie = "1"

            # Escolhe 2-4 produtos desse fornecedor
            prods_forn = [p for p in forn_info["produtos"] if p in produtos_map]
            prods_nf = random.sample(prods_forn, k=min(random.randint(2, 4), len(prods_forn)))

            valor_total = Decimal("0")
            itens = []
            for i, cod in enumerate(prods_nf, 1):
                prod = produtos_map[cod]
                catalog = next(c for c in PRODUTOS_CATALOGO if c[0] == cod)
                _, _, ncm, _, cfop, vunit = catalog
                qtd = Decimal(str(random.randint(5, 200)))
                vunit_var = vunit * Decimal(str(round(random.uniform(0.92, 1.08), 4)))
                vtotal_item = (qtd * vunit_var).quantize(Decimal("0.01"))
                valor_total += vtotal_item

                # busca de-para
                depara_forn = next(
                    (d for d in depara_map.get(cod, []) if d[0] == forn_info["cnpj"]), None
                )
                cod_forn = depara_forn[1] if depara_forn else None
                unid_compra = depara_forn[2] if depara_forn else prod.unidade_estoque
                qtd_convertida = qtd  # fator 1:1 exceto SCkg, simplificado

                saldo_estoque[cod] += qtd_convertida

                itens.append(NfeEntradaItem(
                    numero_item=i,
                    codigo_produto_fornecedor=cod_forn,
                    descricao_produto=prod.descricao,
                    ncm=ncm,
                    cfop="1101",
                    unidade_comercial=unid_compra,
                    quantidade=qtd,
                    valor_unitario=vunit_var.quantize(Decimal("0.0001")),
                    valor_total_item=vtotal_item,
                    produto_id=prod.id,
                    quantidade_convertida=qtd_convertida,
                    unidade_convertida=prod.unidade_estoque,
                    vinculo_pendente=False,
                ))

            nfe = NfeEntrada(
                empresa_id=EMPRESA_ID,
                chave_acesso=chave,
                numero_nf=str(num).zfill(6),
                serie=serie,
                data_emissao=data_emissao,
                data_autorizacao=data_auth,
                cnpj_emitente=forn_info["cnpj"],
                razao_social_emitente=forn_info["razao"],
                valor_total=valor_total,
                status=StatusNfe.autorizada,
            )
            nfe.itens = itens
            db.add(nfe)

            # Movimentação de entrada
            for item in itens:
                db.add(EstoqueMovimentacao(
                    empresa_id=EMPRESA_ID,
                    produto_id=item.produto_id,
                    data_movimentacao=data_emissao,
                    tipo=TipoMovimentacao.entrada,
                    quantidade=item.quantidade_convertida,
                    documento_origem=f"NF-e Entrada {str(num).zfill(6)}",
                ))

            print(f"  + NF-e Entrada {str(num).zfill(3)} | {forn_info['razao'][:30]:30s} | {len(itens)} itens | R$ {valor_total:>10.2f}")

        db.flush()

        #  4. NF-e SAÍDA (100) 
        print("\n Criando 100 NF-e de saída...")
        todos_produtos = list(produtos_map.keys())

        for num in range(1, 101):
            cliente = random.choice(CLIENTES)
            data_emissao = data_aleatoria(data_ini, data_fim)
            data_auth = data_emissao + timedelta(days=random.randint(0, 1))
            chave = gerar_chave(CNPJ_EMPRESA, data_emissao, 1000 + num)

            # 1-4 produtos aleatórios
            prods_nf = random.sample(todos_produtos, k=random.randint(1, 4))

            valor_total = Decimal("0")
            itens_saida = []
            for i, cod in enumerate(prods_nf, 1):
                prod = produtos_map[cod]
                catalog = next(c for c in PRODUTOS_CATALOGO if c[0] == cod)
                _, _, ncm, unid, cfop, vunit = catalog
                qtd = Decimal(str(random.randint(2, 100)))
                vunit_var = vunit * Decimal(str(round(random.uniform(0.95, 1.15), 4)))
                vtotal_item = (qtd * vunit_var).quantize(Decimal("0.01"))
                valor_total += vtotal_item

                saldo_estoque[cod] -= qtd
                itens_saida.append(NfeSaidaItem(
                    numero_item=i,
                    codigo_produto_empresa=cod,
                    descricao_produto=prod.descricao,
                    ncm=ncm,
                    cfop=cfop,
                    unidade_comercial=unid,
                    quantidade=qtd,
                    valor_unitario=vunit_var.quantize(Decimal("0.0001")),
                    valor_total_item=vtotal_item,
                    produto_id=prod.id,
                    quantidade_convertida=qtd,
                    unidade_convertida=unid,
                    vinculo_pendente=False,
                ))

            nfe = NfeSaida(
                empresa_id=EMPRESA_ID,
                chave_acesso=chave,
                numero_nf=str(1000 + num).zfill(6),
                serie="1",
                data_emissao=data_emissao,
                data_autorizacao=data_auth,
                cnpj_destinatario=cliente[0],
                razao_social_destinatario=cliente[1],
                valor_total=valor_total,
                status=StatusNfe.autorizada,
            )
            nfe.itens = itens_saida
            db.add(nfe)

            for item in itens_saida:
                db.add(EstoqueMovimentacao(
                    empresa_id=EMPRESA_ID,
                    produto_id=item.produto_id,
                    data_movimentacao=data_emissao,
                    tipo=TipoMovimentacao.saida,
                    quantidade=item.quantidade_convertida,
                    documento_origem=f"NF-e Saida {str(1000 + num).zfill(6)}",
                ))

            print(f"  + NF-e Saída  {str(num).zfill(3)} | {cliente[1][:30]:30s} | {len(itens_saida)} itens | R$ {valor_total:>10.2f}")

        db.flush()

        #  5. SALDOS MENSAIS 
        print("\n Calculando saldos mensais (JanAbr 2026)...")
        periodos = [date(2026, m, 1) for m in range(1, 5)]

        for cod, prod in produtos_map.items():
            saldo_acum = Decimal("0")
            for periodo in periodos:
                mes_ini = periodo
                mes_fim = date(periodo.year, periodo.month + 1, 1) if periodo.month < 12 else date(periodo.year + 1, 1, 1)
                mes_fim -= timedelta(days=1)

                # entradas do período (via movimentações já inseridas)
                entradas_mes = sum(
                    m.quantidade for m in db.query(EstoqueMovimentacao).filter(
                        EstoqueMovimentacao.empresa_id == EMPRESA_ID,
                        EstoqueMovimentacao.produto_id == prod.id,
                        EstoqueMovimentacao.tipo == TipoMovimentacao.entrada,
                        EstoqueMovimentacao.data_movimentacao >= mes_ini,
                        EstoqueMovimentacao.data_movimentacao <= mes_fim,
                    ).all()
                ) or Decimal("0")

                saidas_mes = sum(
                    m.quantidade for m in db.query(EstoqueMovimentacao).filter(
                        EstoqueMovimentacao.empresa_id == EMPRESA_ID,
                        EstoqueMovimentacao.produto_id == prod.id,
                        EstoqueMovimentacao.tipo == TipoMovimentacao.saida,
                        EstoqueMovimentacao.data_movimentacao >= mes_ini,
                        EstoqueMovimentacao.data_movimentacao <= mes_fim,
                    ).all()
                ) or Decimal("0")

                saldo_final = saldo_acum + entradas_mes - saidas_mes

                db.add(EstoqueSaldo(
                    empresa_id=EMPRESA_ID,
                    produto_id=prod.id,
                    periodo=periodo,
                    saldo_inicial=saldo_acum,
                    entradas=entradas_mes,
                    saidas=saidas_mes,
                    ajustes=Decimal("0"),
                    saldo_final=saldo_final,
                    fechado=(periodo.month < 4),
                ))

                saldo_acum = saldo_final

            print(f"  + {cod:8s} | saldo final abr: {saldo_acum:>10.2f} {prod.unidade_estoque}")

        #  COMMIT 
        db.commit()
        print("\n Seed concluído com sucesso!")
        print(f"   Produtos:         {len(produtos_map)}")
        print(f"   De-Para:          {sum(len(v) for v in depara_map.values())}")
        print(f"   NF-e Entrada:     50")
        print(f"   NF-e Saída:       100")
        print(f"   Saldos mensais:   {len(produtos_map) * len(periodos)}")

    except Exception as e:
        db.rollback()
        print(f"\n Erro: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
