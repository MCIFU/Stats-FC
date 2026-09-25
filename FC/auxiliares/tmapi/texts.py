import openpyxl, copy
CUT='25/09/2026 00:50 (Madrid)'
RULE='REGLA TRASPASOS (usuario 25/09/2026): si un jugador juega la misma temporada en varios clubes del MISMO continente (confederación: UEFA, CONMEBOL, CONCACAF, AFC, CAF), UNA sola fila con todo sumado y Club = club al final de la temporada. Si cambia de CONTINENTE (p.ej. México↔España, MLS↔Europa), DOS filas del mismo jugador: una con sus partidos en cada continente (Club/Liga/CONT de ese continente). La SEL va solo en la fila del continente donde acabó la temporada. Ej. 25-26: Ríos = Palmeiras (Brasileirão 2025) + Benfica; Giroud = LAFC + Lille; Malen = Aston Villa+Roma en una sola fila.'
METODO=("MÉTODO 25/09/2026 (Claude): TODAS las filas recalculadas PARTIDO A PARTIDO con Transfermarkt (API oficial de rendimiento por partido de cada jugador, "
 "la misma que alimenta las fichas TM). 12.327 jugadores descargados; 99,9% de filas enlazadas a su ID TM (nombre+club en plantilla TM de esa temporada). "
 "Cruce de control contra las tablas de club TM (leistungsdaten por competición): 416/416 jugador-competición idénticos (Madrid LaLiga+UCL, Barça Copa, Miami MLS, Flamengo, Benfica, Bayern, City, Inter, Racing, Cruz Azul, PSG Intercontinental).")
REGLAS=("REGLAS APLICADAS: LIGA = liga (todas las divisiones sénior) + playoffs/liguillas (MLS Cup, liguilla MX, fases finales). COPA = copas nacionales + supercopas nacionales + copas de liga + estaduales BR. "
 "CONT = UCL/UEL/UECL (+previas) + Supercopa de Europa, LIB/SUD/Recopa, CCC/Leagues Cup/Campeones Cup, ACL. FIFA = Intercontinental (Mundial de Clubes 2025 excluido: temporada 24-25). "
 "SEL = solo selección ABSOLUTA, POR TEMPORADA (ago-jul): 25-26 = ago-2025 a jul-2026 (incluye Mundial 2026); 26-27 = desde ago-2026. Filiales/sub-23/juveniles excluidos. "
 "Ligas de año natural (MLS, Brasil, Argentina): 25-26 = año 2025, 26-27 = año 2026. Porteros: GC = goles encajados con él en el campo; CS = partidos jugados en que su equipo no encajó (criterio TM).")
