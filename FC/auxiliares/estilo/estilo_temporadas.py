"""Da un formato limpio y homogéneo a Temporada 2025-26.xlsx y Temporada 2026-27.xlsx.

Uso (desde la carpeta FC):  python auxiliares/estilo/estilo_temporadas.py ["Temporada 2025-26.xlsx" ...]

- No cambia ningún dato: solo formato y el ORDEN de las filas de las hojas por puesto
  (TOT G+A, luego G y minutos; porteros por porterías a cero, luego menos goles encajados).
  Las fórmulas TOT/G+A/G/90/Min/PJ se reescriben apuntando a su nueva fila.
- Se conservan los colores de club, liga y competición continental de cada celda.
"""
import copy
import math
import re
import sys
from pathlib import Path

import openpyxl
from openpyxl.formatting.rule import CellIsRule, ColorScaleRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter as L

FC = Path(__file__).resolve().parents[2]
FONT = "Arial"
NAVY, INK, MUTED, LINE = "0F2340", "0F172A", "64748B", "E2E8F0"
SHEETS = ["DELANTEROS", "EXTREMOS", "MEDIAPUNTAS", "MEDIOCENTROS", "DEFENSAS", "PORTEROS"]
TAB = {"DELANTEROS": "DC2626", "EXTREMOS": "EA580C", "MEDIAPUNTAS": "CA8A04", "MEDIOCENTROS": "16A34A",
       "DEFENSAS": "2563EB", "PORTEROS": "7C3AED", "RANKING_TOTAL": NAVY, "RANKING_PORTEROS": NAVY}
# grupos de columnas de las hojas por puesto: (primera, última, color cabecera, tinte del cuerpo)
GROUPS = [(1, 6, NAVY, None), (7, 10, "1D4ED8", "EFF6FF"), (11, 14, "0E7490", "ECFEFF"), (15, 19, "6D28D9", "F5F3FF"),
          (20, 23, "B45309", "FFFBEB"), (24, 27, "9F1239", "FFF1F2"), (28, 31, "334155", "F1F5F9"),
          (32, 34, "047857", "ECFDF5"), (35, 36, NAVY, None)]
KEEP_FILL = {5, 6, 15, 36}  # Club, Liga, CONT., Contrato: colores propios (club/liga/competición/fin de contrato)
WIDTH = {1: 26, 2: 6, 3: 6, 4: 6, 5: 22, 6: 21, 15: 7, 35: 9, 36: 11}


def font(size=10, bold=False, color=INK, italic=False):
    return Font(name=FONT, size=size, bold=bold, color=color, italic=italic)


def fill(c):
    return PatternFill("solid", fgColor=c) if c else PatternFill(fill_type=None)


THIN = Side(style="thin", color=LINE)
SEP = Side(style="thin", color="94A3B8")
CENTER = Alignment(horizontal="center", vertical="center")
LEFT = Alignment(horizontal="left", vertical="center", indent=1)
WRAP_C = Alignment(horizontal="center", vertical="center", wrap_text=True)
WRAP_L = Alignment(horizontal="left", vertical="top", wrap_text=True, indent=1)


def band(ws, row, text, ncol, size, bg, fg="FFFFFF", height=26, italic=False, bold=True):
    for rng in list(ws.merged_cells.ranges):
        if rng.min_row == row:
            ws.unmerge_cells(str(rng))
    ws.cell(row, 1).value = text
    for c in range(1, ncol + 1):
        cell = ws.cell(row, c)
        cell.fill, cell.font = fill(bg), font(size, bold, fg, italic)
        cell.alignment = Alignment(horizontal="left", vertical="center", indent=1, wrap_text=True)
        cell.border = Border()
    if ncol > 1:
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncol)
    ws.row_dimensions[row].height = height


def reset_cf(ws):
    ws.conditional_formatting = type(ws.conditional_formatting)()


