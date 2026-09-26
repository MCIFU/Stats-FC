"""Estadísticas avanzadas de las 5 grandes ligas desde FotMob (datos Opta) y Understat -> avanzadas_big5.csv
(mismo formato que auxiliares/sofascore/descargar_avanzadas.py; el motor lo lee con --avanzadas).

Uso (desde la carpeta FC):
    python auxiliares/avanzadas/descargar_fotmob_understat.py

Fuentes (sin navegador ni clave):
  - Understat getLeagueData/{liga}/{año}: xG, npxG, xA, tiros, pases clave de TODOS los jugadores con minutos.
  - FotMob data.fotmob.com/stats/{liga}/season/{id}/{stat}.json: pase %, pase largo %, regates, entradas,
    intercepciones, despejes, bloqueos, recuperaciones, robos en tercio rival, paradas, goles evitados, nota.
    FotMob solo lista a quien supera un mínimo de minutos (~9 % de los minutos de liga; porteros ~50 %):
    por debajo el dato queda vacío (UNKNOWN), no 0.
No existen en estas fuentes (quedan UNKNOWN): duelos aéreos, centros, pérdidas, errores, pases progresivos,
conducciones, SCA, toques en el área, centros detenidos y salidas del portero.
"""
import argparse, collections, gzip, json, sys, time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
FC = HERE.parent.parent
CACHE = HERE / "cache"
sys.path.insert(0, str(HERE.parent / "sofascore"))
from descargar_avanzadas import excel_rows, match_players  # noqa: E402  (mismo cruce Excel <-> fuente)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/128.0 Safari/537.36")
# liga Excel -> (id FotMob, liga Understat o None, año natural)
LEAGUES = {"Premier": (47, "EPL", False), "LaLiga": (87, "La_liga", False), "Bundesliga": (54, "Bundesliga", False),
           "Serie A": (55, "Serie_A", False), "Ligue 1": (53, "Ligue_1", False), "Eredivisie": (57, None, False),
           "Portugal": (61, None, False), "Scottish Premiership": (64, None, False), "Süper Lig": (71, None, False),
           "Liga Belga": (40, None, False), "Saudi Pro": (536, None, False), "Ekstraklasa": (196, None, False),
           "Liga MX": (230, None, False), "MLS": (130, None, True), "Brasileirão": (268, None, True),
           "Liga Argentina": (112, None, True), "Championship": (48, None, False), "LaLiga2": (140, None, False),
           "Serie B": (86, None, False), "2. Bundesliga": (146, None, False), "Super League 1": (135, None, False),
           "Superliga": (46, None, False), "Super League": (69, None, False), "Bundesliga Austria": (38, None, False),
           "J1 League": (223, None, True), "K League 1": (9080, None, True)}
SPECIAL = {("J1 League", "2026-27"): ("2026", "2026/2027")}
PADJ = ["tackles_won_p90", "interceptions_p90", "recoveries_p90", "blocks_clear_p90", "fm_tackles_p90"]
SEASONS = {"2025-26": ("2025/2026", "2025", 2025), "2026-27": ("2026/2027", "2026", 2026)}
# lista FotMob -> {columna: (valor "stat"|"sub", tipo "p90"|"pct"|"tot")}. Al unir Apertura+Clausura: p90/pct se
# promedian ponderando por minutos y tot se suma.
FOTMOB = {
    "accurate_pass": {"fm_acc_passes_p90": ("stat", "p90"), "pass_cmp_pct": ("sub", "pct")},
    "accurate_long_balls": {"fm_long_balls_p90": ("stat", "p90"), "long_cmp_pct": ("sub", "pct")},
    "won_contest": {"take_ons_won_p90": ("stat", "p90"), "take_on_pct": ("sub", "pct")},
    "total_tackle": {"fm_tackles_p90": ("stat", "p90")},
    "won_tackle": {"tackles_won_p90": ("stat", "p90"), "tackle_pct": ("sub", "pct")},
    "interception": {"interceptions_p90": ("stat", "p90")},
    "effective_clearance": {"fm_clearances_p90": ("stat", "p90")},
    "outfielder_block": {"fm_blocks_p90": ("stat", "p90")},
    "ball_recovery": {"recoveries_p90": ("stat", "p90")},
    "poss_won_att_3rd": {"pressures_att3_p90": ("stat", "p90")},
    "ontarget_scoring_att": {"fm_sot_p90": ("stat", "p90")},
    "total_scoring_att": {"fm_shots_p90": ("stat", "p90")},
    "expected_goals_per_90": {"fm_xg_p90": ("stat", "p90")},
    "expected_assists_per_90": {"fm_xa_p90": ("stat", "p90")},
    "total_att_assist": {"fm_chances_p90": ("sub", "p90")},
    "big_chance_created": {"fm_big_chances_created": ("stat", "tot")},
    "_save_percentage": {"gk_save_pct": ("stat", "pct")},
    "saves": {"fm_saves_p90": ("stat", "p90")},
    "_goals_prevented": {"fm_goals_prevented": ("stat", "tot")},
    "rating": {"fotmob_rating": ("stat", "pct")},
}

