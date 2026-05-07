from pydantic import BaseModel
from datetime import datetime
from models.estoque_alerta import TipoAlerta


class AlertaOut(BaseModel):
    id: int
    empresa_id: int
    tipo: TipoAlerta
    referencia_id: int | None
    mensagem: str
    resolvido: bool
    created_at: datetime

    model_config = {"from_attributes": True}
