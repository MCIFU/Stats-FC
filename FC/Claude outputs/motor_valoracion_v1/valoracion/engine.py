"""
Motor de valoración de futbolistas — rating_model_v1
Capas: RAW -> PER90 -> AJUSTE MUESTRA -> PERCENTILES -> ATRIBUTOS -> ROLES -> CA -> REL_PERF -> PA -> SCOUT
(+ ELO / FORM / CONSISTENCY si hay datos por partido).

Entrada canónica (DataFrame largo, una fila por jugador-temporada-bloque):
  player_id, name, age, nat, pos, club, league, season, block, PJ, Min, G, A, GC, CS, [métricas avanzadas...]
  - block en {LIGA, COPA, CONT, FIFA, SEL}
  - NaN = desconocido. 0 = cero real. El motor nunca convierte NaN en 0.
"""
import json, math
from pathlib import Path
import warnings
import numpy as np
import pandas as pd
warnings.simplefilter("ignore", pd.errors.PerformanceWarning)

CFG_DIR = Path(__file__).parent / "config"


def load_config(cfg_dir=CFG_DIR):
    c = {}
    for f in ["model", "metrics", "attributes", "positions", "roles", "competitions"]:
        p = Path(cfg_dir) / f"{f}.json"
        if p.exists():
            c[f] = json.loads(p.read_text(encoding="utf-8"))
    return c


# ---------------------------------------------------------------- utilidades
def interp_age(table: dict, age):
    """Interpolación lineal en una tabla {edad: valor}. Fuera de rango -> extremo."""
    if age is None or (isinstance(age, float) and math.isnan(age)):
        return np.nan
    ks = sorted((float(k), v) for k, v in table.items())
    if age <= ks[0][0]:
        return ks[0][1]
    if age >= ks[-1][0]:
        return ks[-1][1]
    for (a0, v0), (a1, v1) in zip(ks, ks[1:]):
        if a0 <= age <= a1:
            return v0 + (v1 - v0) * (age - a0) / (a1 - a0)


def pct_rank(values: pd.Series, pool: pd.Series):
    """Percentil (0-100) de cada valor frente a una distribución de referencia (mid-rank para empates).
    NaN se queda NaN."""
    pool = np.sort(pool.dropna().to_numpy(dtype=float))
    n = len(pool)
    out = pd.Series(np.nan, index=values.index)
    if n == 0:
        return out
    v = values.to_numpy(dtype=float)
    ok = ~np.isnan(v)
    lo = np.searchsorted(pool, v[ok], side="left")
    hi = np.searchsorted(pool, v[ok], side="right")
    out.loc[ok] = 100.0 * (lo + 0.5 * (hi - lo)) / n
    return out


def weighted_combo(df: pd.DataFrame, weights: dict, min_cov: float):
    """Media ponderada sobre columnas con dato; devuelve (valor, cobertura). Si cobertura < min_cov -> NaN."""
    total = sum(weights.values())
    num = pd.Series(0.0, index=df.index)
    den = pd.Series(0.0, index=df.index)
    for col, w in weights.items():
        if col not in df:
            continue
        x = df[col]
        m = x.notna()
        num[m] += w * x[m]
        den[m] += w
    cov = den / total if total else den
    val = num / den.replace(0, np.nan)
    val[cov + 1e-9 < min_cov] = np.nan
    return val, cov


