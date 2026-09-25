# search requested players in std_2025_clean.txt
import unicodedata

def norm(s):
    s=s.lower()
    s=''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c)!='Mn')
    return s

requested = {
'Internacional': ["Guillermo Maripán","Félix Torres","Matheus Bahia","Rodrigo Villagra","Paulinho Paula","Niclas Eliasson","Calebe","Alerrandro","Antonio Sanabria"],
'Bahia': ["Marco Moreno","Marcos Victor","Román Gómez","Lautaro López","Cristian Olivera","Alejo Veliz","Everaldo"],
'Vitória': ["Riccieli","Cacá","Emanuel Brítez","Darlan","Luan Cândido","Nathan Mendes","Fabiano","Mateus Silva","Walace","Caíque Gonçalves","Tomás Pochettino","Emmanuel Martínez","Diego Tarzia","Renê","Anderson Pato","Ignacio Laquintana","Lucas Silva","Marinho","Alex Bruno"],
'Santos': ["Lucas Veríssimo","Gabriel Menino","Rodinei","Arthur Melo","Christian Oliva","Miguelito","Philippe Coutinho","Lima","Pepê Fermino","Nadson","Everton","Moisés","Rony","Gabriel Barbosa"],
'Mirassol': ["Willian Machado","Lucas Oliveira","Victor Luís","Igor Formiga","Elias","Wallisson","Gustavo Cazonatti","Denilson","Japa","Eduardo","Fernandinho","Gustavo Silva","André Luis","Zé Roberto","Bruno Santos"],
}

# load clean
rows={}
with open('std_2025_clean.txt',encoding='utf-8') as f:
    for line in f:
        parts=line.strip().split('|')
        if len(parts)!=7: continue
        name,pos,club,mp,mins,gls,ast=parts
        rows.setdefault(norm(name), []).append((name,pos,club,mp,mins,gls,ast))

for club, lst in requested.items():
    print(f'== {club} ==')
    for req in lst:
        n=norm(req)
        # exact match?
        if n in rows:
            print(f'FOUND {req} -> {rows[n]}')
        else:
            # fuzzy: check substring
            cands=[]
            for k,v in rows.items():
                # all tokens of req in k? or k in req?
                if n in k or k in n:
                    cands.append((k,v))
            # also token match
            if cands:
                print(f'FUZZY {req} -> {cands[:3]}')
            else:
                print(f'MISSING {req}')
    print()
