/** Private optional Supabase career pipeline. No credentials are embedded in this repository. */
const $ = id => document.getElementById(id);
const notify = (message, error = false) => { const el = $('careerStatus'); el.textContent = message; el.classList.toggle('error', error); };
const create = (tag, value, target) => { const node = document.createElement(tag); node.textContent = String(value ?? ''); target.append(node); return node; };
export function renderCareerResults(result) {
  if (!result || typeof result !== 'object') throw new Error('Invalid pipeline response');
  const sections = [
    ['jobs', 'careerJobs', r => ({title:r.title, description:`Match ${r.score ?? '—'}% · ${(r.you_have || []).length} matching skills`})],
    ['skills', 'careerSkills', r => ({title:r.skill, description:`Useful for ${(r.needed_by || []).slice(0,3).join(', ')}`})],
    ['repos', 'careerRepos', r => ({title:r.full_name, description:`Match ${r.score ?? '—'} · ★ ${r.stars ?? 0}`, href:/^[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+$/.test(r.full_name || '') ? `https://github.com/${r.full_name}` : null})],
    ['companies', 'careerCompanies', r => ({title:r.name || r.company || 'Company', description:`Match ${r.score ?? '—'}`})],
  ];
  for (const [field, id, format] of sections) {
    const list = $(id); list.replaceChildren(); const rows = Array.isArray(result[field]) ? result[field] : [];
    if (!rows.length) {create('p', 'No matches in your current database.', list); continue;}
    for (const record of rows.slice(0,10)) {
      const article = document.createElement('article'), item = format(record);
      create('b', item.title, article); create('p', item.description, article);
      if (item.href) {const a = create('a', 'VIEW ON GITHUB ↗', article); a.href = item.href; a.target = '_blank'; a.rel = 'noopener noreferrer';}
      list.append(article);
    }
  }
  $('careerResults').hidden = false;
}
export async function initializeCareer() {
  const url = import.meta.env.VITE_SUPABASE_URL, key = import.meta.env.VITE_SUPABASE_ANON_KEY;
  if (!url || !key) {$('careerConnection').textContent = 'NOT CONFIGURED · ARCHITECTURE DEMO ONLY'; notify('To activate CV matching, configure your Supabase project and run the migrations.'); return;}
  let client;
  try {
    const { createClient } = await import('@supabase/supabase-js');
    client = createClient(url, key);
  } catch (error) {notify(`Supabase client unavailable: ${error.message}`, true);return;}
  $('careerConnection').textContent = 'CONNECTED TO SUPABASE'; $('careerWorkspace').hidden = false;
  async function syncAuth() {
    const {data:{user},error} = await client.auth.getUser();
    if (error && error.name !== 'AuthSessionMissingError') notify(error.message,true);
    $('careerSignIn').hidden = Boolean(user); $('careerAuthenticated').hidden = !user;
    $('careerUser').textContent = user ? `Signed in as ${user.email || user.id}` : '';
  }
  client.auth.onAuthStateChange(() => {void syncAuth();}); await syncAuth();
  $('careerSignIn').addEventListener('submit', async e => {
    e.preventDefault(); const email = $('careerEmail').value.trim();
    notify('Sending sign-in link…'); const {error} = await client.auth.signInWithOtp({email, options:{emailRedirectTo:window.location.origin+window.location.pathname}});
    notify(error ? error.message : 'Check your inbox for the sign-in link.',Boolean(error));
  });
  $('careerSignOut').addEventListener('click',async()=>{await client.auth.signOut();$('careerResults').hidden=true;notify('Signed out.');});
  $('careerCvForm').addEventListener('submit',async e=>{
    e.preventDefault(); const button = $('careerRun'); const file = $('careerCv').files?.[0];
    if(!file) return;
    if(file.size>5*1024*1024){notify('CV must be 5 MB or smaller.',true);return;}
    if(!/\.(pdf|txt)$/i.test(file.name)){notify('Only PDF and TXT are supported.',true);return;}
    const {data:{user}} = await client.auth.getUser(); if(!user){notify('Sign in first.',true);return;}
    button.disabled=true; $('careerResults').hidden=true;
    try {
      const extension = file.name.toLowerCase().endsWith('.pdf') ? 'pdf' : 'txt';
      const path = `${user.id}/${crypto.randomUUID()}.${extension}`;
      notify('Uploading CV to private storage…');
      const {error: uploadError} = await client.storage.from('cvs').upload(path,file,{contentType:extension==='pdf'?'application/pdf':'text/plain',upsert:false});
      if(uploadError) throw uploadError;
      notify('Analyzing CV and matching opportunities…');
      const {data,error} = await client.functions.invoke('process-cv',{body:{path,top_jobs:5}});
      if(error) throw error;
      renderCareerResults(data);
      notify('Analysis complete. Results are private to your account.');
    } catch(error){notify(`CV analysis failed: ${error.message}`,true);} finally{button.disabled=false;}
  });
}
