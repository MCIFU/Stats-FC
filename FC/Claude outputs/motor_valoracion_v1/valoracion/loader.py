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
