"""Fotos y enlaces de cada jugador para el panel web (FC/Panel_FC).

- Foto de perfil: la de Transfermarkt (portraitUrl de tmapi /players). TM solo guarda la foto actual, no una por temporada.
- Wikidata (propiedad P2446 = ID de Transfermarkt): elemento, categoría de Wikimedia Commons (fotos de libre uso,
  muchas de partidos) y artículo de Wikipedia en español. El panel pide las fotos de Commons al abrir la ficha.

Uso (desde FC/):  python auxiliares/media/descargar_media.py
Salida: auxiliares/media/media_jugadores.json  {tm_id: {"foto": "...", "qid": "Q...", "cat": "...", "es": "..."}}
"""
import gzip
import json
import sys
import time
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
FC = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "tmapi"))
import descargar_partidos as dp  # noqa: E402

SPARQL = "https://query.wikidata.org/sparql"
UA = {"User-Agent": "StatsFC/1.0 (uso personal; panel de scouting)", "Accept": "application/sparql-results+json"}
PORTRAIT = "https://img.a.transfermarkt.technology/portrait/big/"


def wikidata(ids, cache):
    have = json.loads(cache.read_text()) if cache.exists() else {}
    need = [i for i in ids if i not in have]
    for k in range(0, len(need), 300):
        chunk = need[k:k + 300]
        q = ("SELECT ?tm ?item ?cat ?es WHERE { VALUES ?tm {" + " ".join(f'"{i}"' for i in chunk) + "} ?item wdt:P2446 ?tm . "
             "OPTIONAL{?item wdt:P373 ?cat} OPTIONAL{?es schema:about ?item; schema:isPartOf <https://es.wikipedia.org/>} }")
        for intento in range(5):
            r = requests.post(SPARQL, data={"query": q}, headers=UA, timeout=120)
            if r.status_code == 200:
                break
            time.sleep(10 * (intento + 1))
        r.raise_for_status()
        for i in chunk:
            have.setdefault(i, {})
        for b in r.json()["results"]["bindings"]:
            d = have[b["tm"]["value"]]
            d["qid"] = b["item"]["value"].rsplit("/", 1)[-1]
            if "cat" in b:
                d["cat"] = b["cat"]["value"]
            if "es" in b:
                d["es"] = requests.utils.unquote(b["es"]["value"].rsplit("/wiki/", 1)[-1])
        cache.write_text(json.dumps(have, ensure_ascii=False))
        print(f"  wikidata {min(k + 300, len(need))}/{len(need)}")
        time.sleep(1)
    return have


def main():
    csv = FC / "Claude outputs" / "partidos_TM.csv"
    ids = sorted(set(pd.read_csv(csv, usecols=["tm_id"]).tm_id.dropna().astype(int).astype(str)))
    print(f"{len(ids)} jugadores con ID de Transfermarkt")
    meta = dp.meta("players", ids)
    wd = wikidata(ids, HERE / "cache_wikidata.json")
    out = {}
    for i in ids:
        d = dict(wd.get(i, {}))
        url = (meta.get(i) or {}).get("portraitUrl") or ""
        if url.startswith(PORTRAIT) and "default" not in url:
            d["foto"] = url[len(PORTRAIT):]
        if d:
            out[i] = d
    (HERE / "media_jugadores.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print(f"foto TM: {sum('foto' in v for v in out.values())} · Wikidata: {sum('qid' in v for v in out.values())} · "
          f"Commons: {sum('cat' in v for v in out.values())} · Wikipedia ES: {sum('es' in v for v in out.values())}")


if __name__ == "__main__":
    main()
