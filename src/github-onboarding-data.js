/** Browser-only public GitHub evidence. No authentication or private repository access. */
export function parseGitHubOwner(input) {
  const value=String(input??'').trim().replace(/\/+$/,'');
  if (/^[a-z\d-]{1,39}$/i.test(value) && !value.startsWith('-') && !value.endsWith('-')) return value;
  try {
    const u=new URL(value);
    if(!['github.com','www.github.com'].includes(u.hostname.toLowerCase())||u.protocol!=='https:'||u.username||u.password||u.search||u.hash) return null;
    const parts=u.pathname.split('/').filter(Boolean);
    if(parts.length!==1)return null;
    return parseGitHubOwner(parts[0]);
  } catch {return null;}
}
export function summarizeEvidence(repos,manifests=[]) {
  const grouped=new Map();
  const add=(name,repo,kind,reference)=>{
    if(!name||name==='Other'||name==='Unknown')return;
    if(!grouped.has(name))grouped.set(name,{name,repositories:new Set(),manifestRepos:new Set(),references:[]});
    const v=grouped.get(name);v.repositories.add(repo);if(kind==='manifest')v.manifestRepos.add(repo);
    if(v.references.length<12&&!v.references.some(x=>x.repo===repo&&x.reference===reference))v.references.push({repo,reference,kind});
  };
  for(const r of repos) if(r.language)add(r.language,r.fullName||r.full_name||r.name,'language','GitHub primary-language metadata');
  for(const m of manifests)for(const name of m.technologies||[])add(name,m.repo,'manifest',m.path);
  return [...grouped.values()].map(v=>({name:v.name,repositoryCount:v.repositories.size,manifestCount:v.manifestRepos.size,verification:v.manifestRepos.size?'Dependency/config signal':'Language metadata only',references:v.references})).sort((a,b)=>b.manifestCount-a.manifestCount||b.repositoryCount-a.repositoryCount||a.name.localeCompare(b.name));
}
export function scanManifestText(path,text){
  const matches=new Set();const p=path.toLowerCase();
  if(p.endsWith('package.json')){
    try {const o=JSON.parse(text);const deps={...o.dependencies,...o.devDependencies,...o.peerDependencies};for(const [pkg,name] of [['@angular/core','Angular'],['react','React'],['next','Next.js'],['vue','Vue'],['express','Express'],['nestjs','NestJS'],['@nestjs/core','NestJS'],['typescript','TypeScript'],['vite','Vite']])if(Object.hasOwn(deps,pkg))matches.add(name);}catch{return []}
  } else if(p.endsWith('requirements.txt')||p.endsWith('pyproject.toml')){
    for(const [re,name] of [[/(?:^|\n)\s*fastapi(?:[\[=<>~!\s]|$)/i,'FastAPI'],[/(?:^|\n)\s*django(?:[=<>~!\s]|$)/i,'Django'],[/(?:^|\n)\s*flask(?:[=<>~!\s]|$)/i,'Flask'],[/(?:^|\n)\s*torch(?:[=<>~!\s]|$)/i,'PyTorch'],[/(?:^|\n)\s*transformers(?:[=<>~!\s]|$)/i,'Transformers']])if(re.test(text))matches.add(name);
  } else if(p==='dockerfile'||p.endsWith('/dockerfile'))matches.add('Docker');
  else if(p.endsWith('angular.json'))matches.add('Angular');
  else if(p.endsWith('docker-compose.yml')||p.endsWith('compose.yaml'))matches.add('Docker Compose');
  return [...matches];
}