# ------------------------------------------------------------------ hojas por puesto
def estilo_puesto(ws, sheet):
    gk = sheet == "PORTEROS"
    ncol = 36
    title, sub = ws.cell(1, 1).value, ws.cell(2, 1).value
    sub = re.sub(r" · PJ/Min en gris.*?G verde / A azul", "", sub or "")  # colores del formato anterior
    rows, notes = [], []
    for r in range(4, ws.max_row + 1):
        v = [ws.cell(r, c).value for c in range(1, ncol + 1)]
        if all(x is None for x in v):
            continue
        keep = {c: (copy.copy(ws.cell(r, c).fill), copy.copy(ws.cell(r, c).font)) for c in KEEP_FILL}
        (rows if v[4] else notes).append((v, keep))

    def n(v, cols):
        return sum(v[c - 1] if isinstance(v[c - 1], (int, float)) else 0 for c in cols)
    for v, _ in rows:  # totales en Python solo para ordenar (en la hoja siguen siendo fórmulas)
        v.append(dict(pj=n(v, (7, 11, 16, 20)), mn=n(v, (8, 12, 17, 21)), g=n(v, (9, 13, 18, 22)), a=n(v, (10, 14, 19, 23))))
    if gk:
        rows.sort(key=lambda x: (-x[0][-1]["a"], x[0][-1]["g"] if x[0][-1]["pj"] else 999, -x[0][-1]["pj"]))
    else:
        rows.sort(key=lambda x: (-(x[0][-1]["g"] + x[0][-1]["a"]), -x[0][-1]["g"], -x[0][-1]["mn"]))

    for rng in list(ws.merged_cells.ranges):
        ws.unmerge_cells(str(rng))
    if ws.max_row > 3:
        ws.delete_rows(4, ws.max_row - 3)
    reset_cf(ws)
    band(ws, 1, title, ncol, 14, NAVY, height=30)
    band(ws, 2, sub, ncol, 9, "E2E8F0", fg="334155", height=42, italic=True, bold=False)
    # cabecera por grupos
    for a, b, hc, _ in GROUPS:
        for c in range(a, b + 1):
            cell = ws.cell(3, c)
            cell.fill, cell.font, cell.alignment = fill(hc), font(9, True, "FFFFFF"), WRAP_C
            cell.border = Border(left=SEP if c == a and a > 1 else None, bottom=Side(style="medium", color=NAVY))
    ws.row_dimensions[3].height = 32

    first = 4
    for i, (v, keep) in enumerate(rows):
        r = first + i
        for c in range(1, ncol + 1):
            cell = ws.cell(r, c)
            if 28 <= c <= 34:
                continue
            cell.value = v[c - 1]
        ws[f"AB{r}"] = f"=G{r}+K{r}+P{r}+T{r}"
        ws[f"AC{r}"] = f"=H{r}+L{r}+Q{r}+U{r}"
        ws[f"AD{r}"] = f"=I{r}+M{r}+R{r}+V{r}"
        ws[f"AE{r}"] = f"=J{r}+N{r}+S{r}+W{r}"
        ws[f"AF{r}"] = f"=IF(AB{r}=0,0,AE{r}/AB{r})" if gk else f"=AD{r}+AE{r}"
        ws[f"AG{r}"] = f"=IF(AC{r}=0,0,AD{r}/AC{r}*90)"
        ws[f"AH{r}"] = f"=IF(AB{r}=0,0,AC{r}/AB{r})"
        for a, b, _, tint in GROUPS:
            for c in range(a, b + 1):
                cell = ws.cell(r, c)
                cell.border = Border(bottom=THIN, left=SEP if c == a and a > 1 else None)
                if c in KEEP_FILL:
                    f0, ft = keep[c]
                    cell.fill = f0
                    cell.font = Font(name=FONT, size=9, bold=True, color=ft.color)
                    cell.alignment = CENTER
                    continue
                cell.fill = fill(tint)
                cell.font = font(10, bold=(c == 1 or 28 <= c <= 32))
                cell.alignment = LEFT if c == 1 else CENTER
        ws.row_dimensions[r].height = 17
    last = first + len(rows) - 1
    for j, (v, _) in enumerate(notes):  # notas al pie
        r = last + 2 + j
        ws.cell(r, 1).value = v[0]
        ws.cell(r, 1).font = font(9, italic=True, color=MUTED)
    # formatos de número
    for r in range(first, last + 1):
        for c in (8, 12, 17, 21, 25, 29):
            ws.cell(r, c).number_format = "#,##0"
        ws.cell(r, 32).number_format = "0%" if gk else "0"
        ws.cell(r, 33).number_format = "0.00"
        ws.cell(r, 34).number_format = "0"
        ws.cell(r, 35).number_format = "[<1]0.0##;#,##0.0"
    # ceros en gris claro; escalas en G+A (o %CS) y G/90 (o GC/90, al revés)
    if last >= first:
        ws.conditional_formatting.add(f"G{first}:N{last}", CellIsRule(operator="equal", formula=["0"], font=Font(color="CBD5E1")))
        ws.conditional_formatting.add(f"P{first}:AE{last}", CellIsRule(operator="equal", formula=["0"], font=Font(color="CBD5E1")))
        ws.conditional_formatting.add(f"AF{first}:AF{last}", ColorScaleRule(start_type="percentile", start_value=5, start_color="FFFFFF",
                                                                          end_type="percentile", end_value=99, end_color="34D399"))
        lo, hi = ("34D399", "FFFFFF") if gk else ("FFFFFF", "FBBF24")
        ws.conditional_formatting.add(f"AG{first}:AG{last}", ColorScaleRule(start_type="percentile", start_value=5, start_color=lo,
                                                                          end_type="percentile", end_value=95, end_color=hi))
    for c in range(1, ncol + 1):
        ws.column_dimensions[L(c)].width = WIDTH.get(c, 8 if c in (8, 12, 17, 21, 25, 29) else 6.5)
    ws.freeze_panes = "B4"
    ws.auto_filter.ref = f"A3:{L(ncol)}{max(last, 3)}"
    ws.sheet_view.showGridLines = False
    ws.sheet_view.zoomScale = 100
    ws.sheet_properties.tabColor = TAB[sheet]


