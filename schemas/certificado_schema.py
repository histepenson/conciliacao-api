from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
from models.certificado_digital import StatusCertificado


class CertificadoOut(BaseModel):
    id: int
    empresa_id: int
    cnpj_certificado: str
    razao_social_certificado: Optional[str] = None
    validade: Optional[date] = None
    status: StatusCertificado
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
