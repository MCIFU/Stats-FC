"""Portada del panel: partidos (resultados de los últimos 7 días y próximos 7) y noticias.

- Partidos: FotMob /api/data/matches?date=AAAAMMDD. Solo las competiciones de COMPS, en ese orden de importancia.
- Noticias: RSS de AS, Marca, Mundo Deportivo y BBC Sport.

Uso (desde FC/):  python auxiliares/portada/descargar_portada.py
Escribe directamente FC/Panel_FC/portada.js (se puede lanzar a diario sin recalcular nada más).
"""
import datetime as dt
import email.utils
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
FC = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "avanzadas"))
import descargar_fotmob_understat as FM  # noqa: E402

# id principal de FotMob → nombre en el panel, en orden de importancia (de mayor a menor)
COMPS = [(42, "Champions League"), (47, "Premier League"), (87, "LaLiga"), (55, "Serie A"), (54, "Bundesliga"), (53, "Ligue 1"),
         (77, "Mundial"), (50, "Eurocopa"), (44, "Copa América"), (78, "Mundial de Clubes"), (73, "Europa League"),
         (10216, "Conference League"), (9806, "Nations League A"), (10197, "Clasificación Mundial (UEFA)"), (45, "Copa Libertadores"),
         (138, "Copa del Rey"), (139, "Supercopa de España"), (132, "FA Cup"), (133, "Carabao Cup"), (209, "DFB Pokal"), (141, "Coppa Italia"),
         (134, "Coupe de France"), (61, "Liga Portugal"), (57, "Eredivisie"), (71, "Süper Lig"), (40, "Liga Belga"), (268, "Brasileirão"),
         (112, "Liga Argentina"), (130, "MLS"), (230, "Liga MX"), (536, "Saudi Pro League"), (64, "Scottish Premiership"), (48, "Championship"),
         (140, "LaLiga2"), (86, "Serie B"), (146, "2. Bundesliga"), (135, "Super League Grecia"), (46, "Superliga Dinamarca"),
         (69, "Super League Suiza"), (38, "Bundesliga Austria"), (196, "Ekstraklasa"), (223, "J1 League"), (9080, "K League 1"),
         (299, "Copa Sudamericana"), (9807, "Nations League B"), (114, "Amistosos de selecciones")]
FEEDS = [("AS", "https://as.com/rss/futbol/portada.xml"), ("Marca", "https://e00-marca.uecdn.es/rss/futbol/primera-division.xml"),
         ("Mundo Deportivo", "https://www.mundodeportivo.com/rss/futbol.xml"), ("BBC Sport", "https://feeds.bbci.co.uk/sport/football/rss.xml")]


def partidos(dias_atras=7, dias_adelante=7):
    order = {k: i for i, (k, _) in enumerate(COMPS)}
    out = []
    hoy = dt.date.today()
    for k in range(-dias_atras, dias_adelante + 1):
        d = hoy + dt.timedelta(days=k)
        try:
            m = FM.get(f"https://www.fotmob.com/api/data/matches?date={d:%Y%m%d}") or {}
        except Exception as e:  # noqa: BLE001
            print("  sin partidos", d, e)
            continue
        for lg in m.get("leagues") or []:
            pid = lg.get("primaryId")
            if pid not in order:
                continue
            stage = lg.get("name") if lg.get("isGroup") or lg.get("name") != lg.get("parentLeagueName") else None
            for x in lg.get("matches") or []:
                st, h, a = x.get("status") or {}, x.get("home") or {}, x.get("away") or {}
                out.append([pid, st.get("utcTime"), h.get("name"), a.get("name"), h.get("id"), a.get("id"),
                            h.get("score") if st.get("started") else None, a.get("score") if st.get("started") else None,
                            1 if st.get("finished") else 0, 1 if st.get("cancelled") else 0, stage if lg.get("isGroup") else None])
    out.sort(key=lambda r: (order[r[0]], r[1] or ""))
    return out


def noticias(n=12):
    out = []
    for src, url in FEEDS:
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (StatsFC; uso personal)"}, timeout=30)
            items = ET.fromstring(r.content).findall(".//item")[:n]
        except Exception as e:  # noqa: BLE001
            print("  sin noticias de", src, e)
            continue
        for it in items:
            try:
                ts = email.utils.parsedate_to_datetime(it.findtext("pubDate")).astimezone(dt.timezone.utc).isoformat()
            except Exception:  # noqa: BLE001
                ts = None
            out.append([(it.findtext("title") or "").strip(), (it.findtext("link") or "").strip(), src, ts])
    out.sort(key=lambda r: r[3] or "", reverse=True)
    return out


def main():
    data = {"generated": dt.datetime.now(dt.timezone.utc).isoformat(), "comps": COMPS, "matches": partidos(), "news": noticias()}
    p = FC / "Panel_FC" / "portada.js"
    p.write_text("window.FC_HOME=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"portada: {len(data['matches'])} partidos · {len(data['news'])} noticias → {p}")


if __name__ == "__main__":
    main()
