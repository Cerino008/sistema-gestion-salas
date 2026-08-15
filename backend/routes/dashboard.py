"""
routes/dashboard.py
Endpoint unificado para el Dashboard Principal.

Cruza datos de los 4 módulos para calcular, en tiempo real, el color de
cada puesto:
    - Módulo I  (Infraestructura): estado_anclaje, estado_jack, estado_cable
    - Módulo II (Inventario):      estado_operativo de la PC, periféricos
    - Módulo III (Auditoría):      alertas de la última auditoría de software
    - Módulo IV (Red):             estado del switch de la sala

El color NUNCA se guarda en la base -- se recalcula en cada request a
partir del estado actual de todo lo demás. Así el dashboard siempre
refleja la realidad sin riesgo de quedar desincronizado.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlmodel import Session, SQLModel, select

from database.connection import get_session
from database.models import (
    AuditoriaSoftware,
    AuditoriaSoftwareDetalle,
    Computadora,
    EstadoAnclaje,
    EstadoOperativoPC,
    EstadoPeriferico,
    Periferico,
    PuestoAnclaje,
    Sala,
    SoftwareCatalogo,
    Switch,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# ================================================================
# Reglas de color (ajustables en un solo lugar)
# ================================================================

ESTADOS_PC_ROJO = {"No arranca", "Sin dar imagen", "Baja"}
ESTADOS_PC_AMARILLO = {"Da imagen pero queda en BIOS"}

ESTADOS_ANCLAJE_ROJO = {"Roto", "Faltante"}
ESTADOS_ANCLAJE_AMARILLO = {"Flojo", "Incompleto"}

ESTADOS_CABLEADO_ROJO = {"Roto"}
ESTADOS_CABLEADO_AMARILLO = {"Con fallas"}

ESTADOS_PERIFERICO_AMARILLO = {"Falla Parcial", "Roto", "Faltante"}

ESTADOS_SWITCH_ROJO = {"Fuera de servicio"}
ESTADOS_SWITCH_AMARILLO = {"Con fallas"}


# ================================================================
# Schemas
# ================================================================

class PuestoDashboardRead(SQLModel):
    id: int
    numero_puesto: int
    color: str  # 'verde' | 'amarillo' | 'rojo' | 'vacio'
    motivos: List[str]
    tiene_pc: bool
    computadora_id: Optional[int] = None


class SalaDashboardRead(SQLModel):
    id: int
    nombre: str
    switch_estado: Optional[str] = None
    puestos: List[PuestoDashboardRead]


# ================================================================
# Helpers de cálculo
# ================================================================

def _alertas_ultima_auditoria(session: Session, computadora_id: int) -> List[str]:
    """Recalcula las alertas de la auditoría más reciente de una PC (o [] si no tiene ninguna)."""
    auditoria = session.exec(
        select(AuditoriaSoftware)
        .where(AuditoriaSoftware.computadora_id == computadora_id)
        .order_by(AuditoriaSoftware.fecha_auditoria.desc())
    ).first()

    if not auditoria:
        return []

    alertas: List[str] = []
    if not auditoria.deep_freeze:
        alertas.append("Deep Freeze desactivado")
    if auditoria.malware_detectado:
        alertas.append(f"Malware detectado: {auditoria.malware_detectado}")
    if auditoria.software_no_autorizado:
        alertas.append(f"Software no autorizado: {auditoria.software_no_autorizado}")

    faltantes = session.exec(
        select(SoftwareCatalogo.nombre)
        .join(AuditoriaSoftwareDetalle, AuditoriaSoftwareDetalle.software_id == SoftwareCatalogo.id)
        .where(AuditoriaSoftwareDetalle.auditoria_id == auditoria.id)
        .where(AuditoriaSoftwareDetalle.instalado == False)  # noqa: E712
    ).all()
    if faltantes:
        alertas.append(f"Software obligatorio faltante: {', '.join(faltantes)}")

    return alertas


def _calcular_puesto(
    session: Session, puesto: PuestoAnclaje, estado_switch: Optional[str]
) -> PuestoDashboardRead:
    motivos_rojo: List[str] = []
    motivos_amarillo: List[str] = []

    # --- Red (afecta a todo el puesto, venga o no de la PC) ---
    if estado_switch in ESTADOS_SWITCH_ROJO:
        motivos_rojo.append(f"Switch de la sala fuera de servicio")
    elif estado_switch in ESTADOS_SWITCH_AMARILLO:
        motivos_amarillo.append("Switch de la sala con fallas")

    if puesto.estado_cable in ESTADOS_CABLEADO_ROJO or puesto.estado_jack in ESTADOS_CABLEADO_ROJO:
        motivos_rojo.append("Cable o jack de red roto")
    elif puesto.estado_cable in ESTADOS_CABLEADO_AMARILLO or puesto.estado_jack in ESTADOS_CABLEADO_AMARILLO:
        motivos_amarillo.append("Cable o jack de red con fallas")

    # --- Infraestructura física (anclaje) ---
    estado_anclaje = session.get(EstadoAnclaje, puesto.estado_anclaje_id)
    nombre_anclaje = estado_anclaje.nombre if estado_anclaje else None
    if nombre_anclaje in ESTADOS_ANCLAJE_ROJO:
        motivos_rojo.append(f"Anclaje del gabinete: {nombre_anclaje}")
    elif nombre_anclaje in ESTADOS_ANCLAJE_AMARILLO:
        motivos_amarillo.append(f"Anclaje del gabinete: {nombre_anclaje}")

    # --- Periféricos del puesto ---
    perifericos = session.exec(select(Periferico).where(Periferico.puesto_id == puesto.id)).all()
    for periferico in perifericos:
        estado_p = session.get(EstadoPeriferico, periferico.estado_id)
        if estado_p and estado_p.nombre in ESTADOS_PERIFERICO_AMARILLO:
            motivos_amarillo.append(f"Periférico con falla: {estado_p.nombre}")

    # --- Computadora (si hay una en el puesto) ---
    computadora = session.exec(
        select(Computadora).where(Computadora.puesto_id == puesto.id)
    ).first()

    if not computadora:
        return PuestoDashboardRead(
            id=puesto.id,
            numero_puesto=puesto.numero_puesto,
            color="vacio",
            motivos=motivos_rojo + motivos_amarillo,
            tiene_pc=False,
            computadora_id=None,
        )

    estado_pc = session.get(EstadoOperativoPC, computadora.estado_operativo_id)
    nombre_estado_pc = estado_pc.nombre if estado_pc else None
    if nombre_estado_pc in ESTADOS_PC_ROJO:
        motivos_rojo.append(f"PC: {nombre_estado_pc}")
    elif nombre_estado_pc in ESTADOS_PC_AMARILLO:
        motivos_amarillo.append(f"PC: {nombre_estado_pc}")

    motivos_amarillo.extend(_alertas_ultima_auditoria(session, computadora.id))

    if motivos_rojo:
        color = "rojo"
    elif motivos_amarillo:
        color = "amarillo"
    else:
        color = "verde"

    return PuestoDashboardRead(
        id=puesto.id,
        numero_puesto=puesto.numero_puesto,
        color=color,
        motivos=motivos_rojo + motivos_amarillo,
        tiene_pc=True,
        computadora_id=computadora.id,
    )


# ================================================================
# Endpoint principal
# ================================================================

@router.get("/", response_model=List[SalaDashboardRead])
def obtener_dashboard(session: Session = Depends(get_session)):
    salas = session.exec(select(Sala)).all()
    resultado: List[SalaDashboardRead] = []

    for sala in salas:
        estado_switch = None
        if sala.switch_id is not None:
            switch = session.get(Switch, sala.switch_id)
            estado_switch = switch.estado if switch else None

        puestos = session.exec(
            select(PuestoAnclaje)
            .where(PuestoAnclaje.sala_id == sala.id)
            .order_by(PuestoAnclaje.numero_puesto)
        ).all()

        puestos_dashboard = [_calcular_puesto(session, p, estado_switch) for p in puestos]

        resultado.append(
            SalaDashboardRead(
                id=sala.id,
                nombre=sala.nombre,
                switch_estado=estado_switch,
                puestos=puestos_dashboard,
            )
        )

    return resultado


@router.get("/puestos/{puesto_id}", response_model=PuestoDashboardRead)
def obtener_dashboard_puesto(puesto_id: int, session: Session = Depends(get_session)):
    """Detalle de un solo puesto -- útil para la vista puesto-detalle.html."""
    puesto = session.get(PuestoAnclaje, puesto_id)
    if not puesto:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Puesto no encontrado.")

    sala = session.get(Sala, puesto.sala_id)
    estado_switch = None
    if sala and sala.switch_id is not None:
        switch = session.get(Switch, sala.switch_id)
        estado_switch = switch.estado if switch else None

    return _calcular_puesto(session, puesto, estado_switch)