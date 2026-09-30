"""Estado entre ejecuciones de GitHub Actions (datos del panel, Excel de temporada y entradas del motor).

  python .github/scripts/estado.py guardar     copia los archivos de datos a _estado/
  python .github/scripts/estado.py restaurar   los devuelve a su sitio SOLO si son más recientes que los del repositorio
                                               (fecha "generated" de Panel_FC/datos.js), para no pisar lo que se suba a mano.
El código del panel (index.html, sw.js, logos…) nunca se guarda: siempre manda el del repositorio.
"""
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EST = ROOT / "_estado"
PANEL = "FC/Panel_FC"
FILES = ["FC/Temporada 2025-26.xlsx", "FC/Temporada 2026-27.xlsx", "FC/Claude outputs/partidos_TM.csv.gz", "FC/Claude outputs/avanzadas.csv"]
PANEL_DATA = ["datos*.js", "extra*.js", "partidos*.js", "equipos.js", "estadios.js", "equipaciones.js", "entrenadores.js", "portada.js",
              "ligas.js", "goles.js", "nombres.js", "selecciones.js"]
PANEL_DIRS = ["carrera", "ligas", "sel", "partido"]


def fecha(base):
    f = base / PANEL / "datos.js"
    if not f.exists():
        return None
    m = re.search(r'"generated":"(\d\d/\d\d/\d{4})', f.read_text(encoding="utf-8")[:400])
    return datetime.strptime(m.group(1), "%d/%m/%Y") if m else None


def rutas(base):
    out = [base / f for f in FILES]
    p = base / PANEL
    for pat in PANEL_DATA:
        out += sorted(p.glob(pat))
    for d in PANEL_DIRS:
        out.append(p / d)
    return out


def copiar(src_base, dst_base):
    n = 0
    for s in rutas(src_base):
        if not s.exists():
            continue
        d = dst_base / s.relative_to(src_base)
        d.parent.mkdir(parents=True, exist_ok=True)
        if s.is_dir():
            shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d)
        n += 1
    return n


def main(cmd):
    if cmd == "guardar":
        shutil.rmtree(EST, ignore_errors=True)
        print(f"guardados {copiar(ROOT, EST)} elementos en _estado/")
    elif cmd == "restaurar":
        fe, fr = fecha(EST), fecha(ROOT)
        print(f"estado guardado: {fe}  ·  repositorio: {fr}")
        if fe and (not fr or fe >= fr):
            print(f"restaurados {copiar(EST, ROOT)} elementos")
        else:
            print("el repositorio es más reciente: se usa el del repositorio")


if __name__ == "__main__":
    main(sys.argv[1])
