"""
routes/historial.py
Endpoints para el Módulo V (Historial de Soporte y Cambio de Componentes).

Decisión de diseño: este es un log append-only por convención de
aplicación (así lo definiste en el Paso 1, punto 10). Por eso este
archivo NO tiene endpoints PUT ni DELETE para historial_soporte -- ni
siquiera existen como ruta. Si un registro se cargó mal, se carga un
registro nuevo aclarando el error en "observaciones"; nunca se corrige
el original. La fecha_hora se completa sola con ahora_argentina()
(definida en connection.py), así que todo el log queda en hora real
de la escuela sin que el frontend tenga que calcular nada.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, select

from database.connection import get_session
from database.models import Computadora, HistorialSoporte, TipoComponente

router = APIRouter(tags=["Historial de Soporte"])


# ================================================================
# Schemas
# ================================================================

class HistorialSoporteCreate(SQLModel):
    computadora_id: int
    tipo_componente_id: int
    componente_retirado_detalle: Optional[str] = None
    componente_nuevo_detalle: Optional[str] = None
    nro_serie_nuevo: Optional[str] = None
    observaciones: Optional[str] = None
    usuario_registro: Optional[str] = None


class HistorialSoporteRead(SQLModel):
    id: int
    computadora_id: int
    tipo_componente_id: int
    componente_retirado_detalle: Optional[str] = None
    componente_nuevo_detalle: Optional[str] = None
    nro_serie_nuevo: Optional[str] = None
    fecha_hora: datetime
    observaciones: Optional[str] = None
    usuario_registro: Optional[str] = None


class TipoComponenteCreate(SQLModel):
    nombre: str


# ================================================================
# HISTORIAL DE SOPORTE (solo creación y lectura - NUNCA edición/borrado)
# ================================================================

@router.post("/historial-soporte/", response_model=HistorialSoporteRead, status_code=201)
def crear_registro_soporte(
    datos: HistorialSoporteCreate, session: Session = Depends(get_session)
):
    if not session.get(Computadora, datos.computadora_id):
        raise HTTPException(status_code=404, detail="La computadora indicada no existe.")

    if not session.get(TipoComponente, datos.tipo_componente_id):
        raise HTTPException(status_code=404, detail="El tipo de componente indicado no existe.")

    registro = HistorialSoporte(
        computadora_id=datos.computadora_id,
        tipo_componente_id=datos.tipo_componente_id,
        componente_retirado_detalle=datos.componente_retirado_detalle,
        componente_nuevo_detalle=datos.componente_nuevo_detalle,
        nro_serie_nuevo=datos.nro_serie_nuevo,
        observaciones=datos.observaciones,
        usuario_registro=datos.usuario_registro,
    )
    session.add(registro)
    session.commit()
    session.refresh(registro)
    return registro


@router.get("/historial-soporte/", response_model=List[HistorialSoporteRead])
def listar_registros_soporte(
    computadora_id: Optional[int] = None,
    tipo_componente_id: Optional[int] = None,
    session: Session = Depends(get_session),
):
    consulta = select(HistorialSoporte).order_by(HistorialSoporte.fecha_hora.desc())
    if computadora_id is not None:
        consulta = consulta.where(HistorialSoporte.computadora_id == computadora_id)
    if tipo_componente_id is not None:
        consulta = consulta.where(HistorialSoporte.tipo_componente_id == tipo_componente_id)
    return session.exec(consulta).all()


@router.get("/historial-soporte/{registro_id}", response_model=HistorialSoporteRead)
def obtener_registro_soporte(registro_id: int, session: Session = Depends(get_session)):
    registro = session.get(HistorialSoporte, registro_id)
    if not registro:
        raise HTTPException(status_code=404, detail="Registro de soporte no encontrado.")
    return registro


@router.get(
    "/computadoras/{computadora_id}/historial-soporte",
    response_model=List[HistorialSoporteRead],
)
def historial_soporte_de_computadora(
    computadora_id: int, session: Session = Depends(get_session)
):
    """Bitácora técnica completa de una PC puntual, más reciente primero."""
    if not session.get(Computadora, computadora_id):
        raise HTTPException(status_code=404, detail="Computadora no encontrada.")

    consulta = (
        select(HistorialSoporte)
        .where(HistorialSoporte.computadora_id == computadora_id)
        .order_by(HistorialSoporte.fecha_hora.desc())
    )
    return session.exec(consulta).all()


# ================================================================
# CATÁLOGO DE TIPOS DE COMPONENTE
# ================================================================

@router.get("/historial-soporte/catalogos/tipos-componente", response_model=List[TipoComponente])
def listar_tipos_componente(session: Session = Depends(get_session)):
    return session.exec(select(TipoComponente)).all()


@router.post(
    "/historial-soporte/catalogos/tipos-componente",
    response_model=TipoComponente,
    status_code=201,
)
def crear_tipo_componente(
    datos: TipoComponenteCreate, session: Session = Depends(get_session)
):
    tipo = TipoComponente(nombre=datos.nombre)
    session.add(tipo)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail="Ya existe un tipo de componente con ese nombre.")
    session.refresh(tipo)
    return tipo