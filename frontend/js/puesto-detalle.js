/**
 * js/puesto-detalle.js
 * Componente Alpine.js para puesto-detalle.html.
 *
 * Toma el ?id=X de la URL y junta en una sola pantalla la "materia
 * prima" de los 4 módulos: infraestructura (I), hardware (II),
 * auditoría de software (III) y red (IV).
 */

function puestoDetalleApp() {
  return {
    ...formulariosMixin(),

    puestoId: null,

    cargando: true,
    error: null,
    guardandoCableado: false,
    mensajeGuardado: null,

    puesto: null, // datos crudos de infraestructura (salas.py)
    dashboard: null, // color + motivos (dashboard.py)
    computadora: null, // specs de hardware (inventario.py)
    perifericos: [],
    tiposPeriferico: {}, // { id: nombre }
    estadosPeriferico: {}, // { id: nombre }
    auditoria: null, // última auditoría de software (o null si no tiene)
    historialSoporte: [],
    historialUbicaciones: [],

    // Formulario de reporte de falla de cableado
    formCableado: {
      estado_jack: "Bien",
      estado_cable: "Bien",
    },

    async init() {
      const parametros = new URLSearchParams(window.location.search);
      this.puestoId = parametros.get("id");

      if (!this.puestoId) {
        this.error = "No se especificó ningún puesto (falta ?id= en la URL).";
        this.cargando = false;
        return;
      }

      await this.cargarTodo();
    },

    async cargarTodo() {
      try {
        this.error = null;

        // Datos que no dependen de si hay PC o no
        const [puesto, dashboard, perifericos, tipos, estados] = await Promise.all([
          api.obtenerPuesto(this.puestoId),
          api.obtenerPuestoDashboard(this.puestoId),
          api.obtenerPerifericosPorPuesto(this.puestoId),
          api.obtenerTiposPeriferico(),
          api.obtenerEstadosPeriferico(),
        ]);

        this.puesto = puesto;
        this.dashboard = dashboard;
        this.perifericos = perifericos;
        this.formCableado.estado_jack = puesto.estado_jack;
        this.formCableado.estado_cable = puesto.estado_cable;

        // Mapas id -> nombre para pintar los periféricos sin otro round-trip
        this.tiposPeriferico = Object.fromEntries(tipos.map((t) => [t.id, t.nombre]));
        this.estadosPeriferico = Object.fromEntries(estados.map((e) => [e.id, e.nombre]));

        // Si hay una PC en el puesto, traemos todo lo que depende de ella
        if (dashboard.tiene_pc) {
          const [computadora, auditoria, historialSoporte, historialUbicaciones] =
            await Promise.all([
              api.obtenerComputadora(dashboard.computadora_id),
              api.obtenerUltimaAuditoria(dashboard.computadora_id),
              api.obtenerHistorialSoporte(dashboard.computadora_id),
              api.obtenerHistorialUbicaciones(dashboard.computadora_id),
            ]);
          this.computadora = computadora;
          this.auditoria = auditoria;
          this.historialSoporte = historialSoporte;
          this.historialUbicaciones = historialUbicaciones;
        }
      } catch (err) {
        this.error = err.message;
      } finally {
        this.cargando = false;
      }
    },

    async guardarEstadoCableado() {
      this.guardandoCableado = true;
      this.mensajeGuardado = null;
      try {
        const actualizado = await api.actualizarEstadoCableado(this.puestoId, this.formCableado);
        this.puesto.estado_jack = actualizado.estado_jack;
        this.puesto.estado_cable = actualizado.estado_cable;
        // El color del semáforo puede haber cambiado -> recalculamos
        this.dashboard = await api.obtenerPuestoDashboard(this.puestoId);
        this.mensajeGuardado = "Estado de cableado actualizado.";
      } catch (err) {
        this.mensajeGuardado = `Error: ${err.message}`;
      } finally {
        this.guardandoCableado = false;
        setTimeout(() => (this.mensajeGuardado = null), 4000);
      }
    },

    nombreTipoPeriferico(id) {
      return this.tiposPeriferico[id] || `Tipo #${id}`;
    },

    nombreEstadoPeriferico(id) {
      return this.estadosPeriferico[id] || `Estado #${id}`;
    },

    claseColorTexto(color) {
      const clases = {
        verde: "text-green-600",
        amarillo: "text-yellow-600",
        rojo: "text-red-600",
        vacio: "text-gray-400",
      };
      return clases[color] || clases.vacio;
    },

    claseBadgeEstado(estado) {
      // Para estado_jack / estado_cable / estado de periférico
      const clases = {
        Bien: "bg-green-100 text-green-700",
        Excelente: "bg-green-100 text-green-700",
        "Con fallas": "bg-yellow-100 text-yellow-700",
        "Falla Parcial": "bg-yellow-100 text-yellow-700",
        Flojo: "bg-yellow-100 text-yellow-700",
        Incompleto: "bg-yellow-100 text-yellow-700",
        Roto: "bg-red-100 text-red-700",
        Faltante: "bg-red-100 text-red-700",
      };
      return clases[estado] || "bg-gray-100 text-gray-600";
    },

    formatearFecha(fechaIso) {
      if (!fechaIso) return "-";
      return new Date(fechaIso).toLocaleString("es-AR");
    },
  };
}