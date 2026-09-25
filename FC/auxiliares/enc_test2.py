import requests
headers={'User-Agent':'Mozilla/5.0'}
url='https://www.transfermarkt.com/club-de-gimnasia-y-esgrima-la-plata/leistungsdaten/verein/1106/plus/1?reldata=ARCA%262025'
r=requests.get(url, headers=headers, timeout=30)
idx=r.content.find(b'Insfr')
snippet=r.content[idx:idx+10]
print(list(snippet))
# snippet should be Insfr + c3 a1 + n
# decode
s=snippet.decode('utf-8')
print([hex(ord(c)) for c in s])
print(repr(s))
# now via bs4
from bs4 import BeautifulSoup
soup=BeautifulSoup(r.content, 'html.parser')
table=soup.find('table', class_='items')
rows=table.find('tbody').find_all('tr', recursive=False)
tr=rows[0]
tds=tr.find_all('td', recursive=False)
player_td=tds[1]
for a in player_td.find_all('a', href=True):
    if '/profil/spieler/' in a['href'] and a.get('title'):
        t=a.get('title')
        print([hex(ord(c)) for c in t], repr(t))
        break