# ------------------------------------------------------------------ rankings
MEDAL = {1: "FDE68A", 2: "E5E7EB", 3: "FED7AA"}


def estilo_ranking(ws, name):
    ncol = len([c for c in ws[3] if c.value])
    hdr = [c.value for c in ws[3][:ncol]]
    title, sub = ws.cell(1, 1).value, ws.cell(2, 1).value
    band(ws, 1, title, ncol, 14, NAVY, height=30)
    band(ws, 2, sub, ncol, 9, "E2E8F0", fg="334155", height=22, italic=True, bold=False)
    for c in range(1, ncol + 1):
        cell = ws.cell(3, c)
        cell.fill, cell.font, cell.alignment = fill(NAVY), font(9, True, "FFFFFF"), WRAP_C
        cell.border = Border(bottom=Side(style="medium", color=NAVY))
    ws.row_dimensions[3].height = 30
    idx = {h: i + 1 for i, h in enumerate(hdr)}
    keep = {idx.get(h) for h in ("Club", "Liga")} - {None}
    hot = {idx.get(h) for h in ("G+A", "CS")} - {None}
    last = 3
    for r in range(4, ws.max_row + 1):
        if ws.cell(r, 2).value is None:
            continue
        last = r
        pos = ws.cell(r, 1).value
        for c in range(1, ncol + 1):
            cell = ws.cell(r, c)
            cell.border = Border(bottom=THIN)
            if c in keep:
                ft = cell.font
                cell.font = Font(name=FONT, size=9, bold=True, color=ft.color)
                cell.alignment = CENTER
                continue
            cell.fill = fill(MEDAL.get(pos) if c <= 2 and isinstance(pos, int) and pos <= 3 else ("ECFDF5" if c in hot else None))
            cell.font = font(10, bold=c in (1, 2) or c in hot)
            cell.alignment = LEFT if c == 2 else CENTER
        ws.row_dimensions[r].height = 17
        for h, fmt in (("Min", "#,##0"), ("G/90", "0.00"), ("GC/90", "0.00"), ("Min/PJ", "0"), ("%CS", "0%"), ("Valor M€", "[<1]0.0##;#,##0.0"), ("TOT Min", "#,##0")):
            if h in idx:
                ws.cell(r, idx[h]).number_format = fmt
    reset_cf(ws)
    if "G+A" in idx and last > 3:
        col = L(idx["G+A"])
        ws.conditional_formatting.add(f"{col}4:{col}{last}", ColorScaleRule(start_type="percentile", start_value=50, start_color="FFFFFF",
                                                                           end_type="max", end_color="34D399"))
    width = {"#": 6, "Jugador": 26, "Pos": 6, "Club": 22, "Liga": 21, "Puesto origen": 14, "Valor M€": 9}
    for h, c in idx.items():
        ws.column_dimensions[L(c)].width = width.get(h, 8)
    ws.freeze_panes = "C4"
    ws.auto_filter.ref = f"A3:{L(ncol)}{last}"
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = TAB[name]


# ------------------------------------------------------------------ hojas de texto y tablas pequeñas
FORMATO = [
    "FORMATO VISUAL (25/09/2026):",
    "• Hojas por puesto ordenadas por TOT G+A (desempate: goles y minutos); PORTEROS por porterías a cero (desempate: menos goles encajados).",
    "• Cabecera por bloques: LIGA azul · COPA turquesa · CONT. violeta · FIFA ámbar · SEL granate · TOT gris pizarra · G+A, G/90 y Min/PJ verde. "
    "Cada bloque lleva su tinte suave en las filas; los ceros salen en gris claro.",
    "• Club, Liga, competición continental (CONT.) y Contrato conservan sus colores propios. G+A y G/90 con escala de color (verde = más).",
    "• Paneles fijos: nombre del jugador y cabecera siempre visibles. Rankings con el top 3 resaltado (oro, plata, bronce).",
]


