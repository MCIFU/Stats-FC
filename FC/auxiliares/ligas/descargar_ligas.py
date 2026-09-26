"""Páginas de liga y partidos del panel (FotMob).

Por liga (las 26 de FM.LEAGUES): clasificación (con colores de Champions/descenso…), todos los partidos de la temporada,
máximos goleadores/asistentes y otras listas de jugadores, estadísticas de equipo (incluida la asistencia de público)
y traspasos de la liga. Por partido terminado (ligas + portada + calendarios de equipo): goles con minuto, autor y asistente.
Además, id de FotMob de los jugadores (plantillas y listas) → foto recortada en PNG transparente.

Uso (desde FC/):  python auxiliares/ligas/descargar_ligas.py [--refrescar 0.5]
Salidas: FC/Panel_FC/ligas.js, FC/Panel_FC/goles.js, auxiliares/ligas/fotmob_jugadores.json
"""
import argparse
import gzip
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
FC = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "avanzadas"))
import descargar_fotmob_understat as FM  # noqa: E402

CACHE = HERE / "cache"
PLAYER_STATS = {"goals": "Goles", "goal_assist": "Asistencias", "_goals_and_goal_assist": "Goles + asistencias", "rating": "Nota FotMob",
                "expected_goals": "xG", "expected_assists": "xA", "big_chance_created": "Ocasiones claras creadas", "clean_sheet": "Porterías a cero",
                "yellow_card": "Amarillas", "red_card": "Rojas", "mins_played": "Minutos"}
TEAM_STATS = {"home_attendance_team": "Asistencia media", "possession_percentage_team": "Posesión", "goals_team_match": "Goles por partido",
              "goals_conceded_team_match": "Encajados por partido", "expected_goals_team": "xG", "expected_goals_conceded_team": "xG en contra",
              "clean_sheet_team": "Porterías a cero", "rating_team": "Nota FotMob", "total_yel_card_team": "Amarillas", "total_red_card_team": "Rojas",
              "fk_foul_lost_team": "Faltas por partido", "corner_taken_team": "Córners"}


def cached(name, fn, max_age_days=None):
    p = CACHE / name
    if p.exists() and (max_age_days is None or time.time() - p.stat().st_mtime < max_age_days * 86400):
        return json.loads(gzip.decompress(p.read_bytes()))
    v = fn()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(gzip.compress(json.dumps(v, ensure_ascii=False).encode()))
    return v


def stat_list(url, ref):
    name = "st_" + url.split("/stats/", 1)[-1].replace("/", "_")
    d = cached(name + ".gz", lambda: FM.get(url), ref)
    return ((d or {}).get("TopLists") or [{}])[0].get("StatList", [])


def resumen_liga(lid, liga, ref):
    d = cached(f"league_{lid}.json.gz", lambda: FM.get(f"https://www.fotmob.com/api/data/leagues?id={lid}"), ref) or {}
    det = d.get("details") or {}
    tables = []
    for t in d.get("table") or []:
        td = t.get("data") or {}
        blocks = [td] if (td.get("table") or {}).get("all") else (td.get("tables") or [])
        for b in blocks:
            rows = ((b.get("table") or {}).get("all")) or []
            if not rows:
                continue
            tables.append({"name": b.get("leagueName") or td.get("leagueName"),
                           "legend": [[l.get("title"), l.get("color"), l.get("indices")] for l in (b.get("legend") or td.get("legend") or [])],
                           "rows": [[r.get("idx"), r.get("name"), r.get("id"), r.get("played"), r.get("wins"), r.get("draws"), r.get("losses"),
                                     r.get("scoresStr"), r.get("goalConDiff"), r.get("pts"), r.get("qualColor"), r.get("deduction")] for r in rows]})
    matches = []
    for m in ((d.get("fixtures") or {}).get("allMatches") or []):
        st, h, a = m.get("status") or {}, m.get("home") or {}, m.get("away") or {}
        sc = st.get("scoreStr") if st.get("finished") or st.get("started") else None
        matches.append([int(m["id"]), m.get("round"), st.get("utcTime"), h.get("name"), int(h["id"]) if h.get("id") else None,
                        a.get("name"), int(a["id"]) if a.get("id") else None, sc, 1 if st.get("finished") else 0, 1 if st.get("cancelled") else 0])
    players, teams = {}, {}
    for x in ((d.get("stats") or {}).get("players") or []):
        key = (x.get("participant") or {}).get("stat", {}).get("name") or (x.get("topThree") or [{}])[0].get("stat", {}).get("name")
        if key in PLAYER_STATS and x.get("fetchAllUrl"):
            L = stat_list(x["fetchAllUrl"], ref)[:40]
            players[key] = [[p.get("ParticiantId"), p.get("ParticipantName"), p.get("TeamId"), p.get("TeamName"), p.get("StatValue"),
                             p.get("SubStatValue"), p.get("MatchesPlayed")] for p in L]
    for x in ((d.get("stats") or {}).get("teams") or []):
        key = (x.get("participant") or {}).get("stat", {}).get("name")
        if key in TEAM_STATS and x.get("fetchAllUrl"):
            teams[key] = [[t.get("TeamId"), t.get("ParticipantName"), t.get("StatValue"), t.get("SubStatValue")] for t in stat_list(x["fetchAllUrl"], ref)]
    transfers = []
    for t in ((d.get("transfers") or {}).get("data") or []):
        fee = t.get("fee") or {}
        transfers.append([t.get("name"), t.get("playerId"), (t.get("transferDate") or "")[:10], t.get("fromClub"), t.get("fromClubId"),
                          t.get("toClub"), t.get("toClubId"), fee.get("feeText"), fee.get("value") or t.get("amountEuroEstimated"), 1 if t.get("onLoan") else 0,
                          (t.get("position") or {}).get("label"), t.get("marketValue"), 1 if t.get("contractExtension") else 0])
    season = (d.get("allAvailableSeasons") or [None])[0]
    return {"lid": lid, "liga": liga, "name": det.get("name"), "country": det.get("country"), "season": season, "tables": tables,
            "matches": matches, "players": players, "teams": teams, "transfers": transfers}


