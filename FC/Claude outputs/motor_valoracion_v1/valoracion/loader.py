"""Lee tus Excel 'Temporada XXXX-YY.xlsx' (hojas por puesto) y los pasa al formato canónico largo del motor.
No modifica nada: cada fila del Excel original queda también en DATOS_ORIGEN."""
import re
import numpy as np
import pandas as pd
import openpyxl

SHEETS = ["DELANTEROS", "EXTREMOS", "MEDIAPUNTAS", "MEDIOCENTROS", "DEFENSAS", "PORTEROS"]
BLOCKS = ["LIGA", "COPA", "CONT", "FIFA", "SEL"]


def slug(s):
    return re.sub(r"\s+", " ", str(s).strip()).lower()


def read_season(path, season):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=False)
    wide = []
    for sh in SHEETS:
        ws = wb[sh]
        rows = list(ws.iter_rows(values_only=True))
        hdr_i = next(i for i, r in enumerate(rows[:10]) if r and r[0] == "Jugador")
        hdr = [h for h in rows[hdr_i]]
        for k, r in enumerate(rows[hdr_i + 1:], hdr_i + 2):
            if not r or r[0] is None or str(r[0]).strip() == "":
                continue
            d = {h: v for h, v in zip(hdr, r) if h}
            d["_sheet"], d["_row"] = sh, k
            wide.append(d)
    w = pd.DataFrame(wide)
    w["season"] = season
    # ID estable entre temporadas: nombre + nacionalidad
    w["player_id"] = (w.Jugador.map(slug) + "|" + w.Nac.astype(str).str.upper())
    # filas duplicadas en la misma temporada (regla de continentes) -> sufijo
    w["dup"] = w.groupby("player_id").cumcount()
    w.loc[w.dup > 0, "player_id"] = w.player_id + "#" + (w.dup + 1).astype(str)
    long = []
    for b in BLOCKS:
        gk = w._sheet == "PORTEROS"
        d = pd.DataFrame({"player_id": w.player_id, "name": w.Jugador, "age": pd.to_numeric(w.Edad, errors="coerce"),
                          "nat": w.Nac, "pos": w.Pos, "club": w.Club, "league": w.Liga, "season": season,
                          "value_eur": pd.to_numeric(w["Valor M€"], errors="coerce") * 1e6, "block": b,
                          "cont_comp": w["CONT."] if b == "CONT" else None,
                          "PJ": pd.to_numeric(w[f"{b} PJ"], errors="coerce"), "Min": pd.to_numeric(w[f"{b} Min"], errors="coerce")})
        d["G"] = np.where(gk, np.nan, pd.to_numeric(w.get(f"{b} G"), errors="coerce"))
        d["A"] = np.where(gk, np.nan, pd.to_numeric(w.get(f"{b} A"), errors="coerce"))
        d["GC"] = np.where(gk, pd.to_numeric(w.get(f"{b} GC"), errors="coerce"), np.nan)
        d["CS"] = np.where(gk, pd.to_numeric(w.get(f"{b} CS"), errors="coerce"), np.nan)
        # porteros: G/A no existen en la hoja -> desconocido. Goles del portero = 0 real en la práctica, pero no lo inventamos.
        d["source_sheet"], d["source_row"] = w._sheet, w._row
        long.append(d)
    return pd.concat(long, ignore_index=True), w


# ---------------------------------------------------------------- datos externos (5 grandes ligas)
def _key(df):
    return df.source_sheet.astype(str) + "|" + pd.to_numeric(df.source_row, errors="coerce").astype("Int64").astype(str)


def _pid_map(w):
    return dict(zip(w._sheet.astype(str) + "|" + w._row.astype(str), w.player_id))


def read_matches(path, w, season, club_strength=None, notes_path=None):
    """partidos_big5.csv (auxiliares/tmapi/descargar_partidos.py) -> formato del motor para una temporada.
    club_strength: {club_id TM: competition_strength} para la Elo inicial de cada equipo.
    notes_path: notas_big5.csv (SofaScore) -> columna sofa_rating por jugador y día."""
    m = pd.read_csv(path, dtype={"club_id": str, "opponent_id": str, "tm_id": str})
    m = m[m.season == season].copy()
    m["player_id"] = _key(m).map(_pid_map(w))
    m = m[m.player_id.notna()]
    m["date"] = pd.to_datetime(m.date)
    m["club_key"] = m.club_id.fillna(m.club)
    m["opp_key"] = m.opponent_id.fillna(m.opponent)
    cs = club_strength or {}
    m["club_strength"] = m.club_id.map(cs)
    m["opp_strength"] = m.opponent_id.map(cs)
    m["home"] = m.home.map(lambda x: np.nan if pd.isna(x) else str(x).lower() in ("true", "1", "1.0"))
    for c in ["gf", "ga", "Min", "G", "A", "GC"]:
        m[c] = pd.to_numeric(m.get(c), errors="coerce")
    if notes_path:
        n = pd.read_csv(notes_path)
        n = n[n.season == season].copy()
        n["player_id"] = _key(n).map(_pid_map(w))
        n["day"] = pd.to_datetime(n.date).dt.normalize()
        n = n.dropna(subset=["player_id", "rating"]).drop_duplicates(["player_id", "day"])
        m["day"] = m.date.dt.normalize()
        m = m.merge(n[["player_id", "day", "rating"]].rename(columns={"rating": "sofa_rating"}), on=["player_id", "day"], how="left")
        m = m.drop(columns="day")
    return m


def read_advanced(path, w, season, metric_names):
    """avanzadas_big5.csv (auxiliares/sofascore/descargar_avanzadas.py) -> player_id + métricas avanzadas."""
    a = pd.read_csv(path)
    a = a[(a.season == season) & a.match_how.notna()].copy()
    a["player_id"] = _key(a).map(_pid_map(w))
    cols = [c for c in metric_names if c in a]
    return a.dropna(subset=["player_id"])[["player_id"] + cols]
