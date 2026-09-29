# Panel Scouting FC

Abre `index.html` con doble clic (Chrome, Edge o Firefox). Necesita en la misma carpeta: `datos*.js`, `extra*.js`, `partidos*.js` (3 partes cada uno),
`equipos.js`, `portada.js`, `ligas.js`, `selecciones.js`, `goles.js`, `estadios.js`, `equipaciones.js`, `entrenadores.js`, `nombres.js` y las carpetas `carrera/`, `ligas/` y `sel/`.
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
- **Entrenadores** (clic en su nombre en el equipo o la liga): ficha personal, palmarés, trayectoria por clubes con puntos por partido,
  gráfico por temporada, etapas con edad media del once y sistema, últimos partidos, mayores victorias y temporada a temporada.
- **Ligas**: clasificación general, de local, de visitante, tras cada jornada y de cada temporada desde 2010/11, y predicción final
  (simulación de los partidos que faltan); historia (resumen, campeones desde el inicio, más veces campeón, podio, nuevos y descensos de cada año);
  partidos por jornada con goles, estadio, árbitro y asistencia; 37 rankings de jugadores y 29 de equipos (pulsa uno para verlo entero);
  equipos y estadios con foto, ocupación y entrenador; traspasos y, en LaLiga y LaLiga2, límite salarial (2019-20 a 2026-27).
  Los datos de cada liga están en `ligas/h_<id>.js` y se cargan al abrirla.
- **Selecciones**: ranking FIFA (211 selecciones) y 22 competiciones: Mundial, Eurocopa, Nations League A-D, Copa América, Copa Oro,
  Copa África, Copa Asia, Nations League CONCACAF, Finalissima, Juegos Olímpicos y clasificatorias. Cada competición: grupos, cuadro final
  de cada edición, historia (campeones desde 1930, más títulos), partidos, rankings de jugadores y de selecciones.
  Cada selección (`#s-<id>`): resumen (ranking, seleccionador, forma, próximos partidos y resultados, último once, destacados),
  convocatoria con nivel de cada jugador, partidos, palmarés y seleccionadores. Datos en `sel/s_<id>.js` e índice en `selecciones.js`.
  Fotos con la camiseta de la selección: FIFA (Mundial 2026) y UEFA (Nations League 2026-27); también en la ficha del jugador, junto a la del club.

Logos: `logos/index.html` compara las variantes A–F (claro/oscuro e icono). El panel usa la A.

Los datos se regeneran con `python actualizar_semanal.py` (carpeta FC; `--diario` solo portada, equipos y ligas)
o al recalcular la valoración (`run_all.py` → `build_web.py`).

Nivel (motor v1.5): mezcla por percentiles de rendimiento estadístico ajustado por liga (45 %), ELO partido a partido (25 %) y valor de
mercado corregido por edad (30 %). Edad calculada con la fecha de nacimiento y posición principal de la ficha de Transfermarkt
(los Excel de temporada no se modifican). "Rendimiento" en la ficha = solo estadísticas; la vista Oportunidades de Fichajes usa ese dato.

Ligas (36): las 26 anteriores más Primera y Segunda Federación, League One, League Two, National League, Ligue 2, Ligue 3, 3. Liga,
Regionalliga (5 grupos) y Serie C (3 grupos). Tercera Federación no entra: Transfermarkt no tiene sus partidos jugador a jugador.
Primera/Segunda Federación, Ligue 3, Regionalliga y Serie C no tienen estadísticas avanzadas en FotMob: su nivel sale de partidos,
minutos, goles, asistencias, resultados (ELO) y valor de mercado.
