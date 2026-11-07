import {readFile,writeFile,mkdir,copyFile} from 'node:fs/promises';
const vendor=new URL('../ui/vendor/',import.meta.url);
const three=new URL('./node_modules/three/',import.meta.url);
await mkdir(vendor,{recursive:true});
for(const name of ['three.module.js','three.core.js'])await copyFile(new URL('build/'+name,three),new URL(name,vendor));
await copyFile(new URL('LICENSE',three),new URL('THREE-LICENSE.txt',vendor));
for(const [name,sub] of [['GLTFLoader.js','loaders'],['BufferGeometryUtils.js','utils']]){
 const code=(await readFile(new URL(`examples/jsm/${sub}/${name}`,three),'utf8')).replaceAll("from 'three'","from './three.module.js'").replaceAll("'../utils/BufferGeometryUtils.js'","'./BufferGeometryUtils.js'");
 await writeFile(new URL(name,vendor),code);
}
const splats=new URL('./node_modules/@mkkellogg/gaussian-splats-3d/',import.meta.url);
const splatCode=(await readFile(new URL('build/gaussian-splats-3d.module.js',splats),'utf8')).replaceAll("from 'three'","from './three.module.js'").replace(/\/\/# sourceMappingURL=.*\n?$/,'');
await writeFile(new URL('gaussian-splats-3d.module.js',vendor),splatCode);
await copyFile(new URL('LICENSE',splats),new URL('GAUSSIAN-SPLATS-3D-LICENSE.txt',vendor));
