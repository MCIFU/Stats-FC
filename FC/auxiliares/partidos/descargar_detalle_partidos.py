"""Detalle de cada partido (FotMob matchDetails) para la página de partido del panel.

Partidos: todos los terminados de la temporada actual de las ligas del panel (Panel_FC/ligas.js), los de la portada
y los de selecciones de los últimos 120 días (Panel_FC/sel). Un partido terminado no cambia: caché permanente, así que
cada semana solo se descargan los nuevos.

Por partido: equipos, marcador, fecha, competición y jornada, estadio, árbitro, público, mejor jugador; goles (con
asistencia, penalti, en propia), tarjetas y cambios; alineaciones con dibujo, posición en el campo, dorsal y nota de
cada jugador, suplentes, entrenador; y las estadísticas del partido (posesión, xG, tiros, pases, duelos…).

Uso (desde FC/):  python auxiliares/partidos/descargar_detalle_partidos.py [--workers 4]
Salida: Panel_FC/partido/m_<id>.js (window.FC_MD[id]) e índice Panel_FC/partidos_det.js (ids disponibles).
"""
import argparse
import datetime as dt
import gzip
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
FC = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "avanzadas"))
import descargar_fotmob_understat as FM  # noqa: E402

CACHE = HERE / "cache_detalle"
OUT = FC / "Panel_FC"


def load_js(p):
    t = p.read_text(encoding="utf-8")
    i = t.index("=") + 1
    if t.startswith("window.FC_LH") or t.startswith("window.FC_NT"):
        i = t.index("]=") + 2
    return json.loads(t[i:].rstrip().rstrip(";"))


def ids_a_descargar():
    ids = set()
    L = load_js(OUT / "ligas.js")
    for l in (L.get("ligas") or {}).values():
        for m in l.get("matches") or []:
            if m[8] and m[0]:
                ids.add(int(m[0]))
    pf = OUT / "portada.js"
    if pf.exists():
        H = load_js(pf)
        for m in H.get("matches") or []:
            if len(m) > 11 and m[11] and (m[8] or m[6] is not None):
                ids.add(int(m[11]))
    lim = (dt.date.today() - dt.timedelta(days=120)).isoformat()
    for f in (OUT / "sel").glob("s_*.js"):
        for m in load_js(f).get("fx") or []:
            if m[10] and m[0] and (m[1] or "") >= lim:
                ids.add(int(m[0]))
    return ids


def raw(mid):
    p = CACHE / f"{mid}.json.gz"
    if p.exists():
        return json.loads(gzip.decompress(p.read_bytes()))
    d = FM.get(f"https://www.fotmob.com/api/data/matchDetails?matchId={mid}")
    if d and (d.get("general") or {}).get("finished"):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(gzip.compress(json.dumps(d, ensure_ascii=False).encode()))
    return d


