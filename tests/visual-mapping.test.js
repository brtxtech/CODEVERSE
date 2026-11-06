import test from 'node:test';
import assert from 'node:assert/strict';
import {buildingMetrics} from '../src/model.js';
const repos=[{name:'large',size:20000,stars:80,updatedAt:'2026-10-30T12:00:00Z'},{name:'small',size:200,stars:0,updatedAt:'2026-01-01T12:00:00Z'}];
const now=Date.parse('2026-10-31T00:00:00Z');
test('largest repo gets maximum height',()=>{const big=buildingMetrics(repos[0],repos,{maxHeight:28},now);const small=buildingMetrics(repos[1],repos,{maxHeight:28},now);assert.equal(big.height,28);assert.ok(small.height<big.height);});
test('stars control width, never height',()=>{const a=buildingMetrics(repos[0],repos,{},now),b=buildingMetrics(repos[1],repos,{},now);assert.ok(a.width>b.width);assert.ok(a.height>b.height);const noStars=buildingMetrics(repos[0],repos,{starInfluence:0},now);assert.equal(noStars.width,2.4);assert.equal(noStars.height,a.height);});
test('color uses last public push activity threshold',()=>{assert.equal(buildingMetrics(repos[0],repos,{activeDays:30},now).activityColor,'#64caa0');assert.equal(buildingMetrics(repos[1],repos,{activeDays:30},now).activityColor,'#7aaee5');});
