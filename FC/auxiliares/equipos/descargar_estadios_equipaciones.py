"""Foto del estadio y equipaciones actuales de cada club (Wikidata + Wikipedia en inglés, licencias libres de Commons).

- Estadio: Wikidata (club por id TM, P7223) → sede (P115) → imagen (P18). Miniatura de 360 px en JPEG.
- Equipaciones: las cajas de camiseta de la ficha del club en Wikipedia (primera, segunda, tercera…) y las del artículo de
  la temporada ("2026–27 <club> season"), que suele añadir las de competición europea o especiales. Cada caja son 5 piezas
  (manga izq., cuerpo, manga der., pantalón, medias) con color de fondo + dibujo PNG + contorno; aquí se componen en un PNG.

Uso (desde FC/):  python auxiliares/equipos/descargar_estadios_equipaciones.py [--refrescar 7]
Salidas: Panel_FC/estadios.js (window.FC_STADIUMS) y Panel_FC/equipaciones.js (window.FC_KITS), con las imágenes embebidas
para que se vean también sin conexión y en la página publicada.
"""
import argparse
import base64
import gzip
import html
import io
import json
import re
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from PIL import Image

HERE = Path(__file__).resolve().parent
FC = HERE.parents[1]
CACHE = HERE / "cache_media"
UA = {"User-Agent": "StatsFC/1.0 (https://github.com/MCIFU/Stats-FC; panel de scouting personal)"}
S = requests.Session()
S.headers.update(UA)
SEASON_EN = "2026–27"


_LAST = {}
_LOCK = threading.Lock()


def get(url, binary=False, tries=6):
    """Wikipedia/Commons limitan por IP: una petición cada 1,5 s por host y espera larga si responden 429."""
    host = urllib.parse.urlparse(url).netloc
    for k in range(tries):
        with _LOCK:
            wait = _LAST.get(host, 0) + (0.1 if host.startswith(("upload.", "thumb.")) else 1.2) - time.time()
            if wait > 0:
                time.sleep(wait)
            _LAST[host] = time.time()
        try:
            r = S.get(url, timeout=40)
            if r.status_code == 404:
                return None
            if r.status_code == 429:
                time.sleep(min(600, 60 * (k + 1)))
                continue
            if r.status_code in (500, 502, 503, 504):
                raise requests.HTTPError(str(r.status_code))
            r.raise_for_status()
            return r.content if binary else r.text
        except Exception:  # noqa: BLE001
            if k == tries - 1:
                return None
            time.sleep(3 * 2 ** k)
    return None


def cached(name, fn, days=None, binary=False):
    p = CACHE / name
    if p.exists() and (days is None or time.time() - p.stat().st_mtime < days * 86400):
        b = p.read_bytes()
        return b if binary else json.loads(gzip.decompress(b))
    v = fn()
    if v is None:
        return None
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(v if binary else gzip.compress(json.dumps(v, ensure_ascii=False).encode()))
    return v


def wikidata(tm_ids):
    """tm → {en: artículo en inglés, venue: nombre, img: archivo de Commons}"""
    out = {}
    for k in range(0, len(tm_ids), 150):
        chunk = tm_ids[k:k + 150]
        q = ("SELECT ?tm ?en ?vl ?img WHERE { VALUES ?tm {" + " ".join(f'"{i}"' for i in chunk) + "} ?item wdt:P7223 ?tm . "
             "OPTIONAL{?en schema:about ?item; schema:isPartOf <https://en.wikipedia.org/>} "
             "OPTIONAL{?item wdt:P115 ?v . OPTIONAL{?v wdt:P18 ?img} OPTIONAL{?v rdfs:label ?vl FILTER(lang(?vl)='es')}} }")

        def fetch():
            for intento in range(5):
                r = S.post("https://query.wikidata.org/sparql", data={"query": q}, timeout=120, headers={"Accept": "application/sparql-results+json"})
                if r.status_code == 200:
                    return r.json()["results"]["bindings"]
                time.sleep(10 * (intento + 1))
            return None
        rows = cached(f"wd_{k}_{abs(hash(tuple(chunk))) % 10**8}.json.gz", fetch, 30) or []
        for b in rows:
            d = out.setdefault(b["tm"]["value"], {})
            if "en" in b:
                d.setdefault("en", urllib.parse.unquote(b["en"]["value"].rsplit("/wiki/", 1)[-1]))
            if "img" in b and "img" not in d:
                d["img"] = urllib.parse.unquote(b["img"]["value"].rsplit("/", 1)[-1])
            if "vl" in b:
                d.setdefault("venue", b["vl"]["value"])
        time.sleep(1)
    return out


