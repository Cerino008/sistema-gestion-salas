"""
models.py
Definición de tablas (SQLModel) para el Sistema de Gestión, Inventario y
Auditoría de Salas de Informática.

Cada clase representa 1:1 una tabla del script schema_gestion_salas.sql
(Paso 1). Los nombres de tabla (__tablename__) coinciden exactamente con
los del script SQL para que SQLModel opere sobre la misma base de datos
ya creada.
"""

from datetime import datetime
from typing import Optional, List

from sqlmodel import SQLModel, Field, Relationship
from database.connection import ahora_argentina
from sqlalchemy import CheckConstraint, Index, UniqueConstraint, text


# ============================================================
# CATÁLOGOS
# ============================================================

class EstadoAnclaje(SQLModel, table=True):
    __tablename__ = "estados_anclaje"

    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(unique=True)


class EstadoOperativoPC(SQLModel, table=True):
    __tablename__ = "estados_operativo_pc"

    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(unique=True)


class EstadoPeriferico(SQLModel, table=True):
    __tablename__ = "estados_periferico"

    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(unique=True)


class TipoPeriferico(SQLModel, table=True):
    __tablename__ = "tipos_periferico"

    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(unique=True)


class SoftwareCatalogo(SQLModel, table=True):
    __tablename__ = "software_catalogo"
    __table_args__ = (
        CheckConstraint(
            "categoria IN ('Programacion','Ofimatica','Navegador','Otro')",
            name="ck_software_categoria",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(unique=True)
    categoria: str


class TipoComponente(SQLModel, table=True):
    __tablename__ = "tipos_componente"

    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(unique=True)


# ============================================================
# MÓDULO IV: RED
# ============================================================

class NodoRed(SQLModel, table=True):
    __tablename__ = "nodos_red"

    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(unique=True)

    switches: List["Switch"] = Relationship(back_populates="nodo")


class Switch(SQLModel, table=True):
    __tablename__ = "switches"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('Operativo','Con fallas','Fuera de servicio')",
            name="ck_switch_estado",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    nodo_id: int = Field(foreign_key="nodos_red.id")
    identificador: str
    estado: str = Field(default="Operativo")

    nodo: Optional[NodoRed] = Relationship(back_populates="switches")
    salas: List["Sala"] = Relationship(back_populates="switch")


# ============================================================
# MÓDULO I: INFRAESTRUCTURA (Salas y Puestos)
# ============================================================

class Sala(SQLModel, table=True):
    __tablename__ = "salas"

    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(unique=True)
    switch_id: Optional[int] = Field(default=None, foreign_key="switches.id")

    switch: Optional[Switch] = Relationship(back_populates="salas")
    puestos: List["PuestoAnclaje"] = Relationship(back_populates="sala")


class PuestoAnclaje(SQLModel, table=True):
    __tablename__ = "puestos_anclajes"
    __table_args__ = (
        UniqueConstraint("sala_id", "numero_puesto", name="ux_sala_numero_puesto"),
        CheckConstraint("estado_jack IN ('Bien','Con fallas','Roto')", name="ck_estado_jack"),
        CheckConstraint("estado_cable IN ('Bien','Con fallas','Roto')", name="ck_estado_cable"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    sala_id: int = Field(foreign_key="salas.id")
    numero_puesto: int
    estado_anclaje_id: int = Field(foreign_key="estados_anclaje.id")
    observaciones: Optional[str] = None
    estado_jack: str = Field(default="Bien")
    estado_cable: str = Field(default="Bien")

    sala: Optional[Sala] = Relationship(back_populates="puestos")
    estado_anclaje: Optional[EstadoAnclaje] = Relationship()
    computadora: Optional["Computadora"] = Relationship(back_populates="puesto")
    perifericos: List["Periferico"] = Relationship(back_populates="puesto")


# ============================================================
# MÓDULO II: INVENTARIO (Computadoras y Periféricos)
# ============================================================

class Computadora(SQLModel, table=True):
    __tablename__ = "computadoras"
    __table_args__ = (
        # Garantiza máximo 1 PC por puesto, pero permite múltiples PCs
        # con puesto_id NULL (todas "en depósito" a la vez). Replica acá
        # el mismo índice parcial ux_computadora_puesto del script SQL del
        # Paso 1, para que la regla se cumpla también si la base se crea
        # desde cero solo con SQLModel.metadata.create_all().
        Index(
            "ux_computadora_puesto",
            "puesto_id",
            unique=True,
            sqlite_where=text("puesto_id IS NOT NULL"),
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    puesto_id: Optional[int] = Field(default=None, foreign_key="puestos_anclajes.id")
    procesador: Optional[str] = None
    ram: Optional[str] = None
    almacenamiento: Optional[str] = None
    tarjeta_grafica: Optional[str] = None
    sistema_operativo: Optional[str] = None
    estado_operativo_id: int = Field(foreign_key="estados_operativo_pc.id")
    numero_serie: Optional[str] = None
    fecha_alta: datetime = Field(default_factory=ahora_argentina)

    puesto: Optional[PuestoAnclaje] = Relationship(back_populates="computadora")
    estado_operativo: Optional[EstadoOperativoPC] = Relationship()
    auditorias: List["AuditoriaSoftware"] = Relationship(back_populates="computadora")
    historial_soporte: List["HistorialSoporte"] = Relationship(back_populates="computadora")
    historial_ubicaciones: List["HistorialUbicacion"] = Relationship(back_populates="computadora")


class Periferico(SQLModel, table=True):
    __tablename__ = "perifericos"

    id: Optional[int] = Field(default=None, primary_key=True)
    puesto_id: int = Field(foreign_key="puestos_anclajes.id")
    tipo_id: int = Field(foreign_key="tipos_periferico.id")
    estado_id: int = Field(foreign_key="estados_periferico.id")
    detalle_falla: Optional[str] = None
    marca_modelo: Optional[str] = None

    puesto: Optional[PuestoAnclaje] = Relationship(back_populates="perifericos")
    tipo: Optional[TipoPeriferico] = Relationship()
    estado: Optional[EstadoPeriferico] = Relationship()


class HistorialUbicacion(SQLModel, table=True):
    __tablename__ = "historial_ubicaciones"

    id: Optional[int] = Field(default=None, primary_key=True)
    computadora_id: int = Field(foreign_key="computadoras.id")
    puesto_id_anterior: Optional[int] = Field(default=None, foreign_key="puestos_anclajes.id")
    puesto_id_nuevo: Optional[int] = Field(default=None, foreign_key="puestos_anclajes.id")
    fecha: datetime = Field(default_factory=ahora_argentina)
    usuario_registro: Optional[str] = None

    computadora: Optional[Computadora] = Relationship(back_populates="historial_ubicaciones")


# ============================================================
# MÓDULO III: AUDITORÍA DE SOFTWARE Y SEGURIDAD
# ============================================================

class AuditoriaSoftware(SQLModel, table=True):
    __tablename__ = "auditorias_software"
    __table_args__ = (
        CheckConstraint("deep_freeze IN (0,1)", name="ck_deep_freeze"),
        CheckConstraint(
            "gravedad_malware IN ('Baja','Media','Alta') OR gravedad_malware IS NULL",
            name="ck_gravedad_malware",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    computadora_id: int = Field(foreign_key="computadoras.id")
    fecha_auditoria: datetime = Field(default_factory=ahora_argentina)
    deep_freeze: bool
    malware_detectado: Optional[str] = None
    gravedad_malware: Optional[str] = None
    software_no_autorizado: Optional[str] = None
    usuario_registro: Optional[str] = None

    computadora: Optional[Computadora] = Relationship(back_populates="auditorias")
    detalle: List["AuditoriaSoftwareDetalle"] = Relationship(back_populates="auditoria")


class AuditoriaSoftwareDetalle(SQLModel, table=True):
    __tablename__ = "auditoria_software_detalle"
    __table_args__ = (
        UniqueConstraint("auditoria_id", "software_id", name="ux_auditoria_software"),
        CheckConstraint("instalado IN (0,1)", name="ck_instalado"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    auditoria_id: int = Field(foreign_key="auditorias_software.id")
    software_id: int = Field(foreign_key="software_catalogo.id")
    instalado: bool

    auditoria: Optional[AuditoriaSoftware] = Relationship(back_populates="detalle")
    software: Optional[SoftwareCatalogo] = Relationship()


# ============================================================
# MÓDULO V: HISTORIAL DE SOPORTE
# ============================================================

class HistorialSoporte(SQLModel, table=True):
    __tablename__ = "historial_soporte"

    id: Optional[int] = Field(default=None, primary_key=True)
    computadora_id: int = Field(foreign_key="computadoras.id")
    tipo_componente_id: int = Field(foreign_key="tipos_componente.id")
    componente_retirado_detalle: Optional[str] = None
    componente_nuevo_detalle: Optional[str] = None
    nro_serie_nuevo: Optional[str] = None
    fecha_hora: datetime = Field(default_factory=ahora_argentina)
    observaciones: Optional[str] = None
    usuario_registro: Optional[str] = None

    computadora: Optional[Computadora] = Relationship(back_populates="historial_soporte")
    tipo_componente: Optional[TipoComponente] = Relationship()