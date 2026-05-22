# models/password_reset.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, text
from sqlalchemy.orm import relationship
from db import Base


class PasswordReset(Base):
    """Modelo para tokens de reset de senha."""

    __tablename__ = "password_reset"
    __table_args__ = {"schema": "concilia"}

    # Colunas principais
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    usuario_id = Column(
        Integer,
        ForeignKey("concilia.usuario.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash = Column(String(255), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    used_at = Column(DateTime(timezone=True), nullable=True)
    ip_address = Column(String(45), nullable=True)

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)

    # Relacionamentos
    usuario = relationship(
        "Usuario",
        back_populates="password_resets",
    )

    def __repr__(self):
        return f"<PasswordReset(id={self.id}, usuario_id={self.usuario_id})>"

    @property
    def is_expired(self) -> bool:
        """Verifica se o token expirou."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_used(self) -> bool:
        """Verifica se o token ja foi usado."""
        return self.used_at is not None

    @property
    def is_valid(self) -> bool:
        """Verifica se o token e valido (nao expirado e nao usado)."""
        return not self.is_expired and not self.is_used