# ---------------------------------------------------------------- capa 1-2: tabla base + per90
def build_base(raw: pd.DataFrame, cfg) -> pd.DataFrame:
    """Una fila por jugador-temporada con métricas LIGA/CONT, contexto de equipo y métricas por 90 (sin ajustar)."""
    M = cfg["model"]
    posmap = cfg["positions"]["pos_map"]
    key = ["player_id", "season"]
    info_cols = ["player_id", "season", "name", "age", "nat", "pos", "club", "league", "value_eur"]
    info = raw.sort_values("block").groupby(key, as_index=False).first()[[c for c in info_cols if c in raw]]

    def block(b):
        d = raw[raw.block == b].groupby(key, as_index=False).agg(
            {c: (lambda s: s.sum(min_count=1)) for c in ["PJ", "Min", "G", "A", "GC", "CS"] if c in raw})
        return d.rename(columns={c: f"{b}_{c}" for c in d.columns if c not in key})

    base = info
    for b in ["LIGA", "COPA", "CONT", "FIFA", "SEL"]:
        base = base.merge(block(b), on=key, how="left")
    base["pos_group"] = base["pos"].map(posmap)

    # advanced metrics (si vienen en la entrada, a nivel LIGA)
    adv = [m for m, d in cfg["metrics"]["metrics"].items() if d["availability"] == "advanced"]
    present = [m for m in adv if m in raw.columns]
    if present:
        a = raw[raw.block == "LIGA"].groupby(key, as_index=False)[present].first()
        base = base.merge(a, on=key, how="left")
    for m in adv:
        if m not in base:
            base[m] = np.nan

    # ------- contexto de equipo (proxy desde tus propios datos)
    liga = base[base.LIGA_Min.fillna(0) > 0]
    tm = liga.groupby(["season", "league", "club"]).agg(team_matches_proxy=("LIGA_PJ", "max"),
                                                       team_goals=("LIGA_G", lambda s: s.sum(min_count=1)),
                                                       n_players=("player_id", "count"))
    gk = liga[liga.pos_group == "GK"].groupby(["season", "league", "club"]).agg(
        gk_gc=("LIGA_GC", lambda s: s.sum(min_count=1)), gk_min=("LIGA_Min", "sum"))
    tm = tm.join(gk, how="left")
    tm["team_gc_p90"] = tm.gk_gc / (tm.gk_min / 90)
    tm.loc[tm.gk_min.fillna(0) < 90 * 5, "team_gc_p90"] = np.nan  # poca muestra de porteros -> desconocido
    tm["team_gf_p90_proxy"] = tm.team_goals / tm.team_matches_proxy
    tm["team_gd_p90_proxy"] = tm.team_gf_p90_proxy - tm.team_gc_p90
    tm = tm.reset_index()
    weak = tm.n_players < M["sample"].get("min_players_team_proxy", 0)
    tm.loc[weak, ["team_matches_proxy", "team_gc_p90", "team_gf_p90_proxy", "team_gd_p90_proxy"]] = np.nan
    tm["team_strength_in_league"] = tm.groupby(["season", "league"])["team_gd_p90_proxy"].rank(pct=True) * 100
    base = base.merge(tm[["season", "league", "club", "team_matches_proxy", "team_gc_p90", "team_gf_p90_proxy",
                          "team_gd_p90_proxy", "team_strength_in_league"]],
                      on=["season", "league", "club"], how="left")

    cont = base[base.CONT_Min.fillna(0) > 0].groupby(["season", "club"]).agg(team_cont_matches_proxy=("CONT_PJ", "max")).reset_index()
    base = base.merge(cont, on=["season", "club"], how="left")

    # ------- métricas básicas (NaN si no hay minutos en el bloque: desconocido, no 0)
    has_liga = base.LIGA_Min.fillna(0) > 0
    n90 = base.LIGA_Min / 90
    base["goals_p90"] = np.where(has_liga, base.LIGA_G / n90, np.nan)
    base["assists_p90"] = np.where(has_liga, base.LIGA_A / n90, np.nan)
    base["min_share"] = np.where(has_liga, (base.LIGA_Min / (base.team_matches_proxy * 90)).clip(upper=1), np.nan)
    base["min_per_app"] = np.where(has_liga & (base.LIGA_PJ > 0), base.LIGA_Min / base.LIGA_PJ, np.nan)
    has_cont = base.CONT_Min.fillna(0) > 0
    base["CONT_GA"] = base.CONT_G + base.CONT_A
    base["cont_ga_p90"] = np.where(has_cont, base.CONT_GA / (base.CONT_Min / 90), np.nan)
    base["cont_min_share"] = np.where(has_cont, (base.CONT_Min / (base.team_cont_matches_proxy * 90)).clip(upper=1), np.nan)
    is_gk = base.pos_group == "GK"
    base["gk_gc_p90"] = np.where(is_gk & has_liga, base.LIGA_GC / n90, np.nan)
    base["gk_cs_pct"] = np.where(is_gk & has_liga & (base.LIGA_PJ > 0), base.LIGA_CS / base.LIGA_PJ, np.nan)
    base.loc[is_gk, "team_gc_p90"] = np.nan  # en porteros ya se usa su GC propio; evita doble conteo
    base["ga_p90"] = np.where(has_liga, (base.LIGA_G + base.LIGA_A) / n90, np.nan)  # solo informativo

    # ------- minutos totales (Liga+Copa+Cont+FIFA; SEL aparte)
    base["TOT_Min"] = base[["LIGA_Min", "COPA_Min", "CONT_Min", "FIFA_Min"]].sum(axis=1, min_count=1)
    base["TOT_PJ"] = base[["LIGA_PJ", "COPA_PJ", "CONT_PJ", "FIFA_PJ"]].sum(axis=1, min_count=1)
    return base


