import unicodedata
def norm(s):
    s=s.lower()
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c)!='Mn')

# load with ages? std_2025_clean.txt doesn't have age. Need to re-parse with age? Let's parse again quickly for candidates only.
# Instead load all_2025_seriea? No.
# Let's just dump all rows containing keywords.

keywords=["pochettino","martinez","rene","ignacio","lucas silva","marinho","menino","coutinho","lima","moises","rony","barbosa","willian machado","lucas oliveira","victor luis","fernandinho","calebe","matheus bahia","marcos victor","olivera","everaldo","caca","britez","walace","luan candido","fabiano","felix torres","paulinho","eduardo","andre","elias","nathan","christian","adson","everton","rodrigo","denilson","gustavo","bruno","ze roberto","japa","wallisson","cazonatti","formiga","verissimo","rodinei","miguel","pepe","nadson","moreno","gomez","lopez","veliz","riccieli","darlan","mateus silva","caique","tarzia","anderson","alex","laquintana","villagra","eliasson","alerrandro","sanabria","maripan"]

with open('std_2025_clean.txt',encoding='utf-8') as f:
    lines=[l.strip() for l in f]

for kw in keywords:
    nk=norm(kw)
    hits=[l for l in lines if nk in norm(l)]
    if hits:
        print(f'--- {kw} ({len(hits)}) ---')
        for h in hits[:10]:
            print(h)
