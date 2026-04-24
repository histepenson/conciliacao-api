# models/usuario.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db import Base


class Usuario(Base):
    """Modelo de Usuario do sistema."""

    __tablename__ = "usuario"
    __table_args__ = {"schema": "concilia"}

    # Colunas principais
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    senha_hash = Column(String(255), nullable=False)
    nome = Column(String(255), nullable=False)

    # Flags
    is_admin = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    email_verified = Column(Boolean, default=False, nullable=False)
    email_verified_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("NOW()"), onupdate=func.now(), nullable=False)
    last_login = Column(DateTime(timezone=True), nullable=True)

    # Relacionamentos
    empresas = relationship(
        "UsuarioEmpresa",
        back_populates="usuario",
        cascade="all, delete-orphan",
        lazy="dynamic",
        foreign_keys="[UsuarioEmpresa.usuario_id]",
    )

    password_resets = relationship(
        "PasswordReset",
        back_populates="usuario",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    sessions = relationship(
        "UserSession",
        back_populates="usuario",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __repr__(self):
        return f"<Usuario(id={self.id}, email='{self.email}', nome='{self.nome}')>"
