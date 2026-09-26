"""Edad y posición desde la ficha de Transfermarkt (auxiliares/tmapi/cache/meta_players.json.gz).

Los Excel de temporada traen una edad escrita a mano en distintos momentos y una posición gruesa (laterales como DFC,
extremos como DC). El motor usa en su lugar:
- Edad: calculada con la fecha de nacimiento. 2026-27 → edad a la fecha de corte de los datos; 2025-26 → edad al 30/06/2026.
- Posición: la posición principal de TM traducida a los códigos del panel (CEN→DFC, PIV→MCD, DEL→DC, interiores→ED/EI…).
Los Excel no se modifican. Sin ficha TM se deja lo del Excel.
"""
import datetime as dt
import gzip
import json
from pathlib import Path

import pandas as pd

META = Path(__file__).resolve().parents[3] / "auxiliares" / "tmapi" / "cache" / "meta_players.json.gz"
POS = {"POR": "POR", "CEN": "DFC", "LD": "LD", "LI": "LI", "PIV": "MCD", "MC": "MC", "MCO": "MCO", "MP": "MCO",
       "ED": "ED", "EI": "EI", "ID": "ED", "II": "EI", "DEL": "DC"}
REF = {"2025-26": dt.date(2026, 6, 30)}


def load_meta():
    return json.loads(gzip.decompress(META.read_bytes())) if META.exists() else {}


def tm_ids(partidos, season):
    """player_id del motor → id TM, a partir de partidos_TM.csv (hoja|nombre|club del Excel)."""
    m = pd.read_csv(partidos, usecols=["season", "source_sheet", "name", "excel_club", "tm_id"], dtype={"tm_id": str})
    m = m[(m.season == season) & m.tm_id.notna()].drop_duplicates(["source_sheet", "name", "excel_club"])
    return dict(zip(m.source_sheet.astype(str) + "|" + m["name"].astype(str) + "|" + m.excel_club.astype(str), m.tm_id))


def age_on(dob, ref):
    try:
        b = dt.date.fromisoformat(str(dob)[:10])
    except ValueError:
        return None
    return ref.year - b.year - ((ref.month, ref.day) < (b.month, b.day))


def corrige(raw, w, partidos, season, meta=None, corte=None):
    """Devuelve raw con age/pos corregidos y un resumen de cambios."""
    meta = meta if meta is not None else load_meta()
    if not partidos or not meta:
        return raw, "sin ficha TM"
    ids = tm_ids(partidos, season)
    key = w._sheet.astype(str) + "|" + w.Jugador.astype(str) + "|" + w.Club.astype(str)
    pid_tm = {p: ids.get(k) for p, k in zip(w.player_id, key) if ids.get(k)}
    ref = REF.get(season) or corte or dt.date.today()
    age, pos = {}, {}
    for p, t in pid_tm.items():
        f = meta.get(str(t)) or {}
        a = age_on((f.get("lifeDates") or {}).get("dateOfBirth"), ref)
        if a is not None:
            age[p] = a
        sp = (((f.get("attributes") or {}).get("position") or {}).get("shortName"))
        if sp in POS:
            pos[p] = POS[sp]
    raw = raw.copy()
    new_age = raw.player_id.map(age)
    new_pos = raw.player_id.map(pos)
    # un portero en la hoja PORTEROS sigue siendo portero (y al revés): la hoja manda en ese caso
    gk_sheet = raw.source_sheet == "PORTEROS"
    new_pos = new_pos.where(~(gk_sheet ^ (new_pos == "POR")) | new_pos.isna(), None)
    ca = (new_age.notna() & (new_age != raw.age)).groupby(raw.player_id).any().sum()
    cp = (new_pos.notna() & (new_pos != raw.pos)).groupby(raw.player_id).any().sum()
    raw["age"] = new_age.fillna(raw.age)
    raw["pos"] = new_pos.fillna(raw.pos)
    raw["tm_id"] = raw.player_id.map(pid_tm)
    return raw, f"{season}: ficha TM en {len(pid_tm)} jugadores · edad corregida en {ca} · posición afinada en {cp}"
