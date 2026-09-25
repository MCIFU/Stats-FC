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
import argparse, gzip, json, sys, time
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
# liga Excel -> (id FotMob, liga Understat)
LEAGUES = {"Premier": (47, "EPL"), "LaLiga": (87, "La_liga"), "Bundesliga": (54, "Bundesliga"),
           "Serie A": (55, "Serie_A"), "Ligue 1": (53, "Ligue_1")}
SEASONS = {"2025-26": ("2025/2026", 2025), "2026-27": ("2026/2027", 2026)}
# lista FotMob -> {columna: "stat" (valor principal) | "sub" (valor secundario)}
FOTMOB = {
    "accurate_pass": {"fm_acc_passes_p90": "stat", "pass_cmp_pct": "sub"},
    "accurate_long_balls": {"fm_long_balls_p90": "stat", "long_cmp_pct": "sub"},
    "won_contest": {"take_ons_won_p90": "stat", "take_on_pct": "sub"},
    "total_tackle": {"fm_tackles_p90": "stat"},
    "won_tackle": {"tackles_won_p90": "stat", "tackle_pct": "sub"},
    "interception": {"interceptions_p90": "stat"},
    "effective_clearance": {"fm_clearances_p90": "stat"},
    "outfielder_block": {"fm_blocks_p90": "stat"},
    "ball_recovery": {"recoveries_p90": "stat"},
    "poss_won_att_3rd": {"pressures_att3_p90": "stat"},
    "ontarget_scoring_att": {"fm_sot_p90": "stat"},
    "total_scoring_att": {"fm_shots_p90": "stat"},
    "big_chance_created": {"fm_big_chances_created": "stat"},
    "_save_percentage": {"gk_save_pct": "stat"},
    "saves": {"fm_saves_p90": "stat"},
    "_goals_prevented": {"fm_goals_prevented": "stat"},
    "rating": {"fotmob_rating": "stat"},
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
    sid = next((x["TournamentId"] for x in info["stats"]["seasonStatLinks"] if x["Name"] == season_name), None)
    if sid is None:
        raise RuntimeError(f"FotMob {lid}: temporada {season_name} no encontrada")
    rows = {}
    for stat, cols in FOTMOB.items():
        d = cached(f"fm_{lid}_{sid}_{stat}.json.gz",
                   lambda: get(f"https://data.fotmob.com/stats/{lid}/season/{sid}/{stat}.json"), refresh)
        for x in ((d or {}).get("TopLists") or [{}])[0].get("StatList", []):
            r = rows.setdefault(x["ParticiantId"], {"sofa_id": x["ParticiantId"], "sofa_name": x["ParticipantName"],
                                                    "sofa_team_id": x["TeamId"], "sofa_team": x["TeamName"]})
            r["fm_minutes"] = max(r.get("fm_minutes", 0), x.get("MinutesPlayed") or 0)
            for c, which in cols.items():
                r[c] = x.get("StatValue" if which == "stat" else "SubStatValue")
    df = pd.DataFrame(rows.values())
    for c in [c for cols in FOTMOB.values() for c in cols]:
        if c not in df:
            df[c] = np.nan
    n90 = (df.fm_minutes / 90).where(df.fm_minutes > 0)
    df["blocks_clear_p90"] = df.fm_clearances_p90 + df.fm_blocks_p90
    df["sot_pct"] = (100 * df.fm_sot_p90 / df.fm_shots_p90).where(df.fm_shots_p90 > 0)
    df["gk_psxg_minus_ga_p90"] = df.fm_goals_prevented / n90
    df["gk_launch_cmp_pct"] = df.long_cmp_pct
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="vuelve a descargar (si no, usa la caché)")
    ap.add_argument("--out", default=str(FC / "Claude outputs" / "avanzadas_big5.csv"))
    a = ap.parse_args()
    ex = excel_rows()
    print(f"{len(ex)} filas de las 5 grandes en los Excel")
    res = []
    for season, (fm_season, us_year) in SEASONS.items():
        for liga, (lid, us_league) in LEAGUES.items():
            e = ex[(ex.season == season) & (ex.liga == liga)]
            fm = fotmob_table(lid, fm_season, a.refresh)
            us = understat_table(us_league, us_year, a.refresh)
            mf = {i: (s, h) for i, s, h in match_players(e, fm, "fm_minutes")}
            mu = {i: (s, h) for i, s, h in match_players(e, us, "us_minutes")}
            nf = sum(1 for s, _ in mf.values() if s is not None)
            nu = sum(1 for s, _ in mu.values() if s is not None)
            print(f"  {season} {liga}: {len(e)} filas · FotMob {len(fm)} jugadores, cruzados {nf} · Understat {len(us)}, cruzados {nu}")
            for i in e.index:
                row = e.loc[i, ["season", "source_sheet", "source_row", "name", "club", "liga", "liga_min"]].to_dict()
                sf, hf = mf[i]
                su, hu = mu[i]
                row["match_how"] = "|".join(x for x in (hf and f"fm:{hf}", hu and f"us:{hu}") if x) or None
                if sf is not None:
                    row.update({k: v for k, v in fm.loc[sf].items() if k not in ("n", "sofa_id", "sofa_team_id")})
                    row["fotmob_id"] = fm.loc[sf, "sofa_id"]
                if su is not None:
                    row.update({k: v for k, v in us.loc[su].items() if k not in ("n", "sofa_name", "sofa_team", "sofa_id", "sofa_team_id")})
                    row["understat_id"] = us.loc[su, "sofa_id"]
                res.append(row)
    df = pd.DataFrame(res)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out, index=False, encoding="utf-8-sig")
    print(f"avanzadas_big5.csv: {len(df)} filas, con FotMob {df.fotmob_id.notna().sum()}, con Understat {df.understat_id.notna().sum()}")


if __name__ == "__main__":
    main()
