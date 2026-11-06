import * as THREE from 'three';
import {clamp,hash,languageColor,seeded,buildingMetrics} from './model.js';
import {techInfo} from './campus.js';
const c=(hex)=>new THREE.Color(hex);
export class CityRenderer {
 constructor(canvas, onSelect){
  this.canvas=canvas;this.onSelect=onSelect;this.scene=new THREE.Scene();this.scene.background=c(0x0c1727);this.scene.fog=new THREE.FogExp2(0x0c1727,.008);
  this.renderer=new THREE.WebGLRenderer({canvas,antialias:true,alpha:false,preserveDrawingBuffer:true,powerPreference:'high-performance'});this.renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));this.renderer.outputColorSpace=THREE.SRGBColorSpace;this.renderer.toneMapping=THREE.ACESFilmicToneMapping;this.renderer.toneMappingExposure=1.25;
  this.camera=new THREE.PerspectiveCamera(38,1,.1,400);this.radius=86;this.azimuth=.72;this.elevation=.78;this.target=new THREE.Vector3(0,2.8,0);this._syncCamera();
  this.scene.add(new THREE.HemisphereLight(0xc9eaf8,0x283546,2.8));const sun=new THREE.DirectionalLight(0xffdcaa,3.5);sun.position.set(-24,48,24);this.scene.add(sun);const fill=new THREE.DirectionalLight(0x7edbd7,1.4);fill.position.set(25,25,-18);this.scene.add(fill);this.sun=sun;
  this.city=new THREE.Group();this.scene.add(this.city);this.buildingMeshes=[];this.animated=[];this.tracers=[];this.clock=new THREE.Clock();this.energy=80;this.progress=1;this.reduceMotion=window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches??false;
  this.raycaster=new THREE.Raycaster();this.pointer=new THREE.Vector2();this.drag={active:false,moved:false,x:0,y:0};
  this._bind();this.resize();this._resizeObserver=new ResizeObserver(()=>this.resize());this._resizeObserver.observe(canvas.parentElement);this._frame();
 }
 _syncCamera(){this.camera.position.set(this.target.x+this.radius*Math.sin(this.azimuth)*Math.cos(this.elevation),this.target.y+this.radius*Math.sin(this.elevation),this.target.z+this.radius*Math.cos(this.azimuth)*Math.cos(this.elevation));this.camera.lookAt(this.target);}
 _bind(){const el=this.canvas;el.addEventListener('pointerdown',e=>{this.drag={active:true,moved:false,x:e.clientX,y:e.clientY};el.setPointerCapture(e.pointerId);});el.addEventListener('pointermove',e=>{if(!this.drag.active)return;const dx=e.clientX-this.drag.x,dy=e.clientY-this.drag.y;if(Math.abs(dx)+Math.abs(dy)>2)this.drag.moved=true;this.azimuth-=dx*.006;this.elevation=clamp(this.elevation+dy*.005,.2,1.4);this.drag.x=e.clientX;this.drag.y=e.clientY;this._syncCamera();});el.addEventListener('pointerup',e=>{if(!this.drag.moved)this.pick(e);this.drag.active=false;});el.addEventListener('wheel',e=>{e.preventDefault();this.radius=clamp(this.radius+e.deltaY*.07,28,160);this._syncCamera();},{passive:false});}
 pick(e){const rect=this.canvas.getBoundingClientRect();this.pointer.set(((e.clientX-rect.left)/rect.width)*2-1,-((e.clientY-rect.top)/rect.height)*2+1);this.raycaster.setFromCamera(this.pointer,this.camera);const hits=this.raycaster.intersectObjects(this.buildingMeshes,false);this.onSelect?.(hits.length?hits[0].object.userData.repo:null);}
 resize(){const w=Math.max(1,this.canvas.clientWidth),h=Math.max(1,this.canvas.clientHeight);this.renderer.setSize(w,h,false);this.camera.aspect=w/h;this.camera.updateProjectionMatrix();}
 reset(){this.radius=86;this.azimuth=.72;this.elevation=.78;this._syncCamera();}
 geometry(w,h,d){return new THREE.BoxGeometry(w,h,d);}
 mat(hex,opts={}){return new THREE.MeshStandardMaterial({color:hex,roughness:.58,metalness:.52,...opts});}
 box(w,h,d,color,x,y,z,opts){const o=new THREE.Mesh(this.geometry(w,h,d),this.mat(color,opts));o.position.set(x,y,z);this.city.add(o);return o;}
 clear(){while(this.city.children.length){const obj=this.city.children[0];this.city.remove(obj);obj.traverse?.(v=>{v.geometry?.dispose();if(Array.isArray(v.material))v.material.forEach(m=>m.dispose());else v.material?.dispose();});}this.buildingMeshes=[];this.animated=[];this.tracers=[];}
 build(data,options=this.options||{}){
  this.options=options;this.mode='city';this.radius=86;this.target.set(0,2.8,0);this._syncCamera();this.data=data;this.clear();const rng=seeded(hash(data.username));
  const base=this.mat(0x35465a,{roughness:.78,metalness:.08});
  const platform=new THREE.Mesh(new THREE.CylinderGeometry(36,37,2.2,8,1),base);
  platform.rotation.y=Math.PI/8;platform.scale.z=.94;platform.position.y=-1.25;this.city.add(platform);
  const grass=new THREE.Mesh(new THREE.CylinderGeometry(35.65,35.9,.35,8,1),this.mat(0x537c72,{roughness:.95,metalness:0}));
  grass.rotation.y=Math.PI/8;grass.scale.z=.94;grass.position.y=0;this.city.add(grass);
  const underglow=new THREE.Mesh(new THREE.TorusGeometry(35.3,.14,6,8),new THREE.MeshBasicMaterial({color:0x76b6aa,transparent:true,opacity:.42}));
  underglow.rotation.x=Math.PI/2;underglow.rotation.z=Math.PI/8;underglow.position.y=-.02;underglow.scale.y=.94;this.city.add(underglow);
  const roadMat=this.mat(0x435e65,{roughness:.96,metalness:0});
  const pathMat=this.mat(0x7da097,{roughness:1,metalness:0});
  // Architectural boulevard: clean graphic grid without a distracting flood of luminous lines.
  for(let i=-3;i<=3;i++){
   const coord=i*7.3;
   const roadH=new THREE.Mesh(this.geometry(49,.045,1.25),roadMat);roadH.position.set(0,.21,coord);this.city.add(roadH);
   const roadV=new THREE.Mesh(this.geometry(1.25,.045,49),roadMat);roadV.position.set(coord,.22,0);this.city.add(roadV);
   for(let j=-3;j<=3;j++){
    const line=new THREE.Mesh(this.geometry(.65,.012,.075),pathMat);line.position.set(j*7.3+2.6,.247,coord);this.city.add(line);
   }
  }
  const spots=[];
  for(let i=-3;i<=2;i++)for(let j=-3;j<=2;j++){
   const x=i*7.3+3.65,z=j*7.3+3.65;
   if(Math.hypot(x,z)<29)spots.push({x,z,d:Math.hypot(x,z)});
  }
  spots.sort((a,b)=>a.d-b.d||hash(`${a.x},${a.z}`)-hash(`${b.x},${b.z}`));
  const repos=data.repos.slice(0,spots.length);
  const facadeColors=[0xf3dbc3,0xbfd4d0,0xc7cadd,0xd7cbbd,0xa9c6be,0xe0d1ca];
  const makeWindows=(x,z,w,d,h,color,kind,phase)=>{
   const material=new THREE.MeshStandardMaterial({color:0xffe6bd,emissive:0xffb879,emissiveIntensity:.46,roughness:.55});
   const rows=Math.max(2,Math.min(12,Math.floor(h/1.35))),cols=Math.max(2,Math.floor(w/1.1)),sideCols=Math.max(2,Math.floor(d/1.1));
   const placements=[];
   for(let side of [-1,1]){
    for(let row=0;row<rows;row++)for(let col=0;col<cols;col++){
     if((row*7+col*11+phase)%9===0)continue;
     placements.push([x-w/2+(col+.5)*w/cols,.9+row*(h-.9)/rows,z+side*(d/2+.06),0]);
    }
    for(let row=0;row<rows;row++)for(let col=0;col<sideCols;col++){
     if((row*5+col*7+phase)%9===0)continue;
     placements.push([x+side*(w/2+.06),.9+row*(h-.9)/rows,z-d/2+(col+.5)*d/sideCols,Math.PI/2]);
    }
   }
   if(!placements.length)return;
   const group=new THREE.InstancedMesh(new THREE.BoxGeometry(.4,.48,.06),material,placements.length);
   const dummy=new THREE.Object3D();
   placements.forEach(([px,py,pz,rot],i)=>{dummy.position.set(px,py,pz);dummy.rotation.set(0,rot,0);dummy.updateMatrix();group.setMatrixAt(i,dummy.matrix);});
   group.instanceMatrix.needsUpdate=true;group.frustumCulled=false;this.city.add(group);
  };
  repos.forEach((repo,i)=>{
   const spot=spots[i],color=languageColor(repo.language);
   const metrics=buildingMetrics(repo,repos,this.options);
   const h=metrics.height,w=metrics.width,d=metrics.depth;
   repo.visualMetrics=metrics;
   // Tiny plinth and rounded-looking tiered architecture; three silhouettes avoid clone buildings.
   this.box(w+.75,.25,d+.75,0xb5c6b7,spot.x,.42,spot.z,{roughness:.93,metalness:0});
   const variant=i%3;
   const shellColor=new THREE.Color(metrics.activityColor).lerp(new THREE.Color(facadeColors[(hash(repo.name)+i)%facadeColors.length]),.23);
   const main=this.box(w,h,d,shellColor,spot.x,h/2+.56,spot.z,{metalness:.07,roughness:.78});
   main.userData.repo=repo;this.buildingMeshes.push(main);
   if(variant===0){
    this.box(w+.28,.25,d+.28,0xe7e5dd,spot.x,h+.68,spot.z,{roughness:.68,metalness:.02});
    this.box(w*.53,1.10,d*.56,0x819da2,spot.x,h+1.36,spot.z,{roughness:.65,metalness:.16});
   }else if(variant===1){
    this.box(w+.35,.18,d+.35,0x718e8d,spot.x,h+.66,spot.z);
    this.box(w*.35,.85,d*.35,0xf3d1a8,spot.x,h+1.17,spot.z);
   }else{
    for(let level=1;level<4;level++){
     const slab=this.box(w+.35,.13,d+.35,0xf1ebdd,spot.x,.56+(h/4)*level,spot.z,{metalness:0,roughness:.75});
     slab.userData.repo=repo;
    }
    this.box(w+.18,.16,d+.18,0x8fa9a2,spot.x,h+.65,spot.z);
   }
   makeWindows(spot.x,spot.z,w,d,h,color,variant,hash(repo.name)%9);
   // Accent is a restrained language-colored crown, not a neon outline on every edge.
   const cap=this.box(w*.67,.13,d*.67,color,spot.x,h+.91,spot.z,{emissive:color,emissiveIntensity:.1,metalness:.16,roughness:.55});
   const beacon=new THREE.Mesh(new THREE.SphereGeometry(.13,10,8),new THREE.MeshBasicMaterial({color:0xffebc2}));
   beacon.position.set(spot.x,h+1.18,spot.z);this.city.add(beacon);this.animated.push({obj:beacon,type:'beacon',phase:rng()*6});
  });
  const leafMaterials=[this.mat(0x83af92,{roughness:1,metalness:0}),this.mat(0x9bb9a5,{roughness:1,metalness:0}),this.mat(0x6d9f95,{roughness:1,metalness:0})];
  const canopyGeo=new THREE.IcosahedronGeometry(.82,1),trunkGeo=new THREE.CylinderGeometry(.12,.16,1.1,6);
  const trunkMat=this.mat(0x937c70,{roughness:1,metalness:0});
  const addTree=(x,z,scale=1)=>{
   const trunk=new THREE.Mesh(trunkGeo,trunkMat);trunk.position.set(x,.87,z);trunk.scale.setScalar(scale);this.city.add(trunk);
   const crown=new THREE.Mesh(canopyGeo,leafMaterials[Math.floor(rng()*leafMaterials.length)]);
   crown.position.set(x,1.86*scale,z);crown.scale.set(.85*scale,1.18*scale,.86*scale);this.city.add(crown);
   this.animated.push({obj:crown,type:'tree',phase:rng()*6,base:crown.scale.clone()});
  };
  // Empty plots become parks instead of fictional repos.
  spots.slice(repos.length).forEach((spot,i)=>{
   this.box(4.95,.10,4.9,0x729b85,spot.x,.35,spot.z,{roughness:1,metalness:0});
   if(i%3===0){this.box(3.6,.03,.62,0xb2beac,spot.x,.43,spot.z);}
   for(let t=0;t<3;t++){addTree(spot.x+(rng()-.5)*3.5,spot.z+(rng()-.5)*3.5,.7+rng()*.32);}
  });
  // A little soft landscaping between blocks keeps the city readable at a glance.
  for(let i=0;i<24;i++){
   const a=rng()*Math.PI*2,r=25.2+rng()*2.1;
   addTree(Math.cos(a)*r,Math.sin(a)*r,.55+rng()*.32);
  }
  // Tiny warm moving vehicles: meaningful activity, rather than a particle storm.
  const carGeo=new THREE.BoxGeometry(.65,.22,.33);
  const carMat=[0xffd2a1,0xbddedd,0xf1e7d5].map(x=>new THREE.MeshStandardMaterial({color:x,emissive:x,emissiveIntensity:.26,roughness:.4}));
  for(let i=0;i<16;i++){
   const obj=new THREE.Mesh(carGeo,carMat[i%carMat.length]);this.city.add(obj);
   this.tracers.push({obj,seed:rng(),offset:rng()*Math.PI*2,axis:i%2,lane:(i%6-2.5)*7.3});
  }
  // Halo around the collectible diorama.
  const shadow=new THREE.Mesh(new THREE.CircleGeometry(43,64),new THREE.MeshBasicMaterial({color:0x12273a,transparent:true,opacity:.25}));
  shadow.rotation.x=-Math.PI/2;shadow.position.y=-2.55;this.city.add(shadow);
  this.setProgress(this.progress,this.energy);
 }

 buildCampus(campus){
  this.mode='campus';this.campus=campus;this.clear();
  const techs=campus.technologies.slice(0,14),n=techs.length,rng=seeded(hash(campus.id));
  this.radius= n>9?60:46;this.target.set(0,2.5,0);this._syncCamera();
  const base=new THREE.Mesh(new THREE.CylinderGeometry(19,20,1.55,8,1),this.mat(0x3b535a,{roughness:.9,metalness:0}));base.position.y=-.83;base.rotation.y=Math.PI/8;this.city.add(base);
  const ground=new THREE.Mesh(new THREE.CylinderGeometry(18.7,18.9,.15,8,1),this.mat(0x76938b,{roughness:1,metalness:0}));ground.rotation.y=Math.PI/8;ground.position.y=0;this.city.add(ground);
  const road=new THREE.Mesh(new THREE.RingGeometry(11.2,12.2,64),this.mat(0xc2c8b8,{roughness:1,metalness:0}));road.rotation.x=-Math.PI/2;road.position.y=.115;this.city.add(road);
  const pos=new Map();techs.forEach((name,i)=>{const a=-Math.PI/2+i*Math.PI*2/Math.max(n,1);const ring=n>8&&i%2?12.4:8.6;pos.set(name,{x:Math.cos(a)*ring,z:Math.sin(a)*ring});});
  const linkMat=new THREE.LineBasicMaterial({color:0xf0d5a4,transparent:true,opacity:.82});
  campus.relations?.forEach(([from,to])=>{const a=pos.get(from),b=pos.get(to);if(!a||!b)return;const points=[new THREE.Vector3(a.x,.25,a.z),new THREE.Vector3((a.x+b.x)/2,.28,(a.z+b.z)/2),new THREE.Vector3(b.x,.25,b.z)];const geometry=new THREE.BufferGeometry().setFromPoints(points);this.city.add(new THREE.Line(geometry,linkMat.clone()));});
  const sign=(name,x,z)=>{const cv=document.createElement('canvas');cv.width=512;cv.height=128;const ctx=cv.getContext('2d');ctx.fillStyle='rgba(19,33,45,.9)';ctx.beginPath();ctx.roundRect(3,6,506,116,24);ctx.fill();ctx.font='bold 43px sans-serif';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillStyle='#fff6e7';ctx.fillText(name.length>20?name.slice(0,18)+'…':name,256,64,476);const tex=new THREE.CanvasTexture(cv);tex.colorSpace=THREE.SRGBColorSpace;const sprite=new THREE.Sprite(new THREE.SpriteMaterial({map:tex,transparent:true,depthWrite:false}));sprite.position.set(x,1.05,z+2.65);sprite.scale.set(5.7,1.43,1);this.city.add(sprite);};
  techs.forEach((name,i)=>{
   const info=techInfo(name),spot=pos.get(name),color=new THREE.Color(info.color||'#adb9c6');
   const h=3.5+(hash(name)%55)/20,w=2.1,d=2.15;
   const plinth=this.box(4,.24,4,0xc2c9ba,spot.x,.24,spot.z,{roughness:.9,metalness:0});
   const main=this.box(w,h,d,color,spot.x,.45+h/2,spot.z,{roughness:.48,metalness:.13});
   main.userData.repo={tech:name,category:info.category,landmark:info.landmark,detection:campus.evidence?.[name]||null,campus:campus.title};this.buildingMeshes.push(main);
   const roof=this.box(2.65,.22,2.65,0xe7e4d7,spot.x,.65+h,spot.z,{roughness:.7,metalness:0});roof.userData.repo=main.userData.repo;this.buildingMeshes.push(roof);
   const shape=info.landmark;
   if(['prism','v','bolt','neural','observatory','lens'].includes(shape)){
    const top=new THREE.Mesh(new THREE.ConeGeometry(shape==='observatory'?1.25:1.05,shape==='prism'?2.5:1.5,shape==='prism'?4:shape==='v'?3:8),this.mat(color,{metalness:.3,roughness:.36}));top.position.set(spot.x,h+1.48,spot.z);top.rotation.y=i*.38;top.userData.repo=main.userData.repo;this.city.add(top);this.buildingMeshes.push(top);
   }else if(['archive','stack','container','library','layers'].includes(shape)){
    for(let j=0;j<3;j++){const layer=new THREE.Mesh(new THREE.CylinderGeometry(1.17,1.17,.48,shape==='container'?6:12),this.mat(color.clone().lerp(new THREE.Color('#f2dcbf'),j*.16),{roughness:.55}));layer.position.set(spot.x,h+.87+j*.55,spot.z);this.city.add(layer);layer.userData.repo=main.userData.repo;this.buildingMeshes.push(layer);}
   }else if(['bridge','chain','network','orbit','graph'].includes(shape)){
    const ring=new THREE.Mesh(new THREE.TorusGeometry(1.3,.095,8,32),new THREE.MeshStandardMaterial({color:0xf4d7a2,emissive:0x8c6445,emissiveIntensity:.12}));ring.position.set(spot.x,h+1.35,spot.z);ring.rotation.x=.47;this.city.add(ring);this.animated.push({obj:ring,type:'orbit',phase:i});
   }else if(['antenna','relay','scanner','control'].includes(shape)){
    const tower=new THREE.Mesh(new THREE.CylinderGeometry(.1,.32,2,8),this.mat(0xd4e1da));tower.position.set(spot.x,h+1.55,spot.z);this.city.add(tower);
    const ball=new THREE.Mesh(new THREE.SphereGeometry(.3,12,8),new THREE.MeshBasicMaterial({color:0xffdfb2}));ball.position.set(spot.x,h+2.55,spot.z);this.city.add(ball);this.animated.push({obj:ball,type:'beacon',phase:i});
   }else{
    const cap=this.box(1.5,.65,1.5,color.clone().lerp(new THREE.Color('#f7e7c7'),.35),spot.x,h+1.04,spot.z);cap.userData.repo=main.userData.repo;this.buildingMeshes.push(cap);
   }
   for(let row=0;row<3;row++)for(let side of [-1,1]){const window=new THREE.Mesh(new THREE.BoxGeometry(.5,.35,.065),new THREE.MeshBasicMaterial({color:0xf9e5b8}));window.position.set(spot.x-.5+row*.5,1.5,spot.z+side*(d/2+.04));this.city.add(window);}
   sign(name,spot.x,spot.z);
  });
  const tmat=this.mat(0x6e947d,{roughness:1,metalness:0});const trunk=this.mat(0xa68a72,{roughness:1,metalness:0});
  for(let i=0;i<28;i++){const a=rng()*Math.PI*2,r=14+rng()*2.2,x=Math.cos(a)*r,z=Math.sin(a)*r;this.box(.2,.9,.2,0xa68a72,x,.55,z,{roughness:1});const foliage=new THREE.Mesh(new THREE.IcosahedronGeometry(.63,1),tmat);foliage.position.set(x,1.25,z);this.city.add(foliage);this.animated.push({obj:foliage,type:'tree',phase:i});}
  this.progress=1;this.energy=62;
 }
 setProgress(progress,energy=60){this.progress=progress;this.energy=energy;if(this.mode==='campus')return;const n=this.buildingMeshes.length;this.buildingMeshes.forEach((mesh,i)=>{const active=progress>=.999||i<n*(.15+.85*progress);mesh.visible=active;mesh.material.opacity=active?1:.16;mesh.material.transparent=!active;});}
 _frame(){
  this.raf=requestAnimationFrame(()=>this._frame());
  const t=this.clock.getElapsedTime(),rate=this.reduceMotion?0:(.2+this.energy/110);
  this.tracers.forEach((p,i)=>{
   const a=t*rate*(.4+p.seed)+p.offset;
   const q=((a*2.1+30)%48)-24;
   if(p.axis===0){p.obj.position.set(q,.48,p.lane);p.obj.rotation.y=0;}
   else{p.obj.position.set(p.lane,.48,q);p.obj.rotation.y=Math.PI/2;}
   p.obj.visible=this.energy>12;
  });
  this.animated.forEach(a=>{
   if(a.type==='beacon')a.obj.scale.setScalar(this.reduceMotion?1:.94+.09*Math.sin(t*1.2+a.phase));
   else if(a.type==='tree')a.obj.rotation.z=this.reduceMotion?0:.018*Math.sin(t*.55+a.phase);
   else if(a.type==='orbit')a.obj.rotation.y=this.reduceMotion?0:t*.16+a.phase;
  });
  this.renderer.render(this.scene,this.camera);
 }
 capturePNG(){this.renderer.render(this.scene,this.camera);return this.canvas.toDataURL('image/png');}
 async record(duration=12000,onStatus=()=>{}){if(!this.canvas.captureStream||!window.MediaRecorder)throw Error('Video recording is not supported in this browser. Use PNG capture or Chrome.');const mime=['video/mp4;codecs=avc1.42E01E','video/webm;codecs=vp9','video/webm'].find(x=>MediaRecorder.isTypeSupported(x));if(!mime)throw Error('No supported video recording format found.');const stream=this.canvas.captureStream(30),chunks=[],recorder=new MediaRecorder(stream,{mimeType:mime,videoBitsPerSecond:8000000});const oldAz=this.azimuth,oldEl=this.elevation,oldRadius=this.radius;return new Promise((resolve,reject)=>{let start;const rotate=now=>{if(recorder.state==='inactive')return;start??=now;const p=Math.min(1,(now-start)/duration);this.azimuth=oldAz+Math.PI*.55*p;this.elevation=oldEl+.08*Math.sin(p*Math.PI);this._syncCamera();onStatus(Math.ceil((1-p)*duration/1000));if(p<1)requestAnimationFrame(rotate);else recorder.stop();};recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};recorder.onerror=e=>reject(e.error||Error('Recorder failed'));recorder.onstop=()=>{stream.getTracks().forEach(t=>t.stop());this.azimuth=oldAz;this.elevation=oldEl;this.radius=oldRadius;this._syncCamera();resolve({blob:new Blob(chunks,{type:mime}),extension:mime.includes('mp4')?'mp4':'webm'});};recorder.start(250);requestAnimationFrame(rotate);});}
 dispose(){cancelAnimationFrame(this.raf);this._resizeObserver?.disconnect();this.clear();this.renderer.dispose();}
}
