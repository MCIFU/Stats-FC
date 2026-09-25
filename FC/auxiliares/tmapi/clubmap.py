import json,collections
from unidecode import unidecode
from rapidfuzz import fuzz, process
cl=json.load(open('clublists.json'))
LIG={'LaLiga':['ES1'],'Premier':['GB1'],'Bundesliga':['L1'],'Serie A':['IT1'],'Ligue 1':['FR1'],'Eredivisie':['NL1'],'Portugal':['PO1'],'Ekstraklasa':['PL1'],'Scottish Premiership':['SC1'],'Süper Lig':['TR1'],'Liga Belga':['BE1'],'Saudi Pro':['SA1'],'MLS':['MLS1'],'Liga MX':['MEXA'],'Brasileirão':['BRA1'],'Liga Argentina':['AR1N','ARG1','ARGC']}
pool=collections.defaultdict(dict)
for code,s,clubs in cl:
    for c in clubs:
        i,n=c.split(':',1); 
        for l,cs in LIG.items():
            if code in cs: pool[l][i]=n.replace('​','')
MAN={'Man. City':'281','Man. United':'985','Wolves':'543','Newcastle':'762','Inter':'46','Juventus':'506','PSG':'583','Marseille':'244','Olympique Lyonnais':'1041','Estrasburgo':'667','AZ':'1090','PSV':'383','Ajax':'610','Twente':'317','Sporting CP':'336','FC Porto':'720','AVS':'110302','Atlético Madrid':'13','Valencia':'1049','Getafe':'3709','Celta':'940','RC Celta':'940','Racing Santander':'630','Deportivo La Coruña':'897','Real Betis':'150','Legia Warszawa':'255','Wisła Kraków':'422','Wieczysta Kraków':'30974','Śląsk Wrocław':'759','Lech Poznań':'238','Pogoń Szczecin':'324','Minnesota Utd':'56089','NY Red Bulls':'623','New York City':'40058','LA Galaxy':'1061','Los Angeles FC':'51828','Vancouver':'6321','Cincinnati':'51772','Philadelphia':'25467','New England':'626','San José':'218','Sporting KC':'4284','St. Louis City':'82686','Chicago Fire':'432','Real Salt Lake':'6643','San Diego':'114977','Inter Miami':'69261','Orlando City':'45604','Toronto FC':'11141','Athletico-PR':'679','Atlético-MG':'330','Bragantino':'8793','Ceará':'2029','Fortaleza':'10870','Sport':'8718','Juventude':'10492','Vasco':'978','Botafogo':'537','Remo':'10997','América':'3631','Guadalajara':'6711','Atlante':'6709','Mazatlán':'82696','Atlas':'8590','Pumas UNAM':'7633','Juárez':'49283','León':'4941','Toluca':'1804','Argentinos Jrs':'1030','Estudiantes La Plata':'288','Estudiantes RC':'14602','Gimnasia La Plata':'1106','Gimnasia Mendoza':'14687','Godoy Cruz':'12574','Riestra':'19775','San Martín SJ':'10511','Unión Santa Fe':'7097','Racing Club':'1444','Hearts':'43','St Mirren':'465','St Johnstone':'2578','Beşiktaş':'114','Kasımpaşa':'10484','Club Brugge':'2282','Al-Hilal':'1114','Colonia':'3','1. FC Köln':'3','Mönchengladbach':'18','Union Berlin':'89','Unión Berlín':'89','Hellas Verona':'276','SSC Nápoles':'6195','Atalanta':'800','Bologna':'1025','Niza':'417','Rennes':'273','Stade Rennais':'273','Metz':'347','Nantes':'995','Angers':'1420','Le Havre':'738','Troyes':'1095','Excelsior':'798','Heerenveen':'306','Volendam':'724','Telstar':'1434','Cambuur':'133','Willem II':'403','Groningen':'202','Utrecht':'200','Nacional':'982','Casa Pia':'3268','Estoril':'1465','Alverca':'2521','Tondela':'7179','CD Tondela':'7179','Marítimo':'1301','Académico Viseu':'7788','Jagiellonia Białystok':'2300','Instituto':'1829','Independiente':'1234','Tigre':'11831','Lanús':'333','Talleres':'3938','Belgrano':'2417','Huracán':'2063','Sarmiento':'12454','Platense':'928','Banfield':'830','Aldosivi':'12301','Central Córdoba':'31284','Independiente Rivadavia':'12179','Defensa y Justicia':'2402','Barracas Central':'25184','Atlético Tucumán':'14554','Rosario Central':'1418','Newell\'s Old Boys':'1286','San Lorenzo':'1775','Vélez Sarsfield':'1029','Boca Juniors':'189','River Plate':'209','Monterrey':'2407','Cruz Azul':'3711','Tigres UANL':'7055','Necaxa':'1146','Pachuca':'4035','Tijuana':'13353','Santos Laguna':'1403','Atlético de San Luis':'40188','Puebla':'5662','Querétaro':'4961','Flamengo':'614','Palmeiras':'1023','Cruzeiro':'609','Corinthians':'199','Fluminense':'2462','Bahia':'10010','Santos':'221','São Paulo':'585','Grêmio':'210','Internacional':'6600','Coritiba':'776','Vitória':'2125','Mirassol':'3876','Chapecoense':'17776','Amed SK':'12382','Corum FK':'37951','Fenerbahce':'36','Galatasaray':'141','Göztepe':'1467','Trabzonspor':'449','Basaksehir FK':'6890','Celtic':'371','Rangers':'124','Aberdeen':'370','Hibernian':'903','Kilmarnock':'2553','Motherwell':'987','Dundee FC':'511','Dundee United':'1519','Falkirk':'1191','Paderborn':'127','SV Elversberg':'64','Schalke 04':'33','Heidenheim':'2036','St. Pauli':'35','Hoffenheim':'533','TSG Hoffenheim':'533','Wolfsburgo':'82','Augsburgo':'167','FC Augsburg':'167','Mainz 05':'39','Hamburgo SV':'41','Werder Bremen':'86'}
rows=json.load(open('rows.json'))
need=collections.defaultdict(set)
for t in rows:
    for x in rows[t]:
        if x['club']: need[x['liga']].add(x['club'])
res={}
def norm(s): return unidecode(s).lower().replace('fc','').replace('cf','').strip()
for l,cs in need.items():
    for c in cs:
        if c in MAN: res[c]=MAN[c]; continue
        p=pool.get(l,{})
        best=process.extractOne(norm(c),{i:norm(n) for i,n in p.items()},scorer=fuzz.WRatio)
        res[c]=best[2]
        print(f'{l:12} {c:28} -> {p[best[2]]:35} {best[1]:.0f}')
json.dump(res,open('clubmap.json','w'),ensure_ascii=False)
names={}
for l in pool: names.update(pool[l])
json.dump(names,open('tmclubnames.json','w'),ensure_ascii=False)
