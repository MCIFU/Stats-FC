# Partido a partido (Transfermarkt) y estadísticas avanzadas (SofaScore) — 5 grandes ligas

Activa en el motor de valoración: **ELO, FORM, CONSISTENCY, OPPONENT_STRENGTH** (fuerza del rival) y las
**métricas avanzadas** (xG, tiros, pases, regates, entradas, duelos aéreos, paradas…).

## Requisitos
```
pip install pandas numpy openpyxl requests rapidfuzz unidecode playwright
python -m playwright install chromium      # solo si SofaScore devuelve 403 con requests
```
Salida a internet hacia: `www.transfermarkt.es`, `tmapi.transfermarkt.technology`, `understat.com`, `www.fotmob.com`, `data.fotmob.com` (y `www.sofascore.com`, `api.sofascore.com` si usas SofaScore).
En un entorno de Claude Code en la nube hay que añadir esos dominios en *Network access* del entorno; en tu PC no hace falta nada.

## 1. Partidos de Transfermarkt (≈10-15 min la primera vez; después usa la caché)
```
cd FC
python auxiliares/tmapi/descargar_partidos.py
```
- Lee las filas de LaLiga, Premier, Bundesliga, Serie A y Ligue 1 de los dos Excel.
- Plantillas por club (`/x/leistungsdaten/verein/{id}/plus/1?reldata=%26{temporada}`) → ID TM de cada fila (mismo cruce que `match.py`).
  Filas sin ID → `auxiliares/tmapi/sin_id_tm.csv`; se corrigen en `pidmap_manual.json` (`{"2025-26|DEFENSAS|123": "tmid"}`).
- `performance-game` de cada jugador + metadatos de competiciones y clubes. Mismas reglas de bloque que `LEEME_METODO_TM_API.md`.
  La selección se descarta (no cuenta para ELO/FORM).
- Salida: `Claude outputs/partidos_big5.csv` (una fila por jugador y partido: fecha, bloque, club, rival, local, GF, GC, Min, G, A, GC portero).
- Si al final avisa de que faltan rival/resultado: `python auxiliares/tmapi/descargar_partidos.py --inspect 8198`
  muestra una entrada cruda para ajustar `parse_game()`.

## 2. Estadísticas avanzadas: FotMob + Understat (principal) o SofaScore (alternativa)
```
python auxiliares/avanzadas/descargar_fotmob_understat.py     # ≈2 min, sin navegador
```
- FBref ya no sirve: desde enero de 2026 no publica estadísticas avanzadas (Opta le retiró el acceso).
- **Understat** (todos los jugadores con minutos): npxG, xA, tiros, pases clave, npG − npxG, npxG por tiro.
- **FotMob** (datos Opta; solo quien supera ~9 % de los minutos de liga, porteros ~50 %): % pase, % pase largo,
  regates y % regate, entradas ganadas y % entradas, intercepciones, despejes + bloqueos, recuperaciones,
  robos en tercio rival, % paradas, goles evitados, % tiros a puerta, nota FotMob.
- Cruce con el Excel: club por votación de nombres idénticos; jugador por nombre exacto, aproximado o
  apellido único en el equipo (este último solo si los minutos de liga coinciden). Los cruces aproximados
  con minutos incompatibles se descartan.
- Siguen UNKNOWN (ninguna de las dos fuentes los da): duelos aéreos, centros, pérdidas, errores, pases progresivos,
  conducciones, SCA, toques en el área, centros detenidos y salidas del portero.
- Salida: `Claude outputs/avanzadas_big5.csv`.

Alternativa (desde tu PC; SofaScore bloquea IPs de servidores en la nube):
```
python auxiliares/sofascore/descargar_avanzadas.py            # tabla de temporada
python auxiliares/sofascore/descargar_avanzadas.py --notas    # + nota SofaScore de cada partido de liga (≈30-40 min)
```
SofaScore añade duelos aéreos, centros, pérdidas y errores, y con `--notas` la nota por partido para FORM/CONSISTENCY.

## 3. Recalcular la valoración
```
cd "Claude outputs/motor_valoracion_v1/valoracion"
python run_all.py "../../../Temporada 2025-26.xlsx" "../../../Temporada 2026-27.xlsx" "../../Valoracion_FC_v1.1.xlsx" \
    --partidos ../../partidos_big5.csv --notas ../../notas_big5.csv --avanzadas ../../avanzadas_big5.csv
```
Cada opción es independiente: sin `--notas` la nota de partido se calcula con G+A y goles encajados; sin `--avanzadas`
las métricas avanzadas siguen UNKNOWN.

## Cómo se calcula (model.json → `elo`, `form`, `consistency`, `match_rating`)
- **Elo de equipos**: arranca en 1500 + 4 × (fuerza de su liga − 80); rivales sin liga conocida = fuerza 65.
  K = 20 × (ln(|dif. goles| + 1) + 1). En 26-27 arrastra los resultados de 25-26.
- **OPPONENT_STRENGTH**: cada rival vale fuerza de su liga + (su Elo antes del partido − Elo medio de su liga) / 10; media ponderada
  por minutos, encogida hacia la fuerza de la liga del jugador con pocos partidos (× n/(n+10)). Misma escala 0-100 que
  `competition_strength`. Entra en CONTEXT_SCORE con peso 0,3.
- **Nota de partido** (0-100): con SofaScore, 50 + 30 × (nota − 6,8). Sin ella, w × percentil((G+A)/90 en su posición)
  + (1 − w) × 100·e^(−goles encajados con él en el campo / 1,4); w = 0,85 DC, 0,8 MCO/extremos, 0,6 medios, 0,4 laterales, 0,25 centrales, 0 porteros.
- **ELO** del jugador: K = 24 × min(Min/90, 1) × importancia (Liga 1, Copa 0,8, Cont/FIFA 1,2); resultado esperado frente al Elo del rival;
  puntuación = 0,65 × nota + 0,35 × resultado. Escala: 70 + (Elo − 1500)/10.
- **FORM** = FORM_10: últimos 10 partidos (≤ 365 días), semivida 6 partidos, ponderado por minutos.
- **CONSISTENCY** = % de partidos buenos (nota de partido ≥ mediana de su posición), ponderado por minutos, centrado para que el
  jugador mediano de cada posición = 50 y encogido hacia 50 con pocos partidos (× n/(n+8)); mínimo 8 partidos. (La desviación típica premiaba a quien nunca destaca.)
