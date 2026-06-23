"""
Calcula e EFETIVA (grava no banco, tabela concilia.conciliacoes) uma
conciliacao financeira/bancaria/estoque chamando a API HTTP local --
exatamente o mesmo caminho que o frontend usa quando o usuario faz upload
manual de Excel/CSV e clica em "Efetivar".

Usado para empresas sem integracao com a API do Protheus (ex: GENIX), cujos
dados foram normalizados a partir de CSV (ver skill
".claude/skills/importar-csv-protheus/SKILL.md" para o formato de colunas
esperado por cada normalizador antes de gerar os arquivos *-registros.json).

Pre-requisito: a API precisa estar rodando (uvicorn main:app --reload).

Uso (financeiro - contas a receber/pagar):
    python scripts/efetivar_conciliacao_manual.py financeiro \
        --base-url http://localhost:8000/api \
        --email usuario@empresa.com --password "minha-senha" \
        --empresa-id 7 \
        --conta-contabil-id 12 --conta-contabil "1.1.2.01.0001" \
        --periodo 2026-05 --tipo-conciliacao receber \
        --origem origem_registros.json \
        --contabil-filtrado ctbr140_registros.json \
        --contabil-geral ctbr480_registros.json \
        --arquivo-origem titulos_receber.csv \
        --arquivo-contabil-filtrado ctbr140.csv \
        --arquivo-contabil-geral ctbr480.csv

Uso (bancaria):
    python scripts/efetivar_conciliacao_manual.py bancaria \
        --base-url http://localhost:8000/api --email ... --password ... \
        --empresa-id 7 --conta-contabil-id 5 --data-base 31/05/2026 \
        --extrato extrato_registros.json --razao razao_registros.json \
        --arquivo-extrato finr470.csv --arquivo-razao ctbr400.csv

Uso (estoque):
    python scripts/efetivar_conciliacao_manual.py estoque \
        --base-url http://localhost:8000/api --email ... --password ... \
        --empresa-id 7 --conta-contabil-id 9 --data-base 31/05/2026 \
        --kardex kardex_registros.json --razao razao_registros.json \
        --arquivo-kardex matr900.csv --arquivo-razao ctbr400.csv

Se o usuario logado for admin master (sem empresa fixa no token), passe
--select-empresa-id para obter um token escopado a empresa antes de chamar
os endpoints de conciliacao.
"""

import argparse
import json
import os
import sys

import httpx


def _carregar_registros(caminho: str) -> list[dict]:
    with open(caminho, "r", encoding="utf-8") as f:
        dados = json.load(f)
    if not isinstance(dados, list):
        raise SystemExit(f"{caminho} deve conter uma lista JSON de objetos (registros)")
    return dados


