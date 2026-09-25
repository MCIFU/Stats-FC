import requests, re
headers={'User-Agent':'Mozilla/5.0'}
for sid in [2024, 2023, 2026]:
    url=f'https://www.transfermarkt.com/wettbewerbe/national/wettbewerbe/9/saison_id/{sid}/plus/1'
    r=requests.get(url, headers=headers, timeout=30)
    html=r.text
    links=sorted(set(re.findall(r'/[a-z0-9\-]+/startseite/(?:wettbewerb|pokalwettbewerb)/([A-Z0-9]+)', html)))
    print(sid, links)
    # find Trofeo/Supercopa mentions
    mentions=sorted(set(re.findall(r'(Trofeo[^<]{0,60}|Supercopa[^<]{0,60})', html)))[:20]
    print(' mentions:', mentions[:10])
