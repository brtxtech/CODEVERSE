/** Public GitHub signals; this module never asserts a project's completion or root cause. */
export function safeRepository(value) {
  if (!/^[A-Za-z0-9_.-]{1,100}\/[A-Za-z0-9_.-]{1,100}$/.test(value || '')) throw new Error('Use owner/repository (public GitHub repository).');
  return value;
}
export function releaseDraft(release) {
  const title=String(release?.name || release?.tag_name || 'New release');
  const url=String(release?.html_url || '');
  if (!/^https:\/\/github\.com\//.test(url)) throw new Error('Invalid public GitHub release URL');
  return { title, url, status:'REVIEW REQUIRED', text:`A new release is available: ${title}\n\nRead the release notes: ${url}\n\n#OpenSource #SoftwareEngineering` };
}
export function summarizeRun(run) {
  if (run?.conclusion !== 'failure') return null;
  return {title:String(run.name || 'Workflow failed'), url:String(run.html_url || ''), date:run.updated_at || run.created_at || null, severity:'High', source:'GitHub Actions', detail:'Failed workflow run; check GitHub logs for cause.'};
}
export function summarizeIssue(issue) {
  if (!issue || issue.pull_request || issue.state !== 'open') return null;
  if (!(issue.labels || []).some(l => /^(bug|incident|regression|critical|security)$/i.test(typeof l==='string'?l:l.name||''))) return null;
  return {title:String(issue.title || 'Reported issue'),url:String(issue.html_url || ''),date:issue.updated_at || issue.created_at || null,severity:(issue.labels||[]).some(l=>/^(critical|security)$/i.test(l.name||l))?'High':'Review',source:'GitHub issue',detail:'Label-based issue signal, not an independently verified incident.'};
}
export async function fetchOperations(repo,fetcher=fetch){
  const target=safeRepository(repo);
  const base=`https://api.github.com/repos/${target}`;
  const headers={Accept:'application/vnd.github+json'};
  const [releases,runs,issues]=await Promise.all([
    fetcher(`${base}/releases?per_page=8`,{headers}),
    fetcher(`${base}/actions/runs?per_page=35`,{headers}),
    fetcher(`${base}/issues?state=open&per_page=80`,{headers})
  ]);
  const results=await Promise.all([releases,runs,issues].map(async r=>r.ok?r.json():null));
  if(results.every(x=>!x))throw new Error('Could not fetch this public repository. Check its name, public access and GitHub API limits.');
  const [rel,run,issue]=results;
  return {repo:target, partial:results.some(x=>!x), drafts:Array.isArray(rel)?rel.flatMap(r=>{try{return [releaseDraft(r)];}catch{return [];}}):[],
    incidents:[...(Array.isArray(run?.workflow_runs)?run.workflow_runs.map(summarizeRun):[]),...(Array.isArray(issue)?issue.map(summarizeIssue):[])].filter(Boolean).sort((a,b)=>new Date(b.date||0)-new Date(a.date||0)).slice(0,30)};
}