def _login(client: httpx.Client, base_url: str, email: str, password: str) -> str:
    r = client.post(f"{base_url}/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]


def _select_empresa(client: httpx.Client, base_url: str, token: str, empresa_id: int) -> str:
    r = client.post(
        f"{base_url}/auth/select-empresa",
        json={"empresa_id": empresa_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _obter_token(client: httpx.Client, base_url: str, args) -> str:
    if args.token:
        token = args.token
    else:
        if not (args.email and args.password):
            raise SystemExit("Informe --token, ou --email/--password para fazer login")
        token = _login(client, base_url, args.email, args.password)
    if args.select_empresa_id:
        token = _select_empresa(client, base_url, token, args.select_empresa_id)
    return token


def _ler_bytes(caminho: str) -> bytes:
    with open(caminho, "rb") as f:
        return f.read()


def cmd_financeiro(args) -> None:
    base_url = args.base_url.rstrip("/")
    origem = _carregar_registros(args.origem)
    contabil_filtrado = _carregar_registros(args.contabil_filtrado)
    contabil_geral = _carregar_registros(args.contabil_geral)

    with httpx.Client(timeout=120) as client:
        token = _obter_token(client, base_url, args)
        headers = {"Authorization": f"Bearer {token}"}

        payload_calculo = {
            "base_origem": {"registros": origem, "tipo": args.tipo_conciliacao},
            "base_contabil_filtrada": {"registros": contabil_filtrado, "conta_contabil": args.conta_contabil},
            "base_contabil_geral": {"registros": contabil_geral},
            "parametros": {"data_base": args.periodo.replace("-", "")},
        }
        r = client.post(f"{base_url}/conciliacoes/contabil", json=payload_calculo, headers=headers)
        if r.status_code >= 400:
            raise SystemExit(f"Erro ao calcular conciliacao ({r.status_code}): {r.text}")
        resultado = r.json()
        print("Resumo calculado:", json.dumps(resultado.get("resumo", {}), indent=2, ensure_ascii=False))

        dados_efetivar = {
            "empresa_id": args.empresa_id,
            "conta_contabil_id": args.conta_contabil_id,
            "conta_contabil": args.conta_contabil,
            "periodo": args.periodo,
            "tipo_conciliacao": args.tipo_conciliacao,
            "base_origem": {"registros": origem},
            "base_contabil_filtrada": {"conta_contabil": args.conta_contabil, "registros": contabil_filtrado},
            "base_contabil_geral": {"registros": contabil_geral},
            "resultado": resultado,
        }
        files = {
            "arquivo_origem": (os.path.basename(args.arquivo_origem), _ler_bytes(args.arquivo_origem)),
            "arquivo_contabil_filtrado": (os.path.basename(args.arquivo_contabil_filtrado), _ler_bytes(args.arquivo_contabil_filtrado)),
            "arquivo_contabil_geral": (os.path.basename(args.arquivo_contabil_geral), _ler_bytes(args.arquivo_contabil_geral)),
        }
        r2 = client.post(
            f"{base_url}/conciliacoes/efetivar",
            data={"dados": json.dumps(dados_efetivar, ensure_ascii=False)},
            files=files,
            headers=headers,
        )
        if r2.status_code >= 400:
            raise SystemExit(f"Erro ao efetivar conciliacao ({r2.status_code}): {r2.text}")
        print(json.dumps(r2.json(), indent=2, ensure_ascii=False, default=str))


def cmd_bancaria(args) -> None:
    base_url = args.base_url.rstrip("/")
    extrato = _carregar_registros(args.extrato)
    razao = _carregar_registros(args.razao)

    with httpx.Client(timeout=120) as client:
        token = _obter_token(client, base_url, args)
        headers = {"Authorization": f"Bearer {token}"}

        payload_calculo = {
            "base_extrato": {"registros": extrato},
            "base_razao": {"registros": razao, "conta_contabil": args.conta_contabil or ""},
            "parametros": {"data_base": args.data_base, "empresa_id": args.empresa_id},
        }
        r = client.post(f"{base_url}/conciliacoes/bancaria", json=payload_calculo, headers=headers)
        if r.status_code >= 400:
            raise SystemExit(f"Erro ao calcular conciliacao bancaria ({r.status_code}): {r.text}")
        resultado = r.json()
        print("Resumo calculado:", json.dumps(resultado.get("resumo", {}), indent=2, ensure_ascii=False))

        dados_efetivar = {
            "empresa_id": args.empresa_id,
            "conta_contabil_id": args.conta_contabil_id,
            "data_base": args.data_base,
            "resultado": resultado,
        }
        files = {
            "arquivo_extrato": (os.path.basename(args.arquivo_extrato), _ler_bytes(args.arquivo_extrato)),
            "arquivo_razao": (os.path.basename(args.arquivo_razao), _ler_bytes(args.arquivo_razao)),
        }
        r2 = client.post(
            f"{base_url}/conciliacoes/bancaria/efetivar",
            data={"dados": json.dumps(dados_efetivar, ensure_ascii=False)},
            files=files,
            headers=headers,
        )
        if r2.status_code >= 400:
            raise SystemExit(f"Erro ao efetivar conciliacao bancaria ({r2.status_code}): {r2.text}")
        print(json.dumps(r2.json(), indent=2, ensure_ascii=False, default=str))


def cmd_estoque(args) -> None:
    base_url = args.base_url.rstrip("/")
    kardex = _carregar_registros(args.kardex)
    razao = _carregar_registros(args.razao)

    with httpx.Client(timeout=120) as client:
        token = _obter_token(client, base_url, args)
        headers = {"Authorization": f"Bearer {token}"}

        payload_calculo = {
            "base_kardex": {"registros": kardex},
            "base_razao": {"registros": razao, "conta_contabil": args.conta_contabil or ""},
            "parametros": {"data_base": args.data_base, "empresa_id": args.empresa_id},
        }
        r = client.post(f"{base_url}/conciliacoes/estoque", json=payload_calculo, headers=headers)
        if r.status_code >= 400:
            raise SystemExit(f"Erro ao calcular conciliacao de estoque ({r.status_code}): {r.text}")
        resultado = r.json()
        print("Resumo calculado:", json.dumps(resultado.get("resumo", {}), indent=2, ensure_ascii=False))

        dados_efetivar = {
            "empresa_id": args.empresa_id,
            "conta_contabil_id": args.conta_contabil_id,
            "data_base": args.data_base,
            "resultado": resultado,
        }
        files = {
            "arquivo_kardex": (os.path.basename(args.arquivo_kardex), _ler_bytes(args.arquivo_kardex)),
            "arquivo_razao": (os.path.basename(args.arquivo_razao), _ler_bytes(args.arquivo_razao)),
        }
        r2 = client.post(
            f"{base_url}/conciliacoes/estoque/efetivar",
            data={"dados": json.dumps(dados_efetivar, ensure_ascii=False)},
            files=files,
            headers=headers,
        )
        if r2.status_code >= 400:
            raise SystemExit(f"Erro ao efetivar conciliacao de estoque ({r2.status_code}): {r2.text}")
        print(json.dumps(r2.json(), indent=2, ensure_ascii=False, default=str))


def _add_auth_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--base-url", default="http://localhost:8000/api")
    p.add_argument("--token", help="Access token ja obtido (pula login)")
    p.add_argument("--email")
    p.add_argument("--password")
    p.add_argument("--select-empresa-id", type=int, help="Chama /auth/select-empresa apos login (admin master)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Calcula e efetiva conciliacao via API (importacao manual)")
    sub = parser.add_subparsers(dest="comando", required=True)

    p_fin = sub.add_parser("financeiro", help="Conciliacao financeira (FINR130/150 x CTBR140/480)")
    _add_auth_args(p_fin)
    p_fin.add_argument("--empresa-id", type=int, required=True)
    p_fin.add_argument("--conta-contabil-id", type=int, required=True)
    p_fin.add_argument("--conta-contabil", required=True)
    p_fin.add_argument("--periodo", required=True, help="YYYY-MM")
    p_fin.add_argument("--tipo-conciliacao", choices=["receber", "pagar"], required=True)
    p_fin.add_argument("--origem", required=True, help="JSON com registros normalizados (base_origem)")
    p_fin.add_argument("--contabil-filtrado", required=True, help="JSON com registros normalizados (CTBR140)")
    p_fin.add_argument("--contabil-geral", required=True, help="JSON com registros normalizados (CTBR480)")
    p_fin.add_argument("--arquivo-origem", required=True, help="Arquivo original (csv/xlsx) para guardar como anexo")
    p_fin.add_argument("--arquivo-contabil-filtrado", required=True)
    p_fin.add_argument("--arquivo-contabil-geral", required=True)
    p_fin.set_defaults(func=cmd_financeiro)

    p_banc = sub.add_parser("bancaria", help="Conciliacao bancaria (FINR470 x CTBR400)")
    _add_auth_args(p_banc)
    p_banc.add_argument("--empresa-id", type=int, required=True)
    p_banc.add_argument("--conta-contabil-id", type=int, required=True)
    p_banc.add_argument("--conta-contabil", help="Codigo da conta (opcional, so para o calculo)")
    p_banc.add_argument("--data-base", required=True, help="DD/MM/YYYY")
    p_banc.add_argument("--extrato", required=True, help="JSON com registros normalizados (FINR470)")
    p_banc.add_argument("--razao", required=True, help="JSON com registros normalizados (CTBR400)")
    p_banc.add_argument("--arquivo-extrato", required=True)
    p_banc.add_argument("--arquivo-razao", required=True)
    p_banc.set_defaults(func=cmd_bancaria)

    p_est = sub.add_parser("estoque", help="Conciliacao de estoque (MATR900 x CTBR400)")
    _add_auth_args(p_est)
    p_est.add_argument("--empresa-id", type=int, required=True)
    p_est.add_argument("--conta-contabil-id", type=int, required=True)
    p_est.add_argument("--conta-contabil", help="Codigo da conta (opcional, so para o calculo)")
    p_est.add_argument("--data-base", required=True, help="DD/MM/YYYY")
    p_est.add_argument("--kardex", required=True, help="JSON com registros normalizados (MATR900)")
    p_est.add_argument("--razao", required=True, help="JSON com registros normalizados (CTBR400)")
    p_est.add_argument("--arquivo-kardex", required=True)
    p_est.add_argument("--arquivo-razao", required=True)
    p_est.set_defaults(func=cmd_estoque)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
