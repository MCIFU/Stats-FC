import requests, re, sys, time
from bs4 import BeautifulSoup

clubs = {
    "Gimnasia La Plata": (1106, "club-de-gimnasia-y-esgrima-la-plata"),
    "Newell's Old Boys": (1286, "club-atletico-newells-old-boys"),
    "Platense": (928, "club-atletico-platense"),
    "Defensa y Justicia": (2402, "defensa-y-justicia"),
    "Instituto": (1829, "instituto-ac-cordoba"),
    "Godoy Cruz": (12574, "club-deportivo-godoy-cruz-antonio-tomba"),
    "Independiente Rivadavia": (12179, "independiente-rivadavia"),
    "Unión Santa Fe": (7097, "club-atletico-union"),
    "Central Córdoba": (31284, "club-atletico-central-cordoba-sde-"),
    "Sarmiento": (12454, "club-atletico-sarmiento-junin-"),
    "Banfield": (830, "club-atletico-banfield"),
    "Barracas Central": (25184, "club-atletico-barracas-central"),
    "Riestra": (19775, "cd-riestra"),
    "Aldosivi": (12301, "ca-aldosivi"),
    "San Martín SJ": (10511, "club-atletico-san-martin-sj-"),
}

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml",
}

def fetch(club_name, vid, slug):
    url = f"https://www.transfermarkt.com/{slug}/leistungsdaten/verein/{vid}/plus/1?reldata=ARCA%262025"
    s = requests.Session()
    s.headers.update(headers)
    try:
        r = s.get(url, timeout=30)
        print(f"[{club_name}] GET {url} -> {r.status_code} len={len(r.text)}", file=sys.stderr)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "lxml")
        title = soup.title.string if soup.title else "no-title"
        print(f"[{club_name}] title: {title.strip()}", file=sys.stderr)
        return r.text
    except Exception as e:
        print(f"ERROR {club_name}: {e}", file=sys.stderr)
        return None

def parse(html, club_name):
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", class_="items")
    if not table:
        print(f"[{club_name}] No table.items found", file=sys.stderr)
        return []
    tbody = table.find("tbody")
    rows = tbody.find_all("tr", recursive=False) if tbody else []
    out = []
    for tr in rows:
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 10:
            continue
        try:
            player_td = tds[1]
            pname = None
            for a in player_td.find_all("a", href=True):
                href = a["href"]
                if "/profil/spieler/" in href:
                    if a.get("title"):
                        pname = a.get("title").strip()
                        break
            if not pname:
                continue
            apps = tds[5].get_text(strip=True)
            goals = tds[6].get_text(strip=True)
            assists = tds[7].get_text(strip=True)
            mins = tds[-1].get_text(strip=True)
            def num(x):
                x=x.replace("\u2013","").replace("-","").strip()
                if x=="":
                    return "0"
                return x
            apps_n = num(apps)
            if apps_n=="0" or apps_n=="":
                continue
            try:
                if int(apps_n)<1:
                    continue
            except:
                continue
            g = num(goals)
            a = num(assists)
            mins_digits = mins.replace("'","").replace(".","").strip()
            if mins_digits in ("", "-", "–"):
                mins_digits="?"
            else:
                m = re.search(r"^\d+$", mins_digits)
                if not m:
                    d = re.search(r"(\d+)", mins_digits)
                    mins_digits = d.group(1) if d else "?"
            out.append((pname, apps_n, mins_digits, g, a))
        except Exception as e:
            print(f"parse err {club_name}: {e}", file=sys.stderr)
            continue
    return out

all_lines=[]
for cname, (vid, slug) in clubs.items():
    html = fetch(cname, vid, slug)
    if not html:
        print(f"{cname}: FETCH FAILED", file=sys.stderr)
        continue
    rows = parse(html, cname)
    print(f"[{cname}] parsed {len(rows)} players", file=sys.stderr)
    for pname, pj, mi, g, a in rows:
        all_lines.append(f"{cname}|{pname}|{pj}|{mi}|{g}|{a}")
    time.sleep(2)

with open("copa_arg_2025.txt","w",encoding="utf-8") as f:
    f.write("\n".join(all_lines))
print(f"WROTE {len(all_lines)} lines", file=sys.stderr)
print("\n".join(all_lines))
