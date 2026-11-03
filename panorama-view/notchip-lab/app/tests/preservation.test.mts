import test from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

// Real session controller with in-memory file/native boundaries. No room imagery.
const compiled=await build({entryPoints:[fileURLToPath(new URL('../session.ts',import.meta.url))],
  bundle:true,write:false,platform:'node',format:'esm',plugins:[{name:'device-boundaries',setup(b){
    b.onResolve({filter:/^(expo-file-system|expo-image-manipulator|expo-device|react-native|@notchip\/expo-panoramic-stitcher)$/},
      args=>({path:args.path,namespace:'mock'}));
    b.onLoad({filter:/.*/,namespace:'mock'},args=>({contents:args.path==='expo-file-system'
      ? `export const Paths={document:'file:///documents'};
         export class Directory {uri; constructor(...p){this.uri=p.map(x=>x.uri??x).join('/')} create(){} }
         export class File {uri; constructor(...p){this.uri=p.map(x=>x.uri??x).join('/')}
           copy(dest){globalThis.__copies.push([this.uri,dest.uri])}
           write(text){globalThis.__reports.push(JSON.parse(text))}
           get exists(){return false} }
        `
      : args.path==='expo-device' ? 'export const modelName="fixture",isDevice=false,totalMemory=null;'
      : args.path==='react-native' ? 'export const Platform={OS:"android",Version:36};'
      : args.path==='expo-image-manipulator' ? 'export const SaveFormat={JPEG:"jpeg"}; export const manipulateAsync=()=>{throw new Error("Must reject before resizing")};'
      : 'export const stitchSweep=()=>{throw new Error("Must reject before native stitching")};'}));
  }}]});
const {evaluateCapture}=await import(`data:text/javascript;base64,${Buffer.from(compiled.outputFiles![0]!.text).toString('base64')}`);
for (const [name,count,endedBy] of [['short sweep',2,'finish'],['background abort',8,'background']] as const) {
  test(`${name} preserves every original and error receipt before rejecting`,async()=>{
    (globalThis as any).__copies=[];(globalThis as any).__reports=[];
    const photos=Array.from({length:count},(_,i)=>({uri:`file:///new-fixture-${i}.jpg`,width:600,height:1200,yawDeg:i*15}));
    const result=await evaluateCapture(photos,{startedAt:10,finishedAt:20,endedBy},()=>{});
    assert.equal((globalThis as any).__copies.length,count);
    assert.equal(result.report.accepted360,false);
    assert.equal(result.report.sourcePhotos.length,count);
    assert.match(result.report.error,/foreground sweep/);
    assert.equal(result.preview,null);
    assert.ok((globalThis as any).__reports.length>=2);
  });
}