# ---------------------------------------------------------------- capa 3: contexto de competición
def add_context(base, cfg):
    comps = cfg.get("competitions", {}).get("leagues", {})
    C = cfg["model"]["context"]
    base["competition_strength"] = base.league.map(lambda l: comps.get(l, {}).get("strength", np.nan))
    dq = cfg["model"].get("data_quality_by_players", {})
    thr = sorted(((int(k), v) for k, v in dq.items()), reverse=True)
    cnt = base.groupby(["season", "league"]).player_id.transform("count")
    auto = cnt.map(lambda n: next((v for k, v in thr if n >= k), 0.3))
    base["league_players_in_file"] = cnt
    base["competition_data_quality"] = base.league.map(lambda l: comps.get(l, {}).get("data_quality", np.nan)).fillna(auto)
    base["opponent_strength"] = np.nan  # requiere datos por partido
    opp = base.opponent_strength
    wc, wo = C["w_competition"], C["w_opponent"]
    base["context_score"] = np.where(opp.notna(), (wc * base.competition_strength + wo * opp) / (wc + wo),
                                     base.competition_strength)
    # clubes con muy pocos jugadores dentro de una liga grande: etiqueta de liga no fiable
    Q = cfg["model"]["league_label_check"]
    ncl = base.groupby(["season", "league", "club"]).player_id.transform("count")
    nlg = base.groupby(["season", "league"]).player_id.transform("count")
    base["league_label_warning"] = np.where((ncl < Q["club_min_players"]) & (nlg >= Q["league_min_players"]), Q["message"], None)
    base.loc[base.league_label_warning.notna(), ["context_score", "competition_strength"]] = np.nan
    base["team_strength"] = (base.competition_strength + C["team_spread"] * (base.team_strength_in_league - 50)).clip(0, 100)
    return base


# ---------------------------------------------------------------- capa 4-5: ajuste de muestra + percentiles
def add_percentiles(base, cfg):
    S = cfg["model"]["sample"]
    k = S["shrinkage_prior_minutes"]
    pool_min = S["min_minutes_reference_pool"]
    min_pool_league = S["min_pool_league"]
    metrics = cfg["metrics"]["metrics"]
    base["sample_conf"] = 1 - np.exp(-base.LIGA_Min.fillna(0) / S["confidence_k_minutes"])
    rel = S.get("pool_relative_to_league_max", 1.0)
    lg_max = base.groupby(["season", "league"]).LIGA_Min.transform("max").fillna(0)
    base["pool_threshold"] = np.minimum(pool_min, rel * lg_max)
    base["in_pool"] = (base.LIGA_Min.fillna(0) >= base.pool_threshold) & (base.LIGA_Min.fillna(0) > 0)
    base["league_pool_small"] = False

    for m, d in metrics.items():
        if m not in base or base[m].notna().sum() == 0:
            base[f"adj_{m}"] = np.nan
            base[f"pctG_{m}"] = np.nan
            base[f"pctL_{m}"] = np.nan
            continue
        x = base[m].astype(float)
        mins_col = "CONT_Min" if d.get("block") == "CONT" else "LIGA_Min"
        mins = base[mins_col].fillna(0)
        if mins_col == "LIGA_Min":
            pool_flag = base.in_pool
        else:
            pool_flag = (mins >= np.minimum(pool_min, rel * base.groupby("season")[mins_col].transform("max").fillna(0))) & (mins > 0)
        # --- ajuste por muestra (empirical Bayes hacia la media de su posición en la temporada)
        if d.get("shrink"):
            grp_mean = base[pool_flag].groupby(["season", "pos_group"])[m].mean()
            prior = base.set_index(["season", "pos_group"]).index.map(lambda ix: grp_mean.get(ix, np.nan))
            prior = pd.Series(np.asarray(prior, dtype=float), index=base.index)
            adj = (x * mins + prior * k) / (mins + k)
            adj = adj.where(x.notna())
        else:
            adj = x
        base[f"adj_{m}"] = adj
        inv = d["direction"] == "lower_is_better"
        pG = pd.Series(np.nan, index=base.index)
        pL = pd.Series(np.nan, index=base.index)
        for (season, pg), idx in base.groupby(["season", "pos_group"]).groups.items():
            sub = adj.loc[idx]
            pool = sub[pool_flag.loc[idx]]
            pG.loc[idx] = pct_rank(sub, pool)
            for lg, idx2 in base.loc[idx].groupby("league").groups.items():
                sub2 = adj.loc[idx2]
                pool2 = sub2[pool_flag.loc[idx2]]
                if pool2.notna().sum() >= min_pool_league:
                    pL.loc[idx2] = pct_rank(sub2, pool2)
                else:
                    pL.loc[idx2] = pG.loc[idx2]
                    base.loc[idx2, "league_pool_small"] = True
        if inv:
            pG, pL = 100 - pG, 100 - pL
        base[f"pctG_{m}"] = pG
        base[f"pctL_{m}"] = pL
    return base


# ---------------------------------------------------------------- capa 6-7: atributos y roles
def add_attributes(base, cfg):
    mc = cfg["model"]["coverage"]["attribute_min_coverage"]
    for a, d in cfg["attributes"]["attributes"].items():
        for ref in ["G", "L"]:
            w = {f"pct{ref}_{m}": v for m, v in d["components"].items()}
            val, cov = weighted_combo(base, w, mc)
            base[f"attr{ref}_{a}"] = val
        base[f"cov_{a}"] = cov
    return base


def add_roles(base, cfg):
    mc = cfg["model"]["coverage"]["role_min_coverage"]
    for r, d in cfg["roles"]["roles"].items():
        w = {f"attrL_{a}": v for a, v in d["weights"].items()}
        val, cov = weighted_combo(base, w, mc)
        ok = base.pos_group.isin(d["groups"])
        base[f"role_{r}"] = val.where(ok)
        base[f"rolecov_{r}"] = cov.where(ok)
    return base


# ---------------------------------------------------------------- capa 8: Current Ability
def add_ca(base, cfg):
    CA = cfg["model"]["current_ability"]
    CF = cfg["model"]["confidence"]
    groups = cfg["positions"]["groups"]
    for c in ["score_global", "score_league", "pos_coverage"]:
        base[c] = np.nan
    for g, gd in groups.items():
        idx = base.pos_group == g
        wG = {f"attrG_{a}": v for a, v in gd["ca_weights"].items()}
        wL = {f"attrL_{a}": v for a, v in gd["ca_weights"].items()}
        sG, cov = weighted_combo(base[idx], wG, 0.0)
        sL, _ = weighted_combo(base[idx], wL, 0.0)
        # encoger hacia 50 cuando la posición tiene poca cobertura de datos (no afirmar lo que no medimos)
        fac = np.minimum(1, (cov / CA["coverage_shrink_ref"]) ** 0.5)
        base.loc[idx, "score_global_unshrunk"] = sG
        base.loc[idx, "score_league_unshrunk"] = sL
        base.loc[idx, "score_global"] = 50 + (sG - 50) * fac
        base.loc[idx, "score_league"] = 50 + (sL - 50) * fac
        base.loc[idx, "pos_coverage"] = cov
    rated = base.LIGA_Min.fillna(0) >= cfg["model"]["sample"]["min_minutes_rated"]
    base["league_base"] = CA["league_base_factor"] * base.context_score
    base["CA_CONTEXT"] = (base.league_base + CA["context_slope"] * (base.score_league - 50)).clip(0, 100)
    base["CA_RAW"] = (CA["raw_scale_center"] + CA["raw_scale_slope"] * (base.score_global - 50)).clip(0, 100)
    blend = CA["w_context"] * base.CA_CONTEXT + CA["w_raw"] * base.CA_RAW
    base["CA_FINAL"] = (base.sample_conf * blend + (1 - base.sample_conf) * base.league_base).clip(0, 100)
    base["CA_CONFIDENCE"] = 100 * (CF["w_sample"] * base.sample_conf + CF["w_coverage"] * base.pos_coverage.fillna(0)
                                   + CF["w_competition_data"] * base.competition_data_quality.fillna(0.5)
                                   * np.where(base.league_pool_small, 0.5, 1.0))
    for c in ["CA_CONTEXT", "CA_RAW", "CA_FINAL", "CA_CONFIDENCE"]:
        base.loc[~rated | base.context_score.isna(), c] = np.nan
    return base


