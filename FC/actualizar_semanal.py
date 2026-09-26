"""Actualización semanal completa: Excel de temporada, valoración, resumen y panel web.

Uso (desde la carpeta FC):  python actualizar_semanal.py [--sin-ligas] [--sin-valor]
                            python actualizar_semanal.py --diario   (solo partidos, noticias y clasificaciones; ~5 min)

Pasos:
 1. Ligas completas: añade a quien haya debutado (plantillas TM renovadas cada 27 días).
 2. Partidos TM (caché renovada si tiene > 5 días): escribe en los Excel solo las filas que crecen
    (partidos nuevos); las que bajan quedan en auxiliares/tmapi/diferencias_TM.csv para revisarlas.
    Exporta partidos_TM.csv.
 3. Orden y formato de los Excel.
 4. Estadísticas avanzadas (FotMob + Understat, descarga de nuevo).
 5. Contrato, valor de mercado y lesiones (renovados si tienen > 6 días), fotos/enlaces, trayectorias,
    equipos (FotMob, Wikidata, Wikipedia, noticias), portada (partidos y noticias) y ligas
    (clasificación, partidos con goles, estadísticas, traspasos, límite salarial de LaLiga).
 6. Valoración + resumen + panel web (run_all.py).
Tarda ~1-2 h (Transfermarkt limita la velocidad). Registro en auxiliares/actualizacion_semanal.log.
"""
import argparse
import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

FC = Path(__file__).resolve().parent
AUX = FC / "auxiliares"
VAL = FC / "Claude outputs" / "motor_valoracion_v1" / "valoracion"
LOG = AUX / "actualizacion_semanal.log"
LIGAS = ("Eredivisie,Süper Lig,Liga Belga,Saudi Pro,Liga MX,Scottish Premiership,Liga Argentina,Brasileirão,Ekstraklasa,MLS,Portugal,"
         "Championship,LaLiga2,Serie B,2. Bundesliga,Super League 1,Superliga,Super League,Bundesliga Austria,J1 League,K League 1")


def run(args, cwd=FC, env=None):
    t0 = dt.datetime.now()
    print(f"\n=== {' '.join(str(a) for a in args)}", flush=True)
    with open(LOG, "a", encoding="utf-8") as log:
        log.write(f"\n=== {t0:%d/%m/%Y %H:%M} {' '.join(str(a) for a in args)}\n")
        log.flush()
        r = subprocess.run([sys.executable, *map(str, args)], cwd=cwd, env={**os.environ, **(env or {})},
                           stdout=log, stderr=subprocess.STDOUT)
        log.write(f"--- código {r.returncode} en {(dt.datetime.now() - t0).seconds // 60} min\n")
    if r.returncode:
        sys.exit(f"Falló: {' '.join(map(str, args))} (ver {LOG})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sin-ligas", action="store_true", help="no busca debutantes (más rápido)")
    ap.add_argument("--sin-valor", action="store_true", help="no renueva contrato/valor/lesiones")
    ap.add_argument("--diario", action="store_true", help="solo portada, equipos y ligas (clasificación, goles, traspasos)")
    a = ap.parse_args()
    if a.diario:
        run([AUX / "portada/descargar_portada.py"])
        run([AUX / "equipos/descargar_equipos.py", "--refrescar", "0.5"])
        run([AUX / "ligas/descargar_ligas.py", "--refrescar", "0.5"])
        print(f"\nListo (diario). Registro: {LOG}")
        return
    env = {"TM_REFRESH_DAYS": "perf/=5,squads/=27,ligas/=27"}
    if not a.sin_ligas:
        run([AUX / "tmapi/ampliar_ligas.py", "--ligas", LIGAS, "--escribir"], env=env)
    run([AUX / "tmapi/actualizar_excels.py", "--escribir", "--crecimiento", "--partidos", "todas"], env=env)
    run([AUX / "estilo/estilo_temporadas.py"])
    run([AUX / "avanzadas/descargar_fotmob_understat.py", "--refresh"])
    if not a.sin_valor:
        run([AUX / "tmapi/descargar_valor_lesiones.py", "--refrescar", "6"])
    run([AUX / "media/descargar_media.py"])
    run([AUX / "tmapi/descargar_carrera.py", "--refrescar", "6"])
    run([AUX / "equipos/descargar_equipos.py", "--refrescar", "1"])
    run([AUX / "portada/descargar_portada.py"])
    run([AUX / "ligas/descargar_ligas.py", "--refrescar", "0.5"])
    run(["run_all.py", "../../../Temporada 2025-26.xlsx", "../../../Temporada 2026-27.xlsx", "../../Valoracion_FC_v1.2.xlsx",
         "--partidos", "../../partidos_TM.csv", "--avanzadas", "../../avanzadas.csv"], cwd=VAL)
    print(f"\nListo. Registro: {LOG}")


if __name__ == "__main__":
    main()
