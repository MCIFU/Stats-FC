# Panel Scouting FC

Abre `index.html` con doble clic (Chrome, Edge o Firefox). Necesita `datos.js` en la misma carpeta.
Con internet se ven además las fotos (Transfermarkt), la galería de Wikimedia Commons y las tipografías; sin internet funciona todo lo demás.

Pestañas: **Jugador** (foto, ficha, radar de estilo, ELO partido a partido, media con fotos y enlaces a goles, últimos partidos,
jugadores parecidos) · **Comparar** (dos jugadores lado a lado) · **Rankings** y **Promesas** (filtros por temporada, posición,
liga, edad, minutos y club; pulsa una cabecera para ordenar) · **Ligas**.

`datos.js` se regenera solo al recalcular la valoración (`run_all.py` → `build_web.py`). Fotos y enlaces:
`python auxiliares/media/descargar_media.py`.
