"""Recalcula todo:
    python run_all.py <Temporada 2025-26.xlsx> <Temporada 2026-27.xlsx> <salida.xlsx>
        [--partidos partidos_big5.csv] [--notas notas_big5.csv] [--avanzadas avanzadas_big5.csv] [--clubmap clubmap.json]
Sin --partidos: ELO/FORM/CONSISTENCY/OPPONENT_STRENGTH = UNKNOWN. Sin --avanzadas: métricas avanzadas = UNKNOWN."""
import argparse, json
from pathlib import Path
import numpy as np, pandas as pd
import engine, loader, build_excel

HERE = Path(__file__).resolve().parent


def club_strengths(cfg, clubmap, ws):
    """club_id TM -> competition_strength de la liga en la que aparece ese club en los Excel (la más frecuente)."""
    comps = cfg["competitions"]["leagues"]
    if not clubmap:
        return {}
    cm = json.loads(Path(clubmap).read_text(encoding="utf-8"))
    w = pd.concat([x[["Club", "Liga"]] for x in ws])
    lg = w.groupby("Club").Liga.agg(lambda s: s.value_counts().index[0])
    return {str(cm[c]): comps.get(l, {}).get("strength") for c, l in lg.items() if c in cm and comps.get(l, {}).get("strength")}


def attach_advanced(raw, adv):
    """Añade las métricas avanzadas a las filas LIGA (el motor las lee de ahí)."""
    if adv is None or adv.empty:
        return raw
    cols = [c for c in adv.columns if c != "player_id"]
    raw = raw.drop(columns=[c for c in cols if c in raw])
    liga = raw.block == "LIGA"
    add = raw.loc[liga, ["player_id"]].merge(adv.drop_duplicates("player_id"), on="player_id", how="left")
    for c in cols:
        raw[c] = np.nan
        raw.loc[liga, c] = add[c].to_numpy()
    return raw


def main(f1, f2, out, partidos=None, notas=None, avanzadas=None, clubmap=None):
    cfg = engine.load_config()
    raw1, w1 = loader.read_season(f1, "2025-26")
    raw2, w2 = loader.read_season(f2, "2026-27")
    if partidos:  # edad por fecha de nacimiento y posición principal de la ficha TM
        import ficha_tm
        meta = ficha_tm.load_meta()
        raw1, r1 = ficha_tm.corrige(raw1, w1, partidos, "2025-26", meta)
        raw2, r2 = ficha_tm.corrige(raw2, w2, partidos, "2026-27", meta)
        print(r1); print(r2)
    adv_names = [m for m, d in cfg["metrics"]["metrics"].items() if d["availability"] == "advanced"]
    if avanzadas:
        raw1 = attach_advanced(raw1, loader.read_advanced(avanzadas, w1, "2025-26", adv_names))
        raw2 = attach_advanced(raw2, loader.read_advanced(avanzadas, w2, "2026-27", adv_names))
    m1 = m2 = None
    if partidos:
        cs = club_strengths(cfg, clubmap, [w1, w2])
        m1 = loader.read_matches(partidos, w1, "2025-26", cs, notas)
        m2 = loader.read_matches(partidos, w2, "2026-27", cs, notas)
        print(f"partidos: 25-26 {len(m1)} filas / {m1.player_id.nunique()} jugadores; 26-27 {len(m2)} / {m2.player_id.nunique()}")
    b1, mm1 = engine.run(raw1, cfg, matches=m1)
    # 26-27: el Elo de equipos arrastra los resultados de 25-26
    tg = None if m1 is None else pd.concat([m1, m2], ignore_index=True)
    b2, mm2 = engine.run(raw2, cfg, matches=m2, prev=b1, team_games=tg, prev_mm=mm1)
    base = pd.concat([b1, b2], ignore_index=True)
    mm = None
    if mm1 is not None or mm2 is not None:
        mm = pd.concat([x.assign(season=s) for x, s in ((mm1, "2025-26"), (mm2, "2026-27")) if x is not None], ignore_index=True)
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
    if partidos:
        note += " Partido a partido (5 grandes): Transfermarkt performance-game → ELO, FORM, CONSISTENCY y OPPONENT_STRENGTH."
    if notas:
        note += " Nota de partido: SofaScore."
    if avanzadas:
        note += " Métricas avanzadas (5 grandes, liga): Understat y FotMob (Opta)."
    b = build_excel.build(base, cfg, out, raw=src, sims=sims, corr=corr, matches=mm, history=h, source_note=note)
    import build_resumen  # versión corta y visual, junto al extenso
    build_resumen.build(base, cfg, str(Path(out).with_name("Resumen_FC.xlsx")))
    import build_web  # panel web: FC/Panel_FC/index.html + datos.js
    build_web.build(base, cfg, HERE.parents[2] / "Panel_FC", matches=mm, sims=sims)
    return base, b


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("f1"); ap.add_argument("f2"); ap.add_argument("out")
    ap.add_argument("--partidos"); ap.add_argument("--notas"); ap.add_argument("--avanzadas")
    ap.add_argument("--clubmap", default=str(HERE.parents[2] / "auxiliares" / "tmapi" / "clubmap.json"))
    a = ap.parse_args()
    main(a.f1, a.f2, a.out, a.partidos, a.notas, a.avanzadas, a.clubmap)
