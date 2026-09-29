"""Selecciones nacionales y competiciones de selecciones.

- Competiciones (FotMob): Mundial, Eurocopa, Nations League A-D, Copa América, Copa Oro, Copa África, Copa Asia,
  Nations League CONCACAF, Finalissima, Juegos Olímpicos y clasificatorias. Cada una en Panel_FC/ligas/h_<id>.js
  (mismo formato que las ligas + cuadro de eliminatorias "po" y próximos partidos "up").
- Selecciones (FotMob, las 211 del ranking FIFA): convocatoria, partidos, palmarés, entrenadores, estadio, colores.
  Una por archivo: Panel_FC/sel/s_<id>.js. Índice ligero en Panel_FC/selecciones.js.
- Fotos con la camiseta de la selección:
  * FIFA: plantillas del Mundial 2026 (48 selecciones).
  * UEFA: jugadores de la Nations League 2026-27 (las 54 selecciones europeas).
  Se enlazan con los jugadores de FotMob por fecha de nacimiento + nombre y se guardan por id FotMob (el panel las
  muestra en la selección y en la ficha del jugador, junto a la del club).

Uso (desde FC/):  python auxiliares/selecciones/descargar_selecciones.py [--refrescar 3]
"""
import argparse
import gzip
import json
import re
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
FC = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "avanzadas"))
sys.path.insert(0, str(HERE.parent / "ligas"))
import descargar_fotmob_understat as FM  # noqa: E402
import descargar_historia_ligas as HL  # noqa: E402

CACHE = HERE / "cache"
OUT = FC / "Panel_FC"

# id FotMob -> (nombre en español, grupo, máximo de temporadas a guardar)
COMPS = {
    77: ("Mundial", "Mundiales y Eurocopas", None),
    50: ("Eurocopa", "Mundiales y Eurocopas", None),
    44: ("Copa América", "Torneos continentales", None),
    298: ("Copa Oro", "Torneos continentales", None),
    289: ("Copa África", "Torneos continentales", None),
    290: ("Copa Asia", "Torneos continentales", None),
    10304: ("Finalissima", "Torneos continentales", None),
    9806: ("Nations League A", "Nations League", None),
    9807: ("Nations League B", "Nations League", None),
    9808: ("Nations League C", "Nations League", None),
    9809: ("Nations League D", "Nations League", None),
    9821: ("Nations League CONCACAF", "Nations League", None),
    10195: ("Clasificación Mundial · UEFA", "Clasificatorias", 3),
    10199: ("Clasificación Mundial · CONMEBOL", "Clasificatorias", 3),
    10198: ("Clasificación Mundial · CONCACAF", "Clasificatorias", 3),
    10197: ("Clasificación Mundial · AFC", "Clasificatorias", 3),
    10196: ("Clasificación Mundial · CAF", "Clasificatorias", 3),
    10200: ("Clasificación Mundial · OFC", "Clasificatorias", 3),
    10201: ("Repesca intercontinental", "Clasificatorias", 3),
    10607: ("Clasificación Eurocopa", "Clasificatorias", 3),
    10608: ("Clasificación Copa África", "Clasificatorias", 3),
    66: ("Juegos Olímpicos", "Otros", None),
}
WIKI = {77: "Copa_Mundial_de_Fútbol", 50: "Eurocopa", 44: "Copa_América", 298: "Copa_de_Oro_de_la_Concacaf",
        289: "Copa_Africana_de_Naciones", 290: "Copa_Asiática", 9806: "Liga_de_Naciones_de_la_UEFA",
        9821: "Liga_de_Naciones_de_la_Concacaf", 10304: "Copa_de_Campeones_Conmebol-UEFA",
        66: "Fútbol_en_los_Juegos_Olímpicos"}
POS = {"keepers": "POR", "defenders": "DEF", "midfielders": "MED", "attackers": "DEL"}


def cached(name, fn, max_age_days=None):
    p = CACHE / name
    if p.exists() and (max_age_days is None or time.time() - p.stat().st_mtime < max_age_days * 86400):
        return json.loads(gzip.decompress(p.read_bytes()))
    v = fn()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(gzip.compress(json.dumps(v, ensure_ascii=False).encode()))
    return v


