import openpyxl, json, copy, collections, re
from openpyxl.formatting.rule import ColorScaleRule
F=json.load(open('final.json'))
AGE={}
for ent in open('sq.txt').read().split('~'):
    for p in ent.split('#')[1:]:
        f=p.split('|')
        if len(f)>3 and f[3].isdigit(): AGE.setdefault(f[0],int(f[3]))
SH=['DELANTEROS','EXTREMOS','MEDIAPUNTAS','MEDIOCENTROS','DEFENSAS','PORTEROS']
FILES=[('Temporada 2025-26.xlsx','2526'),('Temporada 2026-27.xlsx','2627')]
# style maps from both workbooks (first occurrence wins)
wbs={f:openpyxl.load_workbook(f) for f,_ in FILES}
def col(c): return openpyxl.utils.column_index_from_string(c)
log=collections.Counter()
for fname,tag in FILES:
    wb=wbs[fname]
    clubst={}; ligst={}; contst={}
    for sh in SH:
        ws=wb[sh]
        for r in range(4,ws.max_row+1):
            e=ws.cell(r,5); f=ws.cell(r,6); o=ws.cell(r,15)
            if e.value and e.value not in clubst: clubst[e.value]=copy.copy(e._style)
            if f.value and f.value not in ligst: ligst[f.value]=copy.copy(f._style)
            if o.value and o.value not in contst: contst[o.value]=copy.copy(o._style)
    allrows={}
    for sh in SH:
        ws=wb[sh]; gk= sh=='PORTEROS'
        data=[]; notes=[]
        for r in range(4,ws.max_row+1):
            vals=[ws.cell(r,c).value for c in range(1,37)]
            sty=[copy.copy(ws.cell(r,c)._style) for c in range(1,37)]
            if vals[0] is None and all(v is None for v in vals): continue
            k=f"{tag}|{sh}|{r}"; rec=F.get(k)
            item=dict(vals=vals,sty=sty,rec=rec)
            if rec is not None and rec['status']=='unmatched' and vals[4] is None: rec=None; item['rec']=None
            if rec is None: notes.append(item); log['nonplayer']+=1; continue
            if rec['status']=='dupe': log['dupe_removed']+=1; continue
            if rec['status']=='unmatched':
                for c in list(range(7,15))+list(range(16,28)): vals[c-1]=0
                log['unmatched_zero']+=1
            else:
                o=rec['out']; idx=(0,1,4,5) if gk else (0,1,2,3)
                for b,start in (('LIGA',7),('COPA',11),('CONT',16),('FIFA',20),('SEL',24)):
                    for j,i in enumerate(idx): vals[start-1+j]=o[b][i]
                if rec.get('cont'):
                    vals[14]=rec['cont']
                    if rec['cont'] in contst: sty[14]=copy.copy(contst[rec['cont']])
                if rec.get('club'):
                    vals[4]=rec['club']; 
                    if rec['club'] in clubst: sty[4]=copy.copy(clubst[rec['club']])
                    else: sty[4]=copy.copy(sty[3])
                    if rec.get('liga'):
                        vals[5]=rec['liga']
                        sty[5]=copy.copy(ligst[rec['liga']]) if rec['liga'] in ligst else copy.copy(sty[3])
                    log['club_changed']+=1
                if vals[2] in (None,'') and rec['pid'] in AGE: vals[2]=AGE[rec['pid']]; log['age_filled']+=1
                log['updated']+=1
            data.append(item)
        def tot(v,a,b,c,d): return sum((v[i-1] or 0) if isinstance(v[i-1],(int,float)) else 0 for i in (a,b,c,d))
        for it in data:
            v=it['vals']
            it['T']=dict(pj=tot(v,7,11,16,20),mn=tot(v,8,12,17,21),g=tot(v,9,13,18,22),a=tot(v,10,14,19,23))
        if gk: data.sort(key=lambda it:(-it['T']['a'],it['T']['g'] if it['T']['pj'] else 999,-it['T']['pj'],-it['T']['mn']))
        else: data.sort(key=lambda it:(-(it['T']['g']+it['T']['a']),-it['T']['g'],-it['T']['mn']))
        allrows[sh]=data
        # rewrite sheet
        maxr=ws.max_row
        for r in range(4,maxr+1):
            for c in range(1,37): ws.cell(r,c).value=None
        out=data+notes
        for i,it in enumerate(out):
            r=4+i; v=it['vals']
            for c in range(1,37):
                cell=ws.cell(r,c); cell._style=it['sty'][c-1]
                if 28<=c<=34 and it['rec'] is not None:
                    continue
                cell.value=v[c-1]
            if it['rec'] is None:
                for c in range(2,37): ws.cell(r,c).value=None
                continue
            ws[f'AB{r}']=f'=G{r}+K{r}+P{r}+T{r}'; ws[f'AC{r}']=f'=H{r}+L{r}+Q{r}+U{r}'
            ws[f'AD{r}']=f'=I{r}+M{r}+R{r}+V{r}'; ws[f'AE{r}']=f'=J{r}+N{r}+S{r}+W{r}'
            if gk: ws[f'AF{r}']=f'=IF(AB{r}=0,0,AE{r}/AB{r})'
            else: ws[f'AF{r}']=f'=AD{r}+AE{r}'
            ws[f'AG{r}']=f'=IF(AC{r}=0,0,AD{r}/AC{r}*90)'; ws[f'AH{r}']=f'=IF(AB{r}=0,0,AC{r}/AB{r})'
        last=3+len(out)
        # clear leftover rows
        for r in range(last+1,maxr+1):
            for c in range(1,37):
                ws.cell(r,c).value=None; ws.cell(r,c).style='Normal'
        if maxr>last: ws.delete_rows(last+1,maxr-last)
        # conditional formats: rebuild AG/AH scales to full range
        old=[ (cf.sqref, cf.rules) for cf in ws.conditional_formatting]
        ws.conditional_formatting=type(ws.conditional_formatting)()
        for sq,rules in old:
            s=str(sq); c0=re.match(r'([A-Z]+)',s).group(1)
            for rule in rules: ws.conditional_formatting.add(f'{c0}4:{c0}{3+len(data)}',rule)
        ws.auto_filter.ref=f'A3:AJ{last}'
    wb._allrows=allrows
    print(fname, dict(log)); log.clear()
import pickle
for fname,tag in FILES:
    wbs[fname].save('stage1_'+fname)
pickle.dump({f:{sh:[dict(vals=it['vals'],T=it['T']) for it in wbs[f]._allrows[sh]] for sh in SH} for f,_ in FILES},open('allrows.pkl','wb'))
