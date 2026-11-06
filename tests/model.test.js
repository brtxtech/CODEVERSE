import test from 'node:test';
import assert from 'node:assert/strict';
import {sanitizeUsername,seeded,hash,transform,stateAt,makeDemo,languageColor} from '../src/model.js';
test('validates GitHub usernames',()=>{assert.equal(sanitizeUsername('octocat'),'octocat');for(const x of ['--bad','a--','-bad','bad/name','', 'x'.repeat(40)])assert.equal(sanitizeUsername(x),null);});
test('stable seeded noise',()=>{const a=seeded(hash('x')),b=seeded(hash('x'));for(let i=0;i<20;i++)assert.equal(a(),b());});
test('sanitizes event and repository inputs',()=>{const data=transform({repos:[{name:'test',language:'Rust',size:23},{name:'fork',fork:true}],events:[{id:'1',type:'PushEvent',created_at:'2026-01-01T00:00:00Z',payload:{size:99}}]});assert.equal(data.repos.length,2);assert.ok(data.repos.some(r=>r.fork));assert.equal(data.events[0].score,20);assert.equal(data.languages[0],'Rust');});
test('timeline is monotonic and energy remains bounded',()=>{const data=makeDemo();assert.equal(data.demo,true);const a=stateAt(data,0),b=stateAt(data,.5),c=stateAt(data,1);assert.ok(a.visibleEvents.length<=b.visibleEvents.length);assert.ok(b.visibleEvents.length<=c.visibleEvents.length);assert.ok(c.energy>=0&&c.energy<=100);assert.equal(c.visibleEvents.length,data.events.length);});
test('language colors fall back for unknown languages',()=>{assert.ok(languageColor('Rust')!==languageColor('madeup'));});
