// EXPLICIT SYNTHETIC PREVIEW. Never treated as real readiness evidence.
export function buildSampleFlow(skills,job,offers,location){
 const req=['python','fastapi','postgresql','docker','kubernetes','github-actions'];
 const filtered=offers.filter(o=>!location||o.location.toLowerCase().includes(location.toLowerCase()));
 const out=filtered.map(o=>({...o,match_percent:Math.round(req.filter(s=>skills.includes(s)).length/req.length*100),missing_skills:req.filter(s=>!skills.includes(s))}));
 const gaps=req.filter(s=>!skills.includes(s));
 return {provider_status:'SYNTHETIC_DEMO_NOT_LIVE',nodes:[{id:'cv',label:'CV Skills',input:[{uploaded_document:'Synthetic example'}],output:skills.map(skill=>({skill,evidence_type:'synthetic_cv_claim'}))},
  {id:'profiles',label:'Target job profile',input:[{job_description:job}],output:req.map(skill=>({skill,weight:1,required_level:2}))},
  {id:'offers',label:'Employer offers',input:skills.map(skill=>({skill})),output:out},
  {id:'gaps',label:'Skill gaps',input:req.map(skill=>({skill,match:skills.includes(skill)?.35:0})),output:gaps.map(skill=>({skill,priority:'synthetic'}))},
  {id:'repos',label:'Learning projects',input:gaps.map(skill=>({skill})),output:gaps.map(skill=>({skill,title:'Build and test a '+skill+' project',criteria:['implementation','tests','documentation']}))},
  {id:'readiness',label:'Readiness score',input:req.map(skill=>({skill})),output:[{score:17.5,algorithm_version:'synthetic_demo'}]}],
  summary:{skills_count:skills.length,offers_count:out.length,gaps_count:gaps.length,readiness:{score:17.5}}};}
