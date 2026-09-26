"""Datos de cada equipo para el panel (páginas de club) y la portada.

Fuentes:
- FotMob /api/data/teams?id=: clasificación, formación y once del último partido, racha, calendario, estadio, entrenador,
  historial de entrenadores, títulos, puestos por temporada.
- FotMob estadísticas de equipo por liga (posesión, pase, juego directo, presión, xG…) → estilo de juego (percentil en su liga).
- Wikidata (P7223 = ID de Transfermarkt del club): fundación y apodos; Wikipedia en español: resumen de la historia.
- Google News (RSS): últimas noticias de cada equipo.

Uso (desde FC/):  python auxiliares/equipos/descargar_equipos.py [--refrescar 1]
Salida: auxiliares/equipos/equipos.json.gz
"""
import argparse
import collections
import gzip
import json
import re
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
FC = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "avanzadas"))
import descargar_fotmob_understat as FM  # noqa: E402

CACHE = HERE / "cache"
KM = {}  # metadatos TM de clubes (colores)
UA = {"User-Agent": "StatsFC/1.0 (uso personal; panel de scouting)"}
TEAMSTATS = {  # lista FotMob → clave corta
    "possession_percentage_team": "pos", "accurate_pass_team": "pas", "accurate_long_balls_team": "lng", "accurate_cross_team": "crz",
    "expected_goals_team": "xg", "expected_goals_conceded_team": "xga", "goals_team_match": "gf", "goals_conceded_team_match": "gc",
    "poss_won_att_3rd_team": "pre", "total_tackle_team": "ent", "interception_team": "int", "fk_foul_lost_team": "fal",
    "_set_piece_goals_team": "abp", "big_chance_team": "oca", "touches_in_opp_box_team": "are", "clean_sheet_team": "cs",
    "rating_team": "rat"}


def cached(name, fn, max_age_days=None):
    p = CACHE / name
    if p.exists() and (max_age_days is None or time.time() - p.stat().st_mtime < max_age_days * 86400):
        return json.loads(gzip.decompress(p.read_bytes()))
    v = fn()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(gzip.compress(json.dumps(v, ensure_ascii=False).encode()))
    return v


def league_team_stats(refresh):
    """{(season, liga): {team_id: {clave: valor}}} y {(season, liga): {nombre FotMob: team_id}}"""
    stats, names, lids = {}, {}, {}
    for season, (fm_season, fm_cal, _) in FM.SEASONS.items():
        for liga, (lid, _, cal) in FM.LEAGUES.items():
            info = cached(f"fm_league_{lid}.json.gz", lambda: FM.get(f"https://www.fotmob.com/api/data/leagues?id={lid}"), refresh)
            nm = FM.SPECIAL.get((liga, season)) or (fm_cal if cal else fm_season)
            nm = nm if isinstance(nm, (tuple, list)) else (nm,)
            bases = sorted({x["RelativePath"].rsplit("/", 1)[0] for x in info["stats"]["seasonStatLinks"] if x["Name"] in nm})
            st, nms = collections.defaultdict(dict), {}
            for base in bases[-1:]:  # la última fase (Liga MX: Clausura / Apertura en curso)
                for stat, key in TEAMSTATS.items():
                    d = cached(f"fm_{base.replace('/', '_')}_{stat}.json.gz",
                               lambda: FM.get(f"https://data.fotmob.com/{base}/{stat}.json"), refresh)
                    for x in ((d or {}).get("TopLists") or [{}])[0].get("StatList", []):
                        st[x["TeamId"]][key] = x.get("StatValue")
                        nms[x["ParticipantName"]] = x["TeamId"]
            stats[(season, liga)], names[(season, liga)] = dict(st), nms
            lids[liga] = lid
    return stats, names, lids


def team_json(tid, refresh):
    return cached(f"team_{tid}.json.gz", lambda: FM.get(f"https://www.fotmob.com/api/data/teams?id={tid}"), refresh)


def _fx(f, tid):
    st = f.get("status") or {}
    h, a = f.get("home") or {}, f.get("away") or {}
    return [(st.get("utcTime") or "")[:10], (f.get("tournament") or {}).get("name"), h.get("name"), a.get("name"),
            st.get("scoreStr") if st.get("finished") else None, 1 if h.get("id") == tid else 0, f.get("result"), f.get("id"),
            h.get("id"), a.get("id")]


