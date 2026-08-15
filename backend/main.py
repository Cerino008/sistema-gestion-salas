"""
main.py
Archivo principal que levanta la API con FastAPI.

Para correrlo (parado dentro de la carpeta backend/):
    uvicorn main:app --reload

La documentación interactiva queda disponible automáticamente en:
    http://127.0.0.1:8000/docs
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database.connection import create_db_and_tables
from routes import auditoria, dashboard, historial, inventario, red, salas


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Se ejecuta al arrancar el servidor: crea las tablas si no existen
    # (si ya corriste schema_gestion_salas.sql, no hace nada nuevo).
    create_db_and_tables()
    yield


app = FastAPI(
    title="Sistema de Gestión de Salas de Informática",
    description="API para inventario, auditoría y control de las 4 salas del establecimiento.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS abierto para desarrollo local: el frontend (HTML+Tailwind+Alpine.js)
# se sirve desde otro puerto/origen mientras programás. Antes de llevarlo
# a producción conviene restringir "allow_origins" a la URL real.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(salas.router)
app.include_router(inventario.router)
app.include_router(auditoria.router)
app.include_router(historial.router)
app.include_router(red.router)
app.include_router(dashboard.router)


@app.get("/", tags=["Estado"])
def estado_api():
    return {"mensaje": "API del Sistema de Gestión de Salas funcionando correctamente."}