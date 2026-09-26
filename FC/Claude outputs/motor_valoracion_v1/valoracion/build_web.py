"""Panel web: exporta la valoración a FC/Panel_FC/datos.js (lo lee index.html, que se abre con doble clic).

Por jugador y temporada: datos, notas, radar de estilo (6 ejes), jugadores parecidos y partido a partido
(fecha, rival, resultado, minutos, G, A, nota del partido y ELO tras el partido).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

import build_resumen

EPOCH = pd.Timestamp("2024-01-01")


def _num(v, nd=1):
    if v is None or (isinstance(v, float) and np.isnan(v)) or pd.isna(v):
        return None
    v = round(float(v), nd)
    return int(v) if nd == 0 or v.is_integer() else v


def build(base, cfg, out_dir, matches=None, sims=None):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    b = build_resumen.proyeccion(build_resumen.preparar(base, cfg), cfg).reset_index(drop=True)
    b = b.sort_values(["season", "CA_FINAL"], ascending=[True, False], na_position="last").reset_index(drop=True)
    idx = {(p, s): i for i, (p, s) in enumerate(zip(b.player_id, b.season))}
    # ID de Transfermarkt de cada ficha (sale de los partidos) → foto y enlaces (auxiliares/media/media_jugadores.json)
    tm = {}
    if matches is not None and "tm_id" in matches:
        t = matches.dropna(subset=["tm_id"]).drop_duplicates(["player_id", "season"])
        tm = {(p, s): str(int(v)) for p, s, v in zip(t.player_id, t.season, t.tm_id)}
    mfile = Path(__file__).resolve().parents[3] / "auxiliares" / "media" / "media_jugadores.json"
    media_all = json.loads(mfile.read_text(encoding="utf-8")) if mfile.exists() else {}
    vfile = mfile.parents[1] / "tmapi" / "valor_lesiones.json"
    vl_all = json.loads(vfile.read_text(encoding="utf-8")) if vfile.exists() else {}
    # escudo TM de cada club del Excel = club_id más frecuente en sus partidos
    crest = {}
    if matches is not None and "club_id" in matches:
        cc = matches.dropna(subset=["club_id"]).groupby("excel_club").club_id.agg(lambda s: s.mode().iloc[0])
        crest = {str(k): str(int(v)) for k, v in cc.items()}
    clubs, leagues, nats = (sorted(b[c].dropna().astype(str).unique().tolist()) for c in ("club", "league", "nat"))
    # nombre visible de cada club = el de FotMob (Excel y Transfermarkt usan variantes: "Real Sporting", "Sporting Gijón"…)
    import gzip as _gz0
    import unicodedata
    efile0 = Path(__file__).resolve().parents[3] / "auxiliares" / "equipos" / "equipos.json.gz"
    eqc = json.loads(_gz0.decompress(efile0.read_bytes()))["clubs"] if efile0.exists() else {}
    disp = [((eqc.get(c) or {}).get("name") or c) for c in clubs]
    fm_team = {c: (eqc.get(c) or {}).get("fm") for c in clubs}
    # id de FotMob de cada jugador (foto PNG recortada): mismo equipo FotMob + nombre (exacto, sin acentos o apellido único)
    nrm = lambda t: " ".join(unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode().lower().replace("-", " ").split())
    fjp = Path(__file__).resolve().parents[3] / "auxiliares" / "ligas" / "fotmob_jugadores.json"
    fmp = json.loads(fjp.read_text(encoding="utf-8")) if fjp.exists() else {}
    by_team, by_name = {}, {}
    for pid, (nm, tid) in fmp.items():
        by_team.setdefault(tid, []).append((nrm(nm), pid))
        by_name.setdefault(nrm(nm), set()).add(pid)

    def fm_id(name, club):
        n = nrm(name)
        cand = by_team.get(fm_team.get(club)) or []
        for k, pid in cand:
            if k == n:
                return pid
        last = n.split(" ")[-1]
        hit = [pid for k, pid in cand if k.split(" ")[-1] == last]
        if len(hit) == 1:
            return hit[0]
        g = by_name.get(n) or set()
        return next(iter(g)) if len(g) == 1 else None
    ci, li, ni = ({v: i for i, v in enumerate(x)} for x in (clubs, leagues, nats))
    grp = list(build_resumen.GRP)
    rad = build_resumen.radar(b)
    rows = []
    for i, x in enumerate(b.itertuples(index=False)):
        rows.append([
            x.name, 0 if x.season == "2025-26" else 1, _num(x.age, 0), ni.get(str(x.nat)), x.pos, grp.index(x.pos_group) if x.pos_group in grp else None,
            ci.get(str(x.club)), li.get(str(x.league)), _num(x.value_eur, 0),
            _num(x.LIGA_Min, 0), _num(x.TOT_Min, 0), _num(x.TOT_PJ, 0), _num(x.TOT_G, 0), _num(x.TOT_A, 0), _num(x.LIGA_G, 0), _num(x.LIGA_A, 0),
            _num(x.CA_FINAL), _num(x.PA_ESTIMATE), _num(x.PA_RANGE_LOW, 0), _num(x.PA_RANGE_HIGH, 0), _num(x.ELO), _num(x.FORM),
            _num(x.CONSISTENCY, 0), _num(x.opponent_strength, 0), _num(x.SCOUT_SCORE), _num(x.CA_CONFIDENCE, 0), x.Rol,
            [_num(v, 0) for v in rad[i]], _num(x.competition_strength, 0), _num(x.SEL_PJ, 0), _num(x.CONT_PJ, 0),
            idx.get((x.player_id, "2026-27" if x.season == "2025-26" else "2025-26")),
            tm.get((x.player_id, x.season)),
            [[_num(getattr(x, f"{bl}_PJ"), 0), _num(getattr(x, f"{bl}_Min"), 0), _num(getattr(x, f"{bl}_G"), 0), _num(getattr(x, f"{bl}_A"), 0)]
             for bl in ("LIGA", "COPA", "CONT", "FIFA", "SEL")],
            [_num(x.PROJ_1), _num(x.PROJ_2), _num(x.PROJ_3), _num(x.PROJ_LO), _num(x.PROJ_HI)],
            fm_id(x.name, str(x.club)),
        ])
    fields = ["name", "season", "age", "nat", "pos", "grp", "club", "league", "value", "ligaMin", "min", "pj", "g", "a", "ligaG", "ligaA",
              "ca", "pa", "paLo", "paHi", "elo", "form", "cons", "opp", "scout", "conf", "rol", "radar", "lgStr", "selPJ", "contPJ", "other", "tm", "comps", "proj", "fm"]

    sim = {}
    if sims is not None and len(sims):
        for (p, s), g in sims.sort_values("rank").groupby(["player_id", "season"]):
            if (p, s) in idx:
                sim[idx[(p, s)]] = [[idx[(q, s)], _num(v, 0)] for q, v in zip(g.similar_id, g.similarity) if (q, s) in idx][:6]

    games, opps = {}, []
    if matches is not None and len(matches):
        m = matches.dropna(subset=["elo_before"]).sort_values("date")
        m = m.assign(elo_after=70 + (m.elo_before + m.elo_delta - 1500) / 10)
        om = {}
        blocks = ["LIGA", "COPA", "CONT", "FIFA"]
        for (p, s), g in m.groupby(["player_id", "season"], sort=False):
            if (p, s) not in idx:
                continue
            arr, d0, e0 = [], 0, 0
            for r in g.itertuples(index=False):
                o = str(r.opponent)
                if o not in om:
                    om[o] = len(opps)
                    opps.append(o)
                day, elo = int((r.date - EPOCH).days), int(round(r.elo_after * 10))
                # plano y en diferencias (día y ELO respecto al partido anterior) para que el archivo pese menos
                arr += [day - d0, om[o], int(r.gf), int(r.ga), int(bool(r.home)), int(r.Min), int(r.G or 0), int(r.A or 0),
                        int(round(r.match_rating)) if pd.notna(r.match_rating) else -1, elo - e0, blocks.index(r.block) if r.block in blocks else 0]
                d0, e0 = day, elo
            games[idx[(p, s)]] = arr
    meta = {"generated": pd.Timestamp.now().strftime("%d/%m/%Y"), "fields": fields, "clubs": clubs, "leagues": leagues, "nats": nats,
            "groups": [[k, v[0], "#" + v[1]] for k, v in build_resumen.GRP.items()],
            "radar": {k: [a for a, _ in v] for k, v in build_resumen.RADAR.items()}, "epoch": EPOCH.strftime("%Y-%m-%d"),
            "gameStride": 11, "gameDelta": ["day", "elo10"], "gameFields": ["day", "opp", "gf", "ga", "home", "min", "g", "a", "rating", "elo10", "block"], "blocks": ["Liga", "Copa", "Continental", "Mundial Clubes"]}
    ti = fields.index("tm")
    usados = {r[ti] for r in rows if r[ti]}
    media = {k: [v.get("foto"), v.get("cat"), v.get("es"), v.get("qid")] for k, v in media_all.items() if k in usados}

    def comp_mv(h):  # [[aaaamm, valor en cientos de miles de €], ...]
        return [[int(d[:4] + d[5:7]), round(v / 1e5)] for d, v in h]
    # ficha TM: nacimiento, altura, pie (para cumpleaños y ficha)
    import gzip as _gz
    mp = mfile.parents[1] / "tmapi" / "cache" / "meta_players.json.gz"
    metap = json.loads(_gz.decompress(mp.read_bytes())) if mp.exists() else {}

    def ficha(k):
        m = metap.get(k) or {}
        at = m.get("attributes") or {}
        return [(m.get("lifeDates") or {}).get("dateOfBirth"), at.get("height"), (at.get("preferredFoot") or {}).get("name")]
    extra = {k: [(vl_all.get(k) or {}).get("c"), comp_mv((vl_all.get(k) or {}).get("mv", [])), (vl_all.get(k) or {}).get("inj", [])] + ficha(k)
             for k in usados}
    meta["crest"] = [crest.get(c) for c in clubs]
    # nombres oficiales cuando FotMob usa uno coloquial
    NAME_FIX = {"Sporting Gijón": "Real Sporting", "Sporting Gijon": "Real Sporting", "Racing Santander": "Real Racing Club",
                "Oviedo": "Real Oviedo", "Zaragoza": "Real Zaragoza", "Valladolid": "Real Valladolid"}
    meta["clubDisp"] = [NAME_FIX.get(d, d) if d else d for d in disp]
    meta["clubFm"] = [fm_team.get(c) for c in clubs]
    data = {"meta": meta, "media": media, "players": rows, "similar": sim}
    dump = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))
    (out_dir / "datos.js").write_text("window.FC_DATA=" + dump(data) + ";\n", encoding="utf-8")
    (out_dir / "extra.js").write_text("window.FC_EXTRA=" + dump(extra) + ";\n", encoding="utf-8")
    # trayectoria completa: 64 paquetes que la página carga al abrir una ficha (carrera/c_NN.js)
    cfile = mfile.parents[1] / "tmapi" / "carrera.json.gz"
    if cfile.exists():
        car = json.loads(_gz.decompress(cfile.read_bytes()))
        cdir = out_dir / "carrera"
        cdir.mkdir(exist_ok=True)
        buckets = {}
        for k, v in car["players"].items():
            if k in usados:
                buckets.setdefault(int(k) % 64, {})[k] = v
        for n in range(64):
            (cdir / f"c_{n:02d}.js").write_text("window.FC_CAR=Object.assign(window.FC_CAR||{}," + dump(buckets.get(n, {})) + ");\n", encoding="utf-8")
        (out_dir / "nombres.js").write_text("window.FC_NAMES=" + dump({"clubs": car["clubs"], "comps": car["comps"]}) + ";\n", encoding="utf-8")
    # equipos (FotMob + Wikidata + Wikipedia + noticias)
    efile = mfile.parents[1] / "equipos" / "equipos.json.gz"
    if efile.exists():
        eq = json.loads(_gz.decompress(efile.read_bytes()))
        (out_dir / "equipos.js").write_text("window.FC_TEAMS=" + dump(eq["clubs"]) + ";\n", encoding="utf-8")
    # partidos aparte: cada archivo por debajo de 16 MB
    (out_dir / "partidos.js").write_text("window.FC_GAMES=" + dump({"games": games, "opponents": opps}) + ";\n", encoding="utf-8")
    return out_dir / "datos.js"


if __name__ == "__main__":  # desde una caché: python build_web.py base.pkl FC/Panel_FC
    import pickle
    import sys
    d = pickle.load(open(sys.argv[1], "rb"))
    p = build(d["base"], d["cfg"], sys.argv[2], d.get("matches"), d.get("sims"))
    for f in ("datos.js", "extra.js", "partidos.js"):
        print(f, f"{(p.parent / f).stat().st_size / 1e6:.1f} MB")
