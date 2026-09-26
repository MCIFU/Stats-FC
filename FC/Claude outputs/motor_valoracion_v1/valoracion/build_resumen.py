"""Excel RESUMEN: lo esencial de la valoración en pocas columnas y hojas visuales (el Excel extenso sigue teniendo todo).

Hojas: LEEME · FICHA (elige jugador) · TOP (mejores por posición) · PROMESAS (≤21) · LIGAS · JUGADORES (tabla corta).
Solo valores (salvo la FICHA, que busca en JUGADORES): se abre rápido y pesa poco.
"""
import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import RadarChart, Reference
from openpyxl.formatting.rule import ColorScaleRule, DataBarRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter as L
from openpyxl.worksheet.datavalidation import DataValidation

FONT, NAVY, INK, MUTED, LINE = "Arial", "0F2340", "0F172A", "64748B", "E2E8F0"
GRP = {"GK": ("Porteros", "7C3AED"), "CB": ("Centrales", "2563EB"), "FB": ("Laterales", "0891B2"),
       "MID": ("Mediocentros", "16A34A"), "AMW": ("Mediapuntas y extremos", "EA580C"), "ST": ("Delanteros", "DC2626")}
MEDAL = {1: "FDE68A", 2: "E5E7EB", 3: "FED7AA"}
THIN = Side(style="thin", color=LINE)
# ejes del radar = media de los atributos disponibles (percentiles 0-100 frente a su posición, todas las ligas)
RADAR = {
    "campo": [("Gol", ["GOAL_OUTPUT", "SHOT_QUALITY", "FINISHING"]), ("Creación", ["ASSIST_OUTPUT", "CHANCE_CREATION"]),
              ("Pase", ["PASSING", "LONG_PASSING"]), ("Regate", ["DRIBBLING"]),
              ("Defensa", ["TACKLING", "INTERCEPTING", "BOX_DEFENDING", "PRESSING"]), ("Peso en el equipo", ["USAGE"])],
    "GK": [("Paradas", ["SHOT_STOPPING"]), ("Resultados", ["GK_RESULTS"]), ("Distribución", ["DISTRIBUTION"]),
           ("Peso en el equipo", ["USAGE"]), ("Forma", ["@FORM"]), ("Regularidad", ["@CONSISTENCY"])],
}


def f(size=10, bold=False, color=INK, italic=False):
    return Font(name=FONT, size=size, bold=bold, color=color, italic=italic)


def fill(c):
    return PatternFill("solid", fgColor=c)


C = Alignment(horizontal="center", vertical="center")
LFT = Alignment(horizontal="left", vertical="center", indent=1)


def title(ws, text, sub, ncol):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncol)
    ws["A1"], ws["A2"] = text, sub
    ws["A1"].font, ws["A1"].fill, ws["A1"].alignment = f(16, True, "FFFFFF"), fill(NAVY), LFT
    ws["A2"].font, ws["A2"].fill, ws["A2"].alignment = f(9, False, "334155", True), fill("E2E8F0"), LFT
    ws.row_dimensions[1].height, ws.row_dimensions[2].height = 34, 20
    ws.sheet_view.showGridLines = False


def header(ws, row, cols, color=NAVY, start=1):
    for j, h in enumerate(cols, start):
        c = ws.cell(row, j, h)
        c.font, c.fill = f(9, True, "FFFFFF"), fill(color)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[row].height = 30


def put(ws, row, vals, fmts, left=(), bold=(), start=1):
    for j, v in enumerate(vals, start):
        if isinstance(v, (np.floating, float)) and np.isnan(v):
            v = None
        elif isinstance(v, np.integer):
            v = int(v)
        elif isinstance(v, np.floating):
            v = float(v)
        c = ws.cell(row, j, v)
        c.font = f(10, (j - start) in bold)
        c.alignment = LFT if (j - start) in left else C
        c.border = Border(bottom=THIN)
        fm = fmts[j - start]
        if fm:
            c.number_format = fm


def scale(ws, ref, lo="F8FAFC", mid=None, hi="34D399"):
    if mid:
        ws.conditional_formatting.add(ref, ColorScaleRule(start_type="num", start_value=40, start_color="FCA5A5", mid_type="num",
                                                          mid_value=65, mid_color="FEF3C7", end_type="num", end_value=85, end_color="34D399"))
    else:
        ws.conditional_formatting.add(ref, ColorScaleRule(start_type="percentile", start_value=5, start_color=lo,
                                                          end_type="percentile", end_value=95, end_color=hi))