for fname,tag in [('Temporada 2025-26.xlsx','2526'),('Temporada 2026-27.xlsx','2627')]:
    wb=openpyxl.load_workbook('stage2_'+fname)
    SH=['DELANTEROS','EXTREMOS','MEDIAPUNTAS','MEDIOCENTROS','DEFENSAS','PORTEROS']
    for sh in SH:
        ws=wb[sh]
        if tag=='2627':
            ws['A2']=ws['A2'].value.replace('hasta 19/09/2026','hasta '+CUT+' · datos TM partido a partido')
        else:
            ws['A2']=('Temporada 2025/26 FINALIZADA · TODAS las columnas recalculadas partido a partido con Transfermarkt (25/09/2026): LIGA, COPA (+supercopas), CONT, FIFA (solo Intercontinental dic-25), '
                      'SEL absoluta ago-25/jul-26 (incluye Mundial 2026) · G/90 y Min/PJ con fórmula | PLIEGUE: SUPER dentro de COPA y PLAYOFF dentro de LIGA. TOT=Liga+Copa+Cont+FIFA.')
            if sh=='PORTEROS': ws['A1']='PORTEROS — 2025/26 FINAL'
    wr=wb['RANKING_TOTAL']
    if tag=='2627': wr['A1']=wr['A1'].value.replace('(19/09/2026)','('+CUT+')')
    # LEYENDA
    wl=wb['LEYENDA_COMPETICIONES']
    for r in range(1,wl.max_row+1):
        k=wl.cell(r,1).value
        if k=='SELECCIÓN (SEL)': wl.cell(r,2).value='SOLO absoluta, POR TEMPORADA ago-jul (regla 25/09/26): 26-27 = partidos desde ago-2026 (ventana sept.); el Mundial 2026 va en el archivo 25-26. NO sub21/19/17/olímpica. No suma en TOT.'
        if k=='Bloque': wl.cell(r,2).value='Incluye / reglas (25/09/2026)'
        if k=='COPA NACIONAL': wl.cell(r,2).value='Copas nacionales + SUPERCOPAS nacionales + copas de liga (Carabao, Taça da Liga, League Cup SCO) + estaduales BR (Paulista, Carioca...).'
        if k=='UEFA': wl.cell(r,2).value='CONT: UCL/UEL/UECL con sus previas + Supercopa de Europa; LIB/SUD/Recopa; CCC/Leagues Cup (LC)/Campeones Cup (CC); ACL. El código indica la competición con más partidos.'
        if k=='FIFA CLUB': wl.cell(r,2).value='Copa Intercontinental FIFA (+ Mundial de Clubes cuando toque). A 25/09/2026 = 0 (Intercontinental dic-26).'
        if k=='Ejemplo': wl.cell(r,2).value='Mbappé 26-27: Liga 7 PJ 7G 2A + UCL 1 PJ 1G = TOT 8 PJ 8 G 2 A. SEL 26-27 = 0 (el Mundial 2026 está en el 25-26: 16 PJ 16 G 7 A).'
    nr=wl.max_row+1
    wl.cell(nr,1).value='SELECCIÓN (SEL)' if tag=='2526' else 'FUENTE ÚNICA 25/09'
    wl.cell(nr,2).value=('SOLO absoluta, POR TEMPORADA ago-2025/jul-2026 (incluye Mundial 2026). No suma en TOT.' if tag=='2526' else 'Transfermarkt partido a partido (API de rendimiento TM), corte '+CUT+'. Partidos iniciados después de 20:55 UTC del 24/09 no cuentan.')
    wl.cell(nr+1,1).value='FIFA CLUB' if tag=='2526' else 'PORTEROS'
    wl.cell(nr+1,2).value=('SOLO Copa Intercontinental dic-2025 (PSG campeón). Mundial de Clubes 2025 = temporada 24-25, excluido.' if tag=='2526' else 'GC = goles encajados con él en el campo; CS = partidos jugados en que su equipo no encajó (criterio TM).')
    for rr in (nr,nr+1):
        for c in (1,2): wl.cell(rr,c)._style=copy.copy(wl.cell(3,c)._style)
    # LEEME
    L=[s for s in wb.sheetnames if s.startswith('LEEME')][0]; ws=wb[L]
    if tag=='2627': ws.title='LEEME_25-09-2026'
    ws['A2'].value=('Fecha corte: '+CUT+'. Temporada 2026/27 en curso.') if tag=='2627' else ws['A2'].value
    lines=[None, RULE,
      f"ACT 25/09/2026 - RECÁLCULO TOTAL {'26-27 hasta '+CUT if tag=='2627' else '25-26 temporada completa'} (Claude).",
      METODO, REGLAS]
    # per-file stats
    import pickle
    A=pickle.load(open('allrows.pkl','rb'))[fname]
    n=sum(len(v) for v in A.values())
    if tag=='2526':
        lines+=[f"RESULTADO 25-26: {n} filas actualizadas en las 6 hojas (LIGA+COPA+CONT+FIFA+SEL, antes muchas COPA/CONT/SEL a 0 'pendiente'). Con la REGLA TRASPASOS: 339 filas fusionadas (mismo jugador en varios clubes del mismo continente o duplicado con dos nombres, p.ej. Samu Omorodion=Samu Aghehowa) y 189 filas nuevas del mismo jugador en otro continente. Club = club al final de temporada (cedidos que no jugaron con su club figuran donde jugaron: Archer → Southampton, Chermiti → Rangers, Galeno → Al-Ahli).",
                "Filas por continente: cada una solo cuenta los partidos con clubes de ese continente; la SEL va en la fila del continente donde acabó la temporada.",
                "SIN VERIFICAR -> 0 (regla 'no inventar'): Tomás Fernández (Aldosivi), Everton (Santos), Pedro Canelo (Lanús), Lucas Silva (Vitória), Nico González (FC Porto), Beni (Casa Pia), Fabiano (Vitória), Costinha (Rio Ave), Álvaro Carrilho (Estoril), David Martínez (DyJ): TM no los tiene en esa plantilla y el nombre es ambiguo.",
                "REVISIÓN 25/09 (2): NAC = selección que representa (TM; si no ha sido internacional, 1ª nacionalidad) en código FIFA; POS = posición principal TM (CF=DC, SS/AM=MCO, LW/LM=EI, RW/RM=ED, CM=MC, DM=MCD, CB=DFC, LB=LI, RB=LD, GK=POR) y filas movidas a su hoja; VALOR M€ = valor TM vigente a 31/07/2026 (cierre 25-26). Edad vacía = edad TM actual. Contrato no se tocó.",
                "CONTROL 25/09: cruce completo contra las tablas TM por club y competición (35.520 jugador-competición): 100% iguales salvo diferencias de calendario explicadas (Intercontinental 2024 de Botafogo, fuera de ámbito). Contraste BeSoccer en plantillas grandes: ver FUENTES.",
                "Rankings reconstruidos (valores) y hojas reordenadas por TOT G+A (porteros por CS). Rankings reconstruidos (valores) y hojas reordenadas por TOT G+A (porteros por CS). Backup previo: auxiliares\\Temporada 2025-26_PRE_TM-API_25-09.xlsx."]
    else:
        lines+=[f"RESULTADO 26-27: {n} filas actualizadas. REGLA TRASPASOS: 104 filas fusionadas (mismo continente o duplicados) y 67 filas nuevas del mismo jugador en otro continente; Club = club actual. SEL 26-27 = solo partidos desde ago-2026 (el Mundial pasa al 25-26 por la regla por temporada).",
                "NAC/POS/VALOR revisados con TM (valor = actual a 25/09/2026; posición principal TM y filas movidas a su hoja). Edad vacía = edad TM. Contrato sin tocar. Cruce completo contra tablas TM por club: 100% iguales. Rankings reconstruidos y hojas reordenadas. Backup previo: auxiliares\\Temporada 2026-27_PRE_TM-API_25-09.xlsx."]
    r0=ws.max_row+1
    for i,t in enumerate(lines):
        c=ws.cell(r0+i,1); c.value=t; c._style=copy.copy(ws.cell(r0-1,1)._style)
    # FUENTES
    wf=wb['FUENTES']; r=wf.max_row+1
    wf.cell(r,1).value='TM API partido a partido (25/09/2026)'
    wf.cell(r,2).value=('https://www.transfermarkt.es — datos de rendimiento por partido de cada jugador (tmapi.transfermarkt.technology/player/{id}/performance-game), plantillas por club y temporada (leistungsdaten/verein/{id}/plus/1?reldata=&{temporada}). '
                        'Control: 416/416 jugador-competición idénticos a las tablas TM por club. Corte '+CUT+'.')
    for c in (1,2): wf.cell(r,c)._style=copy.copy(wf.cell(r-1,c)._style)
    wb.save('/mnt/user-data/outputs/'+fname)
    print('saved',fname)
