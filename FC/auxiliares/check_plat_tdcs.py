import requests, re
from bs4 import BeautifulSoup
headers={'User-Agent':'Mozilla/5.0'}
def fetch_tdcs(club, vid, slug, rel):
    url=f'https://www.transfermarkt.com/{slug}/leistungsdaten/verein/{vid}/plus/1?reldata={rel}'
    r=requests.get(url, headers=headers, timeout=30)
    soup=BeautifulSoup(r.content, 'html.parser')
    table=soup.find('table', class_='items')
    if not table:
        print(club, 'no table')
        return
    rows=table.find('tbody').find_all('tr', recursive=False)
    for tr in rows:
        tds=tr.find_all('td', recursive=False)
        if len(tds)<10:
            continue
        pname=None
        for a in tds[1].find_all('a', href=True):
            if '/profil/spieler/' in a['href'] and a.get('title'):
                pname=a.get('title')
                break
        apps=tds[5].get_text(strip=True).replace('\u2013','').replace('-','').strip()
        if apps=='' or apps=='0':
            continue
        print(f'{club}|{repr(pname)}|{apps}|{tds[6].get_text(strip=True)}|{tds[7].get_text(strip=True)}|{tds[-1].get_text(strip=True)}')

# Platense TDCS 2024 (match Dec 2025 is labelled 2024)
fetch_tdcs('Platense',928,'club-atletico-platense','TDCS%262024')
print('---SCAG Platense 2024---')
fetch_tdcs('Platense',928,'club-atletico-platense','SCAG%262024')
