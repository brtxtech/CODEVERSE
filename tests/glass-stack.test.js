import test from 'node:test';
import assert from 'node:assert/strict';
import {stackMetrics} from '../src/glass-scene.js';
test('commits and stars grow separate visual dimensions monotonically',()=>{
 let previous=stackMetrics({commits:0,stars:0});
 for(const value of [1,2,5,10,100,1000,10000]){const next=stackMetrics({commits:value,stars:value});assert.ok(next.layers>=previous.layers);assert.ok(next.width>=previous.width);previous=next;}
 assert.equal(stackMetrics({commits:500,stars:0}).layers,stackMetrics({commits:500,stars:5000}).layers);
 assert.equal(stackMetrics({commits:0,stars:50}).width,stackMetrics({commits:500,stars:50}).width);
});
test('missing commit metrics remain distinguishable from empty repositories',()=>{assert.equal(stackMetrics({commits:null}).unknown,true);assert.equal(stackMetrics({commits:0}).unknown,false);});
