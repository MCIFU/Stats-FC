"""Estadísticas avanzadas de las 5 grandes ligas desde SofaScore (datos Opta) -> avanzadas_big5.csv
y, con --notas, la nota SofaScore de cada jugador en cada partido de liga -> notas_big5.csv.

Uso (desde la carpeta FC):
    python auxiliares/sofascore/descargar_avanzadas.py            # temporada 25/26 y 26/27
    python auxiliares/sofascore/descargar_avanzadas.py --notas    # + nota por partido (≈1 petición por partido)

Necesita salida a www.sofascore.com y api.sofascore.com. SofaScore suele exigir navegador (Cloudflare):
el script prueba primero con requests y, si recibe 403, abre Chromium con Playwright y hace las
peticiones desde la propia página (pip install playwright && python -m playwright install chromium).

Por qué SofaScore: desde enero de 2026 FBref ya no publica estadísticas avanzadas (Opta retiró el acceso).
Las columnas de salida usan los nombres de config/metrics.json del motor; las que SofaScore no ofrece
(p.ej. pases progresivos, SCA, toques en el área) se quedan vacías = UNKNOWN, no 0.
"""
import argparse, collections, datetime as dt, gzip, json, re, time
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
FC = HERE.parent.parent
CACHE = HERE / "cache"
API = "https://api.sofascore.com/api/v1"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/128.0 Safari/537.36")
LEAGUES = {"Premier": 17, "LaLiga": 8, "Bundesliga": 35, "Serie A": 23, "Ligue 1": 34}
SEASONS = {"2025-26": ("Temporada 2025-26.xlsx", "25/26"), "2026-27": ("Temporada 2026-27.xlsx", "26/27")}
SHEETS = ["DELANTEROS", "EXTREMOS", "MEDIAPUNTAS", "MEDIOCENTROS", "DEFENSAS", "PORTEROS"]
FIELDS = [
    "minutesPlayed", "appearances", "matchesStarted", "rating", "goals", "assists", "penaltyGoals", "penaltiesTaken",
    "expectedGoals", "expectedAssists", "totalShots", "shotsOnTarget", "keyPasses", "bigChancesCreated",
    "accuratePasses", "totalPasses", "accuratePassesPercentage", "accurateFinalThirdPasses",
    "accurateLongBalls", "accurateLongBallsPercentage", "accurateCrosses", "totalCross",
    "successfulDribbles", "successfulDribblesPercentage", "dispossessed", "possessionLost", "touches",
    "tackles", "tacklesWon", "tacklesWonPercentage", "interceptions", "ballRecovery", "clearances",
    "outfielderBlocks", "aerialDuelsWon", "aerialDuelsWonPercentage", "possessionWonAttThird",
    "errorLeadToShot", "errorLeadToGoal", "dribbledPast",
    "saves", "goalsConceded", "goalsPrevented", "highClaims", "crossesNotClaimed", "runsOut", "successfulRunsOut",
    "cleanSheet",
]