S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept": "application/json, */*"})


def get(url, headers=None, tries=5):
    for k in range(tries):
        try:
            r = S.get(url, timeout=30, headers=headers)
            if r.status_code in (403, 404):
                return None
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            if k == tries - 1:
                raise RuntimeError(f"{url}: {e}") from e
            time.sleep(2 ** k)


def cached(name, fn, refresh=False):
    p = CACHE / name
    if p.exists() and not refresh:
        return json.loads(gzip.decompress(p.read_bytes()))
    v = fn()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(gzip.compress(json.dumps(v, ensure_ascii=False).encode()))
    return v


def fotmob_table(lid, season_name, refresh):
    info = cached(f"fm_league_{lid}.json.gz", lambda: get(f"https://www.fotmob.com/api/data/leagues?id={lid}"), refresh=True)
    # una temporada puede tener varias fases con ruta propia (Liga MX: .../Apertura/, .../Clausura/)
    names = season_name if isinstance(season_name, (tuple, list)) else (season_name,)
    bases = sorted({x["RelativePath"].rsplit("/", 1)[0] for x in info["stats"]["seasonStatLinks"] if x["Name"] in names})
    if not bases:
        raise RuntimeError(f"FotMob {lid}: temporada {season_name} no encontrada")
    acc = {}
    stage_min = collections.defaultdict(dict)
    for base in bases:
        for stat, cols in FOTMOB.items():
            d = cached(f"fm_{base.replace('/', '_')}_{stat}.json.gz", lambda: get(f"https://data.fotmob.com/{base}/{stat}.json"), refresh)
            for x in ((d or {}).get("TopLists") or [{}])[0].get("StatList", []):
                pid = x["ParticiantId"]
                r = acc.setdefault(pid, {"sofa_id": pid, "sofa_name": x["ParticipantName"], "sofa_team_id": x["TeamId"],
                                         "sofa_team": x.get("TeamName", str(x["TeamId"])), "_v": collections.defaultdict(list)})
                r["sofa_team_id"], r["sofa_team"] = x["TeamId"], x.get("TeamName", r["sofa_team"])  # último club
                m = x.get("MinutesPlayed") or 0
                stage_min[pid][base] = max(stage_min[pid].get(base, 0), m)
                for c, (which, kind) in cols.items():
                    v = x.get("StatValue" if which == "stat" else "SubStatValue")
                    if v is not None:
                        r["_v"][c].append((v, m, kind))
    # posesión media del equipo (ponderada por fases) para ajustar las acciones defensivas
    poss = collections.defaultdict(list)
    for base in bases:
        d = cached(f"fm_{base.replace('/', '_')}_possession_team.json.gz",
                   lambda: get(f"https://data.fotmob.com/{base}/possession_percentage_team.json"), refresh)
        for x in ((d or {}).get("TopLists") or [{}])[0].get("StatList", []):
            if x.get("StatValue") is not None:
                poss[x.get("TeamId")].append(x["StatValue"])
    poss = {k: float(np.mean(v)) for k, v in poss.items()}
    rows = []
    for pid, r in acc.items():
        out = {k: v for k, v in r.items() if k != "_v"}
        out["fm_minutes"] = sum(stage_min[pid].values())
        for c, L in r["_v"].items():
            if L[0][2] == "tot":
                out[c] = sum(v for v, _, _ in L)
            else:
                w = sum(m for _, m, _ in L)
                out[c] = sum(v * m for v, m, _ in L) / w if w else L[-1][0]
        rows.append(out)
    df = pd.DataFrame(rows)
    for c in [c for cols in FOTMOB.values() for c in cols]:
        if c not in df:
            df[c] = np.nan
    n90 = (df.fm_minutes / 90).where(df.fm_minutes > 0)
    df["blocks_clear_p90"] = df.fm_clearances_p90 + df.fm_blocks_p90
    # ajuste por posesión (PAdj): quien defiende más tiempo suma más entradas/intercepciones sin ser mejor defensor.
    # × 50 / posesión del rival; con 42 % de posesión propia (58 % rival) el volumen baja un 14 %.
    df["team_possession"] = df.sofa_team_id.map(poss)
    fac = (50 / (100 - df.team_possession)).clip(0.7, 1.4).fillna(1.0)
    for c in PADJ:
        df[c + "_raw"] = df[c]
        df[c] = df[c] * fac
    df["sot_pct"] = (100 * df.fm_sot_p90 / df.fm_shots_p90).where(df.fm_shots_p90 > 0)
    df["gk_psxg_minus_ga_p90"] = df.fm_goals_prevented / n90
    df["gk_launch_cmp_pct"] = df.long_cmp_pct
    # disparo y creación desde FotMob (en las 5 grandes los sustituye Understat, que tiene npxG y a todos los jugadores)
    df["npxg_p90"] = df.fm_xg_p90  # xG de FotMob incluye penaltis
    df["shots_p90"] = df.fm_shots_p90
    df["npxg_per_shot"] = (df.fm_xg_p90 / df.fm_shots_p90).where(df.fm_shots_p90 > 0)
    df["xa_p90"] = df.fm_xa_p90
    df["key_passes_p90"] = df.fm_chances_p90
    return df


def understat_table(league, year, refresh):
    d = cached(f"us_{league}_{year}.json.gz", lambda: get(f"https://understat.com/getLeagueData/{league}/{year}",
                                                          headers={"X-Requested-With": "XMLHttpRequest"}), refresh)
    df = pd.DataFrame(d["players"])
    num = ["time", "games", "goals", "xG", "assists", "xA", "shots", "key_passes", "npg", "npxG", "xGChain", "xGBuildup"]
    df[num] = df[num].apply(pd.to_numeric, errors="coerce")
    n90 = (df.time / 90).where(df.time > 0)
    pens = (df.goals - df.npg).clip(lower=0)  # Understat no da penaltis lanzados: se aproxima con los marcados
    out = pd.DataFrame({"sofa_id": df.id, "sofa_name": df.player_name, "sofa_team_id": df.team_title, "sofa_team": df.team_title,
                        "us_minutes": df.time, "npxg_p90": df.npxG / n90, "shots_p90": df.shots / n90,
                        "npg_minus_npxg_p90": (df.npg - df.npxG) / n90,
                        "npxg_per_shot": (df.npxG / (df.shots - pens)).where(df.shots - pens > 0),
                        "xa_p90": df.xA / n90, "key_passes_p90": df.key_passes / n90,
                        "xgchain_p90": df.xGChain / n90, "xgbuildup_p90": df.xGBuildup / n90})
    # jugadores traspasados dentro de la liga: Understat pone "Club A,Club B" -> una fila por club para el cruce
    out["sofa_team"] = out.sofa_team.str.split(",")
    out = out.explode("sofa_team")
    out["sofa_team_id"] = out.sofa_team
    return out.reset_index(drop=True).replace([np.inf, -np.inf], np.nan)


def excel_rows_todas():
    import openpyxl
    out = []
    for season, fname in (("2025-26", "Temporada 2025-26.xlsx"), ("2026-27", "Temporada 2026-27.xlsx")):
        wb = openpyxl.load_workbook(FC / fname, read_only=True)
        for sh in ["DELANTEROS", "EXTREMOS", "MEDIAPUNTAS", "MEDIOCENTROS", "DEFENSAS", "PORTEROS"]:
            rows = list(wb[sh].iter_rows(values_only=True))
            hi = next(i for i, r in enumerate(rows[:10]) if r and r[0] == "Jugador")
            for k, r in enumerate(rows[hi + 1:], hi + 2):
                d = dict(zip(rows[hi], r))
                if r and r[0] and d.get("Liga") in LEAGUES:
                    out.append(dict(season=season, source_sheet=sh, source_row=k, name=d["Jugador"], club=d["Club"],
                                    liga=d["Liga"], liga_min=d.get("LIGA Min")))
    return pd.DataFrame(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="vuelve a descargar (si no, usa la caché)")
    ap.add_argument("--ligas", help="solo estas ligas del Excel, separadas por comas (por defecto todas las configuradas)")
    ap.add_argument("--out", default=str(FC / "Claude outputs" / "avanzadas.csv"))
    a = ap.parse_args()
    ex = excel_rows_todas()
    ligas = [l for l in LEAGUES if not a.ligas or l in a.ligas.split(",")]
    print(f"{len(ex)} filas de {len(LEAGUES)} ligas en los Excel")
    res = []
    for season, (fm_season, fm_cal, us_year) in SEASONS.items():
        for liga in ligas:
            lid, us_league, cal = LEAGUES[liga]
            e = ex[(ex.season == season) & (ex.liga == liga)]
            if e.empty:
                continue
            # Japón: 2025 = año natural; 26-27 = medio torneo feb-jun 2026 + temporada 2026/27 (así lo etiqueta el Excel)
            name = SPECIAL.get((liga, season)) or (fm_cal if cal else fm_season)
            fm = fotmob_table(lid, name, a.refresh)
            us = understat_table(us_league, us_year, a.refresh) if us_league else pd.DataFrame(columns=["sofa_id", "sofa_name", "sofa_team_id", "sofa_team", "us_minutes"])
            mf = {i: (s, h) for i, s, h in match_players(e, fm, "fm_minutes")}
            mu = {i: (s, h) for i, s, h in match_players(e, us, "us_minutes")} if len(us) else {i: (None, "") for i in e.index}
            nf = sum(1 for s, _ in mf.values() if s is not None)
            nu = sum(1 for s, _ in mu.values() if s is not None)
            print(f"  {season} {liga}: {len(e)} filas · FotMob {len(fm)} jugadores, cruzados {nf}" + (f" · Understat {len(us)}, cruzados {nu}" if us_league else ""))
            for i in e.index:
                row = e.loc[i, ["season", "source_sheet", "source_row", "name", "club", "liga", "liga_min"]].to_dict()
                sf, hf = mf[i]
                su, hu = mu[i]
                row["match_how"] = "|".join(x for x in (hf and f"fm:{hf}", hu and f"us:{hu}") if x) or None
                if sf is not None:
                    row.update({k: v for k, v in fm.loc[sf].items() if k not in ("n", "sofa_id", "sofa_team_id")})
                    row["fotmob_id"] = fm.loc[sf, "sofa_id"]
                if su is not None:  # Understat manda en disparo/creación (npxG real y todos los jugadores)
                    row.update({k: v for k, v in us.loc[su].items() if k not in ("n", "sofa_name", "sofa_team", "sofa_id", "sofa_team_id")})
                    row["understat_id"] = us.loc[su, "sofa_id"]
                row["fuente_xg"] = "Understat (npxG)" if su is not None else ("FotMob (xG con penaltis)" if sf is not None else None)
                res.append(row)
    df = pd.DataFrame(res)
    for c in ("fotmob_id", "understat_id"):
        if c not in df:
            df[c] = np.nan
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out, index=False, encoding="utf-8-sig")
    print(f"{Path(a.out).name}: {len(df)} filas, con FotMob {df.fotmob_id.notna().sum()}, con Understat {df.understat_id.notna().sum()}")


if __name__ == "__main__":
    main()