def bar(ws, ref, color="2563EB"):
    ws.conditional_formatting.add(ref, DataBarRule(start_type="num", start_value=40, end_type="num", end_value=100, color=color, showValue=True))


def preparar(base, cfg):
    b = base.copy()
    roles = cfg["roles"]["roles"]
    rc = [c for c in b.columns if c.startswith("role_") and not c.startswith("rolecov_")]
    rv = b[rc].apply(pd.to_numeric, errors="coerce")
    b["Rol"] = None
    has = rv.notna().any(axis=1)
    b.loc[has, "Rol"] = rv[has].idxmax(axis=1).map(lambda x: roles.get(x[5:], {}).get("label"))
    for k in ("G", "A", "PJ"):
        b[f"TOT_{k}"] = b[[f"{bl}_{k}" for bl in ("LIGA", "COPA", "CONT", "FIFA") if f"{bl}_{k}" in b]].sum(axis=1, min_count=1)
    b["KEY"] = b.name.astype(str) + " | " + b.club.astype(str) + " | " + b.season.astype(str)
    b["Grupo"] = b.pos_group.map(lambda g: GRP.get(g, ("", ""))[0])
    return b


# declive medio por año de edad a partir de los 30 (porteros 2 años más tarde, centrales 1): estimación propia
DECLIVE = {30: 0.5, 31: 0.8, 32: 1.2, 33: 1.6}


def proyeccion(b, cfg, years=3):
    """CA esperado dentro de 1..3 años. Crecimiento = parte del margen PA-CA que la curva growth_by_age reparte
    entre este año y el siguiente (misma curva que el PA); declive fijo desde los 30. Banda con el rango del PA."""
    P = cfg["model"]["potential"]
    gba = {int(k): v for k, v in P["growth_by_age"].items()}
    G = lambda a: gba.get(int(min(max(a, min(gba)), max(gba))), 0.0) if a <= max(gba) else 0.0
    delay = P.get("growth_age_delay_by_group", {})
    out = {f"PROJ_{t}": [] for t in range(1, years + 1)} | {"PROJ_LO": [], "PROJ_HI": []}
    for ca, pa, lo, hi, age, g in zip(b.CA_FINAL, b.PA_ESTIMATE, b.PA_RANGE_LOW, b.PA_RANGE_HIGH, b.age, b.pos_group):
        if pd.isna(ca) or pd.isna(age):
            for k in out:
                out[k].append(np.nan)
            continue
        a0 = age - delay.get(g, 0)
        gap = (pa - ca) if pd.notna(pa) else 0.0
        v = ca
        for t in range(1, years + 1):
            frac = 1 - G(a0 + t) / G(a0) if G(a0) > 0 else 1.0
            dec = sum(DECLIVE.get(int(a0 + k), 2.0 if a0 + k > 33 else 0.0) for k in range(t))
            v = ca + max(gap, 0) * frac - dec
            out[f"PROJ_{t}"].append(v)
        f3 = 1 - G(a0 + years) / G(a0) if G(a0) > 0 else 1.0
        w = 1.0 * years
        out["PROJ_LO"].append(v - w - (max(pa - lo, 0) * f3 if pd.notna(lo) and pd.notna(pa) else 0))
        out["PROJ_HI"].append(v + w + (max(hi - pa, 0) * f3 if pd.notna(hi) and pd.notna(pa) else 0))
    for k, v in out.items():
        b[k] = np.clip(v, 0, 100)
    return b


def radar(b):
    out = np.full((len(b), 6), np.nan)
    gk = (b.pos_group == "GK").to_numpy()
    for key, axes in RADAR.items():
        mask = gk if key == "GK" else ~gk
        for k, (_, attrs) in enumerate(axes):
            cols = []
            for a in attrs:
                if a.startswith("@"):  # percentil dentro de los porteros
                    cols.append(b[a[1:]].where(b.pos_group == "GK").groupby(b.season).rank(pct=True) * 100)
                elif f"attrG_{a}" in b:
                    cols.append(b[f"attrG_{a}"])
            if cols:
                out[mask, k] = pd.concat(cols, axis=1).mean(axis=1).to_numpy()[mask]
    return out