def resumen_equipo(d, tid):
    ov, hi, sq = d.get("overview") or {}, d.get("history") or {}, d.get("squad") or {}
    det = d.get("details") or {}
    v = ov.get("venue") or {}
    pairs = dict((v.get("statPairs") or []))
    coach = next((m for g in sq.get("squad") or [] if g.get("title") == "coach" for m in g.get("members") or []), {})
    ll = ov.get("lastLineupStats") or {}
    starters = [[p.get("name"), (p.get("verticalLayout") or {}).get("x"), (p.get("verticalLayout") or {}).get("y"), p.get("shirtNumber"),
                 (p.get("performance") or {}).get("rating"), p.get("id")] for p in ll.get("starters") or []]
    form = [[x.get("resultString"), x.get("score"), (x.get("tooltipText") or {}).get("homeTeam"), (x.get("tooltipText") or {}).get("awayTeam"),
             ((x.get("date") or {}).get("utcTime") or "")[:10], x.get("tournamentName")] for x in ov.get("teamForm") or []]
    fixtures = ((d.get("fixtures") or {}).get("allFixtures") or {}).get("fixtures") or []
    done = [f for f in fixtures if (f.get("status") or {}).get("finished")][-12:]
    nxt = [f for f in fixtures if not (f.get("status") or {}).get("finished") and not (f.get("status") or {}).get("cancelled")][:6]
    trophies = [[t.get("name"), t.get("won"), t.get("runnerup"), t.get("seasonsWon"), t.get("seasonsRunnerup"), t.get("leagueId")]
                for t in hi.get("trophyList") or []]
    ranks = [[r.get("seasonName"), r.get("tournamentName"), r.get("position"), r.get("numberOfTeams"), (r.get("stats") or {}).get("points")]
             for r in ((hi.get("historicalTableData") or {}).get("ranks") or [])]
    coaches = [[c.get("name"), c.get("season"), c.get("leagueName"), c.get("win"), c.get("draw"), c.get("loss"), c.get("pointsPerGame")]
               for c in (ov.get("coachHistory") or hi.get("coachHistory") or [])][-12:]
    tbl = None
    for t in ov.get("table") or []:
        dt = t.get("data") or {}
        rows = ((dt.get("table") or {}).get("all")) or []
        if not rows and dt.get("tables"):  # ligas con grupos/fases
            rows = next((((x.get("table") or {}).get("all")) for x in dt["tables"] if any(r.get("id") == tid for r in ((x.get("table") or {}).get("all") or []))), [])
        if rows:
            tbl = {"lid": dt.get("leagueId"), "name": dt.get("leagueName"),
                   "legend": [[l.get("title"), l.get("color"), l.get("indices")] for l in dt.get("legend") or []],
                   "rows": [[r.get("idx"), r.get("name"), r.get("id"), r.get("played"), r.get("wins"), r.get("draws"), r.get("losses"),
                             r.get("scoresStr"), r.get("goalConDiff"), r.get("pts"), r.get("qualColor")] for r in rows]}
            break
    trd = ((ov.get("transfers") or {}).get("data")) or {}

    def tr(x):
        fee = x.get("fee") or {}
        return [x.get("name"), x.get("playerId"), (x.get("transferDate") or "")[:10], x.get("fromClub"), x.get("fromClubId"), x.get("toClub"),
                x.get("toClubId"), fee.get("feeText"), fee.get("value"), 1 if x.get("onLoan") else 0, (x.get("position") or {}).get("label"),
                x.get("marketValue")]
    transfers = {"in": [tr(x) for x in trd.get("Players in") or []], "out": [tr(x) for x in trd.get("Players out") or []]}
    return {"fm": tid, "name": det.get("name"), "tr": transfers, "short": det.get("shortName"), "country": det.get("country"),
            "league": det.get("primaryLeagueName"), "lid": det.get("primaryLeagueId"),
            "venue": [(v.get("widget") or {}).get("name"), (v.get("widget") or {}).get("city"), pairs.get("Capacity"), pairs.get("Opened"), pairs.get("Surface")],
            "coach": [coach.get("name"), coach.get("age"), coach.get("cname")] if coach else None,
            "formation": ll.get("formation"), "xi": starters, "form": form,
            "done": [_fx(f, tid) for f in done], "next": [_fx(f, tid) for f in nxt],
            "trophies": trophies, "ranks": ranks[-25:], "coaches": coaches, "table": tbl}


def wikidata_clubs(tm_ids):
    p = HERE / "cache_wikidata_clubs.json"
    have = json.loads(p.read_text()) if p.exists() else {}
    need = [i for i in tm_ids if i not in have]
    for k in range(0, len(need), 200):
        chunk = need[k:k + 200]
        q = ("SELECT ?tm ?inc ?nick ?es WHERE { VALUES ?tm {" + " ".join(f'"{i}"' for i in chunk) + "} ?item wdt:P7223 ?tm . "
             "OPTIONAL{?item wdt:P571 ?inc} OPTIONAL{?item wdt:P1449 ?nick FILTER(lang(?nick)=\"es\")} "
             "OPTIONAL{?es schema:about ?item; schema:isPartOf <https://es.wikipedia.org/>} }")
        for intento in range(5):
            r = requests.post("https://query.wikidata.org/sparql", data={"query": q}, timeout=120,
                              headers={**UA, "Accept": "application/sparql-results+json"})
            if r.status_code == 200:
                break
            time.sleep(10 * (intento + 1))
        for i in chunk:
            have.setdefault(i, {})
        for b in r.json()["results"]["bindings"] if r.status_code == 200 else []:
            d = have[b["tm"]["value"]]
            if "inc" in b:
                d["inc"] = b["inc"]["value"][:10]
            if "nick" in b:
                d.setdefault("nick", [])
                if b["nick"]["value"] not in d["nick"]:
                    d["nick"].append(b["nick"]["value"])
            if "es" in b:
                d["es"] = urllib.parse.unquote(b["es"]["value"].rsplit("/wiki/", 1)[-1])
        p.write_text(json.dumps(have, ensure_ascii=False))
        time.sleep(1)
    return have