def goles(mid, ref):
    def fetch():
        m = FM.get(f"https://www.fotmob.com/api/data/matchDetails?matchId={mid}") or {}
        ev = ((((m.get("content") or {}).get("matchFacts") or {}).get("events") or {}).get("events")) or []
        out = []
        for e in ev:
            if e.get("type") != "Goal" or e.get("isPenaltyShootoutEvent"):
                continue
            p = e.get("player") or {}
            flag = "og" if e.get("ownGoal") else ("pen" if (e.get("goalDescriptionKey") or "").startswith("penalty") or e.get("suffixKey") == "penalty" else "")
            out.append([e.get("time"), e.get("overloadTime"), 1 if e.get("isHome") else 0, p.get("name") or e.get("nameStr"), p.get("id"),
                        e.get("assistInput"), e.get("assistPlayerId"), flag])
        gen = m.get("general") or {}
        info = ((m.get("content") or {}).get("matchFacts") or {}).get("infoBox") or {}
        return {"g": out, "att": info.get("Attendance"), "ref": (info.get("Referee") or {}).get("text"),
                "stadium": (info.get("Stadium") or {}).get("name"), "round": gen.get("leagueRoundName")}
    return cached(f"m/{mid}.json.gz", fetch, None)  # un partido terminado no cambia


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refrescar", type=float, default=0.5)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    ligas = {}
    for liga, (lid, _, _) in FM.LEAGUES.items():
        try:
            ligas[str(lid)] = resumen_liga(lid, liga, a.refrescar)
            print(f"  {liga}: {len(ligas[str(lid)]['matches'])} partidos, {len(ligas[str(lid)]['transfers'])} traspasos", flush=True)
        except Exception as e:  # noqa: BLE001
            print("  error", liga, e)
    # partidos terminados cuyos goles hay que tener: ligas + portada + calendarios de equipo
    mids = {m[0] for L in ligas.values() for m in L["matches"] if m[8]}
    home = FC / "Panel_FC" / "portada.js"
    if home.exists():
        h = json.loads(home.read_text(encoding="utf-8")[len("window.FC_HOME="):-2])
        mids |= {m[11] for m in h.get("matches", []) if len(m) > 11 and m[11] and m[8]}
    eq = HERE.parent / "equipos" / "equipos.json.gz"
    if eq.exists():
        E = json.loads(gzip.decompress(eq.read_bytes()))["clubs"]
        mids |= {f[7] for t in E.values() for f in (t.get("done") or []) if len(f) > 7 and f[7]}
    print(f"{len(mids)} partidos terminados → goles", flush=True)
    G = {}
    with ThreadPoolExecutor(a.workers) as ex:
        for n, (mid, g) in enumerate(ex.map(lambda i: (i, goles(i, a.refrescar)), sorted(mids)), 1):
            if g:
                G[str(mid)] = g
            if n % 500 == 0:
                print(f"  {n}/{len(mids)}", flush=True)
    # jugadores de FotMob (id → nombre, equipo) para las fotos
    fmp = {}
    for L in ligas.values():
        for lst in L["players"].values():
            for p in lst:
                if p[0]:
                    fmp[str(p[0])] = [p[1], p[2]]
    for tj in (HERE.parent / "equipos" / "cache").glob("team_*.json.gz"):
        try:
            d = json.loads(gzip.decompress(tj.read_bytes()))
        except Exception:  # noqa: BLE001
            continue
        tid = (d.get("details") or {}).get("id")
        for grp in ((d.get("squad") or {}).get("squad") or []):
            for m in grp.get("members") or []:
                if m.get("id") and grp.get("title") != "coach":
                    fmp[str(m["id"])] = [m.get("name"), tid]
    for mid, g in G.items():
        for x in g["g"]:
            if x[4]:
                fmp.setdefault(str(x[4]), [x[3], None])
    (HERE / "fotmob_jugadores.json").write_text(json.dumps(fmp, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    dump = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"), default=str)
    lim = HERE.parent / "laliga" / "limites_laliga.json"
    extra = {"limits": json.loads(lim.read_text(encoding="utf-8")) if lim.exists() else None}
    (FC / "Panel_FC" / "ligas.js").write_text("window.FC_LEAGUES=" + dump({"ligas": ligas, **extra}) + ";\n", encoding="utf-8")
    (FC / "Panel_FC" / "goles.js").write_text("window.FC_GOALS=" + dump(G) + ";\n", encoding="utf-8")
    print(f"ligas: {len(ligas)} · goles de {len(G)} partidos · {len(fmp)} jugadores FotMob")


if __name__ == "__main__":
    main()
