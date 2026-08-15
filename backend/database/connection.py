"""
connection.py
Inicialización de la conexión a SQLite mediante SQLModel.

Reutiliza el mismo archivo database.db que ya generaste con el script SQL
del Paso 1 (schema_gestion_salas.sql). create_db_and_tables() es segura de
llamar aunque las tablas ya existan: SQLModel/SQLAlchemy no las recrea si
ya están presentes.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlmodel import SQLModel, create_engine, Session

# Zona horaria de Argentina (UTC-3, sin horario de verano).
# Requiere el paquete "tzdata" instalado (ya lo tenés).
TZ_ARGENTINA = ZoneInfo("America/Argentina/Buenos_Aires")


def ahora_argentina() -> datetime:
    """
    Devuelve la hora actual en horario de Argentina, como datetime "naive"
    (sin tzinfo). Se guarda naive a propósito: SQLite no tiene un tipo de
    dato nativo para timestamps con zona horaria, así que en vez de guardar
    UTC y convertir en cada consulta, guardamos directamente la hora local
    de la escuela. Así los reportes y la auditoría se leen tal cual, sin
    tener que restar/sumar horas en el frontend.
    """
    return datetime.now(TZ_ARGENTINA).replace(tzinfo=None)


DATABASE_FILE = "database.db"
DATABASE_URL = f"sqlite:///{DATABASE_FILE}"

# check_same_thread=False es necesario porque FastAPI puede manejar
# requests en distintos threads (uso normal y seguro con SQLite + FastAPI).
connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, echo=True, connect_args=connect_args)


def create_db_and_tables() -> None:
    """Crea las tablas definidas en models.py si no existen todavía."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """
    Dependency de FastAPI: entrega una sesión de base de datos por request
    y la cierra automáticamente al finalizar.

    Uso en un endpoint:
        @app.get("/salas")
        def listar_salas(session: Session = Depends(get_session)):
            ...
    """
    with Session(engine) as session:
        yield session