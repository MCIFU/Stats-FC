"""Excel RESUMEN: lo esencial de la valoración en pocas columnas y hojas visuales (el Excel extenso sigue teniendo todo).

Hojas: LEEME · FICHA (elige jugador) · TOP (mejores por posición) · PROMESAS (≤21) · LIGAS · JUGADORES (tabla corta).
Solo valores (salvo la FICHA, que busca en JUGADORES): se abre rápido y pesa poco.
"""
import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.formatting.rule import ColorScaleRule, DataBarRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter as L
from openpyxl.worksheet.datavalidation import DataValidation

FONT, NAVY, INK, MUTED, LINE = "Arial", "0F2340", "0F172A", "64748B", "E2E8F0"
GRP = {"GK": ("Porteros", "7C3AED"), "CB": ("Centrales", "2563EB"), "FB": ("Laterales", "0891B2"),
       "MID": ("Mediocentros", "16A34A"), "AMW": ("Mediapuntas y extremos", "EA580C"), "ST": ("Delanteros", "DC2626")}
MEDAL = {1: "FDE68A", 2: "E5E7EB", 3: "FED7AA"}
THIN = Side(style="thin", color=LINE)


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


def build(base, cfg, out_path):
    b = preparar(base, cfg)
    wb = Workbook()
    wb._named_styles["Normal"].font = Font(name=FONT, size=10)
    wl = wb.active
    wl.title = "LEEME"
    wf, wt, wp, wg, wj = (wb.create_sheet(n) for n in ("FICHA", "TOP", "PROMESAS", "LIGAS", "JUGADORES"))

    # ---------------- JUGADORES (tabla corta, base de la ficha)
    cols = [("KEY", "KEY", None), ("Jugador", "name", None), ("Temp.", "season", None), ("Edad", "age", "0"), ("POS", "pos", None),
            ("Club", "club", None), ("Liga", "league", None), ("Min", "TOT_Min", "#,##0"), ("PJ", "TOT_PJ", "0"), ("G", "TOT_G", "0"),
            ("A", "TOT_A", "0"), ("NIVEL (CA)", "CA_FINAL", "0.0"), ("POTENCIAL (PA)", "PA_ESTIMATE", "0.0"), ("ELO", "ELO", "0.0"),
            ("FORMA", "FORM", "0.0"), ("REGULARIDAD", "CONSISTENCY", "0"), ("NIVEL RIVALES", "opponent_strength", "0"),
            ("INTERÉS SCOUT", "SCOUT_SCORE", "0.0"), ("Rol", "Rol", None), ("Fiabilidad", "CA_CONFIDENCE", "0\"%\"")]
    j = b.sort_values(["season", "CA_FINAL"], ascending=[False, False], na_position="last")
    title(wj, "JUGADORES — resumen de la valoración", "Una fila por jugador y temporada. Filtra por liga, posición, edad… Todos los detalles y cálculos: Valoracion_FC_v1.2.xlsx", len(cols))
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
    ref = j[(j.season == "2025-26") & (j.LIGA_Min.fillna(0) >= 1500)].dropna(subset=["CA_FINAL"])
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

    # ---------------- LEEME
    wl.column_dimensions["A"].width = 120
    lines = [("CÓMO LEER ESTE RESUMEN", True),
             ("Es la versión corta de la valoración: solo las notas finales, sin cálculos intermedios. Todo sale del Excel extenso (Valoracion_FC_v1.2.xlsx).", False),
             ("", False),
             ("HOJAS", True),
             ("FICHA — elige un jugador y ves sus datos y notas con barras.", False),
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
    wb.save(out_path)
    return out_path