def stadium_photo(fname, days):
    def fetch():
        return get("https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(fname) + "?width=360", binary=True)
    raw = cached("st/" + re.sub(r"[^A-Za-z0-9._-]+", "_", fname)[:120], fetch, None, binary=True)
    if not raw:
        return None
    try:
        im = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:  # noqa: BLE001
        return None
    im.thumbnail((360, 240))
    b = io.BytesIO()
    im.save(b, "JPEG", quality=72, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


# ---------------------------------------------------------------- equipaciones
BOX = re.compile(r'<div style="position: relative; left: 0px; top: 0px; width: 100px; height: 135px;[^"]*">(.*?)</div>\s*</div>\s*(?:<div[^>]*>)?(.*?)</td>', re.S)
PIECE = re.compile(r'<div style="position: absolute; left: (\d+)px; top: (\d+)px; width: (\d+)px; height: (\d+)px;(?: background-color: ?(#[0-9A-Fa-f]{3,6}|[a-zA-Z]+))?[^"]*">(.*?)</div>', re.S)
IMG = re.compile(r'src="(//[^"]+)"')


def page_html(title, days):
    """HTML de la página (la API de Wikipedia limita mucho más que la web normal)."""
    def fetch():
        t = get("https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_")))
        return t if t is not None else ""
    return cached("wp/" + re.sub(r"[^A-Za-z0-9._-]+", "_", title)[:120] + ".json.gz", fetch, days) or ""


def kit_boxes(h):
    """[(caption, [(x, y, w, h, color, [img urls])...])] en el orden de la página."""
    out = []
    segs = h.split("width: 100px; height: 135px;")[1:]
    for seg in segs:
        body, _, rest = seg.partition("padding-top: 0.6em")
        pieces = []
        for x, y, w, hh, col, inner in PIECE.findall(body):
            pieces.append((int(x), int(y), int(w), int(hh), col, ["https:" + html.unescape(u) for u in IMG.findall(inner)]))
        cap = rest.split("</div>", 1)[0] if rest else ""
        cap = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", cap.split(">", 1)[-1]))).strip()
        if len(pieces) >= 3:
            out.append((cap[:40], pieces))
    return out


def piece_img(url):
    url = re.sub(r"\?.*$", "", url)
    raw = cached("kp/" + re.sub(r"[^A-Za-z0-9._-]+", "_", url.rsplit("/", 1)[-1])[:120], lambda: get(url, binary=True), None, binary=True)
    try:
        return Image.open(io.BytesIO(raw)).convert("RGBA") if raw else None
    except Exception:  # noqa: BLE001
        return None


def compose(pieces, scale=2):
    """color de fondo + dibujo + contorno por pieza; lo que el contorno pinta de blanco opaco es el exterior → transparente."""
    W, H = 100 * scale, 135 * scale
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    outside = Image.new("L", (W, H), 0)
    for x, y, w, h, col, urls in pieces:
        pos = (x * scale, y * scale)
        size = (w * scale, h * scale)
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        if col:
            try:
                layer.paste(Image.new("RGBA", size, col), pos)
            except ValueError:
                pass
        for u in urls:
            p = piece_img(u)
            if p is None:
                continue
            p = p.resize(size, Image.LANCZOS)
            if ".svg" in u:  # contorno: blanco opaco = fuera de la prenda
                r, g, b, al = p.split()
                white = Image.eval(Image.merge("RGB", (r, g, b)).convert("L"), lambda v: 255 if v > 240 else 0)
                out_m = Image.composite(white, Image.new("L", size, 0), al.point(lambda v: 255 if v > 200 else 0))
                outside.paste(out_m, pos)
                p = Image.composite(Image.new("RGBA", size, (0, 0, 0, 0)), p, out_m)
            layer.paste(p, pos, p)
        im = Image.alpha_composite(im, layer)
    im.putalpha(Image.composite(Image.new("L", (W, H), 0), im.split()[3], outside))
    return im


