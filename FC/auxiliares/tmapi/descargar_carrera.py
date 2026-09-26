"""Trayectoria completa de cada jugador (Transfermarkt): estadísticas por temporada y competición + traspasos.

Endpoints tmapi: /player/{id}/performance-season y /transfer/history/player/{id}. Caché en cache/career y cache/transfers
(--refrescar N vuelve a pedir lo que tenga más de N días).

Uso (desde FC/):  python auxiliares/tmapi/descargar_carrera.py [--refrescar 6]
Salida: auxiliares/tmapi/carrera.json.gz
  {"players": {tm_id: {"s": [[season_id, comp_id, club_id, PJ, titular, min, G, A, amarillas, rojas, GC_equipo], ...],
                       "t": [[fecha, club_origen, club_destino, traspaso_eur, valor_eur, tipo], ...]}},
   "clubs": {id: nombre}, "comps": {id: [nombre, typeId, país]}}
"""
import argparse
import gzip
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import descargar_partidos as dp  # noqa: E402


def _get(kind, pid, max_age):
    p = dp.CACHE / kind / f"{pid}.json.gz"
    if p.exists() and (max_age is None or time.time() - p.stat().st_mtime < max_age * 86400):
        return json.loads(gzip.decompress(p.read_bytes()))
    url = {"career": f"{dp.TMAPI}/player/{pid}/performance-season", "transfers": f"{dp.TMAPI}/transfer/history/player/{pid}"}[kind]
    d = {}
    for intento in range(4):  # 404 = sin datos (no se reintenta); 429/5xx = espera y reintenta
        try:
            r = dp.S.get(url, timeout=30)
        except Exception:  # noqa: BLE001
            time.sleep(5 * (intento + 1))
            continue
        if r.status_code == 404:
            break
        if r.status_code == 200:
            d = (r.json() or {}).get("data") or {}
            break
        time.sleep(10 * (intento + 1))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(gzip.compress(json.dumps(d, ensure_ascii=False).encode()))
    return d


def _n(x):
    return int(x) if isinstance(x, (int, float)) else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refrescar", type=int, default=None)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    csv = HERE.parents[1] / "Claude outputs" / "partidos_TM.csv"
    ids = sorted(set(pd.read_csv(csv, usecols=["tm_id"]).tm_id.dropna().astype(int).astype(str)))
    print(f"{len(ids)} jugadores", flush=True)

    def one(pid):
        c = _get("career", pid, a.refrescar)
        t = _get("transfers", pid, a.refrescar)
        s = []
        for e in c.get("performance") or []:
            gi, st = e.get("generalInformation") or {}, e.get("statistics") or {}
            gs, cs, pt = st.get("goalStatistics") or {}, st.get("cardStatistics") or {}, st.get("playingTimeStatistics") or {}
            s.append([gi.get("seasonId"), gi.get("competitionId"), gi.get("clubId"), _n(pt.get("appearancesCount")), _n(pt.get("startingCount")),
                      _n(pt.get("playedMinutesSum")), _n(gs.get("goalsSum")), _n(gs.get("assistsSum")), _n(cs.get("yellowCardGrossSum")),
                      _n(cs.get("redCardsCount")) + _n(cs.get("yellowRedCardsCount")), _n(gs.get("opponentGoalsOnThePitch"))])
        tr = []
        for e in ((t.get("history") or {}).get("terminated") or []):
            d = e.get("details") or {}
            tr.append([(d.get("date") or "")[:10], (e.get("transferSource") or {}).get("clubId"), (e.get("transferDestination") or {}).get("clubId"),
                       (d.get("fee") or {}).get("value"), (d.get("marketValue") or {}).get("value"), (e.get("typeDetails") or {}).get("type")])
        return pid, {"s": s, "t": tr}

    out = {}
    with ThreadPoolExecutor(a.workers) as ex:
        for n, (pid, d) in enumerate(ex.map(one, ids), 1):
            if d["s"] or d["t"]:
                out[pid] = d
            if n % 1000 == 0:
                print(f"  {n}/{len(ids)}", flush=True)
    clubs = {str(x[2]) for d in out.values() for x in d["s"]} | {str(x[k]) for d in out.values() for x in d["t"] for k in (1, 2)}
    comps = {str(x[1]) for d in out.values() for x in d["s"]}
    km = dp.meta("clubs", [c for c in clubs if c and c != "None"])
    cm = dp.meta("competitions", [c for c in comps if c and c != "None"])
    names = {k: (v.get("baseDetails") or {}).get("shortName") or v.get("name") for k, v in km.items() if k in clubs}
    cnames = {k: [v.get("name"), v.get("typeId"), (v.get("originDetails") or {}).get("countryId")] for k, v in cm.items() if k in comps}
    res = {"players": out, "clubs": names, "comps": cnames}
    (HERE / "carrera.json.gz").write_bytes(gzip.compress(json.dumps(res, ensure_ascii=False, separators=(",", ":")).encode()))
    print(f"{len(out)} jugadores con trayectoria · {len(names)} clubes · {len(cnames)} competiciones")


if __name__ == "__main__":
    main()
