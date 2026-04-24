# models/usuario_empresa.py
from sqlalchemy import Column, Integer, Boolean, DateTime, ForeignKey, text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db import Base


class UsuarioEmpresa(Base):
    """Modelo de associacao Usuario-Empresa com perfil de permissoes."""

    __tablename__ = "usuario_empresa"
    __table_args__ = (
        UniqueConstraint("usuario_id", "empresa_id", name="uq_usuario_empresa"),
        {"schema": "concilia"},
    )

    # Colunas principais
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    usuario_id = Column(
        Integer,
        ForeignKey("concilia.usuario.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    empresa_id = Column(
        Integer,
        ForeignKey("concilia.empresa.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    perfil_id = Column(
        Integer,
        ForeignKey("concilia.perfil.id"),
        nullable=False,
    )
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("NOW()"), onupdate=func.now(), nullable=False)

    # Auditoria
    created_by = Column(
        Integer,
        ForeignKey("concilia.usuario.id"),
        nullable=True,
    )

    # Relacionamentos
    usuario = relationship(
        "Usuario",
        back_populates="empresas",
        foreign_keys=[usuario_id],
    )
    empresa = relationship(
        "Empresa",
        back_populates="usuarios",
    )
    perfil = relationship(
        "Perfil",
        back_populates="usuarios_empresas",
    )
    criador = relationship(
        "Usuario",
        foreign_keys=[created_by],
    )

    def __repr__(self):
        return f"<UsuarioEmpresa(usuario_id={self.usuario_id}, empresa_id={self.empresa_id}, perfil_id={self.perfil_id})>"
