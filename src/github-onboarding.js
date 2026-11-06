import {CityRenderer} from './renderer.js';
import {transform,makeDemo} from './model.js';
import {parseGitHubOwner,summarizeEvidence,scanManifestText} from './github-onboarding-data.js';
import './github-onboarding.css';
const api='https://api.github.com';
const $=id=>document.getElementById(id);
// The seven-step journey starts at the secure portal's sign-in. Override with VITE_CODEVERSE_API.
const portalBase=String(import.meta.env?.VITE_CODEVERSE_API||'http://localhost:8000').replace(/\/+$/,'');
document.querySelectorAll('[data-portal]').forEach(a=>{a.href=portalBase+'/start'});
let city=null,activeAbort=null,lastData=null,analysis=[];
const headers={'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'};
function status(message,error=false){$('status').textContent=message;$('status').classList.toggle('error',error)}
async function github(path,signal){const r=await fetch(api+path,{signal,headers});if(!r.ok){if([403,429].includes(r.status))throw Error('GitHub API rate limit reached. Retry later; unauthenticated calls are limited.');if(r.status===404)throw Error('GitHub account not found or file not public.');throw Error('GitHub returned HTTP '+r.status);}return r.json()}
function renderEvidence(){const target=$('evidence');target.replaceChildren();$('technologyCount').textContent=String(analysis.length);
  if(!analysis.length){target.textContent='No technology signal detected in public repository metadata.';return}
  for(const tech of analysis){const card=document.createElement('article');card.className='evidence-card';const heading=document.createElement('div');heading.className='evidence-card-heading';const name=document.createElement('strong');name.textContent=tech.name;const badge=document.createElement('span');badge.className=tech.manifestCount?'tag confirmed':'tag';badge.textContent=tech.manifestCount?'Manifest detected':'Metadata only';heading.append(name,badge);
  const desc=document.createElement('p');desc.textContent=tech.manifestCount?`${tech.manifestCount} repo(s) with a manifest signal · ${tech.repositoryCount} total associated`:`${tech.repositoryCount} repo(s) associated · proficiency not verified`;
  const details=document.createElement('details');const summary=document.createElement('summary');summary.textContent='View evidence sources';details.append(summary);
  const list=document.createElement('ul');for(const ref of tech.references){const li=document.createElement('li');li.textContent=`${ref.repo} — ${ref.reference}`;list.append(li)}details.append(list);card.append(heading,desc,details);target.append(card)}
}
function renderRepos(data){const list=$('repos');list.replaceChildren();$('repoCount').textContent=String(data.repos.length);$('languagesCount').textContent=String(data.languages.length);
  if(!data.repos.length){list.textContent='No public repositories were returned. Private repositories cannot be accessed without authorization.';return}
  for(const repo of data.repos){const a=document.createElement('a');a.href=repo.url;a.target='_blank';a.rel='noopener noreferrer';a.className='repo-item';const left=document.createElement('div');const name=document.createElement('b');name.textContent=repo.name;const description=document.createElement('small');description.textContent=repo.description||'No public description';left.append(name,description);const meta=document.createElement('span');meta.textContent=`${repo.language} · ★ ${repo.stars}${repo.fork?' · fork':''}`;a.append(left,meta);list.append(a)}
}
function ensureCity(){if(city)return;try{city=new CityRenderer($('city'),repo=>{const selected=repo?.repo??repo;if(selected?.fullName)$('selectedRepo').textContent=`Selected: ${selected.fullName} · ${selected.language} · ★ ${selected.stars}`;});}catch(error){status(`3D display unavailable (${error.message}). Repository analysis remains accessible below.`,true);}}
async function fetchRepos(owner,signal){const account=await github('/users/'+encodeURIComponent(owner),signal);const endpoint=account.type==='Organization'?'/orgs/':'/users/';let all=[];let truncated=false;
  for(let page=1;page<=3;page++){const batch=await github(`${endpoint}${encodeURIComponent(owner)}/repos?per_page=100&page=${page}&sort=pushed`,signal);if(!Array.isArray(batch))throw Error('Unexpected GitHub API response');all.push(...batch);if(batch.length<100)break;if(page===3)truncated=true}
  return {account,repos:all, truncated};
}
const manifestsToCheck=['package.json','requirements.txt','pyproject.toml','Dockerfile','angular.json','docker-compose.yml','compose.yaml'];
async function scanSmallManifests(data,signal){let scanned=0;const found=[];for(const repo of data.repos.slice(0,8)){
  if(signal.aborted)throw new DOMException('Aborted','AbortError');
  // Request only a few known paths. Each call consumes public API quota.
  for(const path of manifestsToCheck.slice(0,4)){
    if(scanned>=24)break;scanned++;
    const url=`/repos/${repo.fullName}/contents/${path}`;
    try{const result=await github(url,signal);if(result.type!=='file'||result.size>100000||typeof result.content!=='string')continue;
      const decoded=atob(result.content.replace(/\s/g,''));const technologies=scanManifestText(path,decoded);if(technologies.length)found.push({repo:repo.fullName,path,technologies});
    }catch(e){if(e.name==='AbortError'||e.message.includes('rate limit'))throw e; /* 404 = no manifest */}
  }
}return found}
async function start(evt){evt.preventDefault();const owner=parseGitHubOwner($('githubURL').value);if(!owner){status('Enter https://github.com/username or a GitHub username, not a repository URL.',true);$('githubURL').focus();return}
  activeAbort?.abort();activeAbort=new AbortController();const signal=activeAbort.signal;$('generate').disabled=true;status('Loading public repositories from GitHub…');
  try{const result=await fetchRepos(owner,signal);const d=transform({username:result.account.login,repos:result.repos,events:[],createdAt:new Date().toISOString()});lastData=d;
    $('start').classList.add('compact');$('results').hidden=false;$('accountName').textContent=result.account.login;$('repoCount').textContent=String(d.repos.length);
    $('accountLink').href=result.account.html_url;$('accountLink').textContent=`@${result.account.login} ↗`;
    $('profileName').textContent=result.account.name||result.account.login;
    $('profileDescription').textContent=result.account.bio||'Public GitHub profile';
    ensureCity();city?.build(d);renderRepos(d);analysis=summarizeEvidence(d.repos);renderEvidence();
    status(`Generated up to ${d.repos.length} repository buildings for @${d.username}. ${result.repos.length>d.repos.length?'Only the 64 highest-ranked public repositories are visualized. ':''}${result.truncated?'GitHub results limited to 300 repositories. ':''}GitHub language metadata is not proof of proficiency.`);
    $('scan').disabled=false;$('results').scrollIntoView({behavior:'smooth'});
    const url=new URL(location.href);url.searchParams.set('user',owner);history.replaceState(null,'',url);
  }catch(err){if(err.name!=='AbortError')status(err.message,true)}finally{if(!signal.aborted)$('generate').disabled=false}
}
$('startForm').addEventListener('submit',start);
$('scan').addEventListener('click',async()=>{if(!lastData)return;const controller=new AbortController();$('scan').disabled=true;status('Checking a bounded sample of public manifests…');try{const found=await scanSmallManifests(lastData,controller.signal);analysis=summarizeEvidence(lastData.repos,found);renderEvidence();status(`Scanned up to 8 repositories (max 24 manifest requests). Found ${found.length} manifest signals. No code execution or proficiency assessment occurred.`)}catch(e){status(e.message,true)}finally{$('scan').disabled=false}});
$('reset').addEventListener('click',()=>city?.reset());
const urlOwner=new URLSearchParams(location.search).get('user');if(urlOwner&&parseGitHubOwner(urlOwner)){$('githubURL').value=urlOwner;$('startForm').requestSubmit()}

$('demo')?.addEventListener('click',()=>{activeAbort?.abort();const d=makeDemo();lastData=d;$('start').classList.add('compact');$('results').hidden=false;$('accountName').textContent='DEMO CITY · SIMULATED';$('profileName').textContent='Sample profile';$('profileDescription').textContent='Fictional projects for exploring the city design.';$('accountLink').textContent='Fictional demonstration — no GitHub account';$('accountLink').removeAttribute('href');ensureCity();city?.build(d);renderRepos(d);analysis=summarizeEvidence(d.repos);renderEvidence();$('scan').disabled=true;status('SIMULATED demo data — not public GitHub evidence. Enter a real profile link to load live repositories.');$('results').scrollIntoView({behavior:'smooth'});});