# ---------------------------------------------------------------- capa 9-11: REL_PERF, PA
def add_relperf_pa(base, cfg, prev=None):
    R = cfg["model"]["relative_performance"]
    P = cfg["model"]["potential"]
    def band(a):
        if pd.isna(a):
            return None
        for lo, hi, lab in R["age_bands"]:
            if lo <= a <= hi:
                return lab
    base["age_band"] = base.age.map(band)
    base["REL_PERF"] = np.nan
    pool = base.in_pool & base.CA_FINAL.notna()
    for (s, g, b), idx in base.groupby(["season", "pos_group", "age_band"]).groups.items():
        sub = base.loc[idx]
        p1 = pct_rank(sub.score_league, sub.score_league[pool.loc[idx]])
        p2 = pct_rank(sub.CA_CONTEXT, sub.CA_CONTEXT[pool.loc[idx]])
        base.loc[idx, "REL_PERF"] = R["w_league_score"] * p1 + R["w_context_score"] * p2
    base.loc[base.CA_FINAL.isna(), "REL_PERF"] = np.nan

    base["growth_age"] = base.age.map(lambda a: interp_age(P["growth_by_age"], a))
    mult = P["relperf_multiplier_min"] + (P["relperf_multiplier_max"] - P["relperf_multiplier_min"]) * base.REL_PERF / 100
    headroom = ((100 - base.CA_FINAL) / P["headroom_ref"]).clip(0, 1)
    base["growth_effective"] = base.growth_age * mult * headroom
    base["trend_ca"] = np.nan
    if prev is not None:
        pv = prev[["player_id", "CA_FINAL"]].rename(columns={"CA_FINAL": "CA_prev"})
        base = base.merge(pv, on="player_id", how="left")
        ok = base.LIGA_Min.fillna(0) >= P["min_minutes_trend"]
        base["trend_ca"] = np.where(ok, (base.CA_FINAL - base.CA_prev).clip(-5, 5), np.nan)
    trend = base.trend_ca.fillna(0) * P["trend_weight"]
    base["PA_ESTIMATE"] = (base.CA_FINAL + (base.growth_effective + trend).clip(lower=0)).clip(upper=99)
    rb = base.age.map(lambda a: interp_age(P["range_base"], a))
    width = rb * (1.5 - base.CA_CONFIDENCE / 100)
    base["PA_RANGE_LOW"] = np.maximum(base.CA_FINAL, base.PA_ESTIMATE - width)
    base["PA_RANGE_HIGH"] = (base.PA_ESTIMATE + width).clip(upper=100)
    base["PA_CONFIDENCE"] = base.CA_CONFIDENCE * base.age.map(lambda a: interp_age(P["age_confidence"], a))
    for c in ["PA_ESTIMATE", "PA_RANGE_LOW", "PA_RANGE_HIGH", "PA_CONFIDENCE"]:
        base.loc[base.CA_FINAL.isna() | base.age.isna(), c] = np.nan
    return base


