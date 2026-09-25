import requests, re, sys, time
from bs4 import BeautifulSoup

clubs = {
    "Hoffenheim": 533,
    "Wolfsburgo": 82,
    "Werder Bremen": 86,
    "Uni\u00f3n Berl\u00edn": 89,
    "Augsburgo": 167,
    "Colonia": 3,
    "Hamburgo SV": 41,
    "St. Pauli": 35,
    "Heidenheim": 2036,
}

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml",
}

def fetch(club_name, vid):
    url = f"https://www.transfermarkt.com/x/leistungsdaten/verein/{vid}/plus/1?reldata=DFB%262025"
    # use real path with club slug to avoid block? use generic with headers
    # Transfermarkt needs proper club slug? The /x/ should redirect? Let's use direct with dummy slug, follow redirects
    # Better construct with known slug? Use verein id only via search? Try with club name slug:
    # Use https://www.transfermarkt.com/vfl-wolfsburg/leistungsdaten/verein/82/plus/1?reldata=DFB%262025 pattern - need slug per club
    slugs = {
        "Hoffenheim": "tsg-1899-hoffenheim",
        "Wolfsburgo": "vfl-wolfsburg",
        "Werder Bremen": "sv-werder-bremen",
        "Uni\u00f3n Berl\u00edn": "1-fc-union-berlin",
        "Augsburgo": "fc-augsburg",
        "Colonia": "1-fc-koln",
        "Hamburgo SV": "hamburger-sv",
        "St. Pauli": "fc-st-pauli",
        "Heidenheim": "1-fc-heidenheim-1846",
    }
    slug = slugs.get(club_name, "x")
    url = f"https://www.transfermarkt.com/{slug}/leistungsdaten/verein/{vid}/plus/1?reldata=DFB%262025"
    s = requests.Session()
    s.headers.update(headers)
    try:
        r = s.get(url, timeout=30)
        print(f"[{club_name}] GET {url} -> {r.status_code} len={len(r.text)}", file=sys.stderr)
        if r.status_code != 200:
            print(f"FAILED {club_name} {r.status_code}", file=sys.stderr)
            return None
        # check title
        soup = BeautifulSoup(r.text, "lxml")
        title = soup.title.string if soup.title else "no-title"
        print(f"[{club_name}] title: {title.strip()}", file=sys.stderr)
        return r.text
    except Exception as e:
        print(f"ERROR {club_name}: {e}", file=sys.stderr)
        return None

def parse(html, club_name):
    soup = BeautifulSoup(html, "lxml")
    # Find table with items
    table = soup.find("table", class_="items")
    if not table:
        print(f"[{club_name}] No table.items found", file=sys.stderr)
        # dump snippet
        return []
    rows = table.find("tbody").find_all("tr", recursive=False) if table.find("tbody") else table.find_all("tr")
    out = []
    for tr in rows:
        # player name: first td with class hauptlink? Actually detailed view: second column?
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 12:
            continue
        # tds[0] = number, tds[1] = player (with img + name links), tds[2]=age, tds[3]=nat, tds[4]=in squad, tds[5]=apps, tds[6]=goals, tds[7]=assists, ... last = minutes?
        # Let's extract
        try:
            player_td = tds[1]
            # There are two links: full name and short? Take first <a> with title?
            a_tags = player_td.find_all("a", title=True)
            pname = None
            for a in a_tags:
                t = a.get("title","").strip()
                if t:
                    pname = t
                    break
            if not pname:
                # fallback text
                pname = player_td.get_text(strip=True)[:50]
            # clean: Transfermarkt title is player name
            age = tds[2].get_text(strip=True)
            in_squad = tds[4].get_text(strip=True)
            apps = tds[5].get_text(strip=True)
            goals = tds[6].get_text(strip=True)
            assists = tds[7].get_text(strip=True)
            # minutes is last td? In detailed view, last column is minutes like "210'"
            mins = tds[-1].get_text(strip=True)
            # Normalize
            def num(x):
                x=x.replace("\u2013","-").replace("-","").strip()
                if x=="" or x=="-":
                    return "0"
                return x
            apps_n = num(apps)
            # apps may be "-" for 0
            if apps_n=="0" or apps_n=="":
                continue
            # need integer check
            # filter at least 1 appearance
            try:
                if int(apps_n)<1:
                    continue
            except:
                continue
            g = num(goals)
            a = num(assists)
            # minutes: like "210'" or "-" -> "?"
            mins_clean = mins.replace("'","").replace(".","").replace(",","").strip()
            # Transfermarkt uses e.g., "1.710'"? Actually "210'" . Some have "1.250'"? Remove dots.
            # Keep digits only
            m = re.search(r"(\d+)", mins_clean)
            if m:
                # reconstruct: original may have dot as thousand sep, e.g., "1.710" meaning 1710? But for 2 games max 360, so simple.
                # Remove dots then int
                mins_digits = mins.replace("'","").replace(".","").strip()
                # ensure numeric
                if not mins_digits.isdigit():
                    mins_digits="?"
                else:
                    mins_digits=str(int(mins_digits))
            else:
                mins_digits="?"
                if mins.strip()=="-" or mins.strip()=="":
                    mins_digits="?"
            out.append((pname, apps_n, mins_digits, g, a))
        except Exception as e:
            print(f"parse row error {club_name}: {e}", file=sys.stderr)
            continue
    return out

all_lines=[]
for cname, vid in clubs.items():
    html = fetch(cname, vid)
    if not html:
        print(f"{cname}: FETCH FAILED", file=sys.stderr)
        continue
    rows = parse(html, cname)
    print(f"[{cname}] parsed {len(rows)} players", file=sys.stderr)
    for pname, pj, mi, g, a in rows:
        all_lines.append(f"{cname}|{pname}|{pj}|{mi}|{g}|{a}")
    time.sleep(2)

print("\n".join(all_lines))
