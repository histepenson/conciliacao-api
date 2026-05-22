"""
Teste da API MATR900 (Kardex Fisico-Financeiro)
Chama diretamente o Protheus via ZMATR900API.

Uso:
    python test_matr900.py
    python test_matr900.py --data-ini 20260101 --data-fim 20260131
    python test_matr900.py --produto-de 000001 --produto-ate 000010
    python test_matr900.py --via-backend          # chama localhost:8000 ao inves do Protheus direto
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.parse
import ssl
from dotenv import load_dotenv

load_dotenv()

# -- Configuracoes (lidas do .env) ----------------------------------------------
PROTHEUS_URL  = os.getenv("PROTHEUS_URL", "https://192.168.1.100:8089")
PROTHEUS_USER = os.getenv("PROTHEUS_USER", "")
PROTHEUS_PASS = os.getenv("PROTHEUS_PASSWORD", "")
TENANT_ID     = os.getenv("PROTHEUS_TENANT", "02,0201")
BACKEND_URL   = "http://localhost:8000"

ENDPOINT_DIRETO  = "/rest/zmatr900api/api/v1/matr900"
ENDPOINT_BACKEND = "/api/v1/matr900"


# -- Helpers --------------------------------------------------------------------
def _build_url(base: str, path: str, params: dict) -> str:
    qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    return f"{base.rstrip('/')}{path}?{qs}"


def _request(url: str, user: str = "", password: str = "", tenant_id: str = "") -> dict:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(url)
    if tenant_id:
        req.add_header("tenantId", tenant_id)
    if user:
        import base64
        cred = base64.b64encode(f"{user}:{password}".encode()).decode()
        req.add_header("Authorization", f"Basic {cred}")

    print(f"\n> GET {url}")
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=120) as resp:
            raw = resp.read()
            print(f"  Status: {resp.status}")
    except urllib.error.HTTPError as e:
        print(f"  ERRO HTTP {e.code}: {e.reason}")
        body = e.read().decode("utf-8", errors="replace")
        print(f"  Corpo: {body[:500]}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"  ERRO de conexao: {e.reason}")
        sys.exit(1)

    try:
        data = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError:
        data = json.loads(raw.decode("windows-1252"))

    return data


def _paginar_tudo(base: str, path: str, params: dict, user: str, password: str, tenant_id: str) -> dict:
    """Busca todas as paginas e consolida."""
    page = 1
    all_linhas = []
    parametros = {}
    total_pages = 1

    while page <= total_pages:
        params["page"] = page
        url = _build_url(base, path, params)
        data = _request(url, user, password, tenant_id)

        if data.get("erro"):
            print(f"\n  ERRO DO PROTHEUS: {data.get('mensagem')} - {data.get('detalhe')}")
            sys.exit(1)

        total_pages = int(data.get("total_pages", 1))
        linhas = data.get("linhas", [])
        all_linhas.extend(linhas)
        parametros = data.get("parametros", {})

        print(f"  Pagina {page}/{total_pages}  |  registros nesta pagina: {len(linhas)}")
        page += 1

    return {
        "parametros": parametros,
        "total_registros": len(all_linhas),
        "linhas": all_linhas,
    }


def _imprimir_resumo(data: dict) -> None:
    total = data.get("total_registros", 0)
    linhas = data.get("linhas", [])
    params = data.get("parametros", {})

    print("\n" + "=" * 60)
    print("RESULTADO")
    print("=" * 60)
    print(f"Total de registros : {total}")
    print(f"Parametros usados  : {json.dumps(params, ensure_ascii=False)}")

    if not linhas:
        print("\n(nenhum registro retornado)")
        return

    # Amostra: primeiros 5
    print(f"\nAmostra (ate 5 de {total}):")
    for i, linha in enumerate(linhas[:5], 1):
        print(f"\n  [{i}] Produto  : {linha.get('Codigo')} - {linha.get('Descricao')}")
        print(f"      Data     : {linha.get('Operacao Data')}")
        print(f"      TES/CF   : {linha.get('TES')} / {linha.get('CF')}")
        print(f"      Entrada  : qtd={linha.get('Entradas Quantidade')}  vlr={linha.get('Entradas Custo Total')}")
        print(f"      Saida    : qtd={linha.get('Saidas Quantidade')}  vlr={linha.get('Saidas Custo Total')}")
        print(f"      Saldo    : qtd={linha.get('Saldo Quantidade')}  vlr={linha.get('Saldo Valor Total')}")
        print(f"      Parceiro : {linha.get('CLI/FOR/CC/PJ/OP/OS')}")

    # Totalizadores
    total_ent_qtd = sum(float(l.get("Entradas Quantidade") or 0) for l in linhas)
    total_ent_vlr = sum(float(l.get("Entradas Custo Total") or 0) for l in linhas)
    total_sai_qtd = sum(float(l.get("Saidas Quantidade") or 0) for l in linhas)
    total_sai_vlr = sum(float(l.get("Saidas Custo Total") or 0) for l in linhas)

    print("\n" + "-" * 40)
    print(f"Total Entradas : qtd={total_ent_qtd:,.2f}  vlr=R$ {total_ent_vlr:,.2f}")
    print(f"Total Saidas   : qtd={total_sai_qtd:,.2f}  vlr=R$ {total_sai_vlr:,.2f}")


# -- Main -----------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Teste ZMATR900API - Kardex Fisico-Financeiro")
    parser.add_argument("--data-ini",          default="20260101",  help="Data inicio YYYYMMDD (padrao: 20260101)")
    parser.add_argument("--data-fim",          default="20260131",  help="Data fim YYYYMMDD (padrao: 20260131)")
    parser.add_argument("--produto-de",        default=None)
    parser.add_argument("--produto-ate",       default=None)
    parser.add_argument("--tipo-de",           default=None)
    parser.add_argument("--tipo-ate",          default=None)
    parser.add_argument("--grupo-de",          default=None)
    parser.add_argument("--grupo-ate",         default=None)
    parser.add_argument("--armazem",           default=None,        help="Armazem/Local (ex: 01)")
    parser.add_argument("--documento-por",     default="D",         help="D=Documento  S=Sequencia")
    parser.add_argument("--moeda",             default="1")
    parser.add_argument("--ordem",             default="1",         help="1=Produto  2=Tipo")
    parser.add_argument("--considera-filiais", default="2",         help="1=Todas  2=Filial corrente")
    parser.add_argument("--tipo-custo",        default="1",         help="1=Medio  2=Reposicao")
    parser.add_argument("--page-size",         default=500, type=int)
    parser.add_argument("--via-backend",       action="store_true", help="Chama localhost:8000 ao inves do Protheus direto")
    parser.add_argument("--salvar",            default=None,        metavar="ARQUIVO.json", help="Salva resultado em JSON")

    args = parser.parse_args()

    params = {
        "data_ini":          args.data_ini,
        "data_fim":          args.data_fim,
        "pageSize":          args.page_size,
        "produto_de":        args.produto_de,
        "produto_ate":       args.produto_ate,
        "tipo_de":           args.tipo_de,
        "tipo_ate":          args.tipo_ate,
        "grupo_de":          args.grupo_de,
        "grupo_ate":         args.grupo_ate,
        "armazem":           args.armazem,
        "documento_por":     args.documento_por,
        "moeda":             args.moeda,
        "ordem":             args.ordem,
        "considera_filiais": args.considera_filiais,
        "tipo_custo":        args.tipo_custo,
    }

    print("=" * 60)
    print("TESTE MATR900 - Kardex Fisico-Financeiro")
    print("=" * 60)
    print(f"Periodo  : {args.data_ini} a {args.data_fim}")
    print(f"Modo     : {'via backend (localhost:8000)' if args.via_backend else 'direto > Protheus'}")

    if args.via_backend:
        # Chama o backend local (que ja cuida de paginacao)
        url = _build_url(BACKEND_URL, ENDPOINT_BACKEND, params)
        data = _request(url)
    else:
        print(f"Servidor : {PROTHEUS_URL}")
        data = _paginar_tudo(PROTHEUS_URL, ENDPOINT_DIRETO, params, PROTHEUS_USER, PROTHEUS_PASS, TENANT_ID)

    _imprimir_resumo(data)

    if args.salvar:
        with open(args.salvar, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\nResultado salvo em: {args.salvar}")


if __name__ == "__main__":
    main()
