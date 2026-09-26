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
    b = build_resumen.preparar(base, cfg).reset_index(drop=True)
    b = b.sort_values(["season", "CA_FINAL"], ascending=[True, False], na_position="last").reset_index(drop=True)
    idx = {(p, s): i for i, (p, s) in enumerate(zip(b.player_id, b.season))}
    # ID de Transfermarkt de cada ficha (sale de los partidos) → foto y enlaces (auxiliares/media/media_jugadores.json)
    tm = {}
    if matches is not None and "tm_id" in matches:
        t = matches.dropna(subset=["tm_id"]).drop_duplicates(["player_id", "season"])
        tm = {(p, s): str(int(v)) for p, s, v in zip(t.player_id, t.season, t.tm_id)}
    mfile = Path(__file__).resolve().parents[3] / "auxiliares" / "media" / "media_jugadores.json"
    media_all = json.loads(mfile.read_text(encoding="utf-8")) if mfile.exists() else {}
    clubs, leagues, nats = (sorted(b[c].dropna().astype(str).unique().tolist()) for c in ("club", "league", "nat"))
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
        ])
    fields = ["name", "season", "age", "nat", "pos", "grp", "club", "league", "value", "ligaMin", "min", "pj", "g", "a", "ligaG", "ligaA",
              "ca", "pa", "paLo", "paHi", "elo", "form", "cons", "opp", "scout", "conf", "rol", "radar", "lgStr", "selPJ", "contPJ", "other", "tm"]

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
    usados = {r[-1] for r in rows if r[-1]}
    media = {k: [v.get("foto"), v.get("cat"), v.get("es"), v.get("qid")] for k, v in media_all.items() if k in usados}
    data = {"meta": meta, "media": media, "players": rows, "similar": sim, "games": games, "opponents": opps}
    js = "window.FC_DATA=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n"
    (out_dir / "datos.js").write_text(js, encoding="utf-8")
    return out_dir / "datos.js"


if __name__ == "__main__":  # desde una caché: python build_web.py base.pkl FC/Panel_FC
    import pickle
    import sys
    d = pickle.load(open(sys.argv[1], "rb"))
    p = build(d["base"], d["cfg"], sys.argv[2], d.get("matches"), d.get("sims"))
    print(p, f"{p.stat().st_size / 1e6:.1f} MB")
