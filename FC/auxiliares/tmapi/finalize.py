import json,collections
exec(open('process.py').read().split("res={}")[0])   # reuse loaders + bucket/compute
rows=json.load(open('rows.json')); pidmap=json.load(open('pidmap.json')); cm=json.load(open('clubmap.json'))
# reverse club map: tm id -> most common Excel name
rev=collections.defaultdict(collections.Counter)
excel_liga_of=collections.defaultdict(collections.Counter)
for t in rows:
    for x in rows[t]:
        if x['club']: rev[cm[x['club']]][x['club']]+=1; excel_liga_of[cm[x['club']]][x['liga']]+=1
REV={k:v.most_common(1)[0][0] for k,v in rev.items()}
LIGNAME={'ES1':'LaLiga','GB1':'Premier','L1':'Bundesliga','IT1':'Serie A','FR1':'Ligue 1','NL1':'Eredivisie','PO1':'Portugal','PL1':'Ekstraklasa','SC1':'Scottish Premiership','SCPM':'Scottish Premiership','SCPA':'Scottish Premiership','TR1':'Süper Lig','BE1':'Liga Belga','EJPL':'Liga Belga','SA1':'Saudi Pro','MLS1':'MLS','POUS':'MLS','MEXA':'Liga MX','MEX1':'Liga MX','POMX':'Liga MX','POME':'Liga MX','BRA1':'Brasileirão','ARG1':'Liga Argentina','ARGC':'Liga Argentina','AR1N':'Liga Argentina','A1P1':'Liga Argentina','A1P2':'Liga Argentina'}
PRIO=['UCL','UEL','UECL','LIB','SUD','CCC','LC','CC','ACL','CAF']
def season_games(pid,tag):
    return [g for g in PA.get(pid,{'g':[]})['g'] if g['tag']==tag]
final={}; stats=collections.Counter()
for t in rows:
    bypid=collections.defaultdict(list)
    for x in rows[t]:
        k=f"{t}|{x['sh']}|{x['r']}"
        if k in pidmap: bypid[pidmap[k][0]].append(x)
        else: final[k]=dict(status='unmatched'); stats['unmatched']+=1
    for pid,L in bypid.items():
        clubset={cm.get(x['club']) for x in L}
        multi=len(L)>1 and len(clubset)>1
        seen=set()
        # SEL owner among multi rows
        last=PA.get(pid,{}).get('last',{}).get(t,('',''))[0]
        for i,x in enumerate(L):
            k=f"{t}|{x['sh']}|{x['r']}"
            cid=cm.get(x['club'])
            if (cid in seen):
                final[k]=dict(status='dupe',pid=pid); stats['dupe']+=1; continue
            seen.add(cid)
            out,cont,clubs=compute(pid,t,{cid} if multi else None)
            rec=dict(status='ok',pid=pid,out=out)
            if multi:
                owner = last if last in clubset else max(L,key=lambda y: compute(pid,t,{cm.get(y['club'])})[0]['LIGA'][0])['club']
                owner = owner if owner in clubset else cm.get(owner)
                if cid!=owner: rec['out']['SEL']=[0]*6
                stats['multi']+=1
            else:
                # club change: end-of-season club (last official club game in the tag)
                cl=dict(clubs)
                if cl and cid not in cl:
                    last=max(cl,key=cl.get)
                    newname=REV.get(last) or CLUB.get(last,{}).get('name',last)
                    # league of new club from its league games
                    lc=collections.Counter()
                    for g in season_games(pid,t):
                        if g['club']==last and bucket(g)=='LIGA': lc[g['comp']]+=g['v'][0]
                    lig=None
                    if last in excel_liga_of: lig=excel_liga_of[last].most_common(1)[0][0]
                    elif lc: 
                        c0=lc.most_common(1)[0][0]; lig=LIGNAME.get(c0) or COMP.get(c0,{}).get('name',c0).strip()
                    rec['club']=newname; rec['liga']=lig; rec['oldclub']=x['club']; stats['clubchange']+=1
            if cont:
                cont=list(cont.items())
                mx=max(n for _,n in cont); cands=[c for c,n in cont if n==mx]
                cands.sort(key=lambda c: PRIO.index(c) if c in PRIO else 99)
                rec['cont']=cands[0]
            elif 'club' in rec: rec['cont']='—'
            final[k]=rec; stats['ok']+=1
json.dump(final,open('final.json','w'),ensure_ascii=False)
print(stats)
chg=[(k,v['oldclub'],v['club'],v['liga']) for k,v in final.items() if 'club' in v]
print(collections.Counter(k[:4] for k,*_ in chg))
for c in chg[:25]: print(c)
print(collections.Counter(v['liga'] for k,v in final.items() if 'club' in v).most_common(40))
