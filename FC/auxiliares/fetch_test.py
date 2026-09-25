import urllib.request, re, os, time
url='https://web.archive.org/web/20260306130538/https://fbref.com/en/squads/bf4acd28/2025/Corinthians-Stats'
req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=60) as r:
    html=r.read().decode('utf-8', errors='ignore')
print('len', len(html))
idx=html.find('id="stats_standard_24"')
print('idx', idx)
print(html[idx:idx+3000])
import re
rows=re.findall(r'<tr[^>]*>(.*?)</tr>', html[idx:idx+200000], re.S)
print('nrows', len(rows))
for r in rows[:3]:
    print(r[:500])
    print('---')

