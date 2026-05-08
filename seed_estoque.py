"""
Seed de dados de estoque para testes.
Popula todas as empresas ativas com:
  - 20 produtos agrícolas por empresa
  - De-Para por 4 fornecedores
  - 50 NF-e de entrada + 100 NF-e de saída (jan-abr/2026)
  - Saldos calculados via reprocessar_periodo

Uso:
    python seed_estoque.py              # insere apenas se não existir
    python seed_estoque.py --limpar     # apaga tudo e reinsere
"""

import argparse
import random
import string
from datetime import date, timedelta
from decimal import Decimal

from db import SessionLocal
from models.empresa import Empresa
from models.produto import Produto
from models.produto_fornecedor import ProdutoFornecedor, OperacaoConversao
from models.nfe import NfeEntrada, NfeEntradaItem, NfeSaida, NfeSaidaItem, StatusNfe
from models.estoque import EstoqueSaldo, EstoqueMovimentacao, TipoMovimentacao
from services.estoque_service import reprocessar_periodo

random.seed(42)

PERIODOS = [date(2026, m, 1) for m in range(1, 6)]  # jan-mai 2026

# ── Catálogo de produtos ──────────────────────────────────────────────────────

PRODUTOS_CATALOGO = [
    # (codigo_base, descricao, ncm, unidade, cfop_saida, valor_unitario)
    ("SOJ001", "Soja em Graos",              "12010010", "SC",  "5101", Decimal("120.00")),
    ("SOJ002", "Sementes de Soja RR",        "12010090", "SC",  "5101", Decimal("185.00")),
    ("MIL001", "Milho em Graos",             "10059010", "SC",  "5101", Decimal("75.00")),
    ("MIL002", "Sementes de Milho Hibrido",  "10059090", "SC",  "5101", Decimal("250.00")),
    ("TRI001", "Trigo em Graos",             "10019900", "SC",  "5101", Decimal("90.00")),
    ("FER001", "Fertilizante NPK 20-05-20",  "31049000", "TON", "5101", Decimal("2100.00")),
    ("FER002", "Ureia 46% Granulada",        "31021000", "TON", "5101", Decimal("1850.00")),
    ("FER003", "MAP Fosfato Monoamonico",    "31053000", "TON", "5101", Decimal("3200.00")),
    ("FER004", "KCL Cloreto de Potassio",    "31042000", "TON", "5101", Decimal("1650.00")),
    ("FER005", "Calcario Dolomitico",        "25210000", "TON", "5101", Decimal("120.00")),
    ("DEF001", "Glifosato 480 g/L",          "29310099", "L",   "5101", Decimal("18.50")),
    ("DEF002", "Mancozeb 800 g/kg",          "29309099", "KG",  "5101", Decimal("32.00")),
    ("DEF003", "Azoxystrobin 250 g/L",       "29339999", "L",   "5101", Decimal("95.00")),
    ("DEF004", "Carbendazim 500 g/L",        "29332990", "L",   "5101", Decimal("42.00")),
    ("DEF005", "Thiamethoxam 250 g/L",       "29339999", "L",   "5101", Decimal("180.00")),
    ("DEF006", "Imidacloprid 700 g/L",       "29339999", "L",   "5101", Decimal("95.00")),
    ("INS001", "Inseticida Cipermetrina 200","29149990", "L",   "5101", Decimal("28.00")),
    ("HER001", "Herbicida Atrazina 500 g/L", "29252100", "L",   "5101", Decimal("22.00")),
    ("INO001", "Inoculante para Soja",       "30021200", "L",   "5101", Decimal("45.00")),
    ("EMB001", "Saco Rafia 60kg",            "63053200", "UN",  "5102", Decimal("2.50")),
]

FORNECEDORES_BASE = [
    {
        "cnpj": "60397874000160",
        "razao": "BAYER S.A.",
        "produtos": ["DEF001", "DEF003", "DEF005", "INO001"],
        "prefixo": "BAY",
        "unidade": "L",
        "fator": Decimal("1.0000"),
        "operacao": OperacaoConversao.multiplicar,
    },
    {
        "cnpj": "55260534000190",
        "razao": "BASF S.A.",
        "produtos": ["DEF002", "DEF004", "DEF006", "HER001"],
        "prefixo": "BSF",
        "unidade": "KG",
        "fator": Decimal("1.0000"),
        "operacao": OperacaoConversao.multiplicar,
    },
    {
        "cnpj": "33042403000175",
        "razao": "MOSAIC FERTILIZANTES S.A.",
        "produtos": ["FER001", "FER002", "FER003", "FER004", "FER005"],
        "prefixo": "MOS",
        "unidade": "TON",
        "fator": Decimal("1.0000"),
        "operacao": OperacaoConversao.multiplicar,
    },
    {
        "cnpj": "04184766000160",
        "razao": "COOPERATIVA AGRICOLA LTDA",
        "produtos": ["SOJ001", "SOJ002", "MIL001", "MIL002", "TRI001", "EMB001", "INS001"],
        "prefixo": "COP",
        "unidade": "SC",
        "fator": Decimal("1.0000"),
        "operacao": OperacaoConversao.multiplicar,
    },
]

