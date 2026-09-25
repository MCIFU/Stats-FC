import requests, re, sys, time
from bs4 import BeautifulSoup

clubs = {
    "Hoffenheim": 533,
    "Wolfsburgo": 82,
    "Werder Bremen": 86,
    "Unión Berlín": 89,
    "Augsburgo": 167,
    "Colonia": 3,
    "Hamburgo SV": 41,
    "St. Pauli": 35,
    "Heidenheim": 2036,
}
slugs = {
    "Hoffenheim": "tsg-1899-hoffenheim",
    "Wolfsburgo": "vfl-wolfsburg",
    "Werder Bremen": "sv-werder-bremen",
    "Unión Berlín": "1-fc-union-berlin",
    "Augsburgo": "fc-augsburg",
    "Colonia": "1-fc-koln",
    "Hamburgo SV": "hamburger-sv",
    "St. Pauli": "fc-st-pauli",
    "Heidenheim": "1-fc-heidenheim-1846",
}

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml",
}

def fetch(club_name, vid):
    slug = slugs.get(club_name, "x")
    url = f"https://www.transfermarkt.com/{slug}/leistungsdaten/verein/{vid}/plus/1?reldata=DFB%262025"
    s = requests.Session()
    s.headers.update(headers)
    r = s.get(url, timeout=30)
    r.encoding = "utf-8"
    print(f"[{club_name}] {r.status_code} len={len(r.text)}", file=sys.stderr)
    return r.text if r.status_code==200 else None

def parse(html, club_name):
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", class_="items")
    if not table:
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
            # find a with href containing /profil/spieler/
            pname = None
            for a in player_td.find_all("a", href=True):
                href = a["href"]
                if "/profil/spieler/" in href:
                    # title attr is full name, else text
                    t = (a.get("title") or a.get_text(strip=True)).strip()
                    if t and len(t)>1:
                        # prefer longer full name (first one is full with img? second is short?)
                        # Actually first a (with img) has title=full name, second a text=short? Take title if available
                        if a.get("title"):
                            pname = a.get("title").strip()
                            break
            if not pname:
                continue
            in_squad = tds[4].get_text(strip=True)
            apps = tds[5].get_text(strip=True)
            goals = tds[6].get_text(strip=True)
            assists = tds[7].get_text(strip=True)
            mins = tds[-1].get_text(strip=True)
            def num(x):
                x=x.replace("\u2013","").replace("-","").strip()
                if x=="" :
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
                    # try extract digits
                    d = re.search(r"(\d+)", mins_digits)
                    mins_digits = d.group(1) if d else "?"
                    # handle thousand sep already removed
            out.append((pname, apps_n, mins_digits, g, a))
        except Exception as e:
            print(f"parse err {club_name}: {e}", file=sys.stderr)
            continue
    return out

all_lines=[]
for cname, vid in clubs.items():
    html = fetch(cname, vid)
    if not html:
        continue
    rows = parse(html, cname)
    print(f"[{cname}] parsed {len(rows)}", file=sys.stderr)
    for pname, pj, mi, g, a in rows:
        all_lines.append(f"{cname}|{pname}|{pj}|{mi}|{g}|{a}")
    time.sleep(1)

with open("dfb_output.txt","w",encoding="utf-8") as f:
    f.write("\n".join(all_lines))
print(f"WROTE {len(all_lines)} lines", file=sys.stderr)
