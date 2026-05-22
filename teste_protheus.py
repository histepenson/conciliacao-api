import httpx

url = "https://192.168.1.100:8089/rest/zfin470api/api/v1/finr470"
params = {
    "banco": "0001",
    "agencia": "102060",
    "conta": "12164",
    "data_ini": "20260101",
    "data_fim": "20260131",
    "moeda": "1",
    "situacao": "1",
    "todas_filiais": "2",
    "pageSize": "200",
    "page": "1",
}

resp = httpx.get(url, params=params, verify=False, timeout=30.0,
                 auth=("histepenson.ribeiro", "010101"))

print("Status:", resp.status_code)
print("Body:", resp.text[:2000])
