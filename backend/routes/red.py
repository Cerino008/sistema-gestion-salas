"""
routes/red.py
Endpoints para el Módulo IV (Mapa de Red e Infraestructura de Cableado).

Cubre la topología: 2 Nodos -> 1 Switch por nodo -> 2 Salas por switch.
La asignación Sala -> Switch ya se maneja en routes/salas.py (el campo
switch_id de SalaUpdate); acá nos concentramos en administrar los Nodos,
los Switches en sí, y el estado de jack/cable de cada puesto (que vive
en la tabla puestos_anclajes, pero es una acción propia de Red).
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, select

from database.connection import get_session
from database.models import NodoRed, PuestoAnclaje, Sala, Switch

router = APIRouter(prefix="/red", tags=["Red"])

ESTADOS_VALIDOS_JACK_CABLE = {"Bien", "Con fallas", "Roto"}
ESTADOS_VALIDOS_SWITCH = {"Operativo", "Con fallas", "Fuera de servicio"}


# ================================================================
# Schemas
# ================================================================

class NodoRedCreate(SQLModel):
    nombre: str


class NodoRedRead(SQLModel):
    id: int
    nombre: str


class SwitchCreate(SQLModel):
    nodo_id: int
    identificador: str
    estado: str = "Operativo"


class SwitchUpdate(SQLModel):
    nodo_id: Optional[int] = None
    identificador: Optional[str] = None
    estado: Optional[str] = None


class SwitchRead(SQLModel):
    id: int
    nodo_id: int
    identificador: str
    estado: str


class PuestoEstadoRedUpdate(SQLModel):
    estado_jack: Optional[str] = None
    estado_cable: Optional[str] = None


class PuestoRedRead(SQLModel):
    id: int
    numero_puesto: int
    estado_jack: str
    estado_cable: str


class SalaTopologiaRead(SQLModel):
    id: int
    nombre: str
    puestos: List[PuestoRedRead]


class SwitchTopologiaRead(SQLModel):
    id: int
    identificador: str
    estado: str
    salas: List[SalaTopologiaRead]


class NodoTopologiaRead(SQLModel):
    id: int
    nombre: str
    switches: List[SwitchTopologiaRead]


# ================================================================
# NODOS
# ================================================================

@router.post("/nodos/", response_model=NodoRedRead, status_code=201)
def crear_nodo(datos: NodoRedCreate, session: Session = Depends(get_session)):
    nodo = NodoRed(nombre=datos.nombre)
    session.add(nodo)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail="Ya existe un nodo con ese nombre.")
    session.refresh(nodo)
    return nodo


@router.get("/nodos/", response_model=List[NodoRedRead])
def listar_nodos(session: Session = Depends(get_session)):
    return session.exec(select(NodoRed)).all()


@router.get("/nodos/{nodo_id}", response_model=NodoRedRead)
def obtener_nodo(nodo_id: int, session: Session = Depends(get_session)):
    nodo = session.get(NodoRed, nodo_id)
    if not nodo:
        raise HTTPException(status_code=404, detail="Nodo no encontrado.")
    return nodo


# ================================================================
# SWITCHES
# ================================================================

@router.post("/switches/", response_model=SwitchRead, status_code=201)
def crear_switch(datos: SwitchCreate, session: Session = Depends(get_session)):
    if not session.get(NodoRed, datos.nodo_id):
        raise HTTPException(status_code=404, detail="El nodo indicado no existe.")
    if datos.estado not in ESTADOS_VALIDOS_SWITCH:
        raise HTTPException(
            status_code=400,
            detail=f"Estado inválido. Debe ser uno de: {', '.join(ESTADOS_VALIDOS_SWITCH)}.",
        )

    switch = Switch(nodo_id=datos.nodo_id, identificador=datos.identificador, estado=datos.estado)
    session.add(switch)
    session.commit()
    session.refresh(switch)
    return switch


@router.get("/switches/", response_model=List[SwitchRead])
def listar_switches(nodo_id: Optional[int] = None, session: Session = Depends(get_session)):
    consulta = select(Switch)
    if nodo_id is not None:
        consulta = consulta.where(Switch.nodo_id == nodo_id)
    return session.exec(consulta).all()


@router.get("/switches/{switch_id}", response_model=SwitchRead)
def obtener_switch(switch_id: int, session: Session = Depends(get_session)):
    switch = session.get(Switch, switch_id)
    if not switch:
        raise HTTPException(status_code=404, detail="Switch no encontrado.")
    return switch


@router.put("/switches/{switch_id}", response_model=SwitchRead)
def actualizar_switch(
    switch_id: int, datos: SwitchUpdate, session: Session = Depends(get_session)
):
    switch = session.get(Switch, switch_id)
    if not switch:
        raise HTTPException(status_code=404, detail="Switch no encontrado.")

    cambios = datos.model_dump(exclude_unset=True)

    if "nodo_id" in cambios and not session.get(NodoRed, cambios["nodo_id"]):
        raise HTTPException(status_code=404, detail="El nodo indicado no existe.")

    if "estado" in cambios and cambios["estado"] not in ESTADOS_VALIDOS_SWITCH:
        raise HTTPException(
            status_code=400,
            detail=f"Estado inválido. Debe ser uno de: {', '.join(ESTADOS_VALIDOS_SWITCH)}.",
        )

    for campo, valor in cambios.items():
        setattr(switch, campo, valor)

    session.add(switch)
    session.commit()
    session.refresh(switch)
    return switch


# ================================================================
# ESTADO DE CABLEADO POR PUESTO (jack / cable)
# ================================================================

@router.put("/puestos/{puesto_id}/estado-cableado", response_model=PuestoRedRead)
def actualizar_estado_cableado(
    puesto_id: int, datos: PuestoEstadoRedUpdate, session: Session = Depends(get_session)
):
    """
    Endpoint angosto: solo toca estado_jack / estado_cable del puesto.
    Para el resto de los campos de infraestructura (estado_anclaje,
    observaciones) usar el CRUD de puestos en salas.py.
    """
    puesto = session.get(PuestoAnclaje, puesto_id)
    if not puesto:
        raise HTTPException(status_code=404, detail="Puesto no encontrado.")

    cambios = datos.model_dump(exclude_unset=True)
    for campo in ("estado_jack", "estado_cable"):
        if campo in cambios and cambios[campo] not in ESTADOS_VALIDOS_JACK_CABLE:
            raise HTTPException(
                status_code=400,
                detail=f"{campo}: valor inválido. Debe ser uno de: {', '.join(ESTADOS_VALIDOS_JACK_CABLE)}.",
            )

    for campo, valor in cambios.items():
        setattr(puesto, campo, valor)

    session.add(puesto)
    session.commit()
    session.refresh(puesto)
    return puesto


# ================================================================
# TOPOLOGÍA COMPLETA (para mapa de red / futuro dashboard)
# ================================================================

@router.get("/topologia", response_model=List[NodoTopologiaRead])
def obtener_topologia(session: Session = Depends(get_session)):
    """
    Arma el árbol completo: Nodo -> Switches -> Salas -> Puestos, con el
    estado de jack/cable de cada puesto. Pensado para un futuro mapa de
    red visual y como una de las señales de entrada del Dashboard.
    """
    nodos = session.exec(select(NodoRed)).all()
    resultado: List[NodoTopologiaRead] = []

    for nodo in nodos:
        switches = session.exec(select(Switch).where(Switch.nodo_id == nodo.id)).all()
        switches_out = []

        for switch in switches:
            salas = session.exec(select(Sala).where(Sala.switch_id == switch.id)).all()
            salas_out = []

            for sala in salas:
                puestos = session.exec(
                    select(PuestoAnclaje).where(PuestoAnclaje.sala_id == sala.id)
                ).all()
                salas_out.append(
                    SalaTopologiaRead(
                        id=sala.id,
                        nombre=sala.nombre,
                        puestos=[
                            PuestoRedRead(
                                id=p.id,
                                numero_puesto=p.numero_puesto,
                                estado_jack=p.estado_jack,
                                estado_cable=p.estado_cable,
                            )
                            for p in puestos
                        ],
                    )
                )

            switches_out.append(
                SwitchTopologiaRead(
                    id=switch.id,
                    identificador=switch.identificador,
                    estado=switch.estado,
                    salas=salas_out,
                )
            )

        resultado.append(
            NodoTopologiaRead(id=nodo.id, nombre=nodo.nombre, switches=switches_out)
        )

    return resultado