"""
routes/auditoria.py
Endpoints para el Módulo III (Auditoría de Software, Seguridad y Configuración).

Decisiones de diseño:
- Una auditoría y su checklist de software se crean SIEMPRE juntas, en una
  sola transacción (POST /auditorias/). Si algo falla (ej: un software_id
  que no existe en el catálogo), no se guarda nada -> nunca queda una
  auditoría "a medias".
- Las auditorías son snapshots inmutables: no existe PUT para editarlas.
  Si se cargó algo mal, se crea una auditoría nueva (mismo criterio que
  ya usamos para historial_soporte y historial_ubicaciones).
- Las alertas (Deep Freeze apagado, malware, software faltante) se
  calculan al vuelo a partir de los datos guardados; no se guardan como
  columna en ningún lado.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, select

from database.connection import get_session
from database.models import (
    AuditoriaSoftware,
    AuditoriaSoftwareDetalle,
    Computadora,
    SoftwareCatalogo,
)

router = APIRouter(tags=["Auditoría de Software"])


# ================================================================
# Schemas
# ================================================================

class ChecklistItemInput(SQLModel):
    software_id: int
    instalado: bool


class AuditoriaSoftwareCreate(SQLModel):
    computadora_id: int
    deep_freeze: bool
    malware_detectado: Optional[str] = None
    gravedad_malware: Optional[str] = None  # 'Baja' | 'Media' | 'Alta'
    software_no_autorizado: Optional[str] = None
    usuario_registro: Optional[str] = None
    checklist: List[ChecklistItemInput] = []


class ChecklistItemRead(SQLModel):
    software_id: int
    nombre_software: str
    categoria: str
    instalado: bool


class AuditoriaSoftwareRead(SQLModel):
    id: int
    computadora_id: int
    fecha_auditoria: datetime
    deep_freeze: bool
    malware_detectado: Optional[str] = None
    gravedad_malware: Optional[str] = None
    software_no_autorizado: Optional[str] = None
    usuario_registro: Optional[str] = None
    checklist: List[ChecklistItemRead]
    alertas: List[str]


class SoftwareCatalogoCreate(SQLModel):
    nombre: str
    categoria: str  # 'Programacion' | 'Ofimatica' | 'Navegador' | 'Otro'


# ================================================================
# Helpers
# ================================================================

def _calcular_alertas(auditoria: AuditoriaSoftware, checklist: List[ChecklistItemRead]) -> List[str]:
    alertas: List[str] = []

    if not auditoria.deep_freeze:
        alertas.append("Deep Freeze desactivado")

    if auditoria.malware_detectado:
        detalle_gravedad = f" (gravedad: {auditoria.gravedad_malware})" if auditoria.gravedad_malware else ""
        alertas.append(f"Malware detectado: {auditoria.malware_detectado}{detalle_gravedad}")

    faltante = [item.nombre_software for item in checklist if not item.instalado]
    if faltante:
        alertas.append(f"Software obligatorio faltante: {', '.join(faltante)}")

    if auditoria.software_no_autorizado:
        alertas.append(f"Software no autorizado presente: {auditoria.software_no_autorizado}")

    return alertas


def _armar_respuesta(session: Session, auditoria: AuditoriaSoftware) -> AuditoriaSoftwareRead:
    filas = session.exec(
        select(AuditoriaSoftwareDetalle, SoftwareCatalogo)
        .where(AuditoriaSoftwareDetalle.auditoria_id == auditoria.id)
        .where(AuditoriaSoftwareDetalle.software_id == SoftwareCatalogo.id)
    ).all()

    checklist = [
        ChecklistItemRead(
            software_id=software.id,
            nombre_software=software.nombre,
            categoria=software.categoria,
            instalado=detalle.instalado,
        )
        for detalle, software in filas
    ]

    return AuditoriaSoftwareRead(
        id=auditoria.id,
        computadora_id=auditoria.computadora_id,
        fecha_auditoria=auditoria.fecha_auditoria,
        deep_freeze=auditoria.deep_freeze,
        malware_detectado=auditoria.malware_detectado,
        gravedad_malware=auditoria.gravedad_malware,
        software_no_autorizado=auditoria.software_no_autorizado,
        usuario_registro=auditoria.usuario_registro,
        checklist=checklist,
        alertas=_calcular_alertas(auditoria, checklist),
    )


# ================================================================
# AUDITORÍAS
# ================================================================

@router.post("/auditorias/", response_model=AuditoriaSoftwareRead, status_code=201)
def crear_auditoria(datos: AuditoriaSoftwareCreate, session: Session = Depends(get_session)):
    if not session.get(Computadora, datos.computadora_id):
        raise HTTPException(status_code=404, detail="La computadora indicada no existe.")

    ids_recibidos = [item.software_id for item in datos.checklist]
    if len(ids_recibidos) != len(set(ids_recibidos)):
        raise HTTPException(status_code=400, detail="El checklist tiene un software_id repetido.")

    auditoria = AuditoriaSoftware(
        computadora_id=datos.computadora_id,
        deep_freeze=datos.deep_freeze,
        malware_detectado=datos.malware_detectado,
        gravedad_malware=datos.gravedad_malware,
        software_no_autorizado=datos.software_no_autorizado,
        usuario_registro=datos.usuario_registro,
    )
    session.add(auditoria)
    session.flush()  # asigna auditoria.id sin cerrar la transacción todavía

    for item in datos.checklist:
        if not session.get(SoftwareCatalogo, item.software_id):
            session.rollback()
            raise HTTPException(
                status_code=404, detail=f"El software_id {item.software_id} no existe en el catálogo."
            )
        session.add(
            AuditoriaSoftwareDetalle(
                auditoria_id=auditoria.id,
                software_id=item.software_id,
                instalado=item.instalado,
            )
        )

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail="Error de integridad al guardar el checklist.")

    session.refresh(auditoria)
    return _armar_respuesta(session, auditoria)


@router.get("/auditorias/", response_model=List[AuditoriaSoftwareRead])
def listar_auditorias(
    computadora_id: Optional[int] = None,
    session: Session = Depends(get_session),
):
    consulta = select(AuditoriaSoftware).order_by(AuditoriaSoftware.fecha_auditoria.desc())
    if computadora_id is not None:
        consulta = consulta.where(AuditoriaSoftware.computadora_id == computadora_id)
    auditorias = session.exec(consulta).all()
    return [_armar_respuesta(session, a) for a in auditorias]


@router.get("/auditorias/{auditoria_id}", response_model=AuditoriaSoftwareRead)
def obtener_auditoria(auditoria_id: int, session: Session = Depends(get_session)):
    auditoria = session.get(AuditoriaSoftware, auditoria_id)
    if not auditoria:
        raise HTTPException(status_code=404, detail="Auditoría no encontrada.")
    return _armar_respuesta(session, auditoria)


@router.get(
    "/computadoras/{computadora_id}/auditorias/ultima",
    response_model=AuditoriaSoftwareRead,
)
def obtener_ultima_auditoria(computadora_id: int, session: Session = Depends(get_session)):
    """
    Pensado para el dashboard: trae la auditoría más reciente de una PC,
    con sus alertas ya calculadas, para decidir el color del puesto.
    """
    if not session.get(Computadora, computadora_id):
        raise HTTPException(status_code=404, detail="Computadora no encontrada.")

    auditoria = session.exec(
        select(AuditoriaSoftware)
        .where(AuditoriaSoftware.computadora_id == computadora_id)
        .order_by(AuditoriaSoftware.fecha_auditoria.desc())
    ).first()

    if not auditoria:
        raise HTTPException(status_code=404, detail="Esta computadora todavía no tiene auditorías cargadas.")

    return _armar_respuesta(session, auditoria)


# ================================================================
# CATÁLOGO DE SOFTWARE
# ================================================================

@router.get("/software-catalogo/", response_model=List[SoftwareCatalogo])
def listar_software_catalogo(
    categoria: Optional[str] = None, session: Session = Depends(get_session)
):
    consulta = select(SoftwareCatalogo)
    if categoria is not None:
        consulta = consulta.where(SoftwareCatalogo.categoria == categoria)
    return session.exec(consulta).all()


@router.post("/software-catalogo/", response_model=SoftwareCatalogo, status_code=201)
def crear_software_catalogo(
    datos: SoftwareCatalogoCreate, session: Session = Depends(get_session)
):
    software = SoftwareCatalogo(nombre=datos.nombre, categoria=datos.categoria)
    session.add(software)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail="Ya existe un software con ese nombre en el catálogo.")
    session.refresh(software)
    return software