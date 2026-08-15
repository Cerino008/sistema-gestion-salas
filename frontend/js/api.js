/**
 * js/api.js
 * Funciones para comunicarse con el Backend (FastAPI) via Fetch.
 *
 * Cambiá API_BASE si corrés el backend en otro puerto/host.
 */

const API_BASE = "http://127.0.0.1:8080";

/**
 * Wrapper genérico de GET. Lanza un Error con el detail del backend
 * si la respuesta no es OK, para que el caller lo pueda mostrar.
 */
async function apiGet(path) {
  const respuesta = await fetch(`${API_BASE}${path}`);
  if (!respuesta.ok) {
    const cuerpo = await respuesta.json().catch(() => ({}));
    throw new Error(cuerpo.detail || `Error ${respuesta.status} al consultar ${path}`);
  }
  return respuesta.json();
}

async function apiPost(path, datos) {
  const respuesta = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(datos),
  });
  if (!respuesta.ok) {
    const cuerpo = await respuesta.json().catch(() => ({}));
    throw new Error(cuerpo.detail || `Error ${respuesta.status} al enviar a ${path}`);
  }
  return respuesta.json();
}

async function apiPut(path, datos) {
  const respuesta = await fetch(`${API_BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(datos),
  });
  if (!respuesta.ok) {
    const cuerpo = await respuesta.json().catch(() => ({}));
    throw new Error(cuerpo.detail || `Error ${respuesta.status} al actualizar ${path}`);
  }
  return respuesta.json();
}

async function apiDelete(path) {
  const respuesta = await fetch(`${API_BASE}${path}`, { method: "DELETE" });
  if (!respuesta.ok) {
    const cuerpo = await respuesta.json().catch(() => ({}));
    throw new Error(cuerpo.detail || `Error ${respuesta.status} al eliminar ${path}`);
  }
  // 204 No Content -> no hay body que parsear
  return true;
}

// Endpoints puntuales que ya vamos a necesitar en varias pantallas
const api = {
  obtenerDashboard: () => apiGet("/dashboard/"),
  obtenerPuestoDashboard: (puestoId) => apiGet(`/dashboard/puestos/${puestoId}`),
  obtenerPuesto: (puestoId) => apiGet(`/salas/puestos/${puestoId}`),
  obtenerComputadora: (id) => apiGet(`/computadoras/${id}`),
  obtenerPerifericosPorPuesto: (puestoId) => apiGet(`/perifericos/?puesto_id=${puestoId}`),
  obtenerTiposPeriferico: () => apiGet("/perifericos/catalogos/tipos"),
  obtenerEstadosPeriferico: () => apiGet("/perifericos/catalogos/estados"),
  obtenerHistorialUbicaciones: (computadoraId) =>
    apiGet(`/computadoras/${computadoraId}/historial-ubicaciones`),
  obtenerHistorialSoporte: (computadoraId) =>
    apiGet(`/computadoras/${computadoraId}/historial-soporte`),
  obtenerUltimaAuditoria: (computadoraId) =>
    apiGet(`/computadoras/${computadoraId}/auditorias/ultima`).catch(() => null),
  actualizarEstadoCableado: (puestoId, datos) =>
    apiPut(`/red/puestos/${puestoId}/estado-cableado`, datos),
  obtenerSala: (salaId) => apiGet(`/salas/${salaId}`),
  listarPuestosDeSala: (salaId) => apiGet(`/salas/${salaId}/puestos/`),
  crearPuesto: (salaId, datos) => apiPost(`/salas/${salaId}/puestos/`, datos),
  actualizarPuesto: (puestoId, datos) => apiPut(`/salas/puestos/${puestoId}`, datos),
  eliminarPuesto: (puestoId) => apiDelete(`/salas/puestos/${puestoId}`),
  obtenerEstadosAnclaje: () => apiGet("/salas/catalogos/estados-anclaje"),
  crearComputadora: (datos) => apiPost("/computadoras/", datos),
  moverComputadora: (computadoraId, datos) => apiPut(`/computadoras/${computadoraId}/mover`, datos),
  listarComputadorasEnDeposito: () => apiGet("/computadoras/?solo_deposito=true"),
  obtenerEstadosOperativoPC: () => apiGet("/computadoras/catalogos/estados"),
};