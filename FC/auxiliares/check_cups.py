import requests
headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
# try to find competition codes via domestic overview 2025
url='https://www.transfermarkt.com/wettbewerbe/national/wettbewerbe/9/saison_id/2025/plus/1'
r=requests.get(url, headers=headers, timeout=30)
print(r.status_code, len(r.text))
# save
open('arg_overview.html','w',encoding='utf-8').write(r.text)
print('saved')
