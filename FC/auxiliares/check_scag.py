import requests, re
from bs4 import BeautifulSoup
headers={'User-Agent':'Mozilla/5.0'}
for sid in [2024,2025]:
    url=f'https://www.transfermarkt.com/supercopa-argentina/gesamtspielplan/pokalwettbewerb/SCAG/saison_id/{sid}'
    r=requests.get(url, headers=headers, timeout=30)
    soup=BeautifulSoup(r.content,'html.parser')
    links=soup.find_all('a', href=re.compile(r'/spielbericht/index/spielbericht/'))
    print(f'=== SCAG {sid} {len(links)} ===')
    for a in links[:10]:
        print(a.get_text(strip=True), a.get('href'))