CUR = re.compile(r"^(home|away|third|fourth|fifth|alternate|alternative|goalkeeper|european|cup|special|anniversary|champions)", re.I)
CAP_ES = {"home": "Primera", "away": "Segunda", "third": "Tercera", "fourth": "Cuarta", "fifth": "Quinta", "alternate": "Alternativa",
          "alternative": "Alternativa", "goalkeeper": "Portero", "european": "Europea", "cup": "Copa", "special": "Especial",
          "anniversary": "Aniversario", "champions": "Champions"}


def cap_es(c):
    c = re.sub(r"\s*(colours|colors|kit)\s*$", "", c, flags=re.I).strip()
    m = CUR.match(c)
    return (CAP_ES[m.group(1).lower()] + c[m.end():]) if m else c


def kits_for(title, days):
    """[[rótulo, png, 'actual'|'historia']]: primero la ficha y la temporada actual, luego las históricas del artículo."""
    if not title:
        return []
    name = title.replace("_", " ")
    club = kit_boxes(page_html(title, days))
    season = kit_boxes(page_html(f"{SEASON_EN} {name} season", days))
    boxes = [(c, p, "actual") for c, p in club if CUR.match(c)] + [(c, p, "actual") for c, p in season] + \
            [(c, p, "historia") for c, p in club if not CUR.match(c)]
    seen, out = set(), []
    for cap, pieces, kind in boxes:
        sig = tuple((p[4], tuple(p[5])) for p in pieces)
        if sig in seen:
            continue
        seen.add(sig)
        im = compose(pieces)
        if im.getbbox() is None:
            continue
        im = im.crop(im.getbbox())
        b = io.BytesIO()
        im.save(b, "PNG", optimize=True)
        n = sum(1 for x in out if x[2] == kind) + 1
        out.append([cap_es(cap) if cap else ("Equipación " if kind == "actual" else "Histórica ") + str(n),
                    "data:image/png;base64," + base64.b64encode(b.getvalue()).decode(), kind])
    return out[:24]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refrescar", type=float, default=7)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    E = json.loads(gzip.decompress((HERE / "equipos.json.gz").read_bytes()))["clubs"]
    tms = sorted({t["tm"] for t in E.values() if t.get("tm")})
    wd = wikidata(tms)
    print(f"{len(tms)} clubes · wikidata {len(wd)} · con foto de estadio {sum(1 for d in wd.values() if d.get('img'))} · con artículo en inglés {sum(1 for d in wd.values() if d.get('en'))}", flush=True)
    st, kits = {}, {}

    def one(tm):
        d = wd.get(tm) or {}
        ph = stadium_photo(d["img"], a.refrescar) if d.get("img") else None
        ks = kits_for(d.get("en"), a.refrescar)
        return tm, d, ph, ks
    with ThreadPoolExecutor(a.workers) as ex:
        for n, (tm, d, ph, ks) in enumerate(ex.map(one, tms), 1):
            if ph:
                st[tm] = [d.get("venue"), ph, d.get("img")]
            if ks:
                kits[tm] = ks
            if n % 50 == 0:
                print(f"  {n}/{len(tms)}", flush=True)
    dump = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))
    (FC / "Panel_FC" / "estadios.js").write_text("window.FC_STADIUMS=" + dump(st) + ";\n", encoding="utf-8")
    (FC / "Panel_FC" / "equipaciones.js").write_text("window.FC_KITS=" + dump(kits) + ";\n", encoding="utf-8")
    print(f"estadios con foto: {len(st)} · clubes con equipaciones: {len(kits)} ({sum(len(v) for v in kits.values())} camisetas)")


if __name__ == "__main__":
    main()
