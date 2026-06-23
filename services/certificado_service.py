from datetime import date, datetime, timezone

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.serialization import pkcs12
from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from core import storage
from core.config import settings
from models.certificado_digital import CertificadoDigital, StatusCertificado


def _get_fernet() -> Fernet:
    import os
    key = os.environ.get("CERT_ENCRYPTION_KEY") or settings.CERT_ENCRYPTION_KEY
    if not key:
        raise RuntimeError("CERT_ENCRYPTION_KEY nao definida no ambiente")
    return Fernet(key.encode())


def _extrair_info_cert(pfx_bytes: bytes, senha: str) -> dict:
    """Extrai CNPJ, razao social e validade do certificado .pfx."""
    try:
        senha_bytes = senha.encode() if senha else b""
        private_key, cert, _ = pkcs12.load_key_and_certificates(pfx_bytes, senha_bytes)
    except Exception:
        raise HTTPException(400, "Certificado invalido ou senha incorreta")

    subject = cert.subject
    cn = None
    for attr in subject:
        if attr.oid.dotted_string == "2.5.4.3":  # Common Name
            cn = attr.value
            break

    # CNPJ tipicamente aparece apos ":" no CN ou em OID especifico 2.16.76.1.3.3
    cnpj = None
    razao_social = cn or ""

    # Tenta extrair CNPJ do CN no formato "NOME:CNPJ14DIGITOS"
    if cn and ":" in cn:
        partes = cn.split(":")
        possivel_cnpj = partes[-1].strip().replace(".", "").replace("/", "").replace("-", "")
        if len(possivel_cnpj) == 14 and possivel_cnpj.isdigit():
            cnpj = possivel_cnpj
            razao_social = partes[0].strip()

    # Tenta OID de CNPJ brasileiro 2.16.76.1.3.3
    if not cnpj:
        try:
            from cryptography import x509
            for ext in cert.extensions:
                if ext.oid.dotted_string == "2.5.29.17":  # Subject Alt Name
                    pass
            # Percorre atributos do subject buscando OID de CNPJ
            for attr in subject:
                val = attr.value.replace(".", "").replace("/", "").replace("-", "")
                if len(val) == 14 and val.isdigit():
                    cnpj = val
                    break
        except Exception:
            pass

    validade = cert.not_valid_after_utc.date() if hasattr(cert, "not_valid_after_utc") else cert.not_valid_after.date()

    status = StatusCertificado.valido
    if validade < date.today():
        status = StatusCertificado.expirado

    return {"cnpj": cnpj or "", "razao_social": razao_social, "validade": validade, "status": status}


def salvar_certificado(db: Session, empresa_id: int, arquivo: UploadFile, senha: str) -> CertificadoDigital:
    pfx_bytes = arquivo.file.read()

    info = _extrair_info_cert(pfx_bytes, senha)

    # Verifica duplicidade por empresa + CNPJ do certificado
    existente = db.query(CertificadoDigital).filter(
        CertificadoDigital.empresa_id == empresa_id,
        CertificadoDigital.cnpj_certificado == info["cnpj"],
    ).first()
    if existente:
        raise HTTPException(400, f"Certificado para CNPJ {info['cnpj']} ja cadastrado nesta empresa")

    # Salva arquivo no bucket
    nome_arquivo = f"{info['cnpj']}_{arquivo.filename}"
    chave = f"certificados/{empresa_id}/{nome_arquivo}"
    storage.upload_bytes(chave, pfx_bytes)

    # Criptografa senha
    fernet = _get_fernet()
    senha_criptografada = fernet.encrypt(senha.encode()).decode()

    cert = CertificadoDigital(
        empresa_id=empresa_id,
        cnpj_certificado=info["cnpj"],
        razao_social_certificado=info["razao_social"],
        caminho_arquivo=chave,
        senha_criptografada=senha_criptografada,
        validade=info["validade"],
        status=info["status"],
    )
    db.add(cert)
    db.commit()
    db.refresh(cert)
    return cert


def listar_certificados(db: Session, empresa_id: int) -> list[CertificadoDigital]:
    return db.query(CertificadoDigital).filter(
        CertificadoDigital.empresa_id == empresa_id
    ).order_by(CertificadoDigital.cnpj_certificado).all()


def obter_certificado(db: Session, cert_id: int) -> CertificadoDigital | None:
    return db.query(CertificadoDigital).filter(CertificadoDigital.id == cert_id).first()


def deletar_certificado(db: Session, cert_id: int) -> bool:
    cert = obter_certificado(db, cert_id)
    if not cert:
        raise HTTPException(404, "Certificado nao encontrado")

    # Remove arquivo do bucket
    if storage.file_exists(cert.caminho_arquivo):
        storage.delete_file(cert.caminho_arquivo)

    db.delete(cert)
    db.commit()
    return True


def carregar_pfx(db: Session, cert_id: int) -> tuple[bytes, bytes]:
    """Retorna (pfx_bytes, senha_bytes) para uso no SefazService."""
    cert = obter_certificado(db, cert_id)
    if not cert:
        raise HTTPException(404, "Certificado nao encontrado")

    pfx_bytes = storage.download_bytes(cert.caminho_arquivo)

    fernet = _get_fernet()
    senha = fernet.decrypt(cert.senha_criptografada.encode()).decode()
    return pfx_bytes, senha.encode()