# ---------------------------------------------------------------- acceso HTTP (requests -> navegador)
class Client:
    def __init__(self, delay=0.35):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept": "application/json", "Referer": "https://www.sofascore.com/",
                               "Origin": "https://www.sofascore.com"})
        self.page = None
        self.delay = delay

    def _browser(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        b = self._pw.chromium.launch(headless=True)
        self.page = b.new_page(user_agent=UA)
        self.page.goto("https://www.sofascore.com/", wait_until="domcontentloaded", timeout=60000)
        print("  (SofaScore vía navegador)")

    def get(self, path, tries=4):
        url = path if path.startswith("http") else API + path
        for k in range(tries):
            time.sleep(self.delay)
            try:
                if self.page is None:
                    r = self.s.get(url, timeout=30)
                    if r.status_code == 403:
                        self._browser()
                        continue
                    if r.status_code == 404:
                        return None
                    r.raise_for_status()
                    return r.json()
                res = self.page.evaluate("""async (u) => { const r = await fetch(u, {credentials: 'include'});
                                            return {s: r.status, t: await r.text()}; }""", url)
                if res["s"] == 404:
                    return None
                if res["s"] != 200:
                    raise RuntimeError(f"HTTP {res['s']}")
                return json.loads(res["t"])
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


def norm(s):
    from unidecode import unidecode
    s = unidecode(str(s)).lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# ---------------------------------------------------------------- descarga
def season_id(c, ut, year):
    ss = cached(f"seasons_{ut}.json.gz", lambda: c.get(f"/unique-tournament/{ut}/seasons"), refresh=True)
    for s in ss.get("seasons", []):
        if s.get("year") == year:
            return s["id"]
    raise RuntimeError(f"Temporada {year} no encontrada en torneo {ut}")


def league_stats(c, ut, sid, refresh):
    def fetch():
        rows = {}
        for i in range(0, len(FIELDS), 20):  # varias peticiones con pocos campos cada una
            chunk = "%2C".join(FIELDS[i:i + 20])
            off = 0
            while True:
                r = c.get(f"/unique-tournament/{ut}/season/{sid}/statistics?limit=100&offset={off}"
                          f"&order=-rating&accumulation=total&fields={chunk}&filters=position.in.G~D~M~F")
                for x in (r or {}).get("results", []):
                    k = (x["player"]["id"], x["team"]["id"])
                    d = rows.setdefault(k, {"sofa_id": x["player"]["id"], "sofa_name": x["player"]["name"],
                                            "sofa_team_id": x["team"]["id"], "sofa_team": x["team"]["name"]})
                    d.update({f: x.get(f) for f in FIELDS[i:i + 20] if f in x})
                if not r or r.get("page", 1) >= r.get("pages", 0):
                    break
                off += 100
        return list(rows.values())
    return cached(f"stats_{ut}_{sid}.json.gz", fetch, refresh)


def season_events(c, ut, sid, refresh):
    def fetch():
        ev, i = [], 0
        while True:
            r = c.get(f"/unique-tournament/{ut}/season/{sid}/events/last/{i}")
            if not r or not r.get("events"):
                break
            ev += r["events"]
            if not r.get("hasNextPage", True):
                break
            i += 1
        return ev
    return cached(f"events_{ut}_{sid}.json.gz", fetch, refresh)


def lineups(c, eid):
    return cached(f"lineups/{eid}.json.gz", lambda: c.get(f"/event/{eid}/lineups") or {})


# ---------------------------------------------------------------- métricas del motor (config/metrics.json)
def metrics(df):
    n90 = df.minutesPlayed / 90
    n90 = n90.where(df.minutesPlayed > 0)
    pk_xg = 0.79 * df.penaltiesTaken.fillna(0)
    npxg = (df.expectedGoals - pk_xg).clip(lower=0)
    np_shots = (df.totalShots - df.penaltiesTaken.fillna(0)).clip(lower=0)
    pct = lambda a, b: (100 * a / b).where(b > 0)
    m = pd.DataFrame(index=df.index)
    m["npxg_p90"] = npxg / n90
    m["shots_p90"] = df.totalShots / n90
    m["sot_pct"] = pct(df.shotsOnTarget, df.totalShots)
    m["npg_minus_npxg_p90"] = (df.goals - df.penaltyGoals.fillna(0) - npxg) / n90
    m["npxg_per_shot"] = (npxg / np_shots).where(np_shots > 0)
    m["xa_p90"] = df.expectedAssists / n90
    m["key_passes_p90"] = df.keyPasses / n90
    m["pass_cmp_pct"] = df.accuratePassesPercentage
    m["final_third_passes_p90"] = df.accurateFinalThirdPasses / n90
    m["long_cmp_pct"] = df.accurateLongBallsPercentage
    m["crosses_cmp_p90"] = df.accurateCrosses / n90
    m["take_ons_won_p90"] = df.successfulDribbles / n90
    m["take_on_pct"] = df.successfulDribblesPercentage
    m["miscontrols_disp_p90"] = df.dispossessed / n90
    m["tackles_won_p90"] = df.tacklesWon / n90
    m["tackle_pct"] = df.tacklesWonPercentage
    m["interceptions_p90"] = df.interceptions / n90
    m["recoveries_p90"] = df.ballRecovery / n90
    m["aerials_won_p90"] = df.aerialDuelsWon / n90
    m["aerial_pct"] = df.aerialDuelsWonPercentage
    m["blocks_clear_p90"] = (df.outfielderBlocks.fillna(0) + df.clearances.fillna(0)) / n90
    m["pressures_att3_p90"] = df.possessionWonAttThird / n90
    m["errors_p90"] = df.errorLeadToShot / n90
    m["gk_psxg_minus_ga_p90"] = df.goalsPrevented / n90
    m["gk_save_pct"] = pct(df.saves, df.saves + df.goalsConceded)
    m["gk_crosses_stopped_pct"] = pct(df.highClaims, df.highClaims + df.crossesNotClaimed)
    m["gk_def_actions_outside_p90"] = df.successfulRunsOut.fillna(df.runsOut) / n90
    m["gk_launch_cmp_pct"] = df.accurateLongBallsPercentage
    m["sofa_rating"] = df.rating
    return m.replace([np.inf, -np.inf], np.nan)


# ---------------------------------------------------------------- cruce con las filas del Excel
def excel_rows():
    out = []
    for season, (fname, _) in SEASONS.items():
        wb = openpyxl.load_workbook(FC / fname, read_only=True)
        for sh in SHEETS:
            rows = list(wb[sh].iter_rows(values_only=True))
            hi = next(i for i, r in enumerate(rows[:10]) if r and r[0] == "Jugador")
            for k, r in enumerate(rows[hi + 1:], hi + 2):
                d = dict(zip(rows[hi], r))
                if r and r[0] and d.get("Liga") in LEAGUES:
                    out.append(dict(season=season, source_sheet=sh, source_row=k, name=d["Jugador"], club=d["Club"],
                                    liga=d["Liga"], liga_min=d.get("LIGA Min")))
    return pd.DataFrame(out)


def match_players(ex, sofa):
    """Club del Excel -> equipo SofaScore por votación (nombres idénticos), luego jugador dentro del equipo."""
    from rapidfuzz import fuzz, process
    ex = ex.copy()
    ex["n"] = ex.name.map(norm)
    sofa = sofa.copy()
    sofa["n"] = sofa.sofa_name.map(norm)
    team_of = {}
    for club, g in ex.groupby("club"):
        votes = collections.Counter()
        for n in g.n:
            for t in sofa.loc[sofa.n == n, "sofa_team_id"]:
                votes[t] += 1
        if votes:
            team_of[club] = votes.most_common(1)[0][0]
        else:  # sin coincidencias exactas: por nombre del club
            names = sofa.drop_duplicates("sofa_team_id").set_index("sofa_team_id").sofa_team.map(norm).to_dict()
            b = process.extractOne(norm(club), names, scorer=fuzz.WRatio)
            if b and b[1] >= 85:
                team_of[club] = b[2]
    res = []
    for i, r in ex.iterrows():
        cand = sofa[sofa.sofa_team_id == team_of.get(r.club)]
        sid, how = None, ""
        ex_ = cand[cand.n == r.n]
        if len(ex_) == 1:
            sid, how = ex_.index[0], "exact"
        elif len(cand):
            names = cand.n.to_dict()
            b = process.extractOne(r.n, names, scorer=fuzz.token_set_ratio)
            b2 = process.extractOne(r.n, names, scorer=fuzz.WRatio)
            if b and b[1] >= 90 and b2 and b2[2] == b[2]:
                sid, how = b[2], "fuzzy"
            elif b2 and b2[1] >= 88:
                sid, how = b2[2], "wratio"
        if sid is None:
            g = sofa[sofa.n == r.n]
            if len(g) == 1:
                sid, how = g.index[0], "global"
        res.append((i, sid, how))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--notas", action="store_true", help="descarga también la nota por partido (lineups)")
    ap.add_argument("--refresh", action="store_true", help="vuelve a descargar las tablas de temporada")
    ap.add_argument("--outdir", default=str(FC / "Claude outputs"))
    a = ap.parse_args()
    c = Client()
    ex = excel_rows()
    print(f"{len(ex)} filas de las 5 grandes en los Excel")
    adv, notes = [], []
    for season, (_, year) in SEASONS.items():
        for liga, ut in LEAGUES.items():
            sid = season_id(c, ut, year)
            raw = pd.DataFrame(league_stats(c, ut, sid, a.refresh))
            for f in FIELDS:
                if f not in raw:
                    raw[f] = np.nan
            raw[FIELDS] = raw[FIELDS].apply(pd.to_numeric, errors="coerce")
            sofa = pd.concat([raw, metrics(raw)], axis=1)
            e = ex[(ex.season == season) & (ex.liga == liga)]
            mp = match_players(e, sofa)
            ok = collections.Counter(h or "sin_cruce" for _, _, h in mp)
            print(f"  {season} {liga}: {len(sofa)} jugadores SofaScore, cruce {dict(ok)}")
            for i, sid_, how in mp:
                row = e.loc[i, ["season", "source_sheet", "source_row", "name", "club", "liga", "liga_min"]].to_dict()
                row["match_how"] = how
                if sid_ is not None:
                    row.update(sofa.loc[sid_].drop(labels="n").to_dict())
                adv.append(row)
            if a.notas:
                pmap = {sofa.loc[s, "sofa_id"]: e.loc[i] for i, s, _ in mp if s is not None}
                evs = [x for x in season_events(c, ut, sid, a.refresh) if (x.get("status") or {}).get("type") == "finished"]
                print(f"    {len(evs)} partidos terminados; descargando alineaciones…")
                for x in evs:
                    lu = lineups(c, x["id"])
                    when = dt.datetime.fromtimestamp(x["startTimestamp"], dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
                    for side in ("home", "away"):
                        for p in (lu.get(side) or {}).get("players", []):
                            st = p.get("statistics") or {}
                            r = pmap.get(p["player"]["id"])
                            if r is None or not st.get("minutesPlayed"):
                                continue
                            notes.append(dict(season=season, source_sheet=r.source_sheet, source_row=r.source_row,
                                              name=r["name"], date=when, sofa_event=x["id"],
                                              home=side == "home", team=x[f"{side}Team"]["name"],
                                              opponent=x["awayTeam" if side == "home" else "homeTeam"]["name"],
                                              Min=st.get("minutesPlayed"), rating=st.get("rating"),
                                              xG=st.get("expectedGoals"), xA=st.get("expectedAssists")))
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(adv).to_csv(out / "avanzadas_big5.csv", index=False, encoding="utf-8-sig")
    print(f"avanzadas_big5.csv: {len(adv)} filas")
    if a.notas:
        pd.DataFrame(notes).to_csv(out / "notas_big5.csv", index=False, encoding="utf-8-sig")
        print(f"notas_big5.csv: {len(notes)} filas jugador-partido")


if __name__ == "__main__":
    main()
