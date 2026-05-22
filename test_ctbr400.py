import httpx
import json

# Configuracoes
PROTHEUS_URL  = "https://192.168.1.100:8089"
PROTHEUS_USER = "histepenson.ribeiro"
PROTHEUS_PASS = "010101"
TENANT_ID     = "02,0201"

endpoint = PROTHEUS_URL.rstrip("/") + "/rest/zctbr400api/api/v1/ctbr400"

params = {
    "data_ini":      "20260101",
    "data_fim":      "20260131",
    "conta_de":      "11102022",
    "conta_ate":     "11102022",
    "custo_ate":     "zzzzzzzz",
    "item_ate":      "ZZZZZZZZ",
    "clvl_ate":      "ZZZZZZ",
    "moeda":         "01",
    "saldo":         "1",
    "tipo_rel":      "1",
    "salta_linha":   "1",
    "imprime_custo": "2",
    "imprime_item":  "2",
    "imprime_clvl":  "2",
    "page":          "1",
    "pageSize":      "10",
}

headers = {"tenantId": TENANT_ID}

print(f"Endpoint : {endpoint}")
print(f"Params   : {json.dumps(params, indent=2)}")
print(f"Headers  : {headers}")
print("-" * 60)

try:
    with httpx.Client(verify=False, timeout=30.0, auth=(PROTHEUS_USER, PROTHEUS_PASS)) as client:
        resp = client.get(endpoint, params=params, headers=headers)
        print(f"Status   : {resp.status_code}")
        print(f"URL real : {resp.url}")
        print("-" * 60)
        try:
            data = resp.json()
            print(json.dumps(data, indent=2, ensure_ascii=False)[:3000])
        except Exception:
            print(resp.text[:3000])
except Exception as e:
    print(f"ERRO: {e}")