CLIENTES = [
    ("34478592000177", "FAZENDA BOA VISTA LTDA"),
    ("12345678000195", "AGROPECUARIA CERRADO S.A."),
    ("98765432000100", "COOPERATIVA MATO GROSSO"),
    ("11223344000155", "COMERCIO AGRICOLA PANTANAL LTDA"),
    ("55667788000133", "DISTRIBUIDORA AGRO NORTE"),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def gerar_chave(cnpj_emitente: str, data: date, numero: int, empresa_id: int) -> str:
    cuf = "51"
    aamm = data.strftime("%y%m")
    mod = "55"
    serie = "001"
    nnf = str(numero).zfill(9)
    tp_emis = "1"
    # inclui empresa_id no cnf para garantir unicidade entre empresas
    cnf = str(empresa_id).zfill(4) + "".join(random.choices(string.digits, k=4))
    base = f"{cuf}{aamm}{cnpj_emitente}{mod}{serie}{nnf}{tp_emis}{cnf}"
    pesos = list(range(2, 10)) * 6
    soma = sum(int(b) * p for b, p in zip(reversed(base), pesos))
    resto = soma % 11
    cdv = 0 if resto < 2 else 11 - resto
    return base + str(cdv)


def data_aleatoria(inicio: date, fim: date) -> date:
    return inicio + timedelta(days=random.randint(0, (fim - inicio).days))


# ── Limpeza ───────────────────────────────────────────────────────────────────

def limpar_dados(db):
    print("Limpando dados de estoque anteriores...")
    db.query(EstoqueMovimentacao).delete(synchronize_session=False)
    db.query(EstoqueSaldo).delete(synchronize_session=False)
    db.query(NfeEntradaItem).delete(synchronize_session=False)
    db.query(NfeSaidaItem).delete(synchronize_session=False)
    db.query(NfeEntrada).delete(synchronize_session=False)
    db.query(NfeSaida).delete(synchronize_session=False)
    db.query(ProdutoFornecedor).delete(synchronize_session=False)
    db.query(Produto).delete(synchronize_session=False)
    db.commit()
    print("Dados limpos.\n")


# ── Seed por empresa ──────────────────────────────────────────────────────────

def seed_empresa(db, empresa: Empresa):
    eid = empresa.id
    cnpj = (empresa.cnpj or "").replace(".", "").replace("/", "").replace("-", "").zfill(14)[:14]
    print(f"\n  Empresa {eid} — {empresa.nome}")

    # Pula se já tem produtos
    if db.query(Produto).filter(Produto.empresa_id == eid).count() > 0:
        print("    Ja possui produtos — pulando (use --limpar para reinserir).")
        return

    # 1. Produtos
    produtos_map: dict[str, Produto] = {}
    for cod, desc, ncm, unid, _, _ in PRODUTOS_CATALOGO:
        cod_emp = f"{cod}-{eid:02d}"
        p = Produto(empresa_id=eid, codigo_interno=cod_emp, descricao=desc,
                    ncm=ncm, unidade_estoque=unid, ativo=True)
        db.add(p)
        db.flush()
        produtos_map[cod] = p
    print(f"    + {len(produtos_map)} produtos criados")

    # 2. De-Para
    depara_map: dict[str, list[tuple]] = {}
    for forn in FORNECEDORES_BASE:
        for i, cod in enumerate(forn["produtos"]):
            if cod not in produtos_map:
                continue
            prod = produtos_map[cod]
            cod_forn = f"{forn['prefixo']}{eid:02d}{i+1:04d}"
            db.add(ProdutoFornecedor(
                produto_id=prod.id,
                empresa_id=eid,
                cnpj_fornecedor=forn["cnpj"],
                razao_social_fornecedor=forn["razao"],
                codigo_produto_fornecedor=cod_forn,
                descricao_fornecedor=prod.descricao,
                unidade_compra=forn["unidade"],
                fator_conversao=forn["fator"],
                operacao_conversao=forn["operacao"],
                unidade_convertida=prod.unidade_estoque,
            ))
            depara_map.setdefault(cod, []).append((forn["cnpj"], cod_forn, forn["unidade"]))
    db.flush()
    total_depara = sum(len(v) for v in depara_map.values())
    print(f"    + {total_depara} de-para criados")

    data_ini = date(2026, 1, 2)
    data_fim = date(2026, 4, 30)

    # 3. NF-e Entrada (50)
    for num in range(1, 51):
        forn_info = random.choice(FORNECEDORES_BASE)
        data_emissao = data_aleatoria(data_ini, data_fim)
        prods_forn = [c for c in forn_info["produtos"] if c in produtos_map]
        prods_nf = random.sample(prods_forn, k=min(random.randint(2, 4), len(prods_forn)))

        itens = []
        valor_total = Decimal("0")
        for i, cod in enumerate(prods_nf, 1):
            prod = produtos_map[cod]
            catalog = next(c for c in PRODUTOS_CATALOGO if c[0] == cod)
            vunit = catalog[5] * Decimal(str(round(random.uniform(0.92, 1.08), 4)))
            qtd = Decimal(str(random.randint(5, 200)))
            vtotal = (qtd * vunit).quantize(Decimal("0.01"))
            valor_total += vtotal
            depara = next((d for d in depara_map.get(cod, []) if d[0] == forn_info["cnpj"]), None)
            itens.append(NfeEntradaItem(
                numero_item=i,
                codigo_produto_fornecedor=depara[1] if depara else None,
                descricao_produto=prod.descricao,
                ncm=catalog[2],
                cfop="1101",
                unidade_comercial=depara[2] if depara else prod.unidade_estoque,
                quantidade=qtd,
                valor_unitario=vunit.quantize(Decimal("0.0001")),
                valor_total_item=vtotal,
                produto_id=prod.id,
                quantidade_convertida=qtd,
                unidade_convertida=prod.unidade_estoque,
                vinculo_pendente=False,
            ))

        nfe = NfeEntrada(
            empresa_id=eid,
            chave_acesso=gerar_chave(forn_info["cnpj"], data_emissao, num * 10 + eid, eid),
            numero_nf=str(num).zfill(6),
            serie="1",
            data_emissao=data_emissao,
            data_autorizacao=data_emissao + timedelta(days=random.randint(0, 2)),
            cnpj_emitente=forn_info["cnpj"],
            razao_social_emitente=forn_info["razao"],
            valor_total=valor_total,
            status=StatusNfe.autorizada,
        )
        nfe.itens = itens
        db.add(nfe)
    db.flush()
    print("    + 50 NF-e de entrada criadas")

    # 4. NF-e Saída (100)
    todos_cods = list(produtos_map.keys())
    for num in range(1, 101):
        cliente = random.choice(CLIENTES)
        data_emissao = data_aleatoria(data_ini, data_fim)
        prods_nf = random.sample(todos_cods, k=random.randint(1, 4))

        itens = []
        valor_total = Decimal("0")
        for i, cod in enumerate(prods_nf, 1):
            prod = produtos_map[cod]
            catalog = next(c for c in PRODUTOS_CATALOGO if c[0] == cod)
            vunit = catalog[5] * Decimal(str(round(random.uniform(0.95, 1.15), 4)))
            qtd = Decimal(str(random.randint(2, 100)))
            vtotal = (qtd * vunit).quantize(Decimal("0.01"))
            valor_total += vtotal
            itens.append(NfeSaidaItem(
                numero_item=i,
                codigo_produto_empresa=prod.codigo_interno,
                descricao_produto=prod.descricao,
                ncm=catalog[2],
                cfop=catalog[4],
                unidade_comercial=catalog[3],
                quantidade=qtd,
                valor_unitario=vunit.quantize(Decimal("0.0001")),
                valor_total_item=vtotal,
                produto_id=prod.id,
                quantidade_convertida=qtd,
                unidade_convertida=catalog[3],
                vinculo_pendente=False,
            ))

        nfe = NfeSaida(
            empresa_id=eid,
            chave_acesso=gerar_chave(cnpj, data_emissao, 1000 + num * 10 + eid, eid),
            numero_nf=str(1000 + num).zfill(6),
            serie="1",
            data_emissao=data_emissao,
            data_autorizacao=data_emissao + timedelta(days=random.randint(0, 1)),
            cnpj_destinatario=cliente[0],
            razao_social_destinatario=cliente[1],
            valor_total=valor_total,
            status=StatusNfe.autorizada,
        )
        nfe.itens = itens
        db.add(nfe)
    db.flush()
    print("    + 100 NF-e de saída criadas")

    db.commit()

    # 5. Saldos via reprocessar_periodo
    for periodo in PERIODOS:
        count = reprocessar_periodo(db, eid, periodo)
        print(f"    + Período {periodo.strftime('%m/%Y')}: {count} saldo(s) calculado(s)")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limpar", action="store_true",
                        help="Remove todos os dados de estoque antes de inserir")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.limpar:
            limpar_dados(db)

        empresas = db.query(Empresa).filter(Empresa.status == True).order_by(Empresa.id).all()
        if not empresas:
            print("Nenhuma empresa ativa encontrada.")
            return

        print(f"Empresas encontradas: {[f'{e.id}-{e.nome}' for e in empresas]}\n")

        for empresa in empresas:
            seed_empresa(db, empresa)

        print("\nSeed concluido com sucesso!")

    except Exception as e:
        db.rollback()
        print(f"\nErro: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
