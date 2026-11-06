import {mkdir,writeFile} from 'node:fs/promises';
import {transform,sanitizeUsername} from '../src/model.js';
const username=sanitizeUsername(process.env.CODEVERSE_USERNAME||'');
if(!username){console.log('No CODEVERSE_USERNAME configured: app runs in demo mode until visitor enters username.');process.exit(0);}
const headers={Accept:'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'};
if(process.env.GITHUB_TOKEN)headers.Authorization=`Bearer ${process.env.GITHUB_TOKEN}`;
async function get(path){const r=await fetch(`https://api.github.com${path}`,{headers});if(!r.ok)throw Error(`GitHub ${r.status}: ${path}`);return r.json();}
let repos=[],events=[];
for(let page=1;page<=3;page++){const part=await get(`/users/${username}/repos?per_page=100&page=${page}&sort=pushed&type=owner`);repos.push(...part);if(part.length<100)break;}
for(let page=1;page<=3;page++){const part=await get(`/users/${username}/events/public?per_page=100&page=${page}`);events.push(...part);if(part.length<100)break;}
const result={username,repos,events,createdAt:new Date().toISOString()};await mkdir('public',{recursive:true});await writeFile('public/data.json',JSON.stringify(result));console.log(`Cached ${repos.length} repos and ${events.length} recent public events for ${username}`);