def wiki_extract(title, refresh):
    def fetch():
        r = requests.get("https://es.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title), headers=UA, timeout=30)
        return (r.json().get("extract") if r.status_code == 200 else None)
    return cached(f"wiki_{re.sub(r'[^A-Za-z0-9]+', '_', title)[:80]}.json.gz", fetch, None if not refresh else 30)


def noticias(q, n=8, max_age=1):
    def fetch():
        url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q, "hl": "es", "gl": "ES", "ceid": "ES:es"})
        r = requests.get(url, headers=UA, timeout=30)
        if r.status_code != 200:
            return []
        out = []
        for it in ET.fromstring(r.content).findall(".//item")[:n]:
            out.append([it.findtext("title"), it.findtext("link"), it.findtext("source"), it.findtext("pubDate")])
        return out
    return cached(f"news_{re.sub(r'[^A-Za-z0-9]+', '_', q)[:80]}.json.gz", fetch, max_age)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refrescar", type=float, default=1, help="días de validez de la caché de FotMob y noticias")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    ref = a.refrescar
    stats, names, lids = league_team_stats(ref)
    # club del Excel → equipo FotMob (por el nombre de equipo con que FotMob lista a sus jugadores) y → club TM
    av = pd.read_csv(FC / "Claude outputs" / "avanzadas.csv", usecols=["season", "club", "liga", "sofa_team"]).dropna()
    fm_of = {}
    for (season, liga, club), g in av.groupby(["season", "liga", "club"]):
        tid = names.get((season, liga), {}).get(g.sofa_team.mode().iloc[0])
        if tid and (club not in fm_of or season == "2026-27"):
            fm_of[club] = (tid, liga)
    pt = pd.read_csv(FC / "Claude outputs" / "partidos_TM.csv", usecols=["excel_club", "club_id"]).dropna()
    tm_of = pt.groupby("excel_club").club_id.agg(lambda s: str(int(s.mode().iloc[0]))).to_dict()
    print(f"{len(fm_of)} clubes enlazados con FotMob")
    wd = wikidata_clubs(sorted({tm_of[c] for c in fm_of if c in tm_of}))
    kmp = HERE.parent / "tmapi" / "cache" / "meta_clubs.json.gz"
    KM.update(json.loads(gzip.decompress(kmp.read_bytes())) if kmp.exists() else {})

    def one(item):
        club, (tid, liga) = item
        try:
            d = team_json(tid, ref)
        except Exception as e:  # noqa: BLE001
            print("  error", club, e)
            return club, None
        if not d:
            return club, None
        r = resumen_equipo(d, tid)
        r["liga"] = liga
        r["tm"] = tm_of.get(club)
        w = wd.get(r["tm"] or "", {})
        r["founded"], r["nick"] = w.get("inc"), (w.get("nick") or [])[:4]
        cols = ((((KM.get(r["tm"] or "") or {}).get("baseDetails") or {}).get("superiorClub") or {}).get("colors")) or {}
        r["kit"] = [cols.get("firstColor"), cols.get("secondColor"), cols.get("thirdColor")]
        r["wiki"] = w.get("es")
        r["about"] = wiki_extract(w["es"], ref) if w.get("es") else None
        r["style"] = {s: stats.get((s, liga), {}).get(tid) for s in FM.SEASONS}
        r["news"] = noticias(f'"{r["name"]}" fútbol', 8, ref)
        return club, r

    out = {}
    with ThreadPoolExecutor(a.workers) as ex:
        for n, (club, r) in enumerate(ex.map(one, sorted(fm_of.items())), 1):
            if r:
                out[club] = r
            if n % 50 == 0:
                print(f"  {n}/{len(fm_of)}", flush=True)
    # percentiles de estilo dentro de cada liga-temporada
    pct = {}
    for (season, liga), teams in stats.items():
        df = pd.DataFrame.from_dict(teams, orient="index")
        if len(df):
            pct[(season, liga)] = (df.rank(pct=True) * 100).round().to_dict(orient="index")
    for club, r in out.items():
        r["style_pct"] = {s: pct.get((s, r["liga"]), {}).get(r["fm"]) for s in FM.SEASONS}
    (HERE / "equipos.json.gz").write_bytes(gzip.compress(json.dumps({"clubs": out, "leagues": lids}, ensure_ascii=False,
                                                                     separators=(",", ":"), default=str).encode()))
    (FC / "Panel_FC" / "equipos.js").write_text("window.FC_TEAMS=" + json.dumps(out, ensure_ascii=False, separators=(",", ":"), default=str) + ";\n",
                                                encoding="utf-8")
    print(f"{len(out)} equipos · con fundación {sum(1 for r in out.values() if r.get('founded'))} · con noticias "
          f"{sum(1 for r in out.values() if r.get('news'))}")


if __name__ == "__main__":
    main()
