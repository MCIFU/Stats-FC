import json,collections
rows=json.load(open('rows.json')); pidmap=json.load(open('pidmap.json')); cm=json.load(open('clubmap.json'))
m=open('meta.txt').read()
COMP={}; CLUB={}
for x in m.split('~'):
    f=x.split('|')
    if f[0]=='C': COMP[f[1]]=dict(name=f[2],type=int(f[3]))
    elif f[0]=='K': CLUB[f[1]]=dict(name=f[2],nt=f[3]=='1',main=f[4],abbr=f[6] if len(f)>6 else '')
PA={}
for ent in open('pa.txt').read().split('~'):
    p=ent.split(';'); pid=p[0]; games=[]; last={}
    for q in p[1:]:
        f=q.split('|')
        if f[0]=='L': last[f[1]]=(f[2],f[3]); continue
        games.append(dict(tag=f[0],comp=f[1],club=f[2],nat=f[3]=='1',v=list(map(int,f[4:10]))))
    PA[pid]=dict(g=games,last=last)
YOUTH_T={7,15,16,17,18,20,23}
YOUTH_C={'AJ','BK19','ITJE','P23Q','P23C','E21P','MNPP','18GB','ITJP','F19F','IT18','ITJF','7NP1','7NP2','BJ','T19Y','NLBA','PTPR','F17M','MNP3','UL2P'}
CONTCODE={'CL':'UCL','CLQ':'UCL','USC':'UCL','EL':'UEL','ELQ':'UEL','UCOL':'UECL','ECLQ':'UECL','CLI':'LIB','CS':'SUD','RECO':'LIB','CCL':'CCC','USMX':'LC','CAMC':'CC','ACLE':'ACL','ACEQ':'ACL','ACL2':'ACL','AC2Q':'ACL','AFCP':'ACL','ACL':'CAF','CAFC':'CAF','CCAC':'CCC','CCLS':'CCC'}
def bucket(g):
    c=g['comp']; t=COMP.get(c,{}).get('type',0); cl=CLUB.get(g['club'])
    if g['nat']:
        if cl and cl['nt'] and cl['main']==g['club'] and t not in YOUTH_T: return 'SEL'
        return None
    if cl and cl['main'] and cl['main']!=g['club']: return None   # filial/juvenil
    if t in YOUTH_T or c in YOUTH_C: return None
    if c=='FIC1' or c=='KLUB': return 'FIFA'
    if c=='CWCQ': return None
    if t in (10,13): return 'CONT'
    if t in (1,2,3,4,5,6,12): return 'LIGA'
    if t in (8,9,14,21,22,24): return 'COPA'
    return 'X:'+c
unk=collections.Counter()
def compute(pid,tag,clubfilter=None):
    out={b:[0,0,0,0,0,0] for b in ('LIGA','COPA','CONT','FIFA','SEL')}; cont=collections.Counter(); clubs=collections.Counter()
    for g in PA.get(pid,{'g':[]})['g']:
        if g['tag']!=tag: continue
        b=bucket(g)
        if b is None: continue
        if b.startswith('X:'): unk[b]+=g['v'][0]; continue
        if clubfilter and b!='SEL' and g['club'] not in clubfilter: continue
        o=out[b]
        for i in range(6): o[i]+=g['v'][i]
        if b=='CONT': cont[CONTCODE.get(g['comp'],g['comp'])]+=g['v'][0]
        if b in('LIGA','COPA','CONT','FIFA'): clubs[g['club']]+=g['v'][0]
    return out,cont,clubs
res={}
for t in rows:
    # pid -> rows (for double-club)
    bypid=collections.defaultdict(list)
    for x in rows[t]:
        k=f"{t}|{x['sh']}|{x['r']}"
        if k in pidmap: bypid[pidmap[k][0]].append(x)
    for pid,L in bypid.items():
        multi=len(L)>1 and len({cm.get(x['club']) for x in L})>1
        for x in L:
            k=f"{t}|{x['sh']}|{x['r']}"
            cf={cm.get(x['club'])} if multi else None
            out,cont,clubs=compute(pid,t,cf)
            if multi:
                # SEL only on the row of the last club
                last=PA.get(pid,{}).get('last',{}).get(t,('',''))[0]
                if cm.get(x['club'])!=last: out['SEL']=[0]*6
            res[k]=dict(pid=pid,out=out,cont=cont.most_common(),clubs=clubs.most_common(),last=PA.get(pid,{}).get('last',{}).get(t),multi=multi,dupe=len(L)>1 and not multi)
json.dump(res,open('computed.json','w'))
print(len(res)); print(unk.most_common(30))
print('dupes',sum(1 for v in res.values() if v['dupe']),'multi',sum(1 for v in res.values() if v['multi']))
