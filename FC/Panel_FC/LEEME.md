# Panel Scouting FC

Abre `index.html` con doble clic (Chrome, Edge o Firefox). Necesita en la misma carpeta: `datos.js`, `extra.js`, `partidos.js`,
`equipos.js`, `portada.js`, `ligas.js`, `goles.js`, `estadios.js`, `equipaciones.js`, `nombres.js` y la carpeta `carrera/`.
Con internet se ven además las fotos recortadas de los jugadores (FotMob), escudos, logos de liga, la galería de Wikimedia Commons y las tipografías.

Todo nombre de jugador, equipo o liga es un enlace: clic normal lo abre, clic con la rueda (botón central) lo abre en otra pestaña.
Al pasar el ratón por encima de una cabecera (NIVEL, ELO, SCOUT, FORMA…) sale qué significa.

Pestañas:
- **Inicio**: noticias, partidos por competición (pulsa el resultado para ver goles y asistencias), rachas, lesionados, cumpleaños, contratos.
- **Comparar**: dos jugadores lado a lado. Hasta 20 comparaciones guardadas (en este navegador) y botón para empezar de cero.
- **Rankings** y **Promesas**: podio de los tres primeros y tabla con nota en color; filtros por temporada, posición, liga, edad, minutos y club.
- **Fichajes**: últimos movimientos de las cinco grandes ligas; por liga o equipo, altas y bajas (cesiones marcadas), gasto, ingresos,
  balance y, en LaLiga y LaLiga2, el límite salarial. Segunda vista: oportunidades (nivel frente a precio).
- **Once ideal**, **Evolución**, **Seguimiento** (tus jugadores y notas).
- **Ficha de jugador**: fecha y lugar de nacimiento, altura, pie y posición exacta (Transfermarkt); nivel, rendimiento, ELO, forma…;
  trayectoria con línea de clubes (cesiones marcadas), minutos y goles+asistencias por temporada, selección, traspasos y tabla completa.
- **Equipos**: clasificación con los últimos 5 (V/E/D; al pasar el ratón se ve el partido y se resaltan los dos equipos), partidos,
  alineación con las caras recortadas, forma de jugar (8 escalas frente al resto de su liga), estadísticas, plantilla, palmarés con un
  icono por título, historia, efemérides, entrenadores, foto del estadio y equipaciones actuales e históricas (dibujos de Wikipedia).
- **Ligas**: cada liga tiene su página con clasificación, partidos por jornada con goles, goleadores/asistentes y otras listas,
  equipos y estadios con foto (asistencia media), estadísticas de equipo, traspasos y, en LaLiga y LaLiga2, límite salarial por temporada (2019-20 a 2026-27).

Logos: `logos/index.html` compara las variantes A–F (claro/oscuro e icono). El panel usa la A.

Los datos se regeneran con `python actualizar_semanal.py` (carpeta FC; `--diario` solo portada, equipos y ligas)
o al recalcular la valoración (`run_all.py` → `build_web.py`).

Nivel (motor v1.4): mezcla por percentiles de rendimiento estadístico ajustado por liga (45 %), ELO partido a partido (25 %) y valor de
mercado corregido por edad (30 %). Edad calculada con la fecha de nacimiento y posición principal de la ficha de Transfermarkt
(los Excel de temporada no se modifican). "Rendimiento" en la ficha = solo estadísticas; la vista Oportunidades de Fichajes usa ese dato.
