"""Descarga de Transfermarkt los partidos jugador a jugador de las 5 grandes ligas
y genera partidos_big5.csv (una fila por jugador y partido) para el motor de valoración.

Uso (desde la carpeta FC):
    python auxiliares/tmapi/descargar_partidos.py                  # 25-26 y 26-27
    python auxiliares/tmapi/descargar_partidos.py --inspect 8198   # vuelca un partido crudo de un jugador
    python auxiliares/tmapi/descargar_partidos.py --offline        # rehace el CSV solo con la caché

Necesita salida a internet hacia www.transfermarkt.es y tmapi.transfermarkt.technology.
Mismas reglas que LEEME_METODO_TM_API.md (bloques por typeId, filiales fuera, KLUB 2024 fuera, corte 20:55 UTC).
Todo lo descargado queda en auxiliares/tmapi/cache/ (se reutiliza en la siguiente ejecución).
"""
import argparse, collections, os, concurrent.futures as cf, datetime as dt, gzip, json, re, sys, time
from pathlib import Path

import openpyxl
import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
FC = HERE.parent.parent
CACHE = HERE / "cache"
TMAPI = "https://tmapi.transfermarkt.technology"
TMWEB = "https://www.transfermarkt.es"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/128.0 Safari/537.36")
BIG5 = {"LaLiga", "Premier", "Bundesliga", "Serie A", "Ligue 1"}
SHEETS = ["DELANTEROS", "EXTREMOS", "MEDIAPUNTAS", "MEDIOCENTROS", "DEFENSAS", "PORTEROS"]
SEASONS = {"2025-26": ("Temporada 2025-26.xlsx", 2025), "2026-27": ("Temporada 2026-27.xlsx", 2026)}

# ---- reglas de bloque (idénticas a process.py)
YOUTH_T = {7, 15, 16, 17, 18, 20, 23}
YOUTH_C = {'AJ', 'BK19', 'ITJE', 'P23Q', 'P23C', 'E21P', 'MNPP', '18GB', 'ITJP', 'F19F', 'IT18', 'ITJF', '7NP1', '7NP2',
           'BJ', 'T19Y', 'NLBA', 'PTPR', 'F17M', 'MNP3', 'UL2P'}
# ligas/copas de otros continentes: sus clubes no se mezclan con la fila europea (regla de continentes de los Excel)
NON_EU = {'MLS1', 'USL', 'BRA1', 'BRA2', 'ARG1', 'ARGC', 'MEXA', 'MEX1', 'POMX', 'POME', 'KR1', 'CSL', 'JAP1', 'SA1',
          'UAE1', 'QSL', 'TUN1', 'CLPD', 'UZ1', 'AUS1', 'COLP', 'URU1', 'EGY1', 'MAR1'}
CONTCODE = {'CL': 'UCL', 'CLQ': 'UCL', 'USC': 'UCL', 'EL': 'UEL', 'ELQ': 'UEL', 'UCOL': 'UECL', 'ECLQ': 'UECL'}

