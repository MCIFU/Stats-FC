# Panel Scouting FC

Abre `index.html` con doble clic (Chrome, Edge o Firefox). Necesita `datos.js`, `extra.js` y `partidos.js` en la misma carpeta.
Con internet se ven además las fotos (Transfermarkt), la galería de Wikimedia Commons, los escudos y las tipografías.

Pestañas:
- **Jugador**: foto, ficha, radar de estilo, ELO partido a partido, minutos por competición, proyección a 3 años,
  valor de mercado y contrato, lesiones, media (fotos y enlaces a goles), últimos partidos y jugadores parecidos. Botón ☆ Seguir + notas.
- **Comparar**: dos jugadores lado a lado.
- **Rankings** y **Promesas**: filtros por temporada, posición, liga, edad, minutos y club.
- **Fichajes**: nivel real frente al esperado por su valor de mercado, con presupuesto y fin de contrato.
- **Once ideal**: 4-3-3 por liga, temporada, edad y presupuesto total.
- **Evolución**: quién sube y quién baja de 2025-26 a 2026-27.
- **Clubes**: plantilla, nivel por línea (punto débil), valor y contratos que acaban.
- **Ligas** y **Seguimiento** (tus jugadores y notas; se guardan en este navegador).

Los datos se regeneran con `python actualizar_semanal.py` (carpeta FC) o al recalcular la valoración (`run_all.py` → `build_web.py`).
