import requests
from bs4 import BeautifulSoup
headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
url='https://www.transfermarkt.com/club-de-gimnasia-y-esgrima-la-plata/leistungsdaten/verein/1106/plus/1?reldata=ARCA%262025'
r=requests.get(url, headers=headers, timeout=30)
print('enc', r.encoding)
for parser in ['lxml','html.parser']:
    soup=BeautifulSoup(r.content, parser)
    table=soup.find('table', class_='items')
    rows=table.find('tbody').find_all('tr', recursive=False)
    tr=rows[0]
    tds=tr.find_all('td', recursive=False)
    player_td=tds[1]
    for a in player_td.find_all('a', href=True):
        if '/profil/spieler/' in a['href'] and a.get('title'):
            print(parser, repr(a.get('title')))
            break
# raw
import re
idx=r.content.find(b'Insfr')
print(r.content[idx-30:idx+60])
# try decode
print('decode utf8:', r.content[idx-30:idx+60].decode('utf-8', errors='replace'))
