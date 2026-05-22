# models/audit_log.py
from sqlalchemy import Column, BigInteger, Integer, String, DateTime, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from db import Base


class AuditLog(Base):
    """Modelo para log de auditoria de acoes do sistema."""

    __tablename__ = "audit_log"
    __table_args__ = {"schema": "concilia"}

    # Colunas principais
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    usuario_id = Column(
        Integer,
        ForeignKey("concilia.usuario.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    empresa_id = Column(
        Integer,
        ForeignKey("concilia.empresa.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action = Column(String(50), nullable=False, index=True)
    entity_type = Column(String(100), nullable=True)
    entity_id = Column(Integer, nullable=True)
    old_values = Column(JSONB, nullable=True)
    new_values = Column(JSONB, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False, index=True)

    # Relacionamentos
    usuario = relationship("Usuario")
    empresa = relationship("Empresa")

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action='{self.action}', entity_type='{self.entity_type}')>"


# Constantes de acoes para auditoria
class AuditAction:
    """Constantes para tipos de acao no audit log."""

    # Auth
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    LOGIN_FAILED = "LOGIN_FAILED"
    PASSWORD_RESET_REQUEST = "PASSWORD_RESET_REQUEST"
    PASSWORD_RESET = "PASSWORD_RESET"
    PASSWORD_CHANGE = "PASSWORD_CHANGE"

    # CRUD
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"

    # Empresa
    EMPRESA_SELECT = "EMPRESA_SELECT"

    # Admin
    USER_ACTIVATE = "USER_ACTIVATE"
    USER_DEACTIVATE = "USER_DEACTIVATE"
    PERMISSION_GRANT = "PERMISSION_GRANT"
    PERMISSION_REVOKE = "PERMISSION_REVOKE"
