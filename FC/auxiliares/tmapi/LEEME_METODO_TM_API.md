# Actualizar los Excel con Transfermarkt partido a partido (25/09/2026)

Así se recalcularon ambos Excel. Una actualización nueva tarda unos 15-20 minutos.

## 1. Descarga (en un navegador abierto en transfermarkt.es, desde la consola JS)
- Plantillas por club y temporada: `/x/leistungsdaten/verein/{clubId}/plus/1?reldata=%26{temporadaTM}` → ID TM, nombre, posición, edad y PJ.
  - Temporada TM: 2025 = 25/26 y 2026 = 26/27. En ligas de año natural (MLS, BRA, ARG), la temporada TM 2024 corresponde al año 2025 y la 2025 al año 2026.
- Rendimiento por partido de cada jugador: `https://tmapi.transfermarkt.technology/player/{playerId}/performance-game` (CORS abierto, ~40 jugadores/s con 6 en paralelo).
- Metadatos: `tmapi.../competitions?ids[]=...` (typeId de cada competición) y `tmapi.../clubs?ids[]=...` (isNationalTeam, mainClubId).

## 2. Reglas de agregación (aggPlayer / process.py)
- Corte: partidos con saque inicial ≤ 20:55 UTC del día de corte (terminados antes de las 00:50 de Madrid) y no en directo.
- Partido jugado = minutos > 0 o participationState = "played".
- Temporada: clubes europeos/MX → seasonId TM; clubes de año natural (MLS/BRA/ARG) → año de la fecha; selección → ago-jul por fecha.
- El Mundial de Clubes 2025 (KLUB, seasonId 2024) se excluye.
- Qué va en cada bloque según el typeId TM:
  - LIGA: tipos 1-6 y 12.
  - COPA: tipos 8, 9, 14, 21, 22 y 24.
  - CONT: tipos 10 y 13 (sin FIC1/CWCQ).
  - FIFA: FIC1 y KLUB.
  - SEL: solo si el club es una selección absoluta (id == mainClubId).
  - Excluidos: filiales y juveniles (mainClubId != id) y los tipos 7, 15, 16, 17, 18, 20 y 23.
- Porteros: GC = opponentGoalsOnThePitch; CS = partido jugado con club.opponentGoalsTotal == 0 (mismo criterio que la web de TM).
- Las filas doble-club se filtran por el club de la fila.

## 3. Escritura (Python/openpyxl)
Se ejecutan en este orden: match.py (fila → ID TM), finalize.py, writer.py (detalle, fórmulas TOT regeneradas, orden por G+A), ranking.py y texts.py.

## 4. Comprobar / actualizar los Excel desde Python (sin navegador) — `actualizar_excels.py`
```
cd FC
python auxiliares/tmapi/actualizar_excels.py                    # descarga + informe diferencias_TM.csv (no escribe)
python auxiliares/tmapi/actualizar_excels.py --escribir --filas "2026-27|DELANTEROS|7,..."   # escribe solo las revisadas
```
- Mismas reglas que arriba; recalcula TODAS las filas (clubes de clubmap.json + nombres TM exactos) y compara celda a celda.
- Temporada de cada partido de club: liga de año natural (MLS, Brasil, Argentina, Japón y cualquier liga cuya temporada TM
  actual va un año por detrás de LaLiga, p.ej. Paraguay, Chile, Suecia) → año de la fecha; resto → seasonId TM.
  Leagues Cup / Campeones Cup / Concachampions en clubes mexicanos → temporada julio-junio por fecha.
- SEL: solo en la fila del continente del último club ANTES del 1 de agosto; si esa fila no existe, en ninguna.
- Solo cambia PJ/Min/G/A (GC/CS) y CONT.; filas, orden, Club/Liga/NAC/POS/Edad/Valor no se tocan. Rehace RANKING_TOTAL/PORTEROS.
- 25/09/2026: 10.881 filas idénticas a TM; 4 corregidas en 26-27 (Camilo Durán y Iron Gomis tenían sumados en 26-27 sus
  partidos de ene-may 2026 en la liga azerí, que es de la temporada 25-26; Antonetti y De Rosario, Puerto Rico–Guyana del 24/09).
  7 diferencias sin aplicar por cruce de ID/club dudoso: ver diferencias_TM.csv.
