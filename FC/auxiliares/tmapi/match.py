import json,collections,re
from unidecode import unidecode
from rapidfuzz import fuzz, process
rows=json.load(open('rows.json')); cm=json.load(open('clubmap.json'))
CAL={'MLS','Brasileirão','Liga Argentina'}
sq={}
for ent in open('sq.txt').read().split('~'):
    parts=ent.split('#'); k=parts[0]
    sq[k]=[p.split('|') for p in parts[1:] if p]
def n(s): 
    s=unidecode(str(s)).lower(); s=re.sub(r"[^a-z0-9 ]"," ",s); return re.sub(r"\s+"," ",s).strip()
glob=collections.defaultdict(set)  # normname -> pids
pinfo={}
for k,L in sq.items():
    for p in L:
        glob[n(p[1])].add(p[0]); pinfo.setdefault(p[0],p)
allnames={pid:n(p[1]) for pid,p in pinfo.items()}
res={}; stats=collections.Counter(); unmatched=[]
for t in rows:
    for x in rows[t]:
        if not x['club']: stats['noclub']+=1; continue
        sid=(2024 if x['liga'] in CAL else 2025) if t=='2526' else (2025 if x['liga'] in CAL else 2026)
        key=f"{cm[x['club']]}_{sid}"; cand={p[0]:n(p[1]) for p in sq.get(key,[])}
        nm=n(x['name']); pid=None; how=''
        ex=[p for p,v in cand.items() if v==nm]
        if len(ex)==1: pid=ex[0]; how='exact'
        else:
            b=process.extractOne(nm,cand,scorer=fuzz.token_set_ratio) if cand else None
            b2=process.extractOne(nm,cand,scorer=fuzz.WRatio) if cand else None
            if b and b[1]>=90 and b2 and b2[2]==b[2]: pid=b[2]; how=f'fuzzy{b[1]:.0f}'
            elif b2 and b2[1]>=90: pid=b2[2]; how=f'wr{b2[1]:.0f}'
            else:
                g=glob.get(nm)
                if g and len(g)==1: pid=list(g)[0]; how='global'
        if pid: res[f"{t}|{x['sh']}|{x['r']}"]=[pid,how]; stats[how[:5]]+=1
        else:
            unmatched.append((t,x['sh'],x['r'],x['name'],x['club'],(b[0],round(b[1]),cand.get(b[2])) if cand and b else None)); stats['none']+=1
print(stats)
json.dump(res,open('pidmap.json','w'))
json.dump(unmatched,open('unmatched.json','w'),ensure_ascii=False)
for u in unmatched[:60]: print(u)
print(len(unmatched))
# manual fixes
MAN={'Samu Omorodion':'991268','Gabriel Barbosa':'244275','Matías Arezo':'611426','Alan Sosa':'1103941','Galeno':'454121','Jason Remeseiro':'263860','Ángel Romero':'262262','Kanya Fujimoto':'415525','Celio Martins':'982524','Morlaye Sylla':'402112','Hilan Hamzaoui Slimani':'1070591','Iván Marcano':'57723','Vladan Kovacevic':'429070'}
FZ={'William Agada':'willy agada','Andy Moran':'andrew moran','Matthew Longstaff':'matty longstaff','Hennadii Synchuk':'gennadiy synchuk','Calvin Fodrey':'cj fodrey','Andrei Radu':'ionut radu'}
still=[]
for u in unmatched:
    t,sh,r,name,club,b=u
    k=f"{t}|{sh}|{r}"
    if name in MAN: res[k]=[MAN[name],'manual']
    elif name in FZ:
        g=glob.get(FZ[name]); 
        if g and len(g)==1: res[k]=[list(g)[0],'manual']
        else: still.append(u)
    else: still.append(u)
json.dump(res,open('pidmap.json','w'))
json.dump(still,open('unmatched.json','w'),ensure_ascii=False)
print('final unmatched',len(still)); [print(s[:5]) for s in still]
