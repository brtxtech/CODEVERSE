import test from 'node:test';
import assert from 'node:assert/strict';
import {parseGitHubOwner,scanManifestText,summarizeEvidence} from '../src/github-onboarding-data.js';

test('accepts GitHub user link or simple handle',()=>{
  assert.equal(parseGitHubOwner('https://github.com/octocat/'),'octocat');
  assert.equal(parseGitHubOwner('octocat'),'octocat');
  assert.equal(parseGitHubOwner('https://www.github.com/Open5GS'),'Open5GS');
});
test('rejects repository links, malicious hosts and URL tricks',()=>{
 for(const x of ['https://github.com/octocat/hello','https://github.com.evil.test/octocat','http://github.com/octocat','https://github.com/octocat?tab=repositories','-invalid','a/b','https://github.com@evil.com/octocat'])assert.equal(parseGitHubOwner(x),null,x);
});
test('detects Angular from manifests rather than guesswork',()=>{
 const m=JSON.stringify({dependencies:{'@angular/core':'^19.0.0',react:'^19.0.0'}});
 assert.deepEqual(scanManifestText('package.json',m),['Angular','React']);
 assert.deepEqual(scanManifestText('package.json','not-json'),[]);
 assert.deepEqual(scanManifestText('requirements.txt','fastapi==0.100.0\nflask>=3'),['FastAPI','Flask']);
});
test('groups references and never invents proficiency scores',()=>{
 const result=summarizeEvidence([{fullName:'user/app',language:'TypeScript'},{fullName:'user/other',language:'Python'}],[{repo:'user/app',path:'package.json',technologies:['Angular']}]);
 assert.equal(result[0].name,'Angular');assert.equal(result[0].verification,'Dependency/config signal');
 assert.equal(result[0].references[0].reference,'package.json');
 assert.equal(result.find(x=>x.name==='Python').verification,'Language metadata only');
 assert.ok(result.every(x=>!('level' in x)&&!('confidence' in x)));
});