def js(path, var, key, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    head = f"window.{var}=window.{var}||{{}};window.{var}[{json.dumps(str(key))}]=" if key is not None else f"window.{var}="
    path.write_text(head + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")


def nrm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z ]+", " ", s).split()


# ---------------------------------------------------------------- competiciones
def competiciones(ref):
    out = {}

    def one(item):
        lid, (nombre, grupo, mx) = item
        try:
            d = HL.liga(lid, nombre, ref, max_seasons=mx)
        except Exception as e:  # noqa: BLE001
            return lid, None, str(e)
        d["wiki"] = HL.wiki(WIKI[lid]) if lid in WIKI else None
        d["intl"] = 1
        js(OUT / "ligas" / f"h_{lid}.js", "FC_LH", lid, d)
        return lid, d, f"{len(d['champs'])} ediciones · {len(d['hist'])} con datos"
    with ThreadPoolExecutor(3) as ex:
        for lid, d, msg in ex.map(one, COMPS.items()):
            print(f"  {COMPS[lid][0]}: {msg}", flush=True)
            if d:
                cur = d["hist"][0] if d["hist"] else {}
                out[lid] = {"n": COMPS[lid][0], "g": COMPS[lid][1], "s": cur.get("s"),
                            "champ": d["champs"][0][1:3] if d["champs"] else None,
                            "teams": sorted({r[2] for t in cur.get("tables", []) for r in t["all"]} |
                                            {x for _, ms in cur.get("po", []) for m in ms for x in m[:2] if x})}
    return out


# ---------------------------------------------------------------- selecciones
def ranking(ref):
    t = cached("team_6720.json.gz", lambda: FM.get("https://www.fotmob.com/api/data/teams?id=6720"), ref) or {}
    r = ((t.get("overview") or {}).get("fifaRanking") or {})
    return r.get("rankings", {}).get("ranks", []), r.get("updated")


def seleccion(tid, ref):
    t = cached(f"team_{tid}.json.gz", lambda: FM.get(f"https://www.fotmob.com/api/data/teams?id={tid}"), ref) or {}
    if not t:
        return None
    det, ov = t.get("details") or {}, t.get("overview") or {}
    # código FIFA (ESP, ARG...) para el nombre en español: sale de los jugadores destacados o del último once
    code = None
    for grp in ((ov.get("topPlayers") or {}).values() if isinstance(ov.get("topPlayers"), dict) else []):
        for p in (grp.get("players") if isinstance(grp, dict) else None) or []:
            if p.get("teamId") == tid and p.get("ccode"):
                code = p["ccode"]
                break
        if code:
            break
    lls = ov.get("lastLineupStats") or {}
    if not code:
        for p in (lls.get("starters") or []):
            if p.get("countryCode"):
                code = p["countryCode"]
                break
    squad, coach = [], None
    for g in ((t.get("squad") or {}).get("squad") or []):
        for m in g.get("members") or []:
            if g.get("title") == "coach":
                coach = [m.get("id"), m.get("name")]
                continue
            squad.append([m.get("id"), m.get("name"), POS.get(g.get("title"), ""), m.get("shirtNumber"), m.get("cname"), m.get("ccode"),
                          m.get("age"), m.get("dateOfBirth"), m.get("goals"), m.get("assists"), m.get("rating"), m.get("injury") and 1, m.get("transferValue")])
    fx = []
    for m in (((t.get("fixtures") or {}).get("allFixtures") or {}).get("fixtures") or []):
        st, h, a = m.get("status") or {}, m.get("home") or {}, m.get("away") or {}
        tn = m.get("tournament") or {}
        fx.append([m.get("id"), (st.get("utcTime") or "")[:16], tn.get("name"), tn.get("leagueId"), h.get("id"), h.get("name"), a.get("id"), a.get("name"),
                   h.get("score") if st.get("finished") else None, a.get("score") if st.get("finished") else None, 1 if st.get("finished") else 0,
                   (st.get("reason") or {}).get("short") if isinstance(st.get("reason"), dict) else None])
    hist = t.get("history") or {}
    troph = [[x.get("name"), x.get("leagueId"), x.get("won"), x.get("runnerup"), x.get("seasonsWon"), x.get("seasonsRunnerup")]
             for x in (hist.get("trophyList") or [])]
    ch = {}
    for c in (ov.get("coachHistory") or hist.get("coachHistory") or []):
        k = c.get("id") or c.get("name")
        x = ch.setdefault(k, {"id": c.get("id"), "n": c.get("name"), "s": [], "w": 0, "d": 0, "l": 0})
        x["s"].append(str(c.get("season")))
        for f in ("w", "d", "l"):
            x[f] += c.get({"w": "win", "d": "draw", "l": "loss"}[f]) or 0
    coaches = [[x["id"], x["n"], x["s"][0], x["s"][-1], x["w"], x["d"], x["l"]] for x in ch.values()]
    ven = (ov.get("venue") or {})
    vw, sp = ven.get("widget") or {}, dict((ven.get("statPairs") or []))
    tops = {}
    for k, grp in (ov.get("topPlayers") or {}).items():
        ps = (grp.get("players") if isinstance(grp, dict) else None) or []
        if ps:
            tops[k] = [[p.get("id"), p.get("name"), p.get("value")] for p in ps[:3]]
    return {"id": tid, "name": det.get("name"), "code": code, "rank": (det.get("fifaRanking") or None),
            "colors": (ov.get("teamColors") or {}).get("lightMode"), "coach": coach, "squad": squad, "fx": fx, "troph": troph,
            "coaches": coaches, "venue": [vw.get("name"), vw.get("city"), sp.get("Capacity"), sp.get("Opened")] if vw else None,
            "tops": tops, "form": [[f.get("resultString"), (f.get("tooltipText") or {}).get("homeTeamId"), (f.get("tooltipText") or {}).get("awayTeamId"),
                                    f.get("score"), (f.get("date") or {}).get("utcTime", "")[:10], f.get("tournamentName")] for f in (ov.get("teamForm") or [])],
            "lineup": [lls.get("formation"), [[p.get("id"), p.get("name"), p.get("shirtNumber")] for p in (lls.get("starters") or [])]] if lls else None}


# ---------------------------------------------------------------- fotos con la camiseta de la selección
def fotos_fifa(ref):
    """Plantillas del Mundial 2026 (FIFA): [código FIFA, nombre, fecha nac., url]."""
    ua = {"User-Agent": "Mozilla/5.0"}
    cal = cached("fifa_wc2026_cal.json.gz", lambda: requests.get(
        "https://api.fifa.com/api/v3/calendar/matches?idCompetition=17&idSeason=285023&language=es&count=200", headers=ua, timeout=60).json(), ref)
    teams = {}
    for m in cal.get("Results") or []:
        for s in ("Home", "Away"):
            x = m.get(s) or {}
            if x.get("IdTeam"):
                teams[x["IdTeam"]] = x.get("IdCountry")
    out = []
    for tid in teams:
        sq = cached(f"fifa_sq_{tid}.json.gz", lambda tid=tid: requests.get(
            f"https://api.fifa.com/api/v3/teams/{tid}/squad?idCompetition=17&idSeason=285023&language=es", headers=ua, timeout=60).json(), ref) or {}
        for p in sq.get("Players") or []:
            url = (p.get("PlayerPicture") or {}).get("PictureUrl")
            if url:
                out.append([p.get("IdCountry") or sq.get("IdCountry"), (p.get("PlayerName") or [{}])[0].get("Description"), (p.get("BirthDate") or "")[:10],
                            url + "?io=transform:fill,width:320,height:320", "FIFA · Mundial 2026"])
    return out


def fotos_uefa(ref):
    """Jugadores de la Nations League 2026-27 (UEFA): [código, nombre, fecha nac., url]."""
    def fetch():
        allp, off = [], 0
        while True:
            r = requests.get(f"https://comp.uefa.com/v2/players?competitionId=2014&seasonYear=2027&limit=500&offset={off}", timeout=60,
                             headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
            x = r.json() if r.ok else []
            if not isinstance(x, list) or not x:
                break
            allp += x
            off += 500
            if len(x) < 500:
                break
        return allp
    ps = cached("uefa_unl2027_players.json.gz", fetch, ref) or []
    return [[p.get("countryCode"), p.get("internationalName"), (p.get("birthDate") or "")[:10], p.get("imageUrl"), "UEFA · Nations League 2026-27"]
            for p in ps if p.get("imageUrl")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refrescar", type=float, default=3)
    ap.add_argument("--sin-competiciones", action="store_true")
    a = ap.parse_args()
    ref = a.refrescar
    comps = {}
    if not a.sin_competiciones:
        print("Competiciones de selecciones…", flush=True)
        comps = competiciones(ref)
    ranks, upd = ranking(ref)
    ids = [r["id"] for r in ranks]
    extra = {t for c in comps.values() for t in c["teams"]} - set(ids)
    ids += sorted(extra)
    print(f"Selecciones: {len(ids)}…", flush=True)
    teams = {}

    def one(tid):
        try:
            return tid, seleccion(tid, ref)
        except Exception as e:  # noqa: BLE001
            print(f"  {tid}: {e}", flush=True)
            return tid, None
    with ThreadPoolExecutor(4) as ex:
        for tid, d in ex.map(one, ids):
            if d:
                teams[tid] = d

    # fotos: enlazar por fecha de nacimiento + apellido con los convocados de FotMob
    print("Fotos con la camiseta de la selección…", flush=True)
    fotos = []
    for fn in (fotos_fifa, fotos_uefa):
        try:
            fotos += fn(ref)
        except Exception as e:  # noqa: BLE001
            print(f"  {fn.__name__}: {e}", flush=True)
    by_dob = {}
    for f in fotos:
        by_dob.setdefault(f[2], []).append(f)
    ph = {}
    for d in teams.values():
        for m in d["squad"]:
            dob = (m[7] or "")[:10]
            if not dob or dob not in by_dob:
                continue
            n = set(nrm(m[1]))
            best = None
            for f in by_dob[dob]:
                if n & set(nrm(f[1])) and (not best or f[4].startswith("FIFA")):
                    best = f
            if best and m[0]:
                ph[str(m[0])] = [best[3], d["id"], best[4]]
    print(f"  {len(fotos)} fotos descargadas · {len(ph)} enlazadas con jugadores de FotMob", flush=True)

    rk = {r["id"]: r for r in ranks}
    index = {"updated": upd, "comps": comps, "photos": ph,
             "teams": {tid: [d["name"], d["code"], (rk.get(tid) or {}).get("rank"), (rk.get(tid) or {}).get("totalPoints"),
                             (rk.get(tid) or {}).get("previousRank"), d["colors"], len(d["squad"])] for tid, d in teams.items()}}
    for tid, d in teams.items():
        js(OUT / "sel" / f"s_{tid}.js", "FC_NT", tid, d)
    js(OUT / "selecciones.js", "FC_NTI", None, index)
    print(f"Listo: {len(teams)} selecciones, {len(comps)} competiciones.")


if __name__ == "__main__":
    main()
