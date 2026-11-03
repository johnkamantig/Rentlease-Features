import test from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';
import { readFileSync } from 'node:fs';
import { inspectResult, MAX_BYTES } from '../gates';

const photos = Array.from({length:24},(_,i)=>({uri:`file:///photo-${i}.jpg`,width:600,height:1200,yawDeg:i*15}));
test('native compatibility patch changes only the NDK version declaration',()=>{
  const original=readFileSync(new URL('../../package/android/build.gradle',import.meta.url),'utf8').replaceAll('\r\n','\n');
  const installed=readFileSync(new URL('../node_modules/@notchip/expo-panoramic-stitcher/android/build.gradle',import.meta.url),'utf8').replaceAll('\r\n','\n');
  assert.equal(installed.replace('  ndkVersion rootProject.ext.ndkVersion // RentLease lab: match app NDK\n',''),original);
});
function result(): any {
  const geometry = { projection:'spherical',selfCheck:true,warpScale:4096/(2*Math.PI),
    compositeWidth:4096,compositeHeight:1024,origin:{x:-2048,y:512},output:{sx:1,sy:1,tx:0,ty:0},cameras:[] };
  const coverage = {spanDeg:360,coveredDeg:360,holes:[],intervals:[{fromDeg:-180,toDeg:180}]};
  return {success:true,width:4096,height:1024,path:'/out.jpg',usedCount:24,usedIndices:photos.map((_,i)=>i),
    strips:[{geometry,coverage}],gaps:[],wrapClosed:true,wrapClosure:{closureErrorDeg:0,pairs:[
      {photoIndex:0,azimuthDeg:0,duplicateAzimuthDeg:0},{photoIndex:1,azimuthDeg:15,duplicateAzimuthDeg:15}]},
    geometry,warpModeUsed:'spherical',fellBackToCylindrical:false};
}
test('even plausible complete diagnostics cannot certify real 360 or calibrated viewer metadata',()=>{
  const gate=inspectResult(result(),photos,100000);
  assert.equal(gate.diagnosticPrerequisitesPass,true);
  assert.equal(gate.accepted360,false); assert.equal(gate.pannellumReady,false);
  assert.equal(gate.fittedAngles!.vaov,90); assert.equal(gate.fittedAngles!.vOffset,0);
});
for(const [name,mutate] of [
  ['multiple strips with no reported gaps',(r:any)=>r.strips.push(r.strips[0])],
  ['missing photographs',(r:any)=>r.usedIndices.pop()],
  ['gap',(r:any)=>r.gaps.push({fromDeg:20,toDeg:30})],
  ['unknown geometry',(r:any)=>r.geometry=null],
  ['cylindrical fallback',(r:any)=>r.fellBackToCylindrical=true],
  ['coverage hole',(r:any)=>r.strips[0].coverage.holes.push({fromDeg:1,toDeg:2})],
  ['bad loop pair hidden by mean',(r:any)=>r.wrapClosure.pairs[0].duplicateAzimuthDeg=5],
  ['unverified geometry',(r:any)=>r.geometry.selfCheck=false],
  ['oversized canvas must not be capped to 360',(r:any)=>r.geometry.warpScale*=0.9],
  ['nonfinite geometry',(r:any)=>r.geometry.origin.y=NaN],
] as const) test(`reject ${name}`,()=>{const r=result();mutate(r);assert.equal(inspectResult(r,photos,100).diagnosticPrerequisitesPass,false);});
test('strict byte boundary',()=>{
  assert.equal(inspectResult(result(),photos,MAX_BYTES).diagnosticPrerequisitesPass,true);
  assert.equal(inspectResult(result(),photos,MAX_BYTES+1).diagnosticPrerequisitesPass,false);
});
test('partial, excessive and reversed capture rejected',()=>{
  for(const p of [photos.slice(0,15),photos.map((p,i)=>({...p,yawDeg:i*17})),photos.map((p,i)=>({...p,yawDeg:i===10?0:p.yawDeg}))])
    assert.equal(inspectResult(result(),p,100).diagnosticPrerequisitesPass,false);
});

