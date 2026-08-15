/**
 * js/salas.js
 * Componente Alpine.js para salas.html: vista detallada de una sala,
 * gestión de sus puestos (alta, edición de anclaje/observaciones/
 * numeración, borrado).
 *
 * Este es el CRUD "estructural" (Módulo I) -- para el detalle
 * operativo de un puesto puntual (hardware, red, auditorías) se usa
 * puesto-detalle.html.
 */

function salasApp() {
  return {
    salaId: null,
    sala: null,
    puestos: [],
    estadosAnclaje: [],

    cargando: true,
    error: null,

    mostrarFormNuevoPuesto: false,
    guardandoNuevoPuesto: false,
    mensajeNuevoPuesto: null,
    formNuevoPuesto: {
      numero_puesto: "",
      estado_anclaje_id: "",
      observaciones: "",
    },

    // id del puesto que se está editando (null = ninguno)
    editandoPuestoId: null,
    guardandoEdicion: false,
    mensajeEdicion: null,
    formEdicion: {
      numero_puesto: "",
      estado_anclaje_id: "",
      observaciones: "",
    },

    mensajeBorrado: null,

    async init() {
      const parametros = new URLSearchParams(window.location.search);
      this.salaId = parametros.get("id");

      if (!this.salaId) {
        this.error = "No se especificó ninguna sala (falta ?id= en la URL).";
        this.cargando = false;
        return;
      }

      await this.cargarTodo();
    },

    async cargarTodo() {
      try {
        this.error = null;
        const [sala, puestos, estadosAnclaje] = await Promise.all([
          api.obtenerSala(this.salaId),
          api.listarPuestosDeSala(this.salaId),
          api.obtenerEstadosAnclaje(),
        ]);
        this.sala = sala;
        this.puestos = puestos;
        this.estadosAnclaje = estadosAnclaje;
      } catch (err) {
        this.error = err.message;
      } finally {
        this.cargando = false;
      }
    },

    // ============================================================
    // Alta de puesto nuevo
    // ============================================================

    abrirFormNuevoPuesto() {
      // Sugerir el próximo número disponible, para que el docente no
      // tenga que ir a buscar cuál es el último.
      const maxNumero = this.puestos.reduce((max, p) => Math.max(max, p.numero_puesto), 0);
      this.formNuevoPuesto = {
        numero_puesto: maxNumero + 1,
        estado_anclaje_id: "",
        observaciones: "",
      };
      this.mostrarFormNuevoPuesto = true;
    },

    cerrarFormNuevoPuesto() {
      this.mostrarFormNuevoPuesto = false;
    },

    async guardarNuevoPuesto() {
      if (!this.formNuevoPuesto.numero_puesto || !this.formNuevoPuesto.estado_anclaje_id) {
        this.mensajeNuevoPuesto = "Error: completá el número de puesto y el estado de anclaje.";
        return;
      }

      this.guardandoNuevoPuesto = true;
      this.mensajeNuevoPuesto = null;

      try {
        const nuevoPuesto = await api.crearPuesto(this.salaId, {
          numero_puesto: Number(this.formNuevoPuesto.numero_puesto),
          estado_anclaje_id: Number(this.formNuevoPuesto.estado_anclaje_id),
          observaciones: this.formNuevoPuesto.observaciones || null,
        });
        this.puestos.push(nuevoPuesto);
        this.puestos.sort((a, b) => a.numero_puesto - b.numero_puesto);
        this.mostrarFormNuevoPuesto = false;
      } catch (err) {
        this.mensajeNuevoPuesto = `Error: ${err.message}`;
      } finally {
        this.guardandoNuevoPuesto = false;
        setTimeout(() => (this.mensajeNuevoPuesto = null), 5000);
      }
    },

    // ============================================================
    // Edición de puesto existente (anclaje / observaciones / numeración)
    // ============================================================

    empezarEdicion(puesto) {
      this.editandoPuestoId = puesto.id;
      this.formEdicion = {
        numero_puesto: puesto.numero_puesto,
        estado_anclaje_id: puesto.estado_anclaje_id,
        observaciones: puesto.observaciones || "",
      };
      this.mensajeEdicion = null;
    },

    cancelarEdicion() {
      this.editandoPuestoId = null;
    },

    async guardarEdicion(puestoId) {
      this.guardandoEdicion = true;
      this.mensajeEdicion = null;

      try {
        const actualizado = await api.actualizarPuesto(puestoId, {
          numero_puesto: Number(this.formEdicion.numero_puesto),
          estado_anclaje_id: Number(this.formEdicion.estado_anclaje_id),
          observaciones: this.formEdicion.observaciones || null,
        });

        const indice = this.puestos.findIndex((p) => p.id === puestoId);
        if (indice !== -1) this.puestos[indice] = actualizado;
        this.puestos.sort((a, b) => a.numero_puesto - b.numero_puesto);

        this.editandoPuestoId = null;
      } catch (err) {
        this.mensajeEdicion = `Error: ${err.message}`;
      } finally {
        this.guardandoEdicion = false;
      }
    },

    // ============================================================
    // Borrado de puesto
    // ============================================================

    async borrarPuesto(puesto) {
      const confirmado = confirm(
        `¿Eliminar el Puesto ${puesto.numero_puesto}? Esta acción no se puede deshacer.`
      );
      if (!confirmado) return;

      this.mensajeBorrado = null;
      try {
        await api.eliminarPuesto(puesto.id);
        this.puestos = this.puestos.filter((p) => p.id !== puesto.id);
      } catch (err) {
        this.mensajeBorrado = `Error al eliminar Puesto ${puesto.numero_puesto}: ${err.message}`;
        setTimeout(() => (this.mensajeBorrado = null), 6000);
      }
    },

    // ============================================================
    // Helpers de presentación
    // ============================================================

    claseBadgeEstado(estado) {
      const clases = {
        Bien: "bg-green-100 text-green-700",
        Flojo: "bg-yellow-100 text-yellow-700",
        Incompleto: "bg-yellow-100 text-yellow-700",
        Roto: "bg-red-100 text-red-700",
        Faltante: "bg-red-100 text-red-700",
      };
      return clases[estado] || "bg-gray-100 text-gray-600";
    },
  };
}