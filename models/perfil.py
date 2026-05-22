# models/perfil.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db import Base


class Perfil(Base):
    """Modelo de Perfil (Role) de permissoes."""

    __tablename__ = "perfil"
    __table_args__ = {"schema": "concilia"}

    # Colunas principais
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nome = Column(String(100), nullable=False, unique=True, index=True)
    descricao = Column(Text, nullable=True)
    permissoes = Column(JSONB, nullable=False, default=list)
    is_system = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("NOW()"), onupdate=func.now(), nullable=False)

    # Relacionamentos
    usuarios_empresas = relationship(
        "UsuarioEmpresa",
        back_populates="perfil",
        lazy="dynamic",
    )

    def __repr__(self):
        return f"<Perfil(id={self.id}, nome='{self.nome}')>"

    def has_permission(self, permission: str) -> bool:
        """Verifica se o perfil tem uma permissao especifica."""
        if "*" in self.permissoes:
            return True

        if permission in self.permissoes:
            return True

        # Verificar wildcard do recurso (ex: "conciliacao:*")
        resource = permission.split(":")[0]
        if f"{resource}:*" in self.permissoes:
            return True

        return False
