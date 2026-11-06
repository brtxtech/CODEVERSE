import taxonomy from '../data/technology-taxonomy.json';
export const CATALOG=taxonomy;
const index=new Map(taxonomy.technologies.map(t=>[t.name.toLowerCase(),t]));
export const techInfo=name=>index.get(String(name).toLowerCase())||{name,category:'Other',landmark:'tower',color:'#a4b7c5',detection:{kind:'unverified'}};
export const DEMO_CAMPUSES=[
 {id:'ai-assistant',title:'AI Assistant Campus',description:'An illustrative full-stack assistant with retrieval-augmented generation, a web interface and containerized services.',demo:true,technologies:['Angular','Flask','MongoDB','Docker','Transformer','RAG'],relations:[['Angular','Flask','REST API'],['Flask','MongoDB','storage'],['Flask','Transformer','inference'],['Transformer','RAG','retrieval'],['Docker','Flask','runtime']]},
 {id:'vision-lab',title:'Computer Vision Lab',description:'A sample image recognition workflow, from model training to an interactive dashboard.',demo:true,technologies:['React','FastAPI','PyTorch','OpenCV','Docker','PostgreSQL'],relations:[['React','FastAPI','HTTP'],['FastAPI','PyTorch','inference'],['PyTorch','OpenCV','vision pipeline'],['FastAPI','PostgreSQL','results']]},
 {id:'cloud-platform',title:'Cloud Platform Campus',description:'An illustrative deployment architecture with services, orchestration and monitoring.',demo:true,technologies:['Next.js','NestJS','Redis','PostgreSQL','Docker','Kubernetes'],relations:[['Next.js','NestJS','API'],['NestJS','Redis','cache'],['NestJS','PostgreSQL','persistence'],['Docker','Kubernetes','deployment']]}
];
const normal=n=>String(n||'').toLowerCase();
export function buildRepoCampus(repo){
 const technologies=[repo.language||'Other',...new Set(repo.technologies||[])].filter(Boolean);
 return {id:repo.fullName||repo.name,title:repo.name,description:repo.description||'Public GitHub repository. Select a structure to inspect detected technology evidence.',demo:false,url:repo.url,technologies:[...new Set(technologies)],relations:[],evidence:repo.evidence||{},scanned:!!repo.scanned};
}
export function buildCampuses(data){return data.demo?DEMO_CAMPUSES:data.repos.map(buildRepoCampus);}
const PACKAGES={
 'angular':'Angular','@angular/core':'Angular','react':'React','next':'Next.js','vue':'Vue','nuxt':'Nuxt','svelte':'Svelte','@sveltejs/kit':'SvelteKit','three':'Three.js','@react-three/fiber':'React Three Fiber','vite':'Vite','tailwindcss':'Tailwind CSS','express':'Express.js','@nestjs/core':'NestJS','fastify':'Fastify','mongoose':'MongoDB','mongodb':'MongoDB','pg':'PostgreSQL','postgres':'PostgreSQL','redis':'Redis','ioredis':'Redis','graphql':'GraphQL','ws':'WebSocket','socket.io':'WebSocket','jsonwebtoken':'JWT','playwright':'Playwright','@playwright/test':'Playwright','vitest':'Vitest','jest':'Jest','flask':'Flask','django':'Django','fastapi':'FastAPI','torch':'PyTorch','pytorch':'PyTorch','tensorflow':'TensorFlow','keras':'Keras','transformers':'Hugging Face','langchain':'LangChain','langgraph':'LangGraph','llama-index':'LlamaIndex','llama_index':'LlamaIndex','scikit-learn':'Scikit-learn','sklearn':'Scikit-learn','numpy':'NumPy','pandas':'Pandas','opencv-python':'OpenCV','cv2':'OpenCV','ultralytics':'YOLO','xgboost':'XGBoost','lightgbm':'LightGBM','jax':'JAX','pyspark':'Apache Spark','apache-airflow':'Airflow','pytest':'Pytest','sqlalchemy':'SQLAlchemy','optuna':'Optuna','mlflow':'MLflow','qdrant-client':'Qdrant','chromadb':'Chroma','pymongo':'MongoDB'
};
export function detectManifest(path,body){
 const output=[]; const add=(name,evidence)=>{if(!output.some(x=>x.name===name))output.push({name,evidence,kind:'manifest'});};
 const lower=path.toLowerCase();
 if(lower.endsWith('dockerfile')||lower.includes('/dockerfile'))add('Docker',path);
 if(/(^|\/)(compose\.ya?ml|docker-compose\.ya?ml)$/.test(lower))add('Docker Compose',path);
 if(lower.startsWith('.github/workflows/'))add('GitHub Actions',path);
 if(lower.endsWith('angular.json'))add('Angular',path);
 if(lower.endsWith('vite.config.js')||lower.endsWith('vite.config.ts'))add('Vite',path);
 if(lower.endsWith('package.json')){
  try{const pkg=JSON.parse(body);const deps={...pkg.dependencies,...pkg.devDependencies};for(const key of Object.keys(deps))if(PACKAGES[normal(key)])add(PACKAGES[normal(key)],`${path}: ${key}`);}catch{}
 }
 if(/(requirements[^/]*\.txt|pyproject\.toml|pipfile|poetry\.lock|cargo\.toml|go\.mod)$/.test(lower)){
  const lines=body.split('\n');for(let line of lines){line=line.trim().toLowerCase();if(!line||line.startsWith('#'))continue;for(const [pkg,name] of Object.entries(PACKAGES)){if(new RegExp(`(^|["'\\s])${pkg.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')}(?=[\\s=<>!~;"'\\[]|$)`).test(line))add(name,`${path}: ${pkg}`);}}
 }
 return output;
}
export function mergeDetections(repo,detections){const info={...(repo.evidence||{})};for(const d of detections)info[d.name]=d.evidence;return {...repo,technologies:[...new Set([...(repo.technologies||[]),...detections.map(d=>d.name)])],evidence:info,scanned:true};}
export async function scanRepo(repo,signal){
 if(!repo.fullName||repo.url==='#')throw Error('No public GitHub repository to scan.');
 const headers={Accept:'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'};
 const route=`https://api.github.com/repos/${repo.fullName}`;
 const meta=await fetch(route,{signal,headers});if(!meta.ok)throw Error(`GitHub metadata request failed (${meta.status}).`);
 const json=await meta.json();const branch=encodeURIComponent(json.default_branch||'main');
 const treeRes=await fetch(`${route}/git/trees/${branch}?recursive=1`,{signal,headers});if(!treeRes.ok)throw Error(`GitHub tree request failed (${treeRes.status}).`);
 const tree=await treeRes.json();
 const names=(tree.tree||[]).filter(x=>x.type==='blob').map(x=>x.path);
 const target=names.filter(p=>/(^|\/)(package\.json|requirements(?:-[\w]+)?\.txt|pyproject\.toml|pipfile|cargo\.toml|go\.mod|dockerfile|compose\.ya?ml|docker-compose\.ya?ml|angular\.json|vite\.config\.(js|ts))$/i.test(p)&&p.split('/').length<=3).slice(0,12);
 const workflow=names.find(p=>p.startsWith('.github/workflows/')&&/\.ya?ml$/.test(p));
 const detections=[];if(workflow)detections.push(...detectManifest(workflow,''));
 for(const p of target){if(/(?:dockerfile|angular\.json|vite\.config|compose\.ya?ml)/i.test(p)){detections.push(...detectManifest(p,''));continue;}
  const r=await fetch(`https://raw.githubusercontent.com/${repo.fullName}/${encodeURIComponent(json.default_branch||'main')}/${p.split('/').map(encodeURIComponent).join('/')}`,{signal});if(!r.ok)continue;
  const body=(await r.text()).slice(0,180000);detections.push(...detectManifest(p,body));
 }
 return mergeDetections(repo,detections);
}