def compacto(d):
    g, h, c = d.get("general") or {}, d.get("header") or {}, d.get("content") or {}
    mf = c.get("matchFacts") or {}
    ib = mf.get("infoBox") or {}
    T = h.get("teams") or [{}, {}]
    st = h.get("status") or {}
    ev = []
    for e in ((mf.get("events") or {}).get("events") or []):
        t = e.get("type")
        mn = [e.get("time"), e.get("overloadTime") or 0]
        if t == "Goal":
            kind = "og" if e.get("ownGoal") else "pen" if (e.get("goalDescriptionKey") or "").startswith("penalty") or e.get("suffixKey") == "penalty" else ""
            ev.append(["G", mn, 1 if e.get("isHome") else 0, (e.get("player") or {}).get("id"), e.get("nameStr") or (e.get("player") or {}).get("name"),
                       e.get("assistPlayerId"), e.get("assistInput"), kind, e.get("newScore")])
        elif t == "Card":
            ev.append(["C", mn, 1 if e.get("isHome") else 0, (e.get("player") or {}).get("id"), e.get("nameStr") or (e.get("player") or {}).get("name"),
                       e.get("card")])
        elif t == "Substitution":
            sw = e.get("swap") or [{}, {}]
            ev.append(["S", mn, 1 if e.get("isHome") else 0, sw[0].get("id"), sw[0].get("name"), sw[1].get("id") if len(sw) > 1 else None,
                       sw[1].get("name") if len(sw) > 1 else None])
    def team(x):
        if not x:
            return None
        pl = lambda p, st_: [p.get("id"), p.get("name"), p.get("shirtNumber"), p.get("positionId"), ((p.get("performance") or {}).get("rating")),
                             [(p.get("verticalLayout") or {}).get("x"), (p.get("verticalLayout") or {}).get("y")] if st_ else None, p.get("age")]
        co = x.get("coach") or {}
        return {"id": x.get("id"), "form": x.get("formation"), "rating": x.get("rating"), "age": x.get("averageStarterAge"),
                "value": x.get("totalStarterMarketValue"), "xi": [pl(p, True) for p in x.get("starters") or []],
                "subs": [pl(p, False) for p in x.get("subs") or []], "coach": [co.get("id"), co.get("name")] if co else None,
                "out": [[p.get("id"), p.get("name"), ((p.get("unavailability") or {}).get("type"))] for p in (x.get("unavailable") or [])]}
    lu = c.get("lineup") or {}
    stats = []
    for grp in ((((c.get("stats") or {}).get("Periods") or {}).get("All") or {}).get("stats") or []):
        rows = [[s.get("title"), s.get("key"), (s.get("stats") or [None, None])[0], (s.get("stats") or [None, None])[1]]
                for s in grp.get("stats") or [] if s.get("type") != "title" and s.get("stats")]
        if rows:
            stats.append([grp.get("title"), rows])
    pom = mf.get("playerOfTheMatch") or {}
    stad, ref, att = ib.get("Stadium") or {}, ib.get("Referee") or {}, ib.get("Attendance")
    tn = ib.get("Tournament") or {}
    return {"id": int(g.get("matchId") or 0), "date": g.get("matchTimeUTCDate"), "lid": g.get("leagueId"), "league": g.get("leagueName"),
            "round": tn.get("roundName") or g.get("leagueRoundName"),
            "h": [T[0].get("id"), T[0].get("name"), T[0].get("score")], "a": [T[1].get("id"), T[1].get("name"), T[1].get("score")],
            "reason": (st.get("reason") or {}).get("short"), "pens": (st.get("reason") or {}).get("penalties"),
            "stadium": [stad.get("name"), stad.get("city"), stad.get("capacity")] if stad else None, "ref": [ref.get("text"), ref.get("countryCode")] if ref else None,
            "att": att, "pom": [pom.get("id"), (pom.get("name") or {}).get("fullName"), (pom.get("rating") or {}).get("num")] if pom else None,
            "ev": ev, "lu": {"h": team(lu.get("homeTeam")), "a": team(lu.get("awayTeam"))}, "stats": stats,
            "colors": ((g.get("teamColors") or {}).get("lightMode"))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    ids = sorted(ids_a_descargar())
    print(f"{len(ids)} partidos terminados; nuevos: {sum(1 for i in ids if not (CACHE / f'{i}.json.gz').exists())}", flush=True)
    ok = []

    def one(mid):
        try:
            d = raw(mid)
            if not d:
                return None
            x = compacto(d)
            f = OUT / "partido" / f"m_{mid}.js"
            f.parent.mkdir(exist_ok=True)
            f.write_text(f"window.FC_MD=window.FC_MD||{{}};window.FC_MD[{mid}]=" + json.dumps(x, ensure_ascii=False, separators=(",", ":")) + ";\n",
                         encoding="utf-8")
            return mid
        except Exception as e:  # noqa: BLE001
            print(f"  {mid}: {e}", flush=True)
            return None
    with ThreadPoolExecutor(a.workers) as ex:
        for n, r in enumerate(ex.map(one, ids), 1):
            if r:
                ok.append(r)
            if n % 250 == 0:
                print(f"  {n}/{len(ids)}", flush=True)
    todos = sorted({int(f.stem[2:]) for f in (OUT / "partido").glob("m_*.js")})
    (OUT / "partidos_det.js").write_text("window.FC_MDI=new Set(" + json.dumps(todos, separators=(",", ":")) + ");\n", encoding="utf-8")
    print(f"Listo: {len(ok)} partidos ahora, {len(todos)} en total.")


if __name__ == "__main__":
    main()