# ---------------------------------------------------------------- capa 12: ELO / FORM / CONSISTENCY (por partido)
def match_layer(matches: pd.DataFrame, base: pd.DataFrame, cfg):
    """matches: player_id, date, block, club, opponent, home(bool), gf, ga, Min, G, A, [GC], match_rating(opcional 0-100).
    Devuelve (por_jugador, partidos_con_elo). Si no hay partidos, devuelve None."""
    if matches is None or len(matches) == 0:
        return None, None
    E = cfg["model"]["elo"]
    F = cfg["model"]["form"]
    Cn = cfg["model"]["consistency"]
    m = matches.sort_values("date").copy()
    m = m[m.block.map(lambda b: cfg["model"]["rating_blocks"].get(b, {}).get("counts_for_elo", False))]
    # --- Elo de equipos a partir de resultados (fuerza del rival)
    team_elo = {}
    games = m.drop_duplicates(["date", "club", "opponent"])
    for _, r in games.iterrows():
        a, b = r.club, r.opponent
        ea, eb = team_elo.get(a, 1500.0), team_elo.get(b, 1500.0)
        h = E["home_advantage"] if r.home else -E["home_advantage"]
        exp = 1 / (1 + 10 ** ((eb - ea - h) / 400))
        s = 1.0 if r.gf > r.ga else 0.5 if r.gf == r.ga else 0.0
        team_elo[a] = ea + 20 * (s - exp)
        team_elo[b] = eb - 20 * (s - exp)
    # --- rating individual de partido si no viene dado: percentil de (G+A)/90 en su posición + resultado
    pos = base.drop_duplicates("player_id").set_index("player_id").pos_group
    m["pos_group"] = m.player_id.map(pos)
    if "match_rating" not in m or m.match_rating.isna().all():
        m["_ga90"] = (m.G + m.A) / (m.Min.clip(lower=15) / 90)
        m["match_rating"] = m.groupby("pos_group")["_ga90"].rank(pct=True) * 100
    comp = base.drop_duplicates("player_id").set_index("player_id").competition_strength
    elo = {}
    rows = []
    for _, r in m.iterrows():
        p = r.player_id
        if p not in elo:
            cs = comp.get(p, 80)
            elo[p] = E["initial"] + (E["initial_competition_factor"] * ((cs if pd.notna(cs) else 80) - 80) if E["initial_from_competition"] else 0)
        opp = team_elo.get(r.opponent, 1500.0)
        h = E["home_advantage"] if r.home else -E["home_advantage"]
        exp = 1 / (1 + 10 ** ((opp - elo[p] - h) / 400))
        res = 1.0 if r.gf > r.ga else 0.5 if r.gf == r.ga else 0.0
        score = E["w_individual"] * r.match_rating / 100 + E["w_result"] * res
        k = E["k_base"] * min(r.Min / E["minutes_full"], 1) * E["importance"].get(r.block, 1.0)
        delta = k * (score - exp)
        rows.append({**r.to_dict(), "opp_elo": opp, "elo_before": elo[p], "expected": exp, "score": score, "elo_delta": delta})
        elo[p] += delta
    mm = pd.DataFrame(rows)
    sc = E["scale_to_100"]
    out = []
    for p, g in mm.groupby("player_id"):
        g = g.sort_values("date")
        d = {"player_id": p, "ELO_POINTS": elo[p], "ELO": np.clip(sc["center_value"] + (elo[p] - sc["center"]) / sc["points_per_unit"], 0, 100),
             "n_matches": len(g), "opponent_strength_elo": np.average(g.opp_elo, weights=g.Min.clip(lower=1))}
        hl = F["decay_half_life_matches"]
        for n in F["windows"]:
            t = g.tail(n)
            w = 0.5 ** (np.arange(len(t))[::-1] / hl) * (t.Min.clip(lower=1) / 90)
            d[f"FORM_{n}"] = np.average(t.match_rating, weights=w) if len(t) else np.nan
        if len(g) >= Cn["min_matches"]:
            w = g.Min.clip(lower=1)
            mu = np.average(g.match_rating, weights=w)
            sd = math.sqrt(np.average((g.match_rating - mu) ** 2, weights=w))
            shrink = len(g) / (len(g) + Cn["min_matches"])
            d["CONSISTENCY"] = float(np.clip(100 * (1 - sd / (2 * Cn["sd_reference"])), 0, 100) * shrink + 50 * (1 - shrink))
        else:
            d["CONSISTENCY"] = np.nan
        out.append(d)
    return pd.DataFrame(out), mm


