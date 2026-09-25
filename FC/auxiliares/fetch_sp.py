import urllib.request, re, time, html as ihtml
urls=[
 "https://web.archive.org/web/20260220/https://fbref.com/en/squads/5f232eb1/2025/Sao-Paulo-Stats",
 "https://web.archive.org/web/20260115/https://fbref.com/en/squads/5f232eb1/Sao-Paulo-Stats",
 "https://web.archive.org/web/20251230/https://fbref.com/en/squads/5f232eb1/2025/Sao-Paulo-Stats",
]
def fetch(url):
    req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode('utf-8', errors='ignore')
for url in urls:
    try:
        print('TRY', url, flush=True)
        html=fetch(url)
        print('len', len(html), flush=True)
        m=re.search(r'<table[^>]*id="stats_standard[^"]*"[^>]*>(.*?)</table>', html, re.S)
        print('table found' if m else 'no table', flush=True)
        if m:
            tbl=m.group(1)
            rows=re.findall(r'<tr[^>]*>.*?data-stat="player".*?</tr>', tbl, re.S)
            print('rows', len(rows), flush=True)
            if len(rows)>10:
                # save
                import re as _re
                def parse_standard(html):
                    mm=_re.search(r'<table[^>]*id="stats_standard[^"]*"[^>]*>(.*?)</table>', html, re.S)
                    tbl2=mm.group(1)
                    rr=_re.findall(r'<tr[^>]*>(.*?)</tr>', tbl2, re.S)
                    out=[]
                    for r in rr:
                        if 'data-stat="player"' not in r: continue
                        mmm=_re.search(r'data-stat="player"[^>]*>(.*?)</th>', r, re.S)
                        if not mmm: continue
                        name=_re.sub(r'<[^>]+>', '', mmm.group(1)).strip()
                        name=ihtml.unescape(name)
                        if not name or name.lower()=='player': continue
                        if 'Squad Total' in name or 'Opponent Total' in name: continue
                        tds=_re.findall(r'data-stat="([^"]+)"[^>]*>(.*?)</(?:td|th)>', r, re.S)
                        d={}
                        for k,v in tds:
                            d[k]=ihtml.unescape(_re.sub(r'<[^>]+>', '', v).strip())
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
                rows2=parse_standard(html)
                print(f'parsed {len(rows2)}', flush=True)
                with open('std_2025_clean.txt','a',encoding='utf-8') as f:
                    for name,pos,mp,mins,gls,ast in rows2:
                        f.write(f'{name}|pos={pos}|SaoPaulo|{mp}|{mins}|{gls}|{ast}\n'.replace('pos=',''))
                break
        time.sleep(3)
    except Exception as e:
        print('FAIL', e, flush=True)