// Run the PUBLISHED package's actual TS orchestration; only its native bridge
// and optional sidecar I/O are substituted. This is not a native stitching test.
const compiled=await build({entryPoints:[fileURLToPath(new URL('../../package/src/index.ts',import.meta.url))],bundle:true,write:false,
  platform:'node',format:'esm',plugins:[{name:'native-test-double',setup(b){
    b.onResolve({filter:/ExpoPanoramicStitcherModule$/},()=>({path:'native',namespace:'mock'}));
    b.onResolve({filter:/optionalFileSystem$/},()=>({path:'files',namespace:'mock'}));
    b.onLoad({filter:/.*/,namespace:'mock'},args=>({contents:args.path==='native'
      ? 'export default {stitchImagePaths:(...args)=>globalThis.__native(...args)}'
      : 'export const writeTextFile=()=>{}; export const toFileUri=p=>p;'}));
  }}]});
const upstream=await import(`data:text/javascript;base64,${Buffer.from(compiled.outputFiles![0]!.text).toString('base64')}`);
function native(usedIndices:number[]){return {success:true,path:'/out.jpg',width:4096,height:1024,
  usedIndices,usedCount:usedIndices.length,geometryJson:'',errorMessage:''};}
test('actual stitchSweep appends first two and enables wrap matching',async()=>{
  (globalThis as any).__native=async(paths:string[],options:any)=>{
    assert.equal(paths.length,26);assert.deepEqual(paths.slice(-2),['/photo-0.jpg','/photo-1.jpg']);
    assert.equal(options.matchWrap,true);assert.equal(options.autoResize,false);
    return native(Array.from({length:26},(_,i)=>i));
  };
  const r=await upstream.stitchSweep(photos,{warpMode:'spherical',matchNeighbors:2,sidecar:false});
  assert.equal(r.usedCount,24);assert.equal(r.wrapClosed,true);assert.equal(r.wrapClosure,null);
  assert.equal(inspectResult(r,photos,100).diagnosticPrerequisitesPass,false);
});
test('actual salvage can report success and empty gaps while returning two incomplete strips',async()=>{
  let calls=0;
  (globalThis as any).__native=async()=>native(calls++===0?Array.from({length:15},(_,i)=>i):Array.from({length:9},(_,i)=>i));
  const r=await upstream.stitchSweep(photos,{sidecar:false});
  assert.equal(r.success,true);assert.equal(r.strips.length,2);assert.deepEqual(r.gaps,[]);
  assert.equal(inspectResult(r,photos,100).diagnosticPrerequisitesPass,false);
});
test('actual spherical failure falls back once to cylindrical',async()=>{
  const modes:string[]=[];
  (globalThis as any).__native=async(_p:any,o:any)=>{
    modes.push(o.warpMode);if(modes.length===1)throw new Error('ERR_CAMERA_PARAMS_ADJUST_FAIL');
    return native(Array.from({length:26},(_,i)=>i));
  };
  const r=await upstream.stitchSweep(photos,{warpMode:'spherical',sidecar:false});
  assert.deepEqual(modes,['spherical','cylindrical']);assert.equal(r.fellBackToCylindrical,true);
  assert.equal(inspectResult(r,photos,100).diagnosticPrerequisitesPass,false);
});
test('actual native failure propagates; no accepted result',async()=>{
  (globalThis as any).__native=async()=>{throw new Error('Unreadable input');};
  await assert.rejects(upstream.stitchSweep(photos,{sidecar:false}),/Unreadable input/);
});
test('existing viewer rejects the package manifest without invented acceptance metadata',async()=>{
  const {validateMetadata}=await import('../../../viewer/metadata.mjs');
  assert.throws(()=>validateMetadata({schemaVersion:1,generator:'@notchip/expo-panoramic-stitcher',stitch:result()}));
});
