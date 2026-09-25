import urllib.request, re, time, html as ihtml

clubs = [
 ("f98930d1","Bragantino","https://web.archive.org/web/20260115/https://fbref.com/en/squads/f98930d1/Red-Bull-Bragantino-Stats"),
 ("5f232eb1","SaoPaulo","https://web.archive.org/web/20260115/https://fbref.com/en/squads/5f232eb1/Sao-Paulo-Stats"),
 ("d081b697","Juventude","https://web.archive.org/web/20260115/https://fbref.com/en/squads/d081b697/2025/Juventude-Stats"),
 ("ece66b78","Sport","https://web.archive.org/web/20260115/https://fbref.com/en/squads/ece66b78/2025/Sport-Recife-Stats"),
]

def fetch(url):
    req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode('utf-8', errors='ignore')

def parse_standard(html):
    m=re.search(r'<table[^>]*id="stats_standard[^"]*"[^>]*>(.*?)</table>', html, re.S)
    if not m:
        return []
    tbl=m.group(1)
    rows=re.findall(r'<tr[^>]*>(.*?)</tr>', tbl, re.S)
    out=[]
    for r in rows:
        if 'data-stat="player"' not in r:
            continue
        mm=re.search(r'data-stat="player"[^>]*>(.*?)</th>', r, re.S)
        if not mm: continue
        name=re.sub(r'<[^>]+>', '', mm.group(1)).strip()
        name=ihtml.unescape(name)
        if not name or name.lower()=='player': continue
        if 'Squad Total' in name or 'Opponent Total' in name: continue
        tds=re.findall(r'data-stat="([^"]+)"[^>]*>(.*?)</(?:td|th)>', r, re.S)
        d={}
        for k,v in tds:
            d[k]=ihtml.unescape(re.sub(r'<[^>]+>', '', v).strip())
        try: mp=int(d.get('games','0') or '0')
        except: mp=0
        try: mins=int((d.get('minutes','0') or '0').replace(',',''))
        except: mins=0
        try: gls=int(d.get('goals','0') or '0')
        except: gls=0
        try: ast=int(d.get('assists','0') or '0')
        except: ast=0
        pos=d.get('position','')
        out.append((name,pos,mp,mins,gls,ast))
    return out

with open('std_2025_clean.txt','a',encoding='utf-8') as f:
    for cid,label,url in clubs:
        try:
            print(f'FETCH {label}', flush=True)
            html=fetch(url)
            rows=parse_standard(html)
            print(f'  {len(rows)} players', flush=True)
            for name,pos,mp,mins,gls,ast in rows:
                f.write(f'{name}|{pos}|{label}|{mp}|{mins}|{gls}|{ast}\n')
            time.sleep(5)
        except Exception as e:
            print(f'FAIL {label}: {e}', flush=True)
print('done', flush=True)
