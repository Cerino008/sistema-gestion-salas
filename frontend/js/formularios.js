/**
 * js/formularios.js
 * Lógica de carga de datos y checklists: formulario de Auditoría de
 * Software (Módulo III) y formulario de Historial de Soporte (Módulo V).
 *
 * Se usa como "mixin": puesto-detalle.js hace
 *     return { ...formulariosMixin(), ...resto de la pantalla }
 * para que ambos formularios compartan el mismo componente Alpine que
 * ya tiene cargado el puesto, la computadora y el dashboard.
 */

function formulariosMixin() {
  return {
    // ============================================================
    // FORMULARIO: Nueva Auditoría de Software
    // ============================================================

    catalogoSoftware: [],
    mostrarFormAuditoria: false,
    guardandoAuditoria: false,
    mensajeAuditoria: null,

    formAuditoria: {
      deep_freeze: true,
      malware_detectado: "",
      gravedad_malware: "",
      software_no_autorizado: "",
      usuario_registro: "",
      checklist: {}, // { software_id: true/false }, se completa al abrir el form
    },

    async abrirFormAuditoria() {
      this.mostrarFormAuditoria = true;
      if (this.catalogoSoftware.length === 0) {
        this.catalogoSoftware = await apiGet("/software-catalogo/");
      }
      // Cada apertura arranca con el checklist en blanco (todo sin marcar):
      // el docente tilda lo que SÍ está instalado, no al revés.
      const checklistVacio = {};
      this.catalogoSoftware.forEach((sw) => (checklistVacio[sw.id] = false));
      this.formAuditoria.checklist = checklistVacio;
    },

    cerrarFormAuditoria() {
      this.mostrarFormAuditoria = false;
    },

    async guardarAuditoria() {
      this.guardandoAuditoria = true;
      this.mensajeAuditoria = null;

      const checklist = Object.entries(this.formAuditoria.checklist).map(
        ([software_id, instalado]) => ({ software_id: Number(software_id), instalado })
      );

      try {
        const nuevaAuditoria = await apiPost("/auditorias/", {
          computadora_id: this.dashboard.computadora_id,
          deep_freeze: this.formAuditoria.deep_freeze,
          malware_detectado: this.formAuditoria.malware_detectado || null,
          gravedad_malware: this.formAuditoria.malware_detectado
            ? this.formAuditoria.gravedad_malware || null
            : null,
          software_no_autorizado: this.formAuditoria.software_no_autorizado || null,
          usuario_registro: this.formAuditoria.usuario_registro || null,
          checklist,
        });

        this.auditoria = nuevaAuditoria; // reemplaza la vista de "última auditoría"
        this.mensajeAuditoria = "Auditoría guardada correctamente.";
        this.mostrarFormAuditoria = false;

        // Las alertas nuevas pueden haber cambiado el semáforo del puesto.
        this.dashboard = await api.obtenerPuestoDashboard(this.puestoId);

        // Limpiamos los campos de texto para la próxima carga (el nombre
        // del docente lo dejamos puesto, suele ser la misma persona).
        this.formAuditoria.malware_detectado = "";
        this.formAuditoria.gravedad_malware = "";
        this.formAuditoria.software_no_autorizado = "";
      } catch (err) {
        this.mensajeAuditoria = `Error: ${err.message}`;
      } finally {
        this.guardandoAuditoria = false;
        setTimeout(() => (this.mensajeAuditoria = null), 5000);
      }
    },

    // ============================================================
    // FORMULARIO: Registrar Mantenimiento / Soporte Técnico
    // ============================================================

    tiposComponente: [],
    mostrarFormSoporte: false,
    guardandoSoporte: false,
    mensajeSoporte: null,

    formSoporte: {
      tipo_componente_id: "",
      componente_retirado_detalle: "",
      componente_nuevo_detalle: "",
      nro_serie_nuevo: "",
      observaciones: "",
      usuario_registro: "",
    },

    async abrirFormSoporte() {
      this.mostrarFormSoporte = true;
      if (this.tiposComponente.length === 0) {
        this.tiposComponente = await apiGet("/historial-soporte/catalogos/tipos-componente");
      }
    },

    cerrarFormSoporte() {
      this.mostrarFormSoporte = false;
    },

    async guardarSoporte() {
      if (!this.formSoporte.tipo_componente_id) {
        this.mensajeSoporte = "Error: elegí un tipo de componente antes de guardar.";
        return;
      }

      this.guardandoSoporte = true;
      this.mensajeSoporte = null;

      try {
        const nuevoRegistro = await apiPost("/historial-soporte/", {
          computadora_id: this.dashboard.computadora_id,
          tipo_componente_id: Number(this.formSoporte.tipo_componente_id),
          componente_retirado_detalle: this.formSoporte.componente_retirado_detalle || null,
          componente_nuevo_detalle: this.formSoporte.componente_nuevo_detalle || null,
          nro_serie_nuevo: this.formSoporte.nro_serie_nuevo || null,
          observaciones: this.formSoporte.observaciones || null,
          usuario_registro: this.formSoporte.usuario_registro || null,
        });

        // Lo agregamos arriba de la lista sin recargar todo -> el docente
        // ve al toque que quedó guardado.
        this.historialSoporte.unshift(nuevoRegistro);

        this.mensajeSoporte =
          "Registro guardado. Recordá: este historial es inalterable, si algo salió mal cargá un registro nuevo aclarándolo.";
        this.mostrarFormSoporte = false;

        const usuarioAnterior = this.formSoporte.usuario_registro;
        this.formSoporte = {
          tipo_componente_id: "",
          componente_retirado_detalle: "",
          componente_nuevo_detalle: "",
          nro_serie_nuevo: "",
          observaciones: "",
          usuario_registro: usuarioAnterior, // suele ser el mismo técnico
        };
      } catch (err) {
        this.mensajeSoporte = `Error: ${err.message}`;
      } finally {
        this.guardandoSoporte = false;
        setTimeout(() => (this.mensajeSoporte = null), 7000);
      }
    },

    // ============================================================
    // FORMULARIO: Dar de alta una PC nueva en este puesto
    // (solo tiene sentido si el puesto está vacío)
    // ============================================================

    estadosOperativoPC: [],
    mostrarFormAltaPC: false,
    guardandoAltaPC: false,
    mensajeAltaPC: null,

    formAltaPC: {
      procesador: "",
      ram: "",
      almacenamiento: "",
      tarjeta_grafica: "",
      sistema_operativo: "",
      estado_operativo_id: "",
      numero_serie: "",
      usuario_registro: "",
    },

    async abrirFormAltaPC() {
      this.mostrarFormAltaPC = true;
      if (this.estadosOperativoPC.length === 0) {
        this.estadosOperativoPC = await api.obtenerEstadosOperativoPC();
      }
    },

    cerrarFormAltaPC() {
      this.mostrarFormAltaPC = false;
    },

    async guardarAltaPC() {
      if (!this.formAltaPC.estado_operativo_id) {
        this.mensajeAltaPC = "Error: elegí el estado operativo antes de guardar.";
        return;
      }

      this.guardandoAltaPC = true;
      this.mensajeAltaPC = null;

      try {
        await api.crearComputadora({
          puesto_id: this.puesto.id,
          procesador: this.formAltaPC.procesador || null,
          ram: this.formAltaPC.ram || null,
          almacenamiento: this.formAltaPC.almacenamiento || null,
          tarjeta_grafica: this.formAltaPC.tarjeta_grafica || null,
          sistema_operativo: this.formAltaPC.sistema_operativo || null,
          estado_operativo_id: Number(this.formAltaPC.estado_operativo_id),
          numero_serie: this.formAltaPC.numero_serie || null,
          usuario_registro: this.formAltaPC.usuario_registro || null,
        });

        this.mensajeAltaPC = "PC dada de alta en este puesto.";
        this.mostrarFormAltaPC = false;
        await this.cargarTodo(); // refresca dashboard + computadora + todo lo que dependía de "vacío"
      } catch (err) {
        this.mensajeAltaPC = `Error: ${err.message}`;
      } finally {
        this.guardandoAltaPC = false;
        setTimeout(() => (this.mensajeAltaPC = null), 5000);
      }
    },

    // ============================================================
    // FORMULARIO: Asignar a este puesto una PC que ya existe
    // (viene del depósito -- puesto_id era NULL)
    // ============================================================

    computadorasEnDeposito: [],
    mostrarFormAsignarExistente: false,
    guardandoAsignarExistente: false,
    mensajeAsignarExistente: null,

    formAsignarExistente: {
      computadora_id: "",
      usuario_registro: "",
    },

    async abrirFormAsignarExistente() {
      this.mostrarFormAsignarExistente = true;
      this.computadorasEnDeposito = await api.listarComputadorasEnDeposito();
    },

    cerrarFormAsignarExistente() {
      this.mostrarFormAsignarExistente = false;
    },

    async guardarAsignarExistente() {
      if (!this.formAsignarExistente.computadora_id) {
        this.mensajeAsignarExistente = "Error: elegí qué PC del depósito asignar.";
        return;
      }

      this.guardandoAsignarExistente = true;
      this.mensajeAsignarExistente = null;

      try {
        await api.moverComputadora(this.formAsignarExistente.computadora_id, {
          puesto_id_nuevo: this.puesto.id,
          usuario_registro: this.formAsignarExistente.usuario_registro || null,
        });

        this.mensajeAsignarExistente = "PC asignada a este puesto.";
        this.mostrarFormAsignarExistente = false;
        await this.cargarTodo();
      } catch (err) {
        this.mensajeAsignarExistente = `Error: ${err.message}`;
      } finally {
        this.guardandoAsignarExistente = false;
        setTimeout(() => (this.mensajeAsignarExistente = null), 5000);
      }
    },

    // ============================================================
    // FORMULARIO: Mover la PC de este puesto a otro (o a depósito)
    // (solo tiene sentido si el puesto está ocupado)
    // ============================================================

    puestosDisponibles: [],
    mostrarFormMover: false,
    guardandoMover: false,
    mensajeMover: null,

    formMover: {
      destino: "", // id de puesto como string, o "deposito"
      usuario_registro: "",
    },

    async abrirFormMover() {
      this.mostrarFormMover = true;
      const salasCompletas = await api.obtenerDashboard();
      this.puestosDisponibles = [];
      salasCompletas.forEach((sala) => {
        sala.puestos.forEach((p) => {
          if (!p.tiene_pc && p.id !== this.puesto.id) {
            this.puestosDisponibles.push({
              id: p.id,
              etiqueta: `${sala.nombre} - Puesto ${p.numero_puesto}`,
            });
          }
        });
      });
    },

    cerrarFormMover() {
      this.mostrarFormMover = false;
    },

    async guardarMover() {
      if (!this.formMover.destino) {
        this.mensajeMover = "Error: elegí un destino (puesto o depósito).";
        return;
      }

      this.guardandoMover = true;
      this.mensajeMover = null;

      const destino = this.formMover.destino === "deposito" ? null : Number(this.formMover.destino);

      try {
        await api.moverComputadora(this.dashboard.computadora_id, {
          puesto_id_nuevo: destino,
          usuario_registro: this.formMover.usuario_registro || null,
        });

        this.mensajeMover = "PC movida correctamente.";
        this.mostrarFormMover = false;
        await this.cargarTodo(); // la PC ya no está acá -> recargamos todo el puesto
      } catch (err) {
        this.mensajeMover = `Error: ${err.message}`;
      } finally {
        this.guardandoMover = false;
        setTimeout(() => (this.mensajeMover = null), 5000);
      }
    },
  };
}