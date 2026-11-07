import * as THREE from './vendor/three.module.js';
import {GLTFLoader} from './vendor/GLTFLoader.js';

// All resources are local. Material changes only affect this preview, never the GLB.
export class ModelViewer {
  constructor(host, onAngle, onPause) {
    this.host=host;this.onAngle=onAngle;this.onPause=onPause;this.ticket=0;this.angle=0;
    this.spinning=!matchMedia('(prefers-reduced-motion: reduce)').matches;
    this.renderer=new THREE.WebGLRenderer({antialias:true,alpha:false});
    this.renderer.setPixelRatio(Math.min(devicePixelRatio,2));
    this.renderer.setClearColor(0xc4c1ba);this.renderer.outputColorSpace=THREE.SRGBColorSpace;
    host.append(this.renderer.domElement);
    this.scene=new THREE.Scene();this.camera=new THREE.PerspectiveCamera(34,1,.01,100);
    this.scene.add(new THREE.HemisphereLight(0xffffff,0x62665b,2.2));
    const key=new THREE.DirectionalLight(0xffffff,3);key.position.set(3,5,4);this.scene.add(key);
    const fill=new THREE.DirectionalLight(0xe4efff,1);fill.position.set(-4,2,-3);this.scene.add(fill);
    this.pivot=new THREE.Group();this.scene.add(this.pivot);
    this.observer=new ResizeObserver(()=>this.resize());this.observer.observe(host);
    let drag=null;
    this.renderer.domElement.addEventListener('pointerdown',e=>{drag={x:e.clientX,angle:this.angle};this.renderer.domElement.setPointerCapture(e.pointerId)});
    this.renderer.domElement.addEventListener('pointermove',e=>{if(!drag)return;this.setAngle(drag.angle+(e.clientX-drag.x)*.45);this.onPause()});
    for(const name of ['pointerup','pointercancel'])this.renderer.domElement.addEventListener(name,()=>drag=null);
    this.renderer.domElement.addEventListener('webglcontextlost',e=>{e.preventDefault();this.onFailure?.('The 3D preview lost its graphics context. Reload to restore it; downloads and still views remain available.')});
    let previous=performance.now();
    this.renderer.setAnimationLoop(now=>{
      const dt=Math.min((now-previous)/1000,.1);previous=now;
      if(host.hidden||document.hidden)return;
      if(this.spinning&&this.model)this.setAngle(this.angle+dt*30,false); // 12-second turn
      this.renderer.render(this.scene,this.camera);
    });
  }
  resize(){const w=this.host.clientWidth,h=this.host.clientHeight;if(!w||!h)return;this.renderer.setSize(w,h,false);this.camera.aspect=w/h;this.camera.updateProjectionMatrix();this.frame()}
  frame(){if(!this.radius)return;const vertical=THREE.MathUtils.degToRad(this.camera.fov/2),horizontal=Math.atan(Math.tan(vertical)*this.camera.aspect);const distance=this.radius/Math.sin(Math.min(vertical,horizontal))*1.12;this.camera.position.set(0,distance*.08,distance);this.camera.lookAt(0,0,0)}
  setAngle(degrees,pause=true){this.angle=((degrees%360)+360)%360;this.pivot.rotation.y=this.yaw+THREE.MathUtils.degToRad(this.angle);if(pause)this.spinning=false;this.onAngle(Math.floor(this.angle))}
  setTexture(enabled){if(this.model?.userData.isSourceSplat)return;this.textured=enabled;this.model?.traverse(o=>{if(o.isMesh)o.material=enabled?o.userData.displayMaterials:o.userData.neutralMaterial})}
  disposeModel(model){if(!model)return;if(model.userData.isSourceSplat){if(model.userData.disposalStarted)return;model.userData.disposalStarted=true;Promise.resolve(model.userData.loading).catch(()=>{}).then(()=>model.dispose()).catch(e=>console.warn('Splat disposal:',e)).finally(()=>{model.callbackMesh.geometry.dispose();model.callbackMesh.material.dispose()});return}const textures=new Set(),materials=new Set(),geometry=new Set();model.traverse(o=>{if(!o.isMesh)return;geometry.add(o.geometry);for(const m of [o.material,o.userData.originalMaterials,o.userData.displayMaterials,o.userData.neutralMaterial].flat().filter(Boolean)){materials.add(m);for(const v of Object.values(m))if(v?.isTexture)textures.add(v)}});geometry.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());textures.forEach(t=>t.dispose())}
  clear(){this.ticket++;this.abort?.abort();this.disposeModel(this.model);this.disposeModel(this.pendingSplat);this.pendingSplat=null;this.model=null;this.pivot.clear()}
  async loadSplat(url,yaw,angle=0){
    this.clear();const ticket=this.ticket;this.yaw=yaw||0;this.setAngle(angle,false);
    const {DropInViewer,SceneRevealMode}=await import('./vendor/gaussian-splats-3d.module.js');
    if(ticket!==this.ticket)return false;
    const splat=new DropInViewer({sharedMemoryForWorkers:false,gpuAcceleratedSort:false,
      dynamicScene:true,sphericalHarmonicsDegree:0,sceneRevealMode:SceneRevealMode.Instant,
      enableSIMDInSort:true,integerBasedSort:false,ignoreDevicePixelRatio:false});
    splat.userData.isSourceSplat=true;this.pendingSplat=splat;
    try{
      splat.userData.loading=splat.addSplatScene(url,{showLoadingUI:false,progressiveLoad:false,splatAlphaRemovalThreshold:1,
        rotation:[1,0,0,0]}); // IDOL's viewer PLY is flipped 180° about X relative to our GLB.
      await splat.userData.loading;
      if(ticket!==this.ticket)return false; // clear() owns disposal of superseded loads.
      const box=new THREE.Box3(),point=new THREE.Vector3();
      const count=splat.splatMesh.getSplatCount();
      for(let i=0;i<count;i++){splat.splatMesh.getSplatCenter(i,point,true);box.expandByPoint(point)}
      if(box.isEmpty())throw Error('The source splat is empty');
      const center=box.getCenter(new THREE.Vector3()),size=box.getSize(new THREE.Vector3());
      const scale=2/Math.max(size.x,size.y,size.z);
      splat.position.copy(center).multiplyScalar(-scale);splat.scale.setScalar(scale);
      this.radius=size.length()*scale/2;this.splatCount=count;this.pendingSplat=null;this.model=splat;
      this.pivot.add(splat);this.resize();return true;
    }catch(e){if(ticket===this.ticket){this.pendingSplat=null;this.disposeModel(splat);throw e}return false}
  }
  async load(url,yaw,hasTexture,angle=0){
    this.clear();const ticket=this.ticket;this.abort=new AbortController();this.yaw=yaw||0;this.setAngle(angle,false);
    const response=await fetch(url,{signal:this.abort.signal});if(!response.ok)throw Error('Model download failed');
    const buffer=await response.arrayBuffer();if(ticket!==this.ticket)return false;
    const gltf=await new GLTFLoader().parseAsync(buffer,'');
    if(ticket!==this.ticket){this.disposeModel(gltf.scene);return false}
    this.model=gltf.scene;
    const box=new THREE.Box3().setFromObject(this.model);if(box.isEmpty())throw Error('The model contains no visible geometry');
    const center=box.getCenter(new THREE.Vector3()),size=box.getSize(new THREE.Vector3());
    const scale=2/Math.max(size.x,size.y,size.z);this.model.position.sub(center);this.model.position.multiplyScalar(scale);this.model.scale.multiplyScalar(scale);this.radius=size.length()*scale/2;
    this.model.traverse(o=>{if(!o.isMesh)return;const originals=Array.isArray(o.material)?o.material:[o.material];o.userData.originalMaterials=o.material;
      const display=originals.map(m=>new THREE.MeshBasicMaterial({map:m.map,color:m.color,side:THREE.DoubleSide,transparent:m.transparent,opacity:m.opacity,alphaTest:m.alphaTest,vertexColors:m.vertexColors}));
      o.userData.displayMaterials=Array.isArray(o.material)?display:display[0];o.userData.neutralMaterial=new THREE.MeshStandardMaterial({color:0x92998f,roughness:.85,metalness:0,side:THREE.DoubleSide,flatShading:!o.geometry.hasAttribute('normal')});
    });
    this.pivot.add(this.model);this.setTexture(hasTexture);this.resize();return true;
  }
}