def leeme_formato(ws):
    """Añade la sección de formato actual tras las primeras líneas y marca como antiguas las secciones de colores previas."""
    if any(str(ws.cell(r, 1).value or "").startswith("FORMATO VISUAL") for r in range(1, ws.max_row + 1)):
        return
    for r in range(1, ws.max_row + 1):
        t = str(ws.cell(r, 1).value or "")
        if t in ("COLORES:", "ORDEN Y COLORES:", "BLOQUES POR COLOR (cabecera):"):
            ws.cell(r, 1).value = t[:-1] + " — formato anterior, sustituido el 25/09/2026 (ver FORMATO VISUAL):"
    at = 4
    ws.insert_rows(at, len(FORMATO) + 1)
    for i, t in enumerate(FORMATO):
        ws.cell(at + i, 1).value = t
        ws.cell(at + i, 1).font = font(10, bold=(i == 0))


def estilo_texto(ws):
    """LEEME: una columna de texto. Títulos de sección (negrita) con banda clara; resto texto envuelto."""
    ws.column_dimensions["A"].width = 130
    band(ws, 1, ws.cell(1, 1).value, 1, 14, NAVY, height=30)
    for r in range(2, ws.max_row + 1):
        c = ws.cell(r, 1)
        if c.value is None:
            ws.row_dimensions[r].height = 8
            continue
        t = str(c.value)
        head = c.font.b or t.isupper() or t.endswith(":")
        c.font = font(10, bold=head, color=NAVY if head else INK)
        c.fill = fill("DBEAFE" if head else None)
        c.alignment = WRAP_L
        c.border = Border(bottom=THIN)
        lines = sum(max(1, math.ceil(len(p) / 125)) for p in t.split("\n"))
        ws.row_dimensions[r].height = max(18, 14 * lines + 4)
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = "64748B"


def estilo_tabla(ws, widths):
    """TITULOS / FUENTES / LEYENDA: fila 1 título, fila 2 (si la hay) cabecera, luego filas con rayado suave."""
    ncol = ws.max_column
    band(ws, 1, ws.cell(1, 1).value, ncol, 13, NAVY, height=28)
    hdr_row = 2 if ws.cell(2, 1).fill.fgColor.rgb in ("000F2340", "0F2340", "00334155", "334155") else None
    if hdr_row:
        for c in range(1, ncol + 1):
            cell = ws.cell(2, c)
            cell.fill, cell.font, cell.alignment = fill("334155"), font(9, True, "FFFFFF"), WRAP_C
        ws.row_dimensions[2].height = 22
    start = 3 if hdr_row else 2
    for i, r in enumerate(range(start, ws.max_row + 1)):
        longest = 0
        for c in range(1, ncol + 1):
            cell = ws.cell(r, c)
            cell.font = font(10, bold=(c == 1))
            cell.fill = fill("F8FAFC" if i % 2 else None)
            cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True, indent=1)
            cell.border = Border(bottom=THIN)
            if cell.value:
                w = widths[min(c, len(widths)) - 1]
                longest = max(longest, math.ceil(len(str(cell.value)) / (w * 0.95)))
        ws.row_dimensions[r].height = max(18, 15 * longest + 5)
    for c in range(1, ncol + 1):
        ws.column_dimensions[L(c)].width = widths[min(c, len(widths)) - 1]
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = f"A{start}"
    ws.sheet_properties.tabColor = "64748B"


def main(files):
    for f in files:
        p = Path(f) if Path(f).is_absolute() else FC / f
        wb = openpyxl.load_workbook(p)
        wb._named_styles["Normal"].font = Font(name=FONT, size=10)
        for sh in wb.sheetnames:
            ws = wb[sh]
            if sh in SHEETS:
                estilo_puesto(ws, sh)
            elif sh.startswith("RANKING"):
                estilo_ranking(ws, sh)
            elif sh.startswith("LEEME"):
                leeme_formato(ws)
                estilo_texto(ws)
            elif sh.startswith("TITULOS"):
                estilo_tabla(ws, [30, 26, 22, 18, 40])
            elif sh.startswith(("FUENTES", "LEYENDA")):
                estilo_tabla(ws, [30, 120])
        wb.active = 0
        wb.save(p)
        print("ok", p.name)


if __name__ == "__main__":
    main(sys.argv[1:] or ["Temporada 2025-26.xlsx", "Temporada 2026-27.xlsx"])
