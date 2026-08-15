"""
routes/salas.py
Endpoints CRUD para el Módulo I (Salas).

Nota: `cantidad_puestos` se calcula al vuelo con un COUNT(), nunca se
guarda como columna en la tabla `salas` — evitamos dato derivado
almacenado, tal como definimos en el diseño de la base (Paso 1).
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, func, select

from database.connection import get_session
from database.models import Computadora, EstadoAnclaje, Periferico, PuestoAnclaje, Sala

router = APIRouter(prefix="/salas", tags=["Salas"])


# ---------- Schemas de entrada/salida (no son tablas) ----------

class SalaCreate(SQLModel):
    nombre: str
    switch_id: Optional[int] = None


class SalaUpdate(SQLModel):
    nombre: Optional[str] = None
    switch_id: Optional[int] = None


class SalaRead(SQLModel):
    id: int
    nombre: str
    switch_id: Optional[int] = None
    cantidad_puestos: int


class PuestoDetalleRead(SQLModel):
    id: int
    sala_id: int
    sala_nombre: str
    numero_puesto: int
    estado_anclaje_id: int
    estado_anclaje_nombre: str
    observaciones: Optional[str] = None
    estado_jack: str
    estado_cable: str


class PuestoCreate(SQLModel):
    numero_puesto: int
    estado_anclaje_id: int
    observaciones: Optional[str] = None


class PuestoUpdate(SQLModel):
    # A propósito NO incluye estado_jack / estado_cable -> esos se
    # actualizan desde routes/red.py (PUT /red/puestos/{id}/estado-cableado)
    numero_puesto: Optional[int] = None
    estado_anclaje_id: Optional[int] = None
    observaciones: Optional[str] = None


class EstadoAnclajeRead(SQLModel):
    id: int
    nombre: str


# ---------- Helper interno ----------

def _contar_puestos(session: Session, sala_id: int) -> int:
    return session.exec(
        select(func.count())
        .select_from(PuestoAnclaje)
        .where(PuestoAnclaje.sala_id == sala_id)
    ).one()


def _a_sala_read(session: Session, sala: Sala) -> SalaRead:
    return SalaRead(
        id=sala.id,
        nombre=sala.nombre,
        switch_id=sala.switch_id,
        cantidad_puestos=_contar_puestos(session, sala.id),
    )


# ---------- Endpoints ----------

@router.post("/", response_model=SalaRead, status_code=201)
def crear_sala(datos: SalaCreate, session: Session = Depends(get_session)):
    sala = Sala(nombre=datos.nombre, switch_id=datos.switch_id)
    session.add(sala)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail="Ya existe una sala con ese nombre.")
    session.refresh(sala)
    return _a_sala_read(session, sala)


@router.get("/", response_model=List[SalaRead])
def listar_salas(session: Session = Depends(get_session)):
    salas = session.exec(select(Sala)).all()
    return [_a_sala_read(session, sala) for sala in salas]


@router.get("/{sala_id}", response_model=SalaRead)
def obtener_sala(sala_id: int, session: Session = Depends(get_session)):
    sala = session.get(Sala, sala_id)
    if not sala:
        raise HTTPException(status_code=404, detail="Sala no encontrada.")
    return _a_sala_read(session, sala)


@router.put("/{sala_id}", response_model=SalaRead)
def actualizar_sala(sala_id: int, datos: SalaUpdate, session: Session = Depends(get_session)):
    sala = session.get(Sala, sala_id)
    if not sala:
        raise HTTPException(status_code=404, detail="Sala no encontrada.")

    cambios = datos.model_dump(exclude_unset=True)
    for campo, valor in cambios.items():
        setattr(sala, campo, valor)

    session.add(sala)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail="Ya existe una sala con ese nombre.")
    session.refresh(sala)
    return _a_sala_read(session, sala)


@router.delete("/{sala_id}", status_code=204)
def eliminar_sala(sala_id: int, session: Session = Depends(get_session)):
    sala = session.get(Sala, sala_id)
    if not sala:
        raise HTTPException(status_code=404, detail="Sala no encontrada.")

    session.delete(sala)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail="No se puede eliminar: la sala todavía tiene puestos asociados.",
        )


# ================================================================
# CRUD DE PUESTOS (alta, edición de anclaje/observaciones/numeración, borrado)
# ================================================================

def _a_puesto_detalle(session: Session, puesto: PuestoAnclaje) -> PuestoDetalleRead:
    sala = session.get(Sala, puesto.sala_id)
    estado_anclaje = session.get(EstadoAnclaje, puesto.estado_anclaje_id)
    return PuestoDetalleRead(
        id=puesto.id,
        sala_id=puesto.sala_id,
        sala_nombre=sala.nombre if sala else "",
        numero_puesto=puesto.numero_puesto,
        estado_anclaje_id=puesto.estado_anclaje_id,
        estado_anclaje_nombre=estado_anclaje.nombre if estado_anclaje else "",
        observaciones=puesto.observaciones,
        estado_jack=puesto.estado_jack,
        estado_cable=puesto.estado_cable,
    )


@router.get("/puestos/{puesto_id}", response_model=PuestoDetalleRead)
def obtener_puesto(puesto_id: int, session: Session = Depends(get_session)):
    puesto = session.get(PuestoAnclaje, puesto_id)
    if not puesto:
        raise HTTPException(status_code=404, detail="Puesto no encontrado.")
    return _a_puesto_detalle(session, puesto)


@router.post("/{sala_id}/puestos/", response_model=PuestoDetalleRead, status_code=201)
def crear_puesto(sala_id: int, datos: PuestoCreate, session: Session = Depends(get_session)):
    if not session.get(Sala, sala_id):
        raise HTTPException(status_code=404, detail="Sala no encontrada.")
    if not session.get(EstadoAnclaje, datos.estado_anclaje_id):
        raise HTTPException(status_code=404, detail="El estado de anclaje indicado no existe.")

    puesto = PuestoAnclaje(
        sala_id=sala_id,
        numero_puesto=datos.numero_puesto,
        estado_anclaje_id=datos.estado_anclaje_id,
        observaciones=datos.observaciones,
    )
    session.add(puesto)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Ya existe el puesto número {datos.numero_puesto} en esta sala.",
        )
    session.refresh(puesto)
    return _a_puesto_detalle(session, puesto)


@router.get("/{sala_id}/puestos/", response_model=List[PuestoDetalleRead])
def listar_puestos_de_sala(sala_id: int, session: Session = Depends(get_session)):
    if not session.get(Sala, sala_id):
        raise HTTPException(status_code=404, detail="Sala no encontrada.")

    puestos = session.exec(
        select(PuestoAnclaje)
        .where(PuestoAnclaje.sala_id == sala_id)
        .order_by(PuestoAnclaje.numero_puesto)
    ).all()
    return [_a_puesto_detalle(session, p) for p in puestos]


@router.put("/puestos/{puesto_id}", response_model=PuestoDetalleRead)
def actualizar_puesto(
    puesto_id: int, datos: PuestoUpdate, session: Session = Depends(get_session)
):
    puesto = session.get(PuestoAnclaje, puesto_id)
    if not puesto:
        raise HTTPException(status_code=404, detail="Puesto no encontrado.")

    cambios = datos.model_dump(exclude_unset=True)
    if "estado_anclaje_id" in cambios and not session.get(EstadoAnclaje, cambios["estado_anclaje_id"]):
        raise HTTPException(status_code=404, detail="El estado de anclaje indicado no existe.")

    for campo, valor in cambios.items():
        setattr(puesto, campo, valor)

    session.add(puesto)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Ya existe otro puesto con ese número en la misma sala.",
        )
    session.refresh(puesto)
    return _a_puesto_detalle(session, puesto)


@router.delete("/puestos/{puesto_id}", status_code=204)
def eliminar_puesto(puesto_id: int, session: Session = Depends(get_session)):
    puesto = session.get(PuestoAnclaje, puesto_id)
    if not puesto:
        raise HTTPException(status_code=404, detail="Puesto no encontrado.")

    # Chequeo EXPLÍCITO antes de borrar: si dejáramos que SQLAlchemy
    # intente el DELETE directamente, como Computadora.puesto_id es
    # nullable, el ORM pondría NULL ahí solo (mandando la PC a depósito
    # en silencio, sin quedar en historial_ubicaciones) en vez de
    # bloquear el borrado como corresponde. Por eso validamos acá,
    # explícitamente, antes de tocar la base.
    tiene_computadora = session.exec(
        select(Computadora).where(Computadora.puesto_id == puesto_id)
    ).first()
    if tiene_computadora:
        raise HTTPException(
            status_code=400,
            detail=(
                "No se puede eliminar: el puesto tiene una computadora asociada "
                "(usá /mover para pasarla a depósito u otro puesto primero)."
            ),
        )

    tiene_perifericos = session.exec(
        select(Periferico).where(Periferico.puesto_id == puesto_id)
    ).first()
    if tiene_perifericos:
        raise HTTPException(
            status_code=400,
            detail="No se puede eliminar: el puesto tiene periféricos asociados. Eliminalos primero.",
        )

    session.delete(puesto)
    session.commit()


@router.get("/catalogos/estados-anclaje", response_model=List[EstadoAnclajeRead])
def listar_estados_anclaje(session: Session = Depends(get_session)):
    return session.exec(select(EstadoAnclaje)).all()