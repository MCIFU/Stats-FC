"""Historia y estadísticas ampliadas de cada liga (FotMob + Wikipedia). Un archivo por liga que el panel carga al abrirla.

- Campeón y subcampeón de toda la historia (FotMob "seasons": LaLiga desde 1929, Premier desde 1888).
- Las temporadas que ofrece FotMob (≈ desde 2010/11): clasificación completa con zonas (Champions, descenso…),
  todos los partidos (para ver la tabla de cualquier jornada) → top 3, ascendidos y descendidos de cada año.
- Temporada actual: clasificación de local y de visitante.
- Todas las listas de jugadores (37: goles, pases, disparos a puerta, regates, paradas…) y de equipos (29), hasta 100 por lista.
- Resumen de la liga en Wikipedia (español).

Uso (desde FC/):  python auxiliares/ligas/descargar_historia_ligas.py [--refrescar 0.5]
Salida: Panel_FC/ligas/h_<id>.js (window.FC_LH[id])
"""
import argparse
import json
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
FC = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "avanzadas"))
import descargar_fotmob_understat as FM  # noqa: E402
from descargar_ligas import cached  # noqa: E402

WIKI = {47: "Premier_League", 87: "Primera_División_de_España", 54: "Bundesliga", 55: "Serie_A", 53: "Ligue_1", 57: "Eredivisie",
        61: "Primeira_Liga", 64: "Scottish_Premiership", 71: "Superliga_de_Turquía", 40: "Primera_División_de_Bélgica",
        536: "Liga_Profesional_Saudí", 196: "Ekstraklasa", 230: "Liga_MX", 130: "Major_League_Soccer", 268: "Campeonato_Brasileño_de_Serie_A",
        112: "Primera_División_de_Argentina", 48: "EFL_Championship", 140: "Segunda_División_de_España", 86: "Serie_B",
        146: "2._Bundesliga", 135: "Superliga_de_Grecia", 46: "Superliga_de_Dinamarca", 69: "Superliga_de_Suiza",
        38: "Bundesliga_de_Austria", 223: "J1_League", 9080: "K_League_1",
        8968: "Primera_Federación", 9138: "Segunda_Federación", 108: "EFL_League_One", 109: "EFL_League_Two", 117: "National_League",
        110: "Ligue_2", 8970: "Championnat_National", 208: "3._Liga", 512: "Regionalliga", 147: "Serie_C"}


def rows(t):
    return [[r.get("idx"), r.get("name"), r.get("id"), r.get("played"), r.get("wins"), r.get("draws"), r.get("losses"),
             r.get("scoresStr"), r.get("goalConDiff"), r.get("pts")] for r in (t or [])]


def tables(d):
    out = []
    for t in d.get("table") or []:
        td = t.get("data") or {}
        blocks = [td] if (td.get("table") or {}).get("all") else (td.get("tables") or [])
        for b in blocks:
            tb = b.get("table") or {}
            if not tb.get("all"):
                continue
            out.append({"name": b.get("leagueName") or td.get("leagueName"),
                        "legend": [[l.get("title"), l.get("color"), l.get("indices")] for l in (b.get("legend") or td.get("legend") or [])],
                        "all": rows(tb.get("all")), "home": rows(tb.get("home")), "away": rows(tb.get("away"))})
    return out


def fixtures(d):
    out = []
    for m in ((d.get("fixtures") or {}).get("allMatches") or []):
        st, h, a = m.get("status") or {}, m.get("home") or {}, m.get("away") or {}
        if not st.get("finished"):
            continue
        sc = st.get("scoreStr") or ""
        try:
            hs, as_ = [int(x) for x in sc.replace(" ", "").split("-")[:2]]
        except ValueError:
            continue
        out.append([m.get("round"), (st.get("utcTime") or "")[:10], int(h["id"]) if h.get("id") else None, int(a["id"]) if a.get("id") else None, hs, as_])
    return out


def playoff(d):
    """Cuadro de eliminatorias (Mundial, Eurocopa...): [[ronda, [[local, visitante, goles L, goles V, ganador, penaltis?], ...]], ...]."""
    out = []
    for r in ((d.get("playoff") or {}).get("rounds") or []):
        ms = []
        for x in r.get("matchups") or []:
            pens = None
            for m in x.get("matches") or []:
                st = m.get("status") or {}
                pens = (st.get("reason") or {}).get("short") if isinstance(st.get("reason"), dict) else None
            ms.append([x.get("homeTeamId"), x.get("awayTeamId"), x.get("homeScore"), x.get("awayScore"), x.get("winner"),
                       x.get("homeTeam"), x.get("awayTeam"), pens])
        if ms:
            out.append([r.get("stage"), ms])
    return out


def upcoming(d, n=60):
    out = []
    for m in ((d.get("fixtures") or {}).get("allMatches") or []):
        st, h, a = m.get("status") or {}, m.get("home") or {}, m.get("away") or {}
        if st.get("finished") or st.get("cancelled"):
            continue
        out.append([m.get("round"), (st.get("utcTime") or "")[:16], int(h["id"]) if h.get("id") else None, int(a["id"]) if a.get("id") else None,
                    h.get("name"), a.get("name")])
    return out[:n]


def stat_all(url, ref, n=100):
    name = "st_" + url.split("/stats/", 1)[-1].replace("/", "_")
    d = cached(name + ".gz", lambda: FM.get(url), ref)
    return ((d or {}).get("TopLists") or [{}])[0].get("StatList", [])[:n]


