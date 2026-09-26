"""Contrato, historial de valor de mercado y lesiones de cada jugador (tmapi de Transfermarkt).

Endpoints: /players?ids[] (contrato, valor actual), /player/{id}/market-value-history, /player/{id}/injury.
Caché por jugador en cache/mv y cache/inj (--refrescar vuelve a pedir los que tengan más de N días).

Uso (desde FC/):  python auxiliares/tmapi/descargar_valor_lesiones.py [--refrescar 7]
Salida: auxiliares/tmapi/valor_lesiones.json
  {tm_id: {"c": "2028-06-30", "mv": [["2026-07-22", 220000000], ...], "inj": [["2026-02-26", "2026-03-01", 3, 1, "Knock"], ...]}}
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
    url = {"mv": f"{dp.TMAPI}/player/{pid}/market-value-history", "inj": f"{dp.TMAPI}/player/{pid}/injury"}[kind]
    try:
        d = dp.dig(dp.get(url), "data", default={}) or {}
    except Exception:
        return {}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(gzip.compress(json.dumps(d, ensure_ascii=False).encode()))
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refrescar", type=int, default=None, help="vuelve a pedir lo que tenga más de N días")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    csv = HERE.parents[1] / "Claude outputs" / "partidos_TM.csv"
    ids = sorted(set(pd.read_csv(csv, usecols=["tm_id"]).tm_id.dropna().astype(int).astype(str)))
    print(f"{len(ids)} jugadores")
    meta = dp.meta("players", ids)
    out = {}

    def one(pid):
        mv = _get("mv", pid, a.refrescar)
        inj = _get("inj", pid, a.refrescar)
        d = {}
        c = ((meta.get(pid) or {}).get("attributes") or {}).get("contractUntil")
        if c:
            d["c"] = c
        h = [[(x.get("marketValue") or {}).get("determined"), (x.get("marketValue") or {}).get("value")] for x in mv.get("history") or []]
        h = [x for x in h if x[0] and x[1] is not None]
        if h:
            d["mv"] = h
        li = [[x.get("start"), x.get("end"), (x.get("durationDetails") or {}).get("days"), x.get("missedGamesCount"), x.get("name")]
              for x in inj.get("injuries") or []]
        if li:
            d["inj"] = [x for x in li if x[0]]
        return pid, d

    with ThreadPoolExecutor(a.workers) as ex:
        for n, (pid, d) in enumerate(ex.map(one, ids), 1):
            if d:
                out[pid] = d
            if n % 1000 == 0:
                print(f"  {n}/{len(ids)}", flush=True)
    (HERE / "valor_lesiones.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print(f"contrato: {sum('c' in v for v in out.values())} · historial valor: {sum('mv' in v for v in out.values())} · "
          f"con lesiones: {sum('inj' in v for v in out.values())}")


if __name__ == "__main__":
    main()