# ---------------------------------------------------------------- capa 13: SCOUT SCORE
def add_scout(base, cfg):
    S = cfg["model"]["scout_score"]
    base["AGE_SCORE"] = base.age.map(lambda a: interp_age(S["age_score"], a))
    base["CONFIDENCE"] = base.CA_CONFIDENCE
    for c in ["FORM", "ELO", "CONSISTENCY"]:
        if c not in base:
            base[c] = np.nan
    val, cov = weighted_combo(base, S["weights"], 0.0)
    base["SCOUT_SCORE"] = val.where(base.CA_FINAL.notna())
    base["scout_coverage"] = cov
    return base


# ---------------------------------------------------------------- similares
def similar_players(base, cfg):
    T = cfg["model"]["similarity"]
    metr = [m for m, d in cfg["metrics"]["metrics"].items() if d.get("corr_group") not in ("team_def",) and f"pctG_{m}" in base and base[f"pctG_{m}"].notna().any()]
    res = []
    for (s, g), sub in base[(base.LIGA_Min.fillna(0) >= T["min_minutes"])].groupby(["season", "pos_group"]):
        cols = [f"pctG_{m}" for m in metr if sub[f"pctG_{m}"].notna().mean() > 0.5]
        if len(sub) < 3 or not cols:
            continue
        X = sub[cols].to_numpy(dtype=float)
        mask = ~np.isnan(X)
        Xc = np.where(mask, X - 50, 0.0)
        norms = np.linalg.norm(Xc, axis=1)
        norms[norms == 0] = 1
        sim = (Xc @ Xc.T) / np.outer(norms, norms)
        np.fill_diagonal(sim, -9)
        ids = sub.index.to_numpy()
        for i in range(len(sub)):
            top = np.argsort(-sim[i])[: T["top_n"]]
            for rnk, j in enumerate(top, 1):
                res.append({"season": s, "pos_group": g, "player_id": sub.player_id.iloc[i], "name": sub.name.iloc[i],
                            "rank": rnk, "similar_id": sub.player_id.iloc[j], "similar_name": sub.name.iloc[j],
                            "similar_club": sub.club.iloc[j], "similar_league": sub.league.iloc[j],
                            "similarity": round(float(sim[i, j]) * 100, 1), "metrics_used": len(cols)})
    return pd.DataFrame(res)


def correlations(base, cfg):
    metr = [m for m in cfg["metrics"]["metrics"] if f"adj_{m}" in base and base[f"adj_{m}"].notna().sum() > 30]
    out = []
    for g, sub in base[base.in_pool].groupby("pos_group"):
        cols = [f"adj_{m}" for m in metr if sub[f"adj_{m}"].notna().sum() > 30]
        if len(cols) < 2:
            continue
        c = sub[cols].corr(method="spearman")
        for i, a in enumerate(cols):
            for b in cols[i + 1:]:
                out.append({"pos_group": g, "metric_a": a[4:], "metric_b": b[4:], "spearman": round(c.loc[a, b], 3),
                            "flag": "ALTA (>0.7): posible doble conteo" if abs(c.loc[a, b]) > 0.7 else ""})
    return pd.DataFrame(out)


def run(raw: pd.DataFrame, cfg, matches=None, prev=None):
    base = build_base(raw, cfg)
    base = add_context(base, cfg)
    base = add_percentiles(base, cfg)
    base = add_attributes(base, cfg)
    base = add_roles(base, cfg)
    base = add_ca(base, cfg)
    base = add_relperf_pa(base, cfg, prev)
    per_player, mm = match_layer(matches, base, cfg)
    if per_player is not None:
        base = base.drop(columns=[c for c in per_player.columns if c != "player_id" and c in base]).merge(per_player, on="player_id", how="left")
        base["FORM"] = base.get("FORM_10")
    base = add_scout(base, cfg)
    base["model_version"] = cfg["model"]["model_version"]
    return base, mm