def wiki(title):
    """Primer párrafo del artículo en español (API REST; si limita, la página normal). No se guarda si falla."""
    import gzip
    import html as H
    import re
    p = HERE / "cache" / f"wiki_{title[:60]}.json.gz"
    if p.exists():
        v = json.loads(gzip.decompress(p.read_bytes()))
        if v:
            return v
    ua = {"User-Agent": "StatsFC/1.0 (https://github.com/MCIFU/Stats-FC)"}
    v = None
    try:
        r = requests.get("https://es.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title), headers=ua, timeout=30)
        if r.status_code == 200:
            v = r.json().get("extract")
        else:
            r = requests.get("https://es.wikipedia.org/wiki/" + urllib.parse.quote(title), headers=ua, timeout=30)
            if r.status_code == 200:
                for par in re.findall(r"<p>(.*?)</p>", r.text, re.S):
                    t = re.sub(r"\[\d+\]", "", H.unescape(re.sub(r"<[^>]+>", "", par))).strip()
                    if len(t) > 120:
                        v = t
                        break
    except Exception:  # noqa: BLE001
        v = None
    if v:
        p.write_bytes(gzip.compress(json.dumps(v, ensure_ascii=False).encode()))
    return v


def liga(lid, nombre, ref, max_seasons=None):
    cur = cached(f"league_{lid}.json.gz", lambda: FM.get(f"https://www.fotmob.com/api/data/leagues?id={lid}"), ref) or {}
    seasons = (cur.get("allAvailableSeasons") or [])[:max_seasons]
    names = {}
    hist = []
    for k, s in enumerate(seasons):
        if k == 0:
            d = cur
        else:  # temporada terminada: no cambia, caché permanente
            d = cached(f"season_{lid}_{s.replace('/', '-')}.json.gz",
                       lambda s=s: FM.get(f"https://www.fotmob.com/api/data/leagues?id={lid}&season={urllib.parse.quote(s)}"), None) or {}
        tb = tables(d)
        for t in tb:
            for r in t["all"]:
                names[str(r[2])] = r[1]
        h = {"s": s, "tables": [{k2: v for k2, v in t.items() if k == 0 or k2 not in ("home", "away")} for t in tb], "fx": fixtures(d)}
        po = playoff(d)
        if po:
            h["po"] = po
            for _, ms in po:
                for x in ms:
                    for i, n in ((x[0], x[5]), (x[1], x[6])):
                        if i and n:
                            names.setdefault(str(i), n)
        if k == 0:
            up = upcoming(d)
            if up:
                h["up"] = up
                for x in up:
                    for i, n in ((x[2], x[4]), (x[3], x[5])):
                        if i and n:
                            names.setdefault(str(i), n)
        hist.append(h)
        time.sleep(0.2)
    champs = [[x.get("seasonName"), (x.get("winner") or {}).get("id"), (x.get("winner") or {}).get("name"),
               (x.get("loser") or {}).get("id"), (x.get("loser") or {}).get("name")] for x in (cur.get("seasons") or [])]
    for c in champs:
        for i, n in ((c[1], c[2]), (c[3], c[4])):
            if i and n:
                names.setdefault(str(i), n)
    st = cur.get("stats") or {}
    players, teams = {}, {}
    for x in st.get("players") or []:
        key = (x.get("participant") or {}).get("stat", {}).get("name") or (x.get("topThree") or [{}])[0].get("stat", {}).get("name")
        if key and x.get("fetchAllUrl"):
            players[key] = [x.get("header"), [[p.get("ParticiantId"), p.get("ParticipantName"), p.get("TeamId"), p.get("TeamName"), p.get("StatValue"),
                                               p.get("SubStatValue"), p.get("MatchesPlayed"), p.get("MinutesPlayed")] for p in stat_all(x["fetchAllUrl"], ref)]]
    for x in st.get("teams") or []:
        key = (x.get("participant") or {}).get("stat", {}).get("name") or (x.get("topThree") or [{}])[0].get("stat", {}).get("name")
        if key and x.get("fetchAllUrl"):
            teams[key] = [x.get("header"), [[t.get("TeamId"), t.get("ParticipantName"), t.get("StatValue"), t.get("SubStatValue")]
                                            for t in stat_all(x["fetchAllUrl"], ref, 40)]]
    return {"lid": lid, "liga": nombre, "champs": champs, "hist": hist, "names": names, "players": players, "teams": teams,
            "wiki": wiki(WIKI[lid]) if lid in WIKI else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refrescar", type=float, default=0.5)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    out = FC / "Panel_FC" / "ligas"
    out.mkdir(exist_ok=True)

    def one(item):
        nombre, (lid, _, _) = item
        try:
            d = liga(lid, nombre, a.refrescar)
        except Exception as e:  # noqa: BLE001
            return nombre, str(e)
        (out / f"h_{lid}.js").write_text("window.FC_LH=window.FC_LH||{};window.FC_LH[" + json.dumps(str(lid)) + "]="
                                         + json.dumps(d, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
        return nombre, f"{len(d['champs'])} campeones · {len(d['hist'])} temporadas · {len(d['players'])} listas de jugadores"
    with ThreadPoolExecutor(a.workers) as ex:
        for nombre, msg in ex.map(one, FM.LEAGUES.items()):
            print(f"  {nombre}: {msg}", flush=True)


if __name__ == "__main__":
    main()
