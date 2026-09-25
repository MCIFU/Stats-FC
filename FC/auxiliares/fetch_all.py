import urllib.request, re, time, html as ihtml

clubs = [
 ("6f7e1f03","Internacional-Stats","https://web.archive.org/web/20260220/https://fbref.com/en/squads/6f7e1f03/2025/Internacional-Stats"),
 ("157b7fee","Bahia-c24","https://web.archive.org/web/20251230120117/https://fbref.com/en/squads/157b7fee/2025/c24/Bahia-Stats-Serie-A"),
 ("33f95fe0","Vitoria","https://web.archive.org/web/20251224065213/https://fbref.com/en/squads/33f95fe0/Vitoria-Stats"),
 ("712c528f","Santos","https://web.archive.org/web/20260224041024/https://fbref.com/en/squads/712c528f/2025/Santos-Stats"),
 ("289e8847","Mirassol","https://web.archive.org/web/20260815124715/https://fbref.com/en/squads/289e8847/2025/Mirassol-Stats"),
 ("bf4acd28","Corinthians","https://web.archive.org/web/20260306130538/https://fbref.com/en/squads/bf4acd28/2025/Corinthians-Stats"),
 ("2f335e17","Ceara","https://web.archive.org/web/20260214145026/https://fbref.com/en/squads/2f335e17/2025/Ceara-Stats"),
 ("a9d0ab0e","Fortaleza","https://web.archive.org/web/20260211020720/https://fbref.com/en/squads/a9d0ab0e/2025/Fortaleza-Stats"),
 ("abdce579","Palmeiras","https://web.archive.org/web/20260311114738/https://fbref.com/en/squads/abdce579/2025/Palmeiras-Stats"),
 ("03ff5eeb","Cruzeiro","https://web.archive.org/web/20260220084701/https://fbref.com/en/squads/03ff5eeb/2025/Cruzeiro-Stats"),
 ("422bb734","Atletico-Mineiro","https://web.archive.org/web/20260131002216/https://fbref.com/en/squads/422bb734/2025/Atletico-Mineiro-Stats"),
 ("83f55dbe","Vasco","https://web.archive.org/web/20260212150356/https://fbref.com/en/squads/83f55dbe/2025/Vasco-da-Gama-Stats"),
 ("d5ae3703","Gremio","https://web.archive.org/web/20260114155641/https://fbref.com/en/squads/d5ae3703/2025/Gremio-Stats"),
 ("639950ae","Flamengo","https://web.archive.org/web/20260311120456/https://fbref.com/en/squads/639950ae/2025/Flamengo-Stats"),
 ("d9fdd9d9","Botafogo","https://web.archive.org/web/20260129001811/https://fbref.com/en/squads/d9fdd9d9/2025/Botafogo-RJ-Stats"),
]

# add remaining 5 with generic timestamp guess
clubs += [
 ("84d9701c","Fluminense","https://web.archive.org/web/20260220/https://fbref.com/en/squads/84d9701c/2025/Fluminense-Stats"),
 ("f98930d1","Bragantino","https://web.archive.org/web/20260220/https://fbref.com/en/squads/f98930d1/2025/Red-Bull-Bragantino-Stats"),
 ("5f232eb1","SaoPaulo","https://web.archive.org/web/20260220/https://fbref.com/en/squads/5f232eb1/2025/Sao-Paulo-Stats"),
 ("d081b697","Juventude","https://web.archive.org/web/20260220/https://fbref.com/en/squads/d081b697/2025/Juventude-Stats"),
 ("ece66b78","Sport","https://web.archive.org/web/20260220/https://fbref.com/en/squads/ece66b78/2025/Sport-Recife-Stats"),
]

def fetch(url):
    req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode('utf-8', errors='ignore')

def parse_standard(html):
    idx=html.find('id="stats_standard_24"')
    if idx<0:
        idx=html.find('id="stats_standard"')
        if idx<0:
            return []
    seg=html[idx:idx+400000]
    rows=re.findall(r'<tr[^>]*>(.*?)</tr>', seg, re.S)
    out=[]
    for r in rows:
        if 'data-stat="player"' not in r or '<th' not in r:
            continue
        # player name
        m=re.search(r'data-stat="player"[^>]*>(.*?)</th>', r, re.S)
        if not m:
            continue
        cell=m.group(1)
        name=re.sub(r'<[^>]+>', '', cell).strip()
        name=ihtml.unescape(name)
        if not name or name.lower()=='player':
            continue
        # get all td data-stat
        tds=re.findall(r'data-stat="([^"]+)"[^>]*>(.*?)</(?:td|th)>', r, re.S)
        d={}
        for k,v in tds:
            txt=re.sub(r'<[^>]+>', '', v).strip()
            txt=ihtml.unescape(txt)
            d[k]=txt
        # MP=games, Starts=games_starts, Min=minutes, Gls=goals, Ast=assists
        try:
            mp=int(d.get('games','0') or '0')
        except: mp=0
        mins=d.get('minutes','0').replace(',','')
        try: mins=int(mins or '0')
        except: mins=0
        try: gls=int(d.get('goals','0') or '0')
        except: gls=0
        try: ast=int(d.get('assists','0') or '0')
        except: ast=0
        pos=d.get('position','')
        out.append((name,pos,mp,mins,gls,ast))
    return out

all_players={}
for cid,label,url in clubs:
    try:
        print(f'FETCH {label} ...')
        html=fetch(url)
        rows=parse_standard(html)
        print(f'  got {len(rows)} rows len={len(html)}')
        for name,pos,mp,mins,gls,ast in rows:
            key=name.lower()
            if key not in all_players:
                all_players[key]=[]
            all_players[key].append((label,name,pos,mp,mins,gls,ast))
        time.sleep(2)
    except Exception as e:
        print(f'FAIL {label}: {e}')

print(f'TOTAL unique names: {len(all_players)}')
# save all to file
with open('all_2025_seriea.txt','w',encoding='utf-8') as f:
    for k,v in sorted(all_players.items()):
        for label,name,pos,mp,mins,gls,ast in v:
            f.write(f'{name}|{pos}|{label}|{mp}|{mins}|{gls}|{ast}\n')
print('saved')
