"""Entrenadores de los clubes del panel (Transfermarkt).

- Entrenador actual de cada club: tmapi /club/{id}/coach.
- Ficha: tmapi /coaches?ids[] (nacimiento, lugar, nacionalidad, licencia, foto).
- Todos sus partidos: tmapi /coach/{id}/performance-game → etapas (club, fechas, PJ, G-E-P, goles, puntos por partido),
  temporadas por competición, sistemas más usados, edad media del once, últimos partidos, mayores victorias.
- Títulos: web de TM /erfolge/trainer/{id} (una petición cada 2,5 s).

Uso (desde FC/):  python auxiliares/entrenadores/descargar_entrenadores.py [--refrescar 6]
Salida: Panel_FC/entrenadores.js (window.FC_COACHES)
"""
import argparse
import collections
import gzip
import html
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
FC = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "tmapi"))
import descargar_partidos as D  # noqa: E402  (sesión, caché y ritmo de Transfermarkt)

CACHE = HERE / "cache"


def cached(name, fn, days):
    p = CACHE / name
    if p.exists() and (days is None or time.time() - p.stat().st_mtime < days * 86400):
        return json.loads(gzip.decompress(p.read_bytes()))
    v = fn()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(gzip.compress(json.dumps(v, ensure_ascii=False).encode()))
    return v


def api(path):
    try:
        r = D.get(f"{D.TMAPI}/{path}", tries=4)
    except Exception:  # noqa: BLE001
        return None
    return (r or {}).get("data") if isinstance(r, dict) and r.get("success") else None


def titles(cid, days):
    def fetch():
        try:
            t = D.get(f"{D.TMWEB}/x/erfolge/trainer/{cid}", as_json=False, tries=4)
        except Exception:  # noqa: BLE001
            return None
        out = []
        for box in re.split(r'<h2 class="content-box-headline">', t)[1:]:
            head = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", box.split("</h2>", 1)[0]))).strip()
            m = re.match(r"(\d+)x\s+(.*)", head)
            if not m:
                continue
            img = re.search(r'erfolge/medium/(\d+)\.png', box)
            rows = re.findall(r'erfolg_table_saison">\s*([^<]*)</td>.*?verein/(\d+)', box, re.S)
            out.append([m.group(2), int(m.group(1)), img.group(1) if img else None, [[s.strip(), c] for s, c in rows]])
        return out
    return cached(f"erf_{cid}.json.gz", fetch, days)


def games(cid, days):
    return cached(f"perf_{cid}.json.gz", lambda: api(f"coach/{cid}/performance-game") or {}, days)


