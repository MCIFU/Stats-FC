import json,collections
exec(open('process.py').read().split("res={}")[0])   # PA, COMP, CLUB, bucket
rows=json.load(open('rows.json')); pidmap=json.load(open('pidmap.json')); cm=json.load(open('clubmap.json'))
m=open('meta.txt').read()
cc=collections.defaultdict(collections.Counter); clubctry={}
for x in m.split('~'):
    f=x.split('|')
    if f[0]=='C' and f[4]!='0': cc[f[4]][f[5]]+=1
    if f[0]=='K': clubctry[f[1]]=f[5]
CTRY_CONF={k:v.most_common(1)[0][0] for k,v in cc.items()}
COMPCTRY={x.split('|')[1]:x.split('|')[4] for x in m.split('~') if x.startswith('C|')}
CONFNAME={'6':'UEFA','4':'CONMEBOL','3':'CONCACAF','1':'AFC','2':'CAF','5':'OFC'}
def conf_of_club(club,games):
    c=CTRY_CONF.get(clubctry.get(club,''))
    if c and c!='0': return c
    if clubctry.get(club) in ('113','96','213'): return '6'   # Mónaco, Liechtenstein, San Marino
    cnt=collections.Counter()
    for g in games:
        if g['club']==club and not g['nat']:
            cc2=COMPCTRY.get(g['comp'])
            if cc2 and CTRY_CONF.get(cc2): cnt[CTRY_CONF[cc2]]+=g['v'][0]
    return cnt.most_common(1)[0][0] if cnt else '?'
rev=collections.defaultdict(collections.Counter); excel_liga_of=collections.defaultdict(collections.Counter)
for t in rows:
    for x in rows[t]:
        if x['club']: rev[cm[x['club']]][x['club']]+=1; excel_liga_of[cm[x['club']]][x['liga']]+=1
REV={k:v.most_common(1)[0][0] for k,v in rev.items()}
LIGNAME={'ES1':'LaLiga','GB1':'Premier','L1':'Bundesliga','IT1':'Serie A','FR1':'Ligue 1','NL1':'Eredivisie','PO1':'Portugal','PL1':'Ekstraklasa','SC1':'Scottish Premiership','SCPM':'Scottish Premiership','SCPA':'Scottish Premiership','TR1':'Süper Lig','BE1':'Liga Belga','EJPL':'Liga Belga','SA1':'Saudi Pro','MLS1':'MLS','POUS':'MLS','MEXA':'Liga MX','MEX1':'Liga MX','POMX':'Liga MX','POME':'Liga MX','BRA1':'Brasileirão','ARG1':'Liga Argentina','ARGC':'Liga Argentina','AR1N':'Liga Argentina','A1P1':'Liga Argentina','A1P2':'Liga Argentina'}
PRIO=['UCL','UEL','UECL','LIB','SUD','CCC','LC','CC','ACL','CAF']
def liga_of(club,games):
    if club in excel_liga_of: return excel_liga_of[club].most_common(1)[0][0]
    lc=collections.Counter()
    for g in games:
        if g['club']==club and bucket(g)=='LIGA': lc[g['comp']]+=g['v'][0]
    if lc:
        c0=lc.most_common(1)[0][0]; return LIGNAME.get(c0) or COMP.get(c0,{}).get('name',c0).strip()
    return None
def contcode(cont):
    if not cont: return None
    mx=max(cont.values()); c=[k for k,v in cont.items() if v==mx]; c.sort(key=lambda z: PRIO.index(z) if z in PRIO else 99); return c[0]
final={}; stats=collections.Counter(); log=[]
for t in rows:
    bypid=collections.defaultdict(list)
    for x in rows[t]:
        k=f"{t}|{x['sh']}|{x['r']}"
        if k in pidmap: bypid[pidmap[k][0]].append(x)
        else: final[k]=dict(status='unmatched')
    for pid,L in bypid.items():
        games=[g for g in PA.get(pid,{'g':[]})['g'] if g['tag']==t]
        clubgames=collections.Counter()
        for g in games:
            if bucket(g) in ('LIGA','COPA','CONT','FIFA'): clubgames[g['club']]+=g['v'][0]
        conf={c:conf_of_club(c,games) for c in clubgames}
        versions=collections.defaultdict(dict)
        for c,n in clubgames.items(): versions[conf[c]][c]=n
        lastc=PA.get(pid,{}).get('last',{}).get(t,('',''))[0]
        if versions:
            owner = conf.get(lastc) if conf.get(lastc) in versions else max(versions,key=lambda v:sum(versions[v].values()))
        else: owner=None
        # assign excel rows to versions
        assigned={}; rest=[]
        for x in L:
            c=CLUB_CONF=conf_of_club(cm.get(x['club']),games) if x['club'] else None
            if c in versions and c not in assigned.values(): assigned[f"{t}|{x['sh']}|{x['r']}"]=c
            else: rest.append(x)
        primary=f"{t}|{L[0]['sh']}|{L[0]['r']}"
        free=[v for v in sorted(versions,key=lambda v:-sum(versions[v].values())) if v not in assigned.values()]
        # rows not assigned: take free versions, else dupe
        for x in rest:
            k=f"{t}|{x['sh']}|{x['r']}"
            cx=conf_of_club(cm.get(x['club']),games) if x['club'] else None
            if cx in versions: final[k]=dict(status='dupe',pid=pid); stats['merged_or_dupe']+=1; continue
            if free: assigned[k]=free.pop(0)
            elif not versions and k==primary: assigned[k]=None
            else: final[k]=dict(status='dupe',pid=pid); stats['merged_or_dupe']+=1
        # extra versions -> clones of the primary (or first assigned) row
        base = primary if primary in assigned else next(iter(assigned))
        extras=list(free)
        def build(k,x,v):
            if v is None:
                out,cont,clubs=compute(pid,t,None); rec=dict(status='ok',pid=pid,out=out)
                if cont: rec['cont']=contcode(dict(cont))
                return rec
            vclubs=set(versions[v])
            out,cont,clubs=compute(pid,t,vclubs)
            if v!=owner: out['SEL']=[0]*6
            rec=dict(status='ok',pid=pid,out=out,conf=CONFNAME.get(v,v))
            cid=cm.get(x['club']) if x else None
            if cid not in vclubs or (len(vclubs)>1 and lastc in vclubs and lastc!=cid):
                pick = lastc if lastc in vclubs else max(vclubs,key=lambda c:versions[v][c])
                rec['club']=REV.get(pick) or CLUB.get(pick,{}).get('name',pick); rec['liga']=liga_of(pick,PA.get(pid,{'g':[]})['g']) or '—'; rec['oldclub']=x['club'] if x else None
            cd=contcode(dict(cont))
            rec['cont']=cd if cd else ('—' if 'club' in rec else None)
            return rec
        xs={f"{t}|{x['sh']}|{x['r']}":x for x in L}
        for k,v in assigned.items():
            final[k]=build(k,xs[k],v); stats['rows']+=1
        if extras:
            final[base]['extra']=[build(None,None,v) for v in extras]
            stats['extra_rows']+=len(extras); log.append((t,L[0]['name'],[CONFNAME.get(v,v) for v in versions]))
        if len(versions)>1: stats['multi_conf_players']+=1
json.dump(final,open('final.json','w'),ensure_ascii=False)
print(stats)
for l in log[:30]: print(l)
json.dump(log,open('continent_log.json','w'),ensure_ascii=False)
