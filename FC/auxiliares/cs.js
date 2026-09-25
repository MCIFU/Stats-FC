const fs = require('fs');
const data = JSON.parse(fs.readFileSync('C:\\Users\\PCGAMI~1\\AppData\\Local\\Temp\\opencode\\bl1_2025.json','utf8'));
let gc={},cs={};
for(const m of data){
  const t1=m.team1.teamName, t2=m.team2.teamName;
  const res=m.matchResults[m.matchResults.length-1];
  const g1=res.pointsTeam1, g2=res.pointsTeam2;
  if(g1==null) continue;
  if(!(t1 in gc)){gc[t1]=0;cs[t1]=0;}
  if(!(t2 in gc)){gc[t2]=0;cs[t2]=0;}
  gc[t1]+=g2; gc[t2]+=g1;
  if(g2===0) cs[t1]++; if(g1===0) cs[t2]++;
}
console.log(JSON.stringify({gc,cs},null,1));
