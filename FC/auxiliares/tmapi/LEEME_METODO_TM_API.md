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
