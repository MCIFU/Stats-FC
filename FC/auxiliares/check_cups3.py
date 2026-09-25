import requests, re
headers={'User-Agent':'Mozilla/5.0'}
for comp, code in [('Trofeo','TDCS'),('SuperArgentina','SCAG')]:
    for sid in [2024,2025,2026]:
        # try both startseite and gesamtspielplan
        url=f'https://www.transfermarkt.com/{comp.lower()}/gesamtspielplan/pokalwettbewerb/{code}/saison_id/{sid}'
        # correct slugs: trofeo-de-campeones-superliga, supercopa-argentina
        slug='trofeo-de-campeones-superliga' if code=='TDCS' else 'supercopa-argentina'
        url=f'https://www.transfermarkt.com/{slug}/gesamtspielplan/pokalwettbewerb/{code}/saison_id/{sid}'
        r=requests.get(url, headers=headers, timeout=30)
        html=r.text
        # find team names in fixtures: look for verein links
        teams=sorted(set(re.findall(r'/startseite/verein/(\d+)', html)))[:20]
        # find title
        import bs4
        from bs4 import BeautifulSoup
        soup=BeautifulSoup(html,'html.parser')
        title=soup.title.string.strip() if soup.title else 'no'
        print(comp, sid, r.status_code, title[:80], 'teams:', teams[:10])
