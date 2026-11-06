/** Pure deterministic state transforms. Neither dates nor activity are fabricated for real accounts. */
export const clamp = (n,min,max) => Math.min(max,Math.max(min,n));
export function hash(s){ let h=2166136261; for(const c of String(s)){h=Math.imul(h^c.charCodeAt(0),16777619);} return h>>>0; }
export function seeded(seed){let x=(seed>>>0)||1;return ()=>{x^=x<<13;x^=x>>>17;x^=x<<5;return (x>>>0)/4294967296;};}
export const palette={JavaScript:0xf9df71,TypeScript:0x5eafff,Python:0x79b6f2,Rust:0xf3916c,Go:0x65d8d6,Java:0xf4a770,C:0x99a1ff,'C++':0x7f89f3,'C#':0xb48bf6,HTML:0xea8566,CSS:0xac8dff,Shell:0xa0e0ac,Swift:0xf59a74,Kotlin:0xc29af2,PHP:0xa19dee,Ruby:0xf27f97,Vue:0x7cdeb5,Other:0x91b7c2};
export function languageColor(language){return palette[language]??palette.Other;}
export function sanitizeUsername(s){const v=String(s??'').trim();return /^[a-z\d](?:[a-z\d-]{0,37}[a-z\d])?$/i.test(v)?v:null;}
export function scoreEvent(event){switch(event.type){case 'PushEvent': return Math.min(event.payload?.size??event.payload?.commits?.length??1,20);case 'PullRequestEvent': return event.payload?.action==='opened'?4:2;case 'CreateEvent':return 3;case 'ReleaseEvent':return 5;case 'IssuesEvent':return 1;default:return 1;}}
export function transform(raw){
 const repos=(raw.repos||[]).filter(r=>!r.fork).map(r=>({name:r.name, fullName:r.full_name||r.name,url:r.html_url||'#',language:r.language||'Other',stars:r.stargazers_count||0,size:r.size||0,updatedAt:r.pushed_at||r.updated_at||null,description:r.description||'',forks:r.forks_count||0})).sort((a,b)=>b.stars-a.stars||b.size-a.size||a.name.localeCompare(b.name)).slice(0,64);
 const events=(raw.events||[]).filter(e=>e?.created_at&&Number.isFinite(Date.parse(e.created_at))).map(e=>({id:e.id,type:e.type,date:e.created_at,repo:e.repo?.name||'',score:scoreEvent(e)})).sort((a,b)=>Date.parse(a.date)-Date.parse(b.date));
 const languages=[...new Set(repos.map(r=>r.language))];
 const cutoff=Date.now()-7*86400000; const recentScore=events.filter(e=>Date.parse(e.date)>cutoff).reduce((n,e)=>n+e.score,0);
 return {username:raw.username||'demo',demo:!!raw.demo,repos,events,languages,recentScore,createdAt:raw.createdAt||new Date().toISOString(),source:raw.source||'GitHub public REST API'};
}
export function stateAt(data,progress){
 const p=clamp(Number(progress)||0,0,1),events=data.events;
 if(!events.length) return {visibleEvents:[],energy:0,progress:p,endDate:data.createdAt};
 const start=Date.parse(events[0].date),end=Date.parse(events.at(-1).date);
 const threshold=start+(end-start)*p;
 const visibleEvents=events.filter(e=>Date.parse(e.date)<=threshold);
 const current=visibleEvents.filter(e=>Date.parse(e.date)>=threshold-7*86400000);
 const score=current.reduce((a,e)=>a+e.score,0);
 return {visibleEvents,energy:clamp(Math.round(18+score*3.2),0,100),progress:p,endDate:new Date(threshold).toISOString()};
}
export function makeDemo(){
 const names=['neural-atlas','distributed-kernel','vector-search','cloud-orchestrator','syntax-engine','compiler-lab','data-pipeline','rust-runtime','zero-trust-api','graph-analytics','realtime-dashboard','mobile-interface','open-source-sdk','observability','edge-computing','ai-agents','network-simulator','cryptography-lab','image-processing','web-experiments','infra-as-code','event-stream','robotics-vision','terminal-ui'];
 const langs=['Python','Rust','TypeScript','Go','JavaScript','C++','Python','Rust','Go','Python','TypeScript','Swift'];
 const repos=names.map((name,i)=>({name,full_name:`demo/${name}`,language:langs[i%langs.length],stargazers_count:Math.max(0,Math.round(180/(i+1)-8)),size:Math.round(1500+((i*1171)%22000)),html_url:'#',pushed_at:new Date(Date.now()-(i%6)*19*86400000).toISOString(),description:`A demonstration project: ${name.replaceAll('-',' ')}`,fork:false}));
 const rng=seeded(20261031),now=Date.now(),events=[];
 for(let day=89;day>=0;day--){let n= Math.max(0,Math.round(rng()*7+(day<20?3:0)-1));for(let j=0;j<n;j++)events.push({id:`demo-${day}-${j}`,type:['PushEvent','PushEvent','PushEvent','PullRequestEvent','CreateEvent'][Math.floor(rng()*5)],created_at:new Date(now-day*86400000+Math.floor(rng()*8)*3600000).toISOString(),repo:{name:`demo/${names[Math.floor(rng()*names.length)]}`},payload:{size:1+Math.floor(rng()*4),action:'opened'}});}
 return transform({username:'demo',demo:true,repos,events,source:'Synthetic demo data — not GitHub activity'});
}

/** Repository height, footprint and activity share a single deterministic mapping. */
export function buildingMetrics(repo,repos,options={},now=Date.now()){
 const maxHeight=clamp(Number(options.maxHeight)||22,8,36);
 const starInfluence=clamp(Number(options.starInfluence??100),0,150)/100;
 const activeDays=clamp(Number(options.activeDays)||30,7,180);
 const maxSize=Math.max(1,...repos.map(r=>Math.max(0,r.size||0)));
 const maxStars=Math.max(1,...repos.map(r=>Math.max(0,r.stars||0)));
 const height=4+(maxHeight-4)*Math.sqrt(Math.max(0,repo.size||0)/maxSize);
 const ratio=Math.log1p(Math.max(0,repo.stars||0))/Math.log1p(maxStars);
 const footprint=2.4+1.75*starInfluence*ratio;
 const lastPush=repo.updatedAt?Date.parse(repo.updatedAt):NaN;
 const ageDays=Number.isFinite(lastPush)?Math.max(0,(now-lastPush)/86400000):null;
 const active=ageDays!==null&&ageDays<=activeDays;
 return {height,width:footprint,depth:footprint,active,ageDays,activityColor:active?'#64caa0':'#7aaee5',sizeRatio:(repo.size||0)/maxSize,starRatio:ratio};
}
