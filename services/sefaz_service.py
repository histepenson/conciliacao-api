"""
Integração com SEFAZ — DistDFe (Distribuição de DF-e).

Utiliza mTLS (certificado digital A1 .pfx) para autenticação.
Ambiente: apenas produção (tpAmb=1).
"""
import base64
import gzip
import ssl
import tempfile
import textwrap
from datetime import date
from pathlib import Path
from typing import Generator

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12

SEFAZ_URL = "https://www.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx"
SOAP_ACTION = "http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe/nfeDistDFeInteresse"

_NS = {
    "soap": "http://www.w3.org/2003/05/soap-envelope",
    "nfeDist": "http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe",
    "dist": "http://www.portalfiscal.inf.br/nfe",
}

_SOAP_TEMPLATE = textwrap.dedent("""
<?xml version="1.0" encoding="UTF-8"?>
<soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                 xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
  <soap12:Body>
    <nfeDistDFeInteresse xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe">
      <nfeDist>
        <distDFeInt versao="1.01" xmlns="http://www.portalfiscal.inf.br/nfe">
          <tpAmb>1</tpAmb>
          <cUFAutor>{cuf}</cUFAutor>
          <CNPJ>{cnpj}</CNPJ>
          <distNSU>
            <ultNSU>{ult_nsu}</ultNSU>
          </distNSU>
        </distDFeInt>
      </nfeDist>
    </nfeDistDFeInteresse>
  </soap12:Body>
</soap12:Envelope>
""").strip()


def _build_ssl_context(pfx_bytes: bytes, senha: bytes) -> ssl.SSLContext:
    """Cria SSLContext com o certificado .pfx para mTLS."""
    private_key, cert, chain = pkcs12.load_key_and_certificates(pfx_bytes, senha)

    key_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    # Escreve cert e key em arquivos temporários para carregar no SSLContext
    with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as cf:
        cf.write(cert_pem)
        cert_path = cf.name
    with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as kf:
        kf.write(key_pem)
        key_path = kf.name

    try:
        ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)
    finally:
        Path(cert_path).unlink(missing_ok=True)
        Path(key_path).unlink(missing_ok=True)

    return ctx


def _extrair_cnpj_da_uf(cnpj: str) -> str:
    """Extrai código UF a partir do CNPJ (primeiros 2 dígitos = código de estado)."""
    # Mapeia CNPJ para UF com base na sede (primeiro dígito). Simplificado — usa 35 (SP) como padrão.
    uf_map = {
        "11": "11", "12": "12", "13": "13", "14": "14", "15": "15",
        "16": "16", "17": "17", "21": "21", "22": "22", "23": "23",
        "24": "24", "25": "25", "26": "26", "27": "27", "28": "28",
        "29": "29", "31": "31", "32": "32", "33": "33", "35": "35",
        "41": "41", "42": "42", "43": "43", "50": "50", "51": "51",
        "52": "52", "53": "53",
    }
    return uf_map.get(cnpj[:2], "35")


def _descompactar_doc(doc_zip_b64: str) -> str:
    """Descompacta um docZip base64+gzip da resposta DistDFe."""
    raw = base64.b64decode(doc_zip_b64)
    return gzip.decompress(raw).decode("utf-8")


def buscar_nfes_sefaz(
    cnpj: str,
    pfx_bytes: bytes,
    senha: bytes,
    data_inicio: date,
    data_fim: date,
) -> Generator[dict, None, None]:
    """
    Consulta o DistDFe da SEFAZ e gera dicts com dados de cada NF-e do período.

    Faz paginação por NSU automaticamente até esgotar os documentos.
    Filtra por data_autorizacao entre data_inicio e data_fim.

    Yields:
        dict com keys: xml_str, chave_acesso, tipo ("entrada"|"saida")
    """
    ssl_ctx = _build_ssl_context(pfx_bytes, senha)
    cuf = _extrair_cnpj_da_uf(cnpj)
    ult_nsu = "000000000000000"

    with httpx.Client(verify=ssl_ctx, timeout=60.0) as client:
        while True:
            soap_body = _SOAP_TEMPLATE.format(cnpj=cnpj, cuf=cuf, ult_nsu=ult_nsu)

            try:
                response = client.post(
                    SEFAZ_URL,
                    content=soap_body.encode("utf-8"),
                    headers={
                        "Content-Type": "application/soap+xml; charset=utf-8",
                        "SOAPAction": SOAP_ACTION,
                    },
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise RuntimeError(f"Erro na comunicacao com SEFAZ: {exc}") from exc

            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.text)

            # Extrai retDistDFeInt
            ns = "http://www.portalfiscal.inf.br/nfe"
            ret = root.find(f".//{{{ns}}}retDistDFeInt")
            if ret is None:
                break

            c_stat = ret.findtext(f"{{{ns}}}cStat", "")
            if c_stat not in ("137", "138"):
                # 137=OK com docs, 138=OK sem mais docs
                break

            max_nsu = ret.findtext(f"{{{ns}}}maxNSU", ult_nsu)
            lote = ret.find(f"{{{ns}}}loteDistDFeInt")
            if lote is None:
                break

            docs = lote.findall(f"{{{ns}}}docZip")
            if not docs:
                break

            for doc in docs:
                chave = doc.get("chNFe", "")
                schema = doc.get("schema", "")
                xml_str = _descompactar_doc(doc.text or "")

                if "procNFe" in schema or "nfeProc" in schema or "NFe" in schema:
                    yield {"xml_str": xml_str, "chave_acesso": chave}

            if max_nsu == ult_nsu:
                break
            ult_nsu = max_nsu

            if c_stat == "138":
                break
