/**
 * js/dashboard.js
 * Componente Alpine.js para el Dashboard Principal (index.html).
 */

function dashboardApp() {
  return {
    salas: [],
    cargando: true,
    error: null,
    ultimaActualizacion: null,

    async init() {
      await this.cargarDashboard();
      // Refresco automático cada 30s para que el semáforo se mantenga al día
      // sin que el docente tenga que recargar la página a mano.
      setInterval(() => this.cargarDashboard(), 30000);
    },

    async cargarDashboard() {
      try {
        this.error = null;
        this.salas = await api.obtenerDashboard();
        this.ultimaActualizacion = new Date().toLocaleTimeString("es-AR");
      } catch (err) {
        this.error = err.message;
      } finally {
        this.cargando = false;
      }
    },

    // Clases de Tailwind según el color calculado por el backend.
    claseColor(color) {
      const clases = {
        verde: "bg-green-500 hover:bg-green-600",
        amarillo: "bg-yellow-400 hover:bg-yellow-500",
        rojo: "bg-red-500 hover:bg-red-600",
        vacio: "bg-gray-200 hover:bg-gray-300 text-gray-500",
      };
      return clases[color] || clases.vacio;
    },

    // Emoji que acompaña el número dentro del cuadradito.
    emojiColor(color) {
      const emojis = {
        verde: "🟢",
        amarillo: "🟡",
        rojo: "🔴",
        vacio: "⚪",
      };
      return emojis[color] || "⚪";
    },

    // Resumen rápido para el encabezado de cada sala (ej: "2 rojo, 1 amarillo")
    resumenSala(puestos) {
      const contador = { rojo: 0, amarillo: 0, verde: 0, vacio: 0 };
      puestos.forEach((p) => contador[p.color]++);
      const partes = [];
      if (contador.rojo) partes.push(`${contador.rojo} 🔴`);
      if (contador.amarillo) partes.push(`${contador.amarillo} 🟡`);
      if (contador.verde) partes.push(`${contador.verde} 🟢`);
      if (contador.vacio) partes.push(`${contador.vacio} ⚪`);
      return partes.join(" · ") || "Sin puestos";
    },
  };
}