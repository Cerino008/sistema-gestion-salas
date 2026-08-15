"""
routes/inventario.py
Endpoints CRUD para el Módulo II (Computadoras y Periféricos).

Decisión de diseño clave:
- Editar specs de una PC (RAM, procesador, etc.) y MOVER una PC de puesto
  son dos acciones distintas a propósito. PUT /computadoras/{id} nunca
  toca puesto_id. Para mover una PC hay que usar
  PUT /computadoras/{id}/mover, que es el único camino que:
    1) Cambia el puesto_id de la computadora.
    2) Registra automáticamente el movimiento en historial_ubicaciones.
  Esto evita que alguien mueva una PC "por accidente" al hacer un PUT
  genérico y se pierda la trazabilidad que pediste en el Paso 1.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, select

from database.connection import get_session
from database.models import (
    Computadora,
    EstadoOperativoPC,
    EstadoPeriferico,
    HistorialUbicacion,
    Periferico,
    PuestoAnclaje,
    TipoPeriferico,
)

router = APIRouter(tags=["Inventario"])


# ================================================================
# Schemas de Computadoras
# ================================================================

class ComputadoraCreate(SQLModel):
    puesto_id: Optional[int] = None
    procesador: Optional[str] = None
    ram: Optional[str] = None
    almacenamiento: Optional[str] = None
    tarjeta_grafica: Optional[str] = None
    sistema_operativo: Optional[str] = None
    estado_operativo_id: int
    numero_serie: Optional[str] = None
    usuario_registro: Optional[str] = None  # solo para el log, si nace ya ubicada


class ComputadoraUpdate(SQLModel):
    # A propósito NO incluye puesto_id -> usar el endpoint /mover
    procesador: Optional[str] = None
    ram: Optional[str] = None
    almacenamiento: Optional[str] = None
    tarjeta_grafica: Optional[str] = None
    sistema_operativo: Optional[str] = None
    estado_operativo_id: Optional[int] = None
    numero_serie: Optional[str] = None


class ComputadoraMover(SQLModel):
    puesto_id_nuevo: Optional[int] = None  # None = la PC pasa a depósito
    usuario_registro: Optional[str] = None


class ComputadoraRead(SQLModel):
    id: int
    puesto_id: Optional[int] = None
    procesador: Optional[str] = None
    ram: Optional[str] = None
    almacenamiento: Optional[str] = None
    tarjeta_grafica: Optional[str] = None
    sistema_operativo: Optional[str] = None
    estado_operativo_id: int
    numero_serie: Optional[str] = None
    fecha_alta: datetime


class HistorialUbicacionRead(SQLModel):
    id: int
    computadora_id: int
    puesto_id_anterior: Optional[int] = None
    puesto_id_nuevo: Optional[int] = None
    fecha: datetime
    usuario_registro: Optional[str] = None


# ================================================================
# Schemas de Periféricos
# ================================================================

class PerifericoCreate(SQLModel):
    puesto_id: int
    tipo_id: int
    estado_id: int
    detalle_falla: Optional[str] = None
    marca_modelo: Optional[str] = None


class PerifericoUpdate(SQLModel):
    tipo_id: Optional[int] = None
    estado_id: Optional[int] = None
    detalle_falla: Optional[str] = None
    marca_modelo: Optional[str] = None
    puesto_id: Optional[int] = None  # reponer un periférico en otro puesto es un caso válido y simple


class PerifericoRead(SQLModel):
    id: int
    puesto_id: int
    tipo_id: int
    estado_id: int
    detalle_falla: Optional[str] = None
    marca_modelo: Optional[str] = None


# ================================================================
# COMPUTADORAS
# ================================================================

@router.post("/computadoras/", response_model=ComputadoraRead, status_code=201)
def crear_computadora(datos: ComputadoraCreate, session: Session = Depends(get_session)):
    if datos.puesto_id is not None:
        if not session.get(PuestoAnclaje, datos.puesto_id):
            raise HTTPException(status_code=404, detail="El puesto indicado no existe.")

    computadora = Computadora(
        puesto_id=datos.puesto_id,
        procesador=datos.procesador,
        ram=datos.ram,
        almacenamiento=datos.almacenamiento,
        tarjeta_grafica=datos.tarjeta_grafica,
        sistema_operativo=datos.sistema_operativo,
        estado_operativo_id=datos.estado_operativo_id,
        numero_serie=datos.numero_serie,
    )
    session.add(computadora)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail="Ese puesto ya tiene una computadora asociada.")
    session.refresh(computadora)

    # Si la PC nace ya asignada a un puesto, dejamos constancia en el
    # historial de ubicaciones (puesto_id_anterior = None = "alta").
    if computadora.puesto_id is not None:
        session.add(
            HistorialUbicacion(
                computadora_id=computadora.id,
                puesto_id_anterior=None,
                puesto_id_nuevo=computadora.puesto_id,
                usuario_registro=datos.usuario_registro,
            )
        )
        session.commit()

    return computadora


@router.get("/computadoras/", response_model=List[ComputadoraRead])
def listar_computadoras(
    puesto_id: Optional[int] = None,
    estado_operativo_id: Optional[int] = None,
    solo_deposito: Optional[bool] = None,
    session: Session = Depends(get_session),
):
    consulta = select(Computadora)
    if solo_deposito:
        # PCs sin puesto asignado -> "en depósito", listas para asignar.
        consulta = consulta.where(Computadora.puesto_id.is_(None))
    elif puesto_id is not None:
        consulta = consulta.where(Computadora.puesto_id == puesto_id)
    if estado_operativo_id is not None:
        consulta = consulta.where(Computadora.estado_operativo_id == estado_operativo_id)
    return session.exec(consulta).all()


@router.get("/computadoras/{computadora_id}", response_model=ComputadoraRead)
def obtener_computadora(computadora_id: int, session: Session = Depends(get_session)):
    computadora = session.get(Computadora, computadora_id)
    if not computadora:
        raise HTTPException(status_code=404, detail="Computadora no encontrada.")
    return computadora


@router.put("/computadoras/{computadora_id}", response_model=ComputadoraRead)
def actualizar_computadora(
    computadora_id: int, datos: ComputadoraUpdate, session: Session = Depends(get_session)
):
    computadora = session.get(Computadora, computadora_id)
    if not computadora:
        raise HTTPException(status_code=404, detail="Computadora no encontrada.")

    cambios = datos.model_dump(exclude_unset=True)
    for campo, valor in cambios.items():
        setattr(computadora, campo, valor)

    session.add(computadora)
    session.commit()
    session.refresh(computadora)
    return computadora


@router.put("/computadoras/{computadora_id}/mover", response_model=ComputadoraRead)
def mover_computadora(
    computadora_id: int, datos: ComputadoraMover, session: Session = Depends(get_session)
):
    """
    Único endpoint habilitado para cambiar el puesto de una PC.
    Registra automáticamente el movimiento en historial_ubicaciones.
    Usar puesto_id_nuevo = null para mandar la PC a depósito.
    """
    computadora = session.get(Computadora, computadora_id)
    if not computadora:
        raise HTTPException(status_code=404, detail="Computadora no encontrada.")

    if datos.puesto_id_nuevo is not None:
        if not session.get(PuestoAnclaje, datos.puesto_id_nuevo):
            raise HTTPException(status_code=404, detail="El puesto destino no existe.")

    if computadora.puesto_id == datos.puesto_id_nuevo:
        raise HTTPException(status_code=400, detail="La computadora ya se encuentra en ese puesto.")

    puesto_anterior = computadora.puesto_id
    computadora.puesto_id = datos.puesto_id_nuevo
    session.add(computadora)
    session.add(
        HistorialUbicacion(
            computadora_id=computadora.id,
            puesto_id_anterior=puesto_anterior,
            puesto_id_nuevo=datos.puesto_id_nuevo,
            usuario_registro=datos.usuario_registro,
        )
    )

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=400, detail="El puesto destino ya tiene una computadora asociada."
        )

    session.refresh(computadora)
    return computadora


@router.get(
    "/computadoras/{computadora_id}/historial-ubicaciones",
    response_model=List[HistorialUbicacionRead],
)
def historial_ubicaciones_computadora(computadora_id: int, session: Session = Depends(get_session)):
    if not session.get(Computadora, computadora_id):
        raise HTTPException(status_code=404, detail="Computadora no encontrada.")

    consulta = (
        select(HistorialUbicacion)
        .where(HistorialUbicacion.computadora_id == computadora_id)
        .order_by(HistorialUbicacion.fecha.desc())
    )
    return session.exec(consulta).all()


@router.delete("/computadoras/{computadora_id}", status_code=204)
def eliminar_computadora(computadora_id: int, session: Session = Depends(get_session)):
    computadora = session.get(Computadora, computadora_id)
    if not computadora:
        raise HTTPException(status_code=404, detail="Computadora no encontrada.")

    session.delete(computadora)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail=(
                "No se puede eliminar: tiene historial de soporte, auditorías o "
                "movimientos asociados. Usá la baja lógica (PUT con estado 'Baja') en su lugar."
            ),
        )


@router.get("/computadoras/catalogos/estados", response_model=List[EstadoOperativoPC])
def listar_estados_operativos(session: Session = Depends(get_session)):
    return session.exec(select(EstadoOperativoPC)).all()


# ================================================================
# PERIFÉRICOS
# ================================================================

@router.post("/perifericos/", response_model=PerifericoRead, status_code=201)
def crear_periferico(datos: PerifericoCreate, session: Session = Depends(get_session)):
    if not session.get(PuestoAnclaje, datos.puesto_id):
        raise HTTPException(status_code=404, detail="El puesto indicado no existe.")

    periferico = Periferico(**datos.model_dump())
    session.add(periferico)
    session.commit()
    session.refresh(periferico)
    return periferico


@router.get("/perifericos/", response_model=List[PerifericoRead])
def listar_perifericos(
    puesto_id: Optional[int] = None,
    tipo_id: Optional[int] = None,
    session: Session = Depends(get_session),
):
    consulta = select(Periferico)
    if puesto_id is not None:
        consulta = consulta.where(Periferico.puesto_id == puesto_id)
    if tipo_id is not None:
        consulta = consulta.where(Periferico.tipo_id == tipo_id)
    return session.exec(consulta).all()


@router.get("/perifericos/{periferico_id}", response_model=PerifericoRead)
def obtener_periferico(periferico_id: int, session: Session = Depends(get_session)):
    periferico = session.get(Periferico, periferico_id)
    if not periferico:
        raise HTTPException(status_code=404, detail="Periférico no encontrado.")
    return periferico


@router.put("/perifericos/{periferico_id}", response_model=PerifericoRead)
def actualizar_periferico(
    periferico_id: int, datos: PerifericoUpdate, session: Session = Depends(get_session)
):
    periferico = session.get(Periferico, periferico_id)
    if not periferico:
        raise HTTPException(status_code=404, detail="Periférico no encontrado.")

    cambios = datos.model_dump(exclude_unset=True)
    if cambios.get("puesto_id") is not None:
        if not session.get(PuestoAnclaje, cambios["puesto_id"]):
            raise HTTPException(status_code=404, detail="El puesto destino no existe.")

    for campo, valor in cambios.items():
        setattr(periferico, campo, valor)

    session.add(periferico)
    session.commit()
    session.refresh(periferico)
    return periferico


@router.delete("/perifericos/{periferico_id}", status_code=204)
def eliminar_periferico(periferico_id: int, session: Session = Depends(get_session)):
    periferico = session.get(Periferico, periferico_id)
    if not periferico:
        raise HTTPException(status_code=404, detail="Periférico no encontrado.")
    session.delete(periferico)
    session.commit()


@router.get("/perifericos/catalogos/tipos", response_model=List[TipoPeriferico])
def listar_tipos_periferico(session: Session = Depends(get_session)):
    return session.exec(select(TipoPeriferico)).all()


@router.get("/perifericos/catalogos/estados", response_model=List[EstadoPeriferico])
def listar_estados_periferico(session: Session = Depends(get_session)):
    return session.exec(select(EstadoPeriferico)).all()