S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept": "application/json, text/html, */*", "Accept-Language": "es-ES,es;q=0.9",
                  "Referer": TMWEB + "/"})


_LAST_WEB = [0.0]


def get(url, as_json=True, tries=8):
    for k in range(tries):
        try:
            if url.startswith(TMWEB):  # la web (no la API) corta con 405 si se le pide rápido: ≥ 2,5 s entre peticiones
                wait = _LAST_WEB[0] + 2.5 - time.time()
                if wait > 0:
                    time.sleep(wait)
                _LAST_WEB[0] = time.time()
            r = S.get(url, timeout=30)
            if r.status_code in (405, 429, 500, 502, 503, 504):  # 405 = límite de peticiones de la web de TM
                raise requests.HTTPError(str(r.status_code))
            r.raise_for_status()
            return r.json() if as_json else r.text
        except Exception as e:  # noqa: BLE001
            if k == tries - 1:
                raise RuntimeError(f"{url}: {e}") from e
            time.sleep(min(300, 5 * 2 ** k))


# actualización semanal: TM_REFRESH_DAYS="perf/=5,squads/=27" vuelve a pedir lo cacheado con más de N días
REFRESH = {k: float(v) for k, v in (x.split("=") for x in os.environ.get("TM_REFRESH_DAYS", "").split(",") if "=" in x)}


def cached(name, fn):
    p = CACHE / name
    days = next((v for k, v in REFRESH.items() if name.startswith(k)), None)
    if p.exists() and (days is None or time.time() - p.stat().st_mtime < days * 86400):
        return json.loads(gzip.decompress(p.read_bytes()))
    v = fn()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(gzip.compress(json.dumps(v, ensure_ascii=False).encode()))
    return v


def norm(s):
    from unidecode import unidecode
    s = unidecode(str(s)).lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def dig(o, *path, default=None):
    for p in path:
        if not isinstance(o, dict) or p not in o:
            return default
        o = o[p]
    return o


def find(o, names, depth=4):
    """Primer valor cuya clave esté en `names` (búsqueda en anchura, profundidad limitada)."""
    q = [(o, 0)]
    while q:
        x, d = q.pop(0)
        if isinstance(x, dict):
            for n in names:
                if n in x and x[n] is not None and not isinstance(x[n], (dict, list)):
                    return x[n]
            if d < depth:
                q += [(v, d + 1) for v in x.values() if isinstance(v, (dict, list))]
        elif isinstance(x, list) and d < depth:
            q += [(v, d + 1) for v in x if isinstance(v, (dict, list))]
    return None


def as_list(payload):
    """tmapi responde {data: [...]} o {data: {clave: [...]}}; devuelve la lista de dicts con 'id'."""
    d = payload.get("data", payload) if isinstance(payload, dict) else payload
    if isinstance(d, list):
        return d
    if isinstance(d, dict):
        for v in d.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v
    return []


# ---------------------------------------------------------------- 1. filas del Excel (5 grandes)
def excel_rows():
    cm = json.loads((HERE / "clubmap.json").read_text(encoding="utf-8"))
    out = []
    for season, (fname, tmseason) in SEASONS.items():
        wb = openpyxl.load_workbook(FC / fname, read_only=True)
        for sh in SHEETS:
            rows = list(wb[sh].iter_rows(values_only=True))
            hi = next(i for i, r in enumerate(rows[:10]) if r and r[0] == "Jugador")
            hdr = rows[hi]
            for k, r in enumerate(rows[hi + 1:], hi + 2):
                if not r or not r[0]:
                    continue
                d = dict(zip(hdr, r))
                if d.get("Liga") not in BIG5 or d.get("Club") not in cm:
                    continue
                out.append(dict(season=season, tmseason=tmseason, sheet=sh, row=k, name=d["Jugador"],
                                nat=d.get("Nac"), club=d["Club"], club_id=str(cm[d["Club"]]), liga=d["Liga"]))
    return out


# ---------------------------------------------------------------- 2. plantillas TM -> ID de jugador
RX_PLAYER = re.compile(r'href="/[^"/]+/(?:profil|leistungsdaten)/spieler/(\d+)[^"]*"[^>]*>([^<]{2,})</a>')


def squad(club_id, tmseason):
    def fetch():
        html = get(f"{TMWEB}/x/leistungsdaten/verein/{club_id}/plus/1?reldata=%26{tmseason}", as_json=False)
        seen = {}
        for pid, name in RX_PLAYER.findall(html):
            name = re.sub(r"\s+", " ", name).strip()
            if name and pid not in seen:
                seen[pid] = name
        return seen
    return cached(f"squads/{club_id}_{tmseason}.json.gz", fetch)


def map_ids(rows):
    from rapidfuzz import fuzz, process
    manual = {}
    mf = HERE / "pidmap_manual.json"  # {"2025-26|DEFENSAS|Nombre|Club": "tmid"} para corregir a mano
    if mf.exists():
        manual = json.loads(mf.read_text(encoding="utf-8"))
    sq = {}
    keys = sorted({(r["club_id"], r["tmseason"]) for r in rows})
    for i, k in enumerate(keys, 1):  # la web de TM corta con 405 si se le pide en paralelo
        fresh = not (CACHE / f"squads/{k[0]}_{k[1]}.json.gz").exists()
        sq[k] = squad(*k)
        if fresh:
            time.sleep(1.5)
        if i % 25 == 0:
            print(f"  plantillas {i}/{len(keys)}")
    glob = collections.defaultdict(set)
    for v in sq.values():
        for pid, nm in v.items():
            glob[norm(nm)].add(pid)
    stats, bad = collections.Counter(), []
    for r in rows:
        key = f"{r['season']}|{r['sheet']}|{r['name']}|{r['club']}"  # por nombre y club: las hojas se reordenan
        if key in manual:
            r["tm_id"], how = str(manual[key]), "manual"
        else:
            cand = {pid: norm(nm) for pid, nm in sq.get((r["club_id"], r["tmseason"]), {}).items()}
            nm, pid, how = norm(r["name"]), None, ""
            ex_ = [p for p, v in cand.items() if v == nm]
            if len(ex_) == 1:
                pid, how = ex_[0], "exact"
            elif cand:
                b = process.extractOne(nm, cand, scorer=fuzz.token_set_ratio)
                b2 = process.extractOne(nm, cand, scorer=fuzz.WRatio)
                if b and b[1] >= 90 and b2 and b2[2] == b[2]:
                    pid, how = b[2], "fuzzy"
                elif b2 and b2[1] >= 90:
                    pid, how = b2[2], "wratio"
            if pid is None and len(glob.get(nm, ())) == 1:
                pid, how = next(iter(glob[nm])), "global"
            r["tm_id"] = pid
        stats[how or "sin_id"] += 1
        if not r.get("tm_id"):
            bad.append(r)
    print("IDs:", dict(stats))
    if bad:
        pd.DataFrame(bad).to_csv(HERE / "sin_id_tm.csv", index=False, encoding="utf-8-sig")
        print(f"  {len(bad)} filas sin ID -> auxiliares/tmapi/sin_id_tm.csv (añádelas a pidmap_manual.json)")
    return rows


# ---------------------------------------------------------------- 3. partidos por jugador + metadatos
def performance(pid, offline=False):
    name = f"perf/{pid}.json.gz"
    if offline:
        p = CACHE / name
        return json.loads(gzip.decompress(p.read_bytes())) if p.exists() else []
    return cached(name, lambda: dig(get(f"{TMAPI}/player/{pid}/performance-game"), "data", "performance", default=[]))


def meta(kind, ids, offline=False):
    """kind = competitions | clubs. Devuelve {id: dict}. Caché acumulativa."""
    p = CACHE / f"meta_{kind}.json.gz"
    have = json.loads(gzip.decompress(p.read_bytes())) if p.exists() else {}
    need = sorted({str(i) for i in ids if i is not None} - set(have))
    if not offline:
        for i in range(0, len(need), 50):
            q = "&".join(f"ids%5B%5D={x}" for x in need[i:i + 50])
            for it in as_list(get(f"{TMAPI}/{kind}?{q}")):
                have[str(it.get("id"))] = it
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(gzip.compress(json.dumps(have, ensure_ascii=False).encode()))
    return have


def parse_game(e):
    """Aplana una entrada de performance-game. Claves confirmadas: gameInformation.{date.dateTimeUTC, seasonId,
    competitionId}, clubsInformation.club.clubId, statistics.generalStatistics.participationState,
    goalStatistics.{goalsScoredTotal, assists}, playingTimeStatistics.playedMinutes. El resto se busca por nombre."""
    gi, ci, st = e.get("gameInformation") or {}, e.get("clubsInformation") or {}, e.get("statistics") or {}
    club = ci.get("club") or {}
    opp = next((v for k, v in ci.items() if k != "club" and isinstance(v, dict) and "opp" in k.lower()), None) or {}
    gf = find(club, ["goalsTotal", "goals", "clubGoalsTotal"], 1)
    ga = find(club, ["opponentGoalsTotal"], 1)
    if ga is None:
        ga = find(opp, ["goalsTotal", "goals"], 1)
    home = find(e, ["isHomeGame", "isHomeTeam", "isHome", "home"], 3)
    if home is None:
        venue = find(e, ["venue", "homeOrAway", "location"], 3)
        home = None if venue is None else str(venue).lower() in ("h", "home", "heim", "1", "true")
    return dict(
        game_id=find(gi, ["gameId", "id", "matchId"], 1) or find(e, ["gameId"], 2),
        date=dig(gi, "date", "dateTimeUTC") or find(gi, ["dateTimeUTC", "date"], 2),
        season_id=gi.get("seasonId"),
        comp=gi.get("competitionId") or find(e, ["competitionId"], 3),
        comp_type=find(e, ["competitionTypeId", "typeId"], 3),
        live=bool(gi.get("isLiveGame")) or bool(gi.get("isGamePostponed")),
        club_id=str(club.get("clubId")) if club.get("clubId") is not None else None,
        opp_id=str(find(opp, ["clubId", "id"], 1)) if opp else None,
        nat=bool(find(e, ["isNationalTeam", "nationalTeam"], 3)),
        state=dig(st, "generalStatistics", "participationState"),
        Min=dig(st, "playingTimeStatistics", "playedMinutes") or 0,
        G=dig(st, "goalStatistics", "goalsScoredTotal") or 0,
        A=dig(st, "goalStatistics", "assists") or 0,
        GC=find(e, ["opponentGoalsOnThePitch"], 4),
        gf=gf, ga=ga, home=home,
        yellow=dig(st, "cardStatistics", "yellowCardNet"),
        red=find(st, ["redCard", "redCards", "redCardNet"], 2),
        starter=find(st, ["isStarting", "isStartingEleven"], 2),
    )


def block_of(g, COMP, CLUB):
    c = str(g["comp"])
    t = COMP.get(c, {}).get("t") or g["comp_type"] or 0
    t = int(t) if str(t).isdigit() else 0
    cl = CLUB.get(g["club_id"] or "", {})
    if g["nat"] or cl.get("nt"):
        return "SEL" if cl.get("main") in (None, g["club_id"]) and t not in YOUTH_T else None
    if cl.get("main") and cl["main"] != g["club_id"]:
        return None  # filial / juvenil
    if t in YOUTH_T or c in YOUTH_C:
        return None
    if c == "KLUB" and str(g["season_id"]) == "2024":
        return None  # Mundial de Clubes 2025 excluido
    if c in ("FIC1", "KLUB"):
        return "FIFA"
    if c == "CWCQ":
        return None
    if t in (10, 13):
        return "CONT"
    if t in (1, 2, 3, 4, 5, 6, 12):
        return "LIGA"
    if t in (8, 9, 14, 21, 22, 24):
        return "COPA"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inspect", help="ID TM de un jugador: imprime una entrada cruda y sale")
    ap.add_argument("--offline", action="store_true", help="no descarga nada: usa solo la caché")
    ap.add_argument("--corte", default=dt.date.today().isoformat(), help="fecha de corte AAAA-MM-DD (hoy)")
    ap.add_argument("--out", default=str(FC / "Claude outputs" / "partidos_big5.csv"))
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    if a.inspect:
        perf = dig(get(f"{TMAPI}/player/{a.inspect}/performance-game"), "data", "performance", default=[])
        print(len(perf), "partidos"); print(json.dumps(perf[-1] if perf else {}, indent=1, ensure_ascii=False)[:6000])
        print(json.dumps(parse_game(perf[-1]), ensure_ascii=False) if perf else "")
        return

    rows = excel_rows()
    print(f"{len(rows)} filas de las 5 grandes en los Excel")
    rows = map_ids(rows)  # las plantillas se leen de la caché si ya están
    pids = sorted({r["tm_id"] for r in rows if r.get("tm_id")})
    print(f"{len(pids)} jugadores TM; descargando performance-game…")
    t0, perf = time.time(), {}
    with cf.ThreadPoolExecutor(a.workers) as ex:
        futs = {ex.submit(performance, p, a.offline): p for p in pids}
        for i, f in enumerate(cf.as_completed(futs), 1):
            try:
                perf[futs[f]] = f.result()
            except Exception as e:  # noqa: BLE001
                print("  !", futs[f], e)
            if i % 250 == 0:
                print(f"  {i}/{len(pids)} ({time.time() - t0:.0f}s)")

    games = {p: [parse_game(e) for e in L] for p, L in perf.items()}
    comps = {g["comp"] for L in games.values() for g in L}
    clubs = {g["club_id"] for L in games.values() for g in L} | {g["opp_id"] for L in games.values() for g in L}
    cm_ = meta("competitions", comps, a.offline)
    kl_ = meta("clubs", clubs, a.offline)
    COMP = {k: {"t": find(v, ["typeId", "competitionTypeId"], 2), "name": find(v, ["name", "shortName"], 1)} for k, v in cm_.items()}
    CLUB = {k: {"nt": bool(find(v, ["isNationalTeam"], 2)), "main": str(find(v, ["mainClubId"], 2) or k),
                "name": find(v, ["name", "shortName"], 1)} for k, v in kl_.items()}

    non_eu_clubs = {g["club_id"] for L in games.values() for g in L if str(g["comp"]) in NON_EU}
    cut = pd.Timestamp(a.corte + " 20:55", tz="UTC")
    out, chk = [], collections.Counter()
    by_pid = collections.defaultdict(list)
    for r in rows:
        if r.get("tm_id"):
            by_pid[(r["tm_id"], r["season"])].append(r)
    for (pid, season), L in by_pid.items():
        multi = len({r["club_id"] for r in L}) > 1
        for r in L:
            for g in games.get(pid, []):
                played = (g["Min"] or 0) > 0 or g["state"] == "played"
                if not played or g["live"] or not g["date"]:
                    continue
                d = pd.Timestamp(g["date"])
                d = d.tz_localize("UTC") if d.tzinfo is None else d.tz_convert("UTC")
                if d > cut or str(g["season_id"]) != str(r["tmseason"]):
                    continue
                b = block_of(g, COMP, CLUB)
                if b is None or b == "SEL":
                    continue  # la selección no cuenta para ELO/FORM (model.json)
                if g["club_id"] != r["club_id"] and (multi or g["club_id"] in non_eu_clubs):
                    continue
                chk["gf" if g["gf"] is not None else "gf_none"] += 1
                chk["home" if g["home"] is not None else "home_none"] += 1
                out.append(dict(season=season, source_sheet=r["sheet"], source_row=r["row"], name=r["name"], tm_id=pid,
                                date=d.strftime("%Y-%m-%d %H:%M"), block=b, comp=g["comp"],
                                comp_name=COMP.get(str(g["comp"]), {}).get("name"),
                                cont_code=CONTCODE.get(str(g["comp"])) if b == "CONT" else None,
                                game_id=g["game_id"], club_id=g["club_id"], club=CLUB.get(g["club_id"], {}).get("name") or r["club"],
                                opponent_id=g["opp_id"], opponent=CLUB.get(g["opp_id"] or "", {}).get("name") or g["opp_id"],
                                home=g["home"], gf=g["gf"], ga=g["ga"], Min=g["Min"], G=g["G"], A=g["A"],
                                GC=g["GC"] if r["sheet"] == "PORTEROS" else None,
                                yellow=g["yellow"], red=g["red"], starter=g["starter"]))
    df = pd.DataFrame(out).sort_values(["season", "date", "tm_id"])
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out, index=False, encoding="utf-8-sig")
    print(f"{len(df)} filas jugador-partido -> {a.out}")
    print("  por temporada/bloque:", df.groupby(["season", "block"]).size().to_dict())
    print("  control de campos:", dict(chk))
    if chk["gf_none"] > 0.2 * max(1, len(df)) or df.opponent_id.isna().mean() > 0.2:
        print("  AVISO: faltan rival/resultado en muchas filas. Ejecuta --inspect <id> y ajusta parse_game().")
        sys.exit(2)


if __name__ == "__main__":
    main()