def summarize(g):
    """partidos de TM → etapas, temporadas, sistemas, forma, récords"""
    P = []
    for x in (g or {}).get("performance") or []:
        gi, ci = x.get("gameInformation") or {}, x.get("clubsInformation") or {}
        c, o = ci.get("club") or {}, ci.get("opponent") or {}
        if gi.get("gameState") not in (None, "regularly_terminated", "after_extra_time", "after_penalty_shootout") and c.get("goalsTotal") is None:
            continue
        gf, ga = c.get("goalsTotal"), c.get("opponentGoalsTotal")
        if gf is None or ga is None:
            continue
        st = ((x.get("statistics") or {}).get("ageStatistics") or {})
        P.append({"d": ((gi.get("date") or {}).get("dateTimeUTC") or "")[:10], "s": gi.get("seasonId"), "comp": gi.get("competitionId"),
                  "ct": gi.get("competitionTypeId"), "club": c.get("clubId"), "opp": o.get("clubId"), "h": 1 if c.get("venue") == "home" else 0,
                  "gf": gf, "ga": ga, "tac": c.get("tacticId"), "rank": c.get("clubRank"), "age": st.get("startingPlayersAverageAge"),
                  "nat": 1 if gi.get("isNationalGame") else 0})
    P.sort(key=lambda x: x["d"])
    res = lambda x: "W" if x["gf"] > x["ga"] else "D" if x["gf"] == x["ga"] else "L"

    def agg(L):
        w = sum(1 for x in L if x["gf"] > x["ga"])
        d = sum(1 for x in L if x["gf"] == x["ga"])
        return [len(L), w, d, len(L) - w - d, sum(x["gf"] for x in L), sum(x["ga"] for x in L), round((3 * w + d) / len(L), 2) if L else None]
    # etapas: partidos seguidos con el mismo club
    spells = []
    for x in P:
        if spells and spells[-1]["club"] == x["club"]:
            spells[-1]["g"].append(x)
        else:
            spells.append({"club": x["club"], "g": [x]})
    # un club puede repetirse (dos etapas): se mantienen separadas
    sp = []
    for s in spells:
        L = s["g"]
        ages = [x["age"] for x in L if x["age"]]
        tac = collections.Counter(x["tac"] for x in L if x["tac"]).most_common(3)
        sp.append([s["club"], L[0]["d"], L[-1]["d"], *agg(L), round(sum(ages) / len(ages), 1) if ages else None, [[t, n] for t, n in tac], L[0]["nat"]])
    # temporadas por club y competición
    by = collections.defaultdict(list)
    for x in P:
        by[(x["s"], x["club"], x["comp"])].append(x)
    seasons = [[s, c, comp, *agg(L), L[-1]["rank"] if L[-1]["ct"] == 1 else None] for (s, c, comp), L in sorted(by.items(), key=lambda kv: (kv[0][0] or 0), reverse=True)]
    tac_all = collections.Counter(x["tac"] for x in P if x["tac"]).most_common(6)
    big = sorted(P, key=lambda x: (x["gf"] - x["ga"], x["gf"]), reverse=True)[:3]
    last = P[-12:][::-1]
    return {"tot": agg(P), "sp": sp, "se": seasons, "tac": [[t, n] for t, n in tac_all],
            "last": [[x["d"], x["comp"], x["club"], x["opp"], x["h"], x["gf"], x["ga"], res(x)] for x in last],
            "big": [[x["d"], x["comp"], x["club"], x["opp"], x["h"], x["gf"], x["ga"]] for x in big]}, P


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refrescar", type=float, default=6)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    E = json.loads(gzip.decompress((FC / "auxiliares" / "equipos" / "equipos.json.gz").read_bytes()))["clubs"]
    tm_clubs = sorted({t["tm"] for t in E.values() if t.get("tm")})
    fm_formation = {t["tm"]: t.get("formation") for t in E.values() if t.get("tm")}
    cur = {}
    with ThreadPoolExecutor(a.workers) as ex:
        for tm, d in zip(tm_clubs, ex.map(lambda c: cached(f"club_{c}.json.gz", lambda: api(f"club/{c}/coach") or {}, 3), tm_clubs)):
            if d and d.get("coachId") and d["coachId"] != "0":
                cur[tm] = [d["coachId"], (d.get("startDate") or "")[:10]]
    ids = sorted({v[0] for v in cur.values()})
    print(f"{len(tm_clubs)} clubes · {len(ids)} entrenadores actuales", flush=True)
    prof = {}
    for k in range(0, len(ids), 50):
        chunk = ids[k:k + 50]
        q = "&".join(f"ids%5B%5D={i}" for i in chunk)
        for it in cached(f"prof_{k}_{abs(hash(tuple(chunk))) % 10**8}.json.gz", lambda: api(f"coaches?{q}") or [], a.refrescar):
            prof[str(it.get("id"))] = it
    out, allgames = {}, {}
    with ThreadPoolExecutor(a.workers) as ex:
        for cid, g in zip(ids, ex.map(lambda i: games(i, a.refrescar), ids)):
            out[cid], allgames[cid] = summarize(g)
    print("partidos descargados", flush=True)
    for n, cid in enumerate(ids, 1):  # web de TM: en serie
        out[cid]["tit"] = titles(cid, a.refrescar * 5) or []
        if n % 50 == 0:
            print(f"  títulos {n}/{len(ids)}", flush=True)
    # sistema táctico: id de TM → dibujo, votando con el dibujo de FotMob del club actual en sus últimos partidos
    votes = collections.defaultdict(collections.Counter)
    for tm, (cid, _) in cur.items():
        f = fm_formation.get(tm)
        if not f:
            continue
        rec = [x for x in allgames.get(cid, [])[-8:] if x["club"] == tm and x["tac"]]
        if rec:
            votes[collections.Counter(x["tac"] for x in rec).most_common(1)[0][0]][f] += 1
    tactics = {str(t): c.most_common(1)[0][0] for t, c in votes.items() if c.most_common(1)[0][1] >= 2}
    coaches = {}
    for cid in ids:
        p = prof.get(cid) or {}
        bp, ld, nat = p.get("birthPlaceDetails") or {}, p.get("lifeDates") or {}, ((p.get("nationalityDetails") or {}).get("nationalities") or {})
        at = p.get("attributes") or {}
        coaches[cid] = {"n": p.get("name"), "full": (p.get("nationalityDetails") or {}).get("passportName"), "dob": ld.get("dateOfBirth"),
                        "bp": [bp.get("placeOfBirth") or None, bp.get("placeOfBirthAdditionalInfo") or None, bp.get("countryOfBirthId")],
                        "nat": [nat.get("nationalityId"), nat.get("secondNationalityId") or None], "lic": (at.get("license") or {}).get("name"),
                        "pl": at.get("playerId") if at.get("playerId") not in (None, "0", 0) else None, "img": p.get("portraitUrl"), **out[cid]}
    # nombres de clubes que aparecen (los que no estén en nombres.js)
    need = {s[0] for c in coaches.values() for s in c["sp"]} | {x[3] for c in coaches.values() for x in c["last"] + c["big"]} | \
           {s[1] for c in coaches.values() for s in c["se"]} | {r[1] for c in coaches.values() for t in c["tit"] for r in t[3]}
    need.discard(None)
    kc = json.loads(gzip.decompress((FC / "auxiliares" / "tmapi" / "cache" / "meta_clubs.json.gz").read_bytes()))
    miss = sorted(i for i in need if str(i) not in kc)
    for k in range(0, len(miss), 50):
        q = "&".join(f"ids%5B%5D={i}" for i in miss[k:k + 50])
        for it in api(f"clubs?{q}") or []:
            kc[str(it.get("id"))] = it
    names = {str(i): (kc.get(str(i)) or {}).get("name") for i in need}
    dump = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))
    # país TM (id) → código de nacionalidad del panel, aprendido de los jugadores (datos.js: tm + nat)
    code = {}
    try:
        dj = (FC / "Panel_FC" / "datos.js").read_text(encoding="utf-8")
        dd = json.loads(dj[dj.index("=") + 1:].rstrip().rstrip(";"))
        F = dd["meta"]["fields"]
        ti, ni = F.index("tm"), F.index("nat")
        mp = json.loads(gzip.decompress((FC / "auxiliares" / "tmapi" / "cache" / "meta_players.json.gz").read_bytes()))
        cnt = collections.defaultdict(collections.Counter)
        for r in dd["players"]:
            f = mp.get(str(r[ti])) if r[ti] else None
            nid = (((f or {}).get("nationalityDetails") or {}).get("nationalities") or {}).get("nationalityId")
            if nid and r[ni] is not None:
                cnt[nid][dd["meta"]["nats"][r[ni]]] += 1
        code = {str(k): c.most_common(1)[0][0] for k, c in cnt.items()}
    except Exception as e:  # noqa: BLE001
        print("sin mapa de países", e)
    for c in coaches.values():
        c["bp"][2] = code.get(str(c["bp"][2]), None)
        c["nat"] = [code.get(str(x)) for x in c["nat"] if x]
    data = {"coaches": coaches, "byClub": cur, "clubs": {k: v for k, v in names.items() if v}, "tactics": tactics}
    (FC / "Panel_FC" / "entrenadores.js").write_text("window.FC_COACHES=" + dump(data) + ";\n", encoding="utf-8")
    print(f"entrenadores: {len(coaches)} · con títulos {sum(1 for c in coaches.values() if c['tit'])} · sistemas identificados {len(tactics)}")


if __name__ == "__main__":
    main()
