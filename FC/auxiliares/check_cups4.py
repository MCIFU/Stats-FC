import requests, re
headers={'User-Agent':'Mozilla/5.0'}
slug='trofeo-de-campeones-superliga'
code='TDCS'
for sid in [2024,2025]:
    url=f'https://www.transfermarkt.com/{slug}/gesamtspielplan/pokalwettbewerb/{code}/saison_id/{sid}'
    r=requests.get(url, headers=headers, timeout=30)
    html=r.text
    # extract match lines: look for spielbericht links and surrounding teams
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(html,'html.parser')
    # find all match report links
    links=soup.find_all('a', href=re.compile(r'/spielbericht/index/spielbericht/'))
    print(f'=== {sid} {len(links)} links ===')
    for a in links[:20]:
        print(a.get_text(strip=True), a.get('href'))
    # also print raw fixture text snippet
    # find table?