def build(base, cfg, out_path):
    b = preparar(base, cfg)
    rad = radar(b)
    for k in range(6):
        b[f"R{k + 1}"] = np.round(rad[:, k])
    wb = Workbook()
    wb._named_styles["Normal"].font = Font(name=FONT, size=10)
    wl = wb.active
    wl.title = "LEEME"
    wf, wc, wt, wp, wg, wj = (wb.create_sheet(n) for n in ("FICHA", "COMPARAR", "TOP", "PROMESAS", "LIGAS", "JUGADORES"))

    # ---------------- JUGADORES (tabla corta, base de la ficha)
    cols = [("KEY", "KEY", None), ("Jugador", "name", None), ("Temp.", "season", None), ("Edad", "age", "0"), ("POS", "pos", None),
            ("Club", "club", None), ("Liga", "league", None), ("Min", "TOT_Min", "#,##0"), ("PJ", "TOT_PJ", "0"), ("G", "TOT_G", "0"),
            ("A", "TOT_A", "0"), ("NIVEL (CA)", "CA_FINAL", "0.0"), ("POTENCIAL (PA)", "PA_ESTIMATE", "0.0"), ("ELO", "ELO", "0.0"),
            ("FORMA", "FORM", "0.0"), ("REGULARIDAD", "CONSISTENCY", "0"), ("NIVEL RIVALES", "opponent_strength", "0"),
            ("INTERÉS SCOUT", "SCOUT_SCORE", "0.0"), ("Rol", "Rol", None), ("Fiabilidad", "CA_CONFIDENCE", "0\"%\"")]
    cols += [(f"RADAR {k}", f"R{k}", "0") for k in range(1, 7)]  # ejes del radar (ocultos; los usan FICHA y COMPARAR)
    j = b.sort_values(["season", "CA_FINAL"], ascending=[False, False], na_position="last")
    title(wj, "JUGADORES — resumen de la valoración", "Una fila por jugador y temporada. Filtra por liga, posición, edad… Todos los detalles y cálculos: Valoracion_FC_v1.2.xlsx", len(cols) - 6)
    header(wj, 3, [c[0] for c in cols])
    fm = [c[2] for c in cols]
    for i, row in enumerate(j[[c[1] for c in cols]].itertuples(index=False), 4):
        put(wj, i, list(row), fm, left=(1, 5, 6, 18), bold=(1, 11))
    last = 3 + len(j)
    for col in ("L", "M"):
        bar(wj, f"{col}4:{col}{last}", "2563EB" if col == "L" else "7C3AED")
    scale(wj, f"N4:N{last}", mid=True)
    for col in ("O", "P", "R"):
        wj.conditional_formatting.add(f"{col}4:{col}{last}", ColorScaleRule(start_type="percentile", start_value=5, start_color="FCA5A5",
                                                                           mid_type="percentile", mid_value=50, mid_color="FEF3C7",
                                                                           end_type="percentile", end_value=95, end_color="34D399"))
    wj.conditional_formatting.add(f"A4:{L(len(cols))}{last}", FormulaRule(formula=["MOD(ROW(),2)=0"], fill=fill("F8FAFC")))
    for k, w in enumerate([2, 24, 8, 6, 6, 20, 18, 8, 6, 5, 5, 13, 13, 8, 8, 11, 10, 10, 24, 10], 1):
        wj.column_dimensions[L(k)].width = w
    for k in range(21, 27):
        wj.column_dimensions[L(k)].hidden = True
    wj.column_dimensions["A"].hidden = True
    wj.freeze_panes, wj.auto_filter.ref = "C4", f"A3:{L(len(cols))}{last}"
    wj.sheet_properties.tabColor = "64748B"
    colx = {c[0]: L(k) for k, c in enumerate(cols, 1)}

    # ---------------- TOP por posición y temporada
    title(wt, "TOP POR POSICIÓN", "Los 15 mejores por NIVEL (CA) en cada posición. 25-26 con ≥ 900' de liga; 26-27 con ≥ 270' (temporada empezada).", 21)
    tc = ["#", "Jugador", "Edad", "Club", "Liga", "NIVEL", "POT.", "ELO", "FORMA", "G+A"]
    for side, (season, mins) in enumerate((("2025-26", 900), ("2026-27", 270))):
        c0 = 1 + side * 11
        r = 4
        wt.cell(r, c0, f"TEMPORADA {season}").font = f(13, True, NAVY)
        r += 2
        for g, (lab, colr) in GRP.items():
            sub = b[(b.season == season) & (b.pos_group == g) & (b.LIGA_Min.fillna(0) >= mins) & b.CA_FINAL.notna()]
            sub = sub.sort_values("CA_FINAL", ascending=False).head(15)
            cell = wt.cell(r, c0, lab.upper())
            cell.font, cell.fill = f(11, True, "FFFFFF"), fill(colr)
            for k in range(c0, c0 + len(tc)):
                wt.cell(r, k).fill = fill(colr)
            header(wt, r + 1, tc, color="334155", start=c0)
            for i, x in enumerate(sub.itertuples(), 1):
                rr = r + 1 + i
                put(wt, rr, [i, x.name, x.age, x.club, x.league, x.CA_FINAL, x.PA_ESTIMATE, x.ELO, x.FORM,
                             (x.TOT_G or 0) + (x.TOT_A or 0)], [None, None, "0", None, None, "0.0", "0.0", "0.0", "0.0", "0"],
                    left=(1, 3, 4), bold=(0, 1, 5), start=c0)
                if i in MEDAL:
                    for k in (c0, c0 + 1):
                        wt.cell(rr, k).fill = fill(MEDAL[i])
            if len(sub):
                bar(wt, f"{L(c0 + 5)}{r + 2}:{L(c0 + 5)}{r + 1 + len(sub)}")
            r += len(sub) + 4
    for side in (0, 1):
        for k, w in enumerate([5, 24, 6, 18, 16, 12, 8, 8, 8, 7], 1 + side * 11):
            wt.column_dimensions[L(k)].width = w
        wt.column_dimensions[L(11)].width = 4
    wt.freeze_panes = "A4"
    wt.sheet_properties.tabColor = NAVY

    # ---------------- PROMESAS
    pc = ["#", "Jugador", "Temp.", "Edad", "POS", "Club", "Liga", "Min", "NIVEL", "POTENCIAL", "Rango PA", "INTERÉS SCOUT", "Rol"]
    title(wp, "PROMESAS (21 años o menos)", "Ordenadas por INTERÉS SCOUT (potencial, nivel, rendimiento para su edad y fiabilidad). Mínimo 450' de liga. Son señales para investigar, no certezas.", len(pc))
    header(wp, 3, pc)
    pr = b[(b.age <= 21) & (b.LIGA_Min.fillna(0) >= 450) & b.SCOUT_SCORE.notna()].sort_values("SCOUT_SCORE", ascending=False).head(150)
    for i, x in enumerate(pr.itertuples(), 1):
        rng = f"{x.PA_RANGE_LOW:.0f}–{x.PA_RANGE_HIGH:.0f}" if pd.notna(x.PA_RANGE_LOW) else None
        put(wp, 3 + i, [i, x.name, x.season, x.age, x.pos, x.club, x.league, x.LIGA_Min, x.CA_FINAL, x.PA_ESTIMATE, rng, x.SCOUT_SCORE, x.Rol],
            [None, None, None, "0", None, None, None, "#,##0", "0.0", "0.0", None, "0.0", None], left=(1, 5, 6, 12), bold=(1, 9, 11))
        if i in MEDAL:
            for k in (1, 2):
                wp.cell(3 + i, k).fill = fill(MEDAL[i])
    lp = 3 + len(pr)
    bar(wp, f"J4:J{lp}", "7C3AED")
    bar(wp, f"I4:I{lp}", "2563EB")
    scale(wp, f"L4:L{lp}")
    for k, w in enumerate([5, 24, 8, 6, 6, 20, 18, 8, 12, 12, 10, 12, 24], 1):
        wp.column_dimensions[L(k)].width = w
    wp.freeze_panes, wp.auto_filter.ref = "C4", f"A3:{L(len(pc))}{lp}"
    wp.sheet_properties.tabColor = "7C3AED"

    # ---------------- LIGAS
    lc = ["Liga", "Temp.", "Jugadores", "NIVEL medio (top 25)", "NIVEL mediano", "Nivel rivales", "Fuerza liga (modelo)", "Mejor jugador de campo", "Máximo goleador (liga)", "Goles liga"]
    title(wg, "LIGAS", "Ligas con ≥ 150 jugadores valorados. NIVEL = CA. Sin clubes con la liga mal etiquetada (p. ej. Hull City como Premier). Goles: solo liga (con la regla de continentes, un fichaje del verano arrastra los de su liga anterior).", len(lc))
    header(wg, 3, lc)
    rows = []
    ok = b.CA_FINAL.notna() & (b.league_label_warning.isna() if "league_label_warning" in b else True)
    for (s, lg), g in b[ok].groupby(["season", "league"]):
        if len(g) < 150:
            continue
        campo = g[g.pos_group != "GK"]
        best = campo.loc[campo.CA_FINAL.idxmax()]
        # fuera quien suma partidos de otra liga (regla de continentes: más partidos de liga de los que se han jugado aquí)
        tope = 1.25 * g.LIGA_PJ.quantile(0.9) + 1
        limpio = g[g.LIGA_PJ.fillna(0) <= tope]
        sc = limpio.loc[limpio.LIGA_G.fillna(-1).idxmax()]
        rows.append([lg, s, len(g), g.CA_FINAL.nlargest(25).mean(), g.CA_FINAL.median(), g.opponent_strength.median(),
                     g.competition_strength.iloc[0], f"{best['name']} ({best.CA_FINAL:.1f})", f"{sc['name']} ({sc.club})", sc.LIGA_G])
    rows.sort(key=lambda x: (x[1], -x[3]))
    for i, v in enumerate(rows, 4):
        put(wg, i, v, [None, None, "#,##0", "0.0", "0.0", "0", "0", None, None, "0"], left=(0, 7, 8), bold=(0, 3))
    lg_last = 3 + len(rows)
    bar(wg, f"D4:D{lg_last}")
    scale(wg, f"F4:F{lg_last}")
    for k, w in enumerate([22, 8, 10, 14, 12, 11, 12, 30, 30, 7], 1):
        wg.column_dimensions[L(k)].width = w
    wg.freeze_panes = "B4"
    wg.sheet_properties.tabColor = "047857"

    # ---------------- FICHA (busca en JUGADORES)
    title(wf, "FICHA DEL JUGADOR", "Elige un jugador en la celda amarilla (lista desplegable o escribe 'Nombre | Club | Temporada').", 8)
    ref = j[(j.season == "2025-26") & (j.LIGA_Min.fillna(0) >= 1500) & (j.pos_group != "GK")].dropna(subset=["CA_FINAL"])
    top = ref.sort_values("CA_FINAL", ascending=False).iloc[0].KEY if len(ref) else j.iloc[0].KEY
    wf["B4"] = top
    wf["B4"].font, wf["B4"].fill = f(13, True, "1D4ED8"), fill("FEF3C7")
    wf.merge_cells("B4:G4")
    wf["A4"] = "Jugador"
    wf["A4"].font = f(10, True)
    dv = DataValidation(type="list", formula1=f"=JUGADORES!$A$4:$A${last}", allow_blank=False)
    wf.add_data_validation(dv)
    dv.add("B4")
    wf["H4"] = f'=IFERROR(MATCH(B4,JUGADORES!$A$4:$A${last},0),"")'
    wf["H4"].font = f(8, color="FFFFFF")

    def lk(h):
        x = f'INDEX(JUGADORES!${colx[h]}$4:${colx[h]}${last},$H$4)'
        return f'IFERROR(IF({x}="","—",{x}),"—")'
    datos = [("Club", "Club"), ("Liga", "Liga"), ("Temporada", "Temp."), ("Edad", "Edad"), ("Posición", "POS"), ("Rol", "Rol"),
             ("Minutos", "Min"), ("Partidos", "PJ"), ("Goles", "G"), ("Asistencias", "A")]
    notas = [("NIVEL (CA)", "NIVEL (CA)", "Nivel actual estimado (0-100)."), ("POTENCIAL (PA)", "POTENCIAL (PA)", "Hasta dónde puede llegar (estimación)."),
             ("ELO", "ELO", "Rendimiento partido a partido contra la fuerza del rival."), ("FORMA", "FORMA", "Últimos 10 partidos."),
             ("REGULARIDAD", "REGULARIDAD", "% de partidos buenos (50 = normal en su posición)."), ("NIVEL RIVALES", "NIVEL RIVALES", "Fuerza media de sus rivales."),
             ("INTERÉS SCOUT", "INTERÉS SCOUT", "Interés para ojear: potencial + nivel + edad."), ("Fiabilidad", "Fiabilidad", "Cuánto fiarse (minutos y datos disponibles).")]
    wf["A6"], wf["D6"] = "DATOS", "VALORACIÓN"
    for c in ("A6", "D6"):
        wf[c].font, wf[c].fill = f(10, True, "FFFFFF"), fill(NAVY)
    for c in ("B6", "E6", "F6", "G6"):
        wf[c].fill = fill(NAVY)
    for i, (lab, h) in enumerate(datos, 7):
        wf.cell(i, 1, lab).font = f(10, color=MUTED)
        cc = wf.cell(i, 2, "=" + lk(h))
        cc.font, cc.alignment = f(11, True), LFT
        if h == "Min":
            cc.number_format = "#,##0"
    for i, (lab, h, expl) in enumerate(notas, 7):
        wf.cell(i, 4, lab).font = f(10, True)
        cc = wf.cell(i, 5, "=" + lk(h))
        cc.font, cc.alignment, cc.number_format = f(12, True), C, "0\"%\"" if h == "Fiabilidad" else "0.0"
        wf.cell(i, 6, expl).font = f(9, color=MUTED, italic=True)
        wf.row_dimensions[i].height = 22
    wf.conditional_formatting.add("E7:E12", DataBarRule(start_type="num", start_value=30, end_type="num", end_value=100, color="2563EB", showValue=True))
    wf.conditional_formatting.add("E13:E14", DataBarRule(start_type="num", start_value=0, end_type="num", end_value=100, color="7C3AED", showValue=True))
    for k, w in enumerate([14, 30, 3, 18, 14, 52, 3, 4], 1):
        wf.column_dimensions[L(k)].width = w
    wf.sheet_properties.tabColor = "1D4ED8"

    # radar de la FICHA: datos en J7:L12 (etiqueta según portero/campo, valor del jugador, media = 50)
    radar_col = {k: colx[f"RADAR {k}"] for k in range(1, 7)}

    def radar_block(ws, top, col0, idx_cells, pos_cells):
        """Escribe 6 filas (etiqueta, valor de cada jugador, media 50) a partir de (top, col0); devuelve las referencias."""
        for k in range(6):
            r = top + k
            fl, gk = RADAR["campo"][k][0], RADAR["GK"][k][0]
            ws.cell(r, col0, f'=IF({pos_cells[0]}="POR","{gk}","{fl}")')
            for n, ic in enumerate(idx_cells, 1):
                ws.cell(r, col0 + n, f'=IFERROR(N(INDEX(JUGADORES!${radar_col[k + 1]}$4:${radar_col[k + 1]}${last},{ic})),0)')
            ws.cell(r, col0 + len(idx_cells) + 1, 50)
            for n in range(len(idx_cells) + 2):
                ws.cell(r, col0 + n).font = f(8, color="FFFFFF")

    def radar_chart(ws, top, col0, names, colors, anchor, w=15.5, h=10.5):
        ch = RadarChart()
        ch.type, ch.style, ch.width, ch.height = "marker", 2, w, h
        ch.y_axis.scaling.min, ch.y_axis.scaling.max, ch.y_axis.majorUnit = 0, 100, 25
        ch.y_axis.delete = False
        ch.y_axis.majorGridlines = None
        for n, (nm, colr) in enumerate(zip(names, colors), 1):
            ref = Reference(ws, min_col=col0 + n, min_row=top, max_row=top + 5)
            ch.add_data(ref, titles_from_data=False)
            se = ch.series[-1]
            from openpyxl.chart.series import SeriesLabel
            from openpyxl.chart.data_source import StrRef
            se.tx = SeriesLabel(strRef=StrRef(nm)) if nm.startswith("'") else SeriesLabel(v=nm)
            se.graphicalProperties.line.solidFill = colr
            se.graphicalProperties.line.width = 28575 if colr != "94A3B8" else 12700
            if colr == "94A3B8":
                se.graphicalProperties.line.dashStyle = "dash"
                se.marker.symbol = "none"
            else:
                se.marker.symbol, se.marker.size = "circle", 6
                se.marker.graphicalProperties.solidFill = colr
                se.marker.graphicalProperties.line.solidFill = colr
        ch.set_categories(Reference(ws, min_col=col0, min_row=top, max_row=top + 5))
        ch.legend.position = "b"
        ws.add_chart(ch, anchor)

    wf["A17"] = "ESTILO DE JUEGO"
    wf["A17"].font, wf["A17"].fill = f(10, True, "FFFFFF"), fill(NAVY)
    for c in ("B17", "C17", "D17", "E17", "F17"):
        wf[c].fill = fill(NAVY)
    wf["A18"] = "Percentil (0-100) frente a jugadores de su posición en todas las ligas, ajustado por nivel de liga. Línea gris = 50 (normal). Sin datos avanzados = 0."
    wf["A18"].font = f(9, color=MUTED, italic=True)
    radar_block(wf, 7, 10, ["$H$4"], ["$B$11"])
    radar_chart(wf, 7, 10, ["'FICHA'!$B$4", "Media (50)"], ["2563EB", "94A3B8"], "A19")

    # ---------------- COMPARAR (dos jugadores lado a lado)
    GA, GB = "16A34A", "2563EB"
    title(wc, "COMPARAR JUGADORES", "Elige dos jugadores en las celdas de color (lista o 'Nombre | Club | Temporada'). En negrita y con color, quien gana cada fila.", 5)
    ref_st = j[(j.season == "2025-26") & (j.LIGA_Min.fillna(0) >= 1500) & (j.pos_group == "ST")].dropna(subset=["CA_FINAL"]).sort_values("CA_FINAL", ascending=False)
    ka, kb = (ref_st.KEY.iloc[0], ref_st.KEY.iloc[1]) if len(ref_st) > 1 else (j.KEY.iloc[0], j.KEY.iloc[1])
    wc["B4"], wc["D4"], wc["C4"] = ka, kb, "vs"
    for c, colr, tint in (("B4", GA, "DCFCE7"), ("D4", GB, "DBEAFE")):
        wc[c].font, wc[c].fill, wc[c].alignment = f(10, True, colr), fill(tint), C
        wc[c].border = Border(bottom=Side(style="medium", color=colr))
    wc["C4"].font, wc["C4"].alignment = f(12, True, MUTED), C
    dv2 = DataValidation(type="list", formula1=f"=JUGADORES!$A$4:$A${last}", allow_blank=False)
    wc.add_data_validation(dv2)
    dv2.add("B4")
    dv2.add("D4")
    wc["F4"] = f'=IFERROR(MATCH(B4,JUGADORES!$A$4:$A${last},0),"")'
    wc["G4"] = f'=IFERROR(MATCH(D4,JUGADORES!$A$4:$A${last},0),"")'
    for c in ("F4", "G4"):
        wc[c].font = f(8, color="FFFFFF")
    wc.row_dimensions[4].height = 28

    def lkc(h, ic):
        x = f'INDEX(JUGADORES!${colx[h]}$4:${colx[h]}${last},{ic})'
        return f'=IFERROR(IF({x}="","—",{x}),"—")'
    cmp_rows = [("Jugador", None), ("Club", None), ("Liga", None), ("Temp.", None), ("Edad", "0"), ("POS", None), ("Rol", None),
                ("Min", "#,##0"), ("PJ", "0"), ("G", "0"), ("A", "0"), ("NIVEL (CA)", "0.0"), ("POTENCIAL (PA)", "0.0"), ("ELO", "0.0"),
                ("FORMA", "0.0"), ("REGULARIDAD", "0"), ("NIVEL RIVALES", "0"), ("INTERÉS SCOUT", "0.0"), ("Fiabilidad", "0\"%\"")]
    r0 = 6
    for n, (h, fm) in enumerate(cmp_rows):
        r = r0 + n
        lab = wc.cell(r, 3, "" if h == "Jugador" else h.title() if h in ("Club", "Liga", "Rol") else h)
        lab.font, lab.alignment = f(9, True, MUTED), C
        for c, ic, colr in ((2, "$F$4", GA), (4, "$G$4", GB)):
            cc = wc.cell(r, c, lkc(h, ic))
            cc.alignment, cc.border = C, Border(bottom=THIN)
            cc.font = f(14, True, colr) if h == "Jugador" else f(11)
            if fm:
                cc.number_format = fm
        lab.border = Border(bottom=THIN)
        wc.row_dimensions[r].height = 30 if h == "Jugador" else 21
    n0, n1 = r0 + 7, r0 + len(cmp_rows) - 1  # filas numéricas (Min … Fiabilidad)
    wc.conditional_formatting.add(f"B{n0}:B{n1}", FormulaRule(formula=[f"AND(ISNUMBER(B{n0}),ISNUMBER(D{n0}),B{n0}>D{n0})"], fill=fill("DCFCE7"), font=Font(bold=True, color="166534")))
    wc.conditional_formatting.add(f"D{n0}:D{n1}", FormulaRule(formula=[f"AND(ISNUMBER(B{n0}),ISNUMBER(D{n0}),D{n0}>B{n0})"], fill=fill("DBEAFE"), font=Font(bold=True, color="1E40AF")))
    for k, w in enumerate([3, 42, 18, 42, 3], 1):
        wc.column_dimensions[L(k)].width = w
    wc.column_dimensions["F"].width = wc.column_dimensions["G"].width = 3
    rr = n1 + 2
    wc.cell(rr, 2, "ESTILO DE JUEGO").font = f(10, True, "FFFFFF")
    for c in (2, 3, 4):
        wc.cell(rr, c).fill = fill(NAVY)
    radar_block(wc, 7, 10, ["$F$4", "$G$4"], [f"$B${r0 + 5}"])
    radar_chart(wc, 7, 10, ["'COMPARAR'!$B$6", "'COMPARAR'!$D$6", "Media (50)"], [GA, GB, "94A3B8"], f"B{rr + 1}", w=19, h=11)
    wc.cell(rr + 23, 2, "Si uno es portero y el otro de campo, los ejes son los del primero (verde).").font = f(9, color=MUTED, italic=True)
    wc.sheet_properties.tabColor = GA
    for ws, area in ((wf, "A1:G42"), (wc, f"A1:E{rr + 24}")):  # imprimir en una página
        ws.print_area = area
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 1

    # ---------------- LEEME
    wl.column_dimensions["A"].width = 120
    lines = [("CÓMO LEER ESTE RESUMEN", True),
             ("Es la versión corta de la valoración: solo las notas finales, sin cálculos intermedios. Todo sale del Excel extenso (Valoracion_FC_v1.2.xlsx).", False),
             ("", False),
             ("HOJAS", True),
             ("FICHA — elige un jugador y ves sus datos, sus notas con barras y su radar de estilo de juego.", False),
             ("COMPARAR — dos jugadores lado a lado: gana cada fila quien sale en negrita y color, más el radar de los dos.", False),
             ("TOP — los 15 mejores por posición en 25-26 (temporada completa) y 26-27 (en curso).", False),
             ("PROMESAS — los 150 jugadores de 21 años o menos con más interés para ojear.", False),
             ("LIGAS — nivel de cada liga, su mejor jugador y su máximo goleador.", False),
             ("JUGADORES — la tabla completa en 18 columnas; usa los filtros de la cabecera.", False),
             ("", False),
             ("LAS NOTAS (0-100)", True),
             ("NIVEL (CA): lo bueno que es ahora, teniendo en cuenta la liga. 85+ élite mundial · 75-85 muy bueno en liga top · 65-75 titular en liga media.", False),
             ("POTENCIAL (PA): hasta dónde puede llegar según edad y rendimiento. Es una estimación, con más margen cuanto más joven.", False),
             ("ELO: cómo rinde partido a partido frente a la fuerza de cada rival. FORMA: sus últimos 10 partidos. REGULARIDAD: % de partidos buenos.", False),
             ("NIVEL RIVALES: fuerza media de los equipos contra los que jugó. INTERÉS SCOUT: mezcla de potencial, nivel, edad y fiabilidad.", False),
             ("Fiabilidad: cuánto fiarse de la nota (minutos jugados y datos disponibles). Con poca fiabilidad, la nota se acerca a la media de su liga.", False),
             ("", False),
             ("COLORES", True),
             ("Barras azules = nivel · barras moradas = potencial · verde = mejor, amarillo = normal, rojo = peor · oro/plata/bronce = top 3.", False)]
    wl["A1"] = "RESUMEN DE VALORACIÓN FC"
    wl["A1"].font, wl["A1"].fill, wl["A1"].alignment = f(16, True, "FFFFFF"), fill(NAVY), LFT
    wl.row_dimensions[1].height = 34
    for i, (t, h) in enumerate(lines, 3):
        c = wl.cell(i, 1, t)
        c.font = f(11 if h else 10, h, NAVY if h else INK)
        c.fill = fill("DBEAFE") if h else PatternFill(fill_type=None)
        c.alignment = Alignment(wrap_text=True, vertical="center", indent=1)
        wl.row_dimensions[i].height = 20
    wl.sheet_view.showGridLines = False
    wl.sheet_properties.tabColor = NAVY
    wb.active = 1
    wb.calculation.fullCalcOnLoad = True  # Excel calcula la FICHA y COMPARAR al abrir
    wb.save(out_path)
    return out_path
