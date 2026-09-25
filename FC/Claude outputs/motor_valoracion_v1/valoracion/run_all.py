"""Recalcula todo: python run_all.py <Temporada 2025-26.xlsx> <Temporada 2026-27.xlsx> <salida.xlsx>"""
import sys, re
import numpy as np, pandas as pd
import engine, loader, build_excel

def main(f1, f2, out):
    cfg = engine.load_config()
    raw1, w1 = loader.read_season(f1, "2025-26")
    raw2, w2 = loader.read_season(f2, "2026-27")
    b1, _ = engine.run(raw1, cfg)
    b2, _ = engine.run(raw2, cfg, prev=b1)
    base = pd.concat([b1, b2], ignore_index=True)
    sims = pd.concat([engine.similar_players(b1, cfg), engine.similar_players(b2, cfg)], ignore_index=True)
    corr = engine.correlations(b1, cfg)
    # historial por jugador (id = nombre|nac)
    keep = ["player_id", "name", "age", "pos", "club", "league", "LIGA_Min", "CA_FINAL", "CA_CONFIDENCE", "PA_ESTIMATE", "REL_PERF", "score_league"]
    h = b1[keep].merge(b2[keep], on="player_id", how="outer", suffixes=(" 25-26", " 26-27"))
    h["Jugador"] = h["name 25-26"].fillna(h["name 26-27"])
    h["Δ CA"] = h["CA_FINAL 26-27"] - h["CA_FINAL 25-26"]
    h["Nota"] = np.where(h["LIGA_Min 26-27"].fillna(0) < 450, "26-27 con poca muestra: el Δ refleja sobre todo regresión a la media", "")
    cols = ["Jugador", "age 26-27", "pos 26-27", "club 25-26", "league 25-26", "club 26-27", "league 26-27",
            "LIGA_Min 25-26", "CA_FINAL 25-26", "CA_CONFIDENCE 25-26", "PA_ESTIMATE 25-26",
            "LIGA_Min 26-27", "CA_FINAL 26-27", "CA_CONFIDENCE 26-27", "PA_ESTIMATE 26-27", "Δ CA", "Nota"]
    h = h[cols].rename(columns={"age 26-27": "Edad", "pos 26-27": "POS"}).round(1).sort_values("CA_FINAL 26-27", ascending=False)
    # datos origen (columnas de entrada, sin las columnas-fórmula TOT/G+A/G/90...)
    src = []
    for w in (w1, w2):
        c = [x for x in w.columns if not (str(x).startswith("TOT") or x in ("G+A", "G/90", "Min/PJ", "%CS", "GC/90", "dup"))]
        src.append(w[c])
    src = pd.concat(src, ignore_index=True).rename(columns={"_sheet": "Hoja origen", "_row": "Fila origen", "season": "Temporada", "player_id": "ID"})
    note = ("Datos: tus archivos Temporada 2025-26.xlsx y 2026-27.xlsx (PJ/Min/G/A por competición, GC/CS en porteros; "
            "recalculados con Transfermarkt el 25/09/2026). 26-27: ligas europeas con ~6 jornadas → muestra pequeña y confianza baja.")
    b = build_excel.build(base, cfg, out, raw=src, sims=sims, corr=corr, history=h, source_note=note)
    return base, b

if __name__ == "__main__":
    main(*sys.argv[1:4])
