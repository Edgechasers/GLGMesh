import {ModelViewer} from './viewer.js';
const $=id=>document.getElementById(id);let token='',state=null,selected=null,imageData=null,currentView='interactive',lastImage='';
const recipes={fast:'Hunyuan Mini → Blender reduction',medium:'Hunyuan 2.1 → Blender reduction',high:'TRELLIS.2 · 512 resolution → target reduction & texture bake','production-textured':'IDOL → GauStudio mesh → target reduction & 4K texture bake',production:'IDOL → Gaussian-derived mesh → Blender 10k → Hi3D native target'};
async function api(path,data){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-GLGMesh-Token':token},body:JSON.stringify(data)});const body=await r.json();if(!r.ok)throw Error(body.error||'Request failed');return body}
function error(e){$('error').textContent=e.message||e}
const textureDefaults={fast:'rgb',medium:'mv',production:'mv'};
const textureNames={rgb:'Hunyuan Paint 2.0 · 2K',mv:'MV-Adapter SD2.1 · 2K',none:'None · geometry only'};
let textureMode=null;
function modeChanged(reset=true){
 const mode=$('mode').value,production=['production','production-textured'].includes(mode),steps=Number($('idol-steps').value);
 $('idol-steps-field').hidden=!production;$('idol-steps').disabled=!production;
 $('idol-steps-value').textContent=steps;$('idol-steps').setAttribute('aria-valuetext',`${steps} steps`);
 const minutes=steps*2;$('idol-steps-estimate').textContent=`About ${Math.floor(minutes/60)}h ${minutes%60}m for IDOL · ~2 min per step. Mesh processing adds time.`;
 if(textureMode!==mode){
  textureMode=mode;const choices=textureDefaults[mode]?[textureDefaults[mode],'none']:['none'];
  $('texture').replaceChildren(...choices.map(value=>{const option=document.createElement('option');option.value=value;option.textContent=textureNames[value];return option}));
  $('texture').value=textureDefaults[mode]||'none';
 }
 const texture=$('texture').value;$('texture-field').hidden=!textureDefaults[mode];
 if(reset)$('triangles').value=mode==='high'?200000:10000;
 $('recipe').textContent=recipes[mode].replace('IDOL →',`IDOL · ${steps} steps →`)+(texture==='none'?'':` → ${textureNames[texture]}`);
 $('target-note').textContent=mode==='production'?'The intermediate stays at 10k; this target controls the final Hi3D mesh.':'Triangle budget; the final count may be slightly lower.';
 if(!state)return;
 const last=state.jobs.find(j=>j.mode===mode&&(!production||(j.result?.settings?.idol_steps??50)===steps)&&j.status==='complete'&&!j.result?.settings?.texture_only&&!j.result?.settings?.resample_only&&(j.result?.settings?.texture||'none')===texture);
 $('timing').textContent=last?`Last completed local run: ${(last.elapsed_seconds/60).toFixed(1)} min. Times vary by image; estimates exclude setup.`:'Estimates exclude setup. Generation and texturing time depend on the image, settings and available resources.';
 const ready=state.doctor.modes[mode].ready&&(texture==='rgb'?state.doctor.texture_rgb_ready:texture==='mv'?state.doctor.texture_mv_ready:true),busy=state.doctor.busy||state.jobs.some(j=>j.status==='running')||state.setup.status==='running';
 $('installation').textContent=ready?'● Local model ready':'Local model setup required';$('install').hidden=ready;$('install').disabled=busy;$('generate').disabled=!ready||!imageData||busy;
}

async function choose(file){if(!file)return;if(file.size>32*1024**2){error('Choose an image under 32 MB');return}if(!['image/png','image/jpeg','image/webp'].includes(file.type)){error('Choose a PNG, JPG or WebP image');return}const reader=new FileReader();reader.onload=()=>{imageData=reader.result.split(',')[1];$('source').src=reader.result;$('source').hidden=false;$('upload-label').hidden=true;$('error').textContent='';modeChanged(false)};reader.readAsDataURL(file)}
$('image').onchange=e=>choose(e.target.files[0]);$('mode').onchange=()=>modeChanged();$('texture').onchange=()=>modeChanged(false);$('idol-steps').oninput=()=>modeChanged(false);
for(const event of ['dragenter','dragover'])$('drop').addEventListener(event,e=>{e.preventDefault();$('drop').classList.add('drag')});for(const event of ['dragleave','drop'])$('drop').addEventListener(event,e=>{e.preventDefault();$('drop').classList.remove('drag');if(event==='drop')choose(e.dataTransfer.files[0])});
$('form').onsubmit=async e=>{e.preventDefault();$('error').textContent='';$('generate').disabled=true;try{const r=await api('/api/run',{mode:$('mode').value,texture:$('texture').value,triangles:Number($('triangles').value),seed:Number($('seed').value),image:imageData,...(['production','production-textured'].includes($('mode').value)?{idol_steps:Number($('idol-steps').value)}:{})});selected=r.id;currentView='interactive';await poll();$('progress-panel').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'center'})}catch(e){error(e);modeChanged(false)}};
$('install').onclick=async()=>{try{await api('/api/setup',{mode:$('mode').value,texture:$('texture').value});$('setup-panel').open=true;await poll()}catch(e){error(e)}};
$('cancel').onclick=async()=>{try{await api('/api/cancel',{id:selected});await poll()}catch(e){error(e)}};
$('resume').onclick=async()=>{try{await api('/api/resume',{id:selected});await poll()}catch(e){error(e)}};
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{currentView=b.dataset.view;renderJob()});
function renderJob(){const j=state.jobs.find(j=>j.id===selected);if(!j)return;const done=j.status==='complete',running=j.status==='running';$('title').textContent=done?`${j.result.triangles.toLocaleString()} triangles · ${state.modes[j.mode].name}${j.result?.settings?.texture==='rgb'?' · Hunyuan Paint':j.result?.settings?.texture==='mv'?' · MV-Adapter':''}`:state.modes[j.mode].name;$('progress-panel').hidden=false;$('phase').textContent=j.status==='failed'?'Run failed':j.status==='cancelled'?'Run cancelled':j.stage_name||j.status;$('percent').textContent=`${(j.percent||0).toFixed(1)}%`;$('progress').value=j.percent||0;$('progress').classList.toggle('indeterminate',running&&j.indeterminate);$('detail').textContent=j.message+(j.step&&j.total?` · step ${j.step}/${j.total}`:'');const seconds=running?Math.max(0,Date.now()/1000-j.started):j.elapsed_seconds||0;$('elapsed').textContent=`${Math.floor(seconds/60)}m ${Math.floor(seconds%60)}s`;$('stages').replaceChildren(...j.stages.map(s=>{const li=document.createElement('li');li.className=s.status;li.textContent=s.name;return li}));$('cancel').hidden=!running;$('resume').hidden=!['failed','cancelled','interrupted'].includes(j.status);$('log').href=`/runs/${j.id}/console.log`;$('report').hidden=!done;$('report').href=`/runs/${j.id}/qa.json`;$('download').hidden=!done;$('download').href=`/runs/${j.id}/model.glb`;$('download').download=`glgmesh-${j.mode}-${j.result?.triangles}.glb`;const qa=j.result?.qa;const summary=qa?`QA: ${qa.errors.length} errors · ${qa.warnings.length} warnings. `:'';$('qa-note').textContent=done?summary+'Generated mesh for review. Inspect silhouette, thin parts and topology before using it in game.':'';$('views').hidden=!done;$('clay-view').hidden=j.result?.preview_style!=='textured';$('view-style').textContent=j.result?.preview_style==='textured'?'Textured mesh · wireframe shows geometry':'Neutral geometry preview';const showImage=done||Boolean(j.stage);$('render').hidden=!showImage;$('render').alt=done?(j.result?.preview_style==='textured'?'Generated textured mesh preview':'Generated mesh geometry preview'):'Source image for this run';$('preview').querySelector('.empty').hidden=showImage;$('preview-caption').hidden=done||!showImage;$('preview-caption').textContent='Source image · generation in progress';const image=`/runs/${j.id}/${done?(['interactive','splat'].includes(currentView)?'preview':currentView):'input'}.png`;if(showImage&&lastImage!==image){$('render').src=image;lastImage=image}renderOutput(j)}
let historySignature='';
async function poll(){try{const r=await fetch('/api/state');if(!r.ok)throw Error('Local server unavailable');state=await r.json();token=state.token;modeChanged(false);if(!selected&&state.jobs.length)selected=state.jobs[0].id;renderJob();const signature=JSON.stringify(state.jobs.map(j=>[j.id,j.status,j.result?.triangles]));if(state.jobs.length&&signature!==historySignature){historySignature=signature;$('history').replaceChildren(...state.jobs.map(j=>{const b=document.createElement('button');b.className='run';const label=document.createElement('span');label.textContent=(j.result?.settings?.resample_only?`${j.result.triangles.toLocaleString()} triangles · Resampled · `:'')+state.modes[j.mode].name+(j.result?.settings?.texture==='rgb'?' · Hunyuan Paint':j.result?.settings?.texture==='mv'?' · MV-Adapter':'');const small=document.createElement('small');small.textContent=`${j.status} · ${new Date(j.created*1000).toLocaleString()}`;b.append(label,small);b.onclick=()=>{selected=j.id;currentView='interactive';renderJob()};return b}));}$('setup-panel').hidden=state.setup.status==='idle';$('setup-progress').hidden=state.setup.status!=='running';$('setup-log').textContent=state.setup.lines.join('\n');if(state.setup.status==='failed')error('Setup failed. See installation log below.')}catch(e){error(e)}}


let viewer=null,viewerJob=null,toolsJob=null,viewerFailed=false,pendingResample=false;
function spinLabel(){if(!viewer)return;$('spin').textContent=viewer.spinning?'Pause rotation':'Resume rotation';$('spin').setAttribute('aria-pressed',String(viewer.spinning))}
function downloadChoice(){const j=state?.jobs.find(j=>j.id===selected);if(!j)return;const neutral=$('download-style').value==='neutral';$('download').href=`/runs/${j.id}/${neutral?'model-untextured':'model'}.glb`;$('download').download=`glgmesh-${j.mode}-${j.result?.triangles}-${neutral?'untextured':'textured'}.glb`}
$('download-style').onchange=downloadChoice;
$('show-texture').onchange=()=>viewer?.setTexture($('show-texture').checked);
$('rotation').oninput=()=>{viewer?.setAngle(Number($('rotation').value));spinLabel()};
$('spin').onclick=()=>{if(viewer){viewer.spinning=!viewer.spinning;spinLabel()}};
function targetBounds(){const o=state?.jobs.find(j=>j.id===selected)?.output_options;return [o?.resample_min||100,o?.resample_max||2000000]}
function showTargetOnSlider(){const [min,max]=targetBounds(),n=Number($('resample-count').value);$('resample-range').value=1000*Math.log(Math.max(min,Math.min(max,n))/min)/Math.log(max/min);$('resample-range').setAttribute('aria-valuetext',`${n.toLocaleString()} triangles`)}
function syncTarget(from){
  if(from==='resample-range'){const [min,max]=targetBounds();$('resample-count').value=Math.round(min*Math.pow(max/min,Number($('resample-range').value)/1000))}
  showTargetOnSlider();renderResampleButton();
}
$('resample-range').oninput=()=>syncTarget('resample-range');$('resample-count').oninput=()=>syncTarget('resample-count');
function renderResampleButton(){const j=state?.jobs.find(j=>j.id===selected),n=Number($('resample-count').value),o=j?.output_options;const busy=state?.doctor.busy||state?.setup.status==='running'||state?.jobs.some(j=>['queued','running'].includes(j.status));$('resample').disabled=pendingResample||busy||!o?.resample_available||!Number.isInteger(n)||n<o.resample_min||n>o.resample_max}
$('resample').onclick=async()=>{pendingResample=true;renderResampleButton();$('error').textContent='';try{const r=await api('/api/resample',{id:selected,triangles:Number($('resample-count').value)});selected=r.id;currentView='interactive';await poll();$('progress-panel').scrollIntoView({behavior:'smooth',block:'center'})}catch(e){error(e)}finally{pendingResample=false;renderResampleButton()}};
function renderOutput(j){
  const done=j.status==='complete',o=j.output_options||{},interactive=done&&['interactive','splat'].includes(currentView),isSplat=currentView==='splat',viewKey=`${j.id}:${currentView}`;
  $('output-tools').hidden=!done;$('viewer-controls').hidden=!interactive;$('model-viewer').hidden=!interactive;$('viewer-status').hidden=!interactive||(!viewerFailed&&viewer?.model&&viewerJob===viewKey);$('render').hidden=interactive||(!done&&!j.stage);
  $('preview').querySelector('.empty').hidden=done||Boolean(j.stage);
  document.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===currentView)));
  if(!done){if(viewerJob!==null){viewer?.clear();viewerJob=null}return}
  if(toolsJob!==j.id){
    toolsJob=j.id;$('download-style').value=o.has_texture?'textured':'neutral';$('download-style').querySelector('[value=textured]').disabled=!o.has_texture;
    $('show-texture').checked=Boolean(o.has_texture);$('show-texture').disabled=!o.has_texture;$('show-texture').parentElement.title=o.has_texture?'Toggle appearance in the preview':'This model has no texture';
    $('resample-count').min=o.resample_min||100;$('resample-count').max=o.resample_max||2000000;$('resample-count').value=j.result.requested_triangles||j.result.triangles;showTargetOnSlider()
  }
  $('splat-view').hidden=!['production','production-textured'].includes(j.mode);
  $('splat-view').disabled=!o.splat_available;$('splat-view').title=o.splat_available?'Original IDOL Gaussian splat':o.splat_reason;
  $('show-texture').parentElement.hidden=isSplat;
  downloadChoice();
  $('resample-tools').hidden=!['production','production-textured'].includes(j.mode);
  $('resample-source').textContent=j.mode==='production'?(j.result?.settings?.texture==='mv'?'Hi3D + MV-Adapter':'Hi3D'):'Blender + texture rebake';
  $('resample-note').textContent=o.resample_available?'Rebuild from saved dense source: 100–2M triangles, above or below this result. Source detail limits the output.':o.resample_reason;
  for(const id of ['resample-range','resample-count'])$(id).disabled=!o.resample_available;
  renderResampleButton();
  $('view-style').textContent=interactive?(isSplat?'Original IDOL splat · baked appearance':(o.has_texture?'Drag to rotate · texture available':'Drag to rotate · geometry only')):(j.result.preview_style==='textured'?'Textured mesh · wireframe shows geometry':'Neutral geometry preview');
  if(interactive&&viewerJob!==viewKey){
    const angle=viewerJob?.startsWith(j.id+':')?(viewer?.angle||0):0;viewerJob=viewKey;viewerFailed=false;$('viewer-status').hidden=false;$('viewer-status').textContent=isSplat?'Loading source splat…':'Loading 3D model…';
    try{
      viewer??=new ModelViewer($('model-viewer'),angle=>{$('rotation').value=angle;$('angle').textContent=angle+'°'},spinLabel);
      viewer.onFailure=message=>{viewerFailed=true;$('viewer-status').hidden=false;$('viewer-status').textContent=message};
      spinLabel();const loading=isSplat?viewer.loadSplat(`/runs/${j.id}/source-splat.ply`,o.splat_yaw,angle):viewer.load(`/runs/${j.id}/model.glb`,o.front_yaw,o.has_texture,angle);loading.then(loaded=>{if(loaded&&viewerJob===viewKey){$('viewer-status').hidden=true;viewer.setTexture($('show-texture').checked)}}).catch(e=>{if(viewerJob===viewKey&&e.name!=='AbortError'){viewerFailed=true;$('viewer-status').textContent='3D preview unavailable: '+e.message+'. Still views and downloads remain available.'}});
    }catch(e){viewerFailed=true;$('viewer-status').textContent='3D preview unavailable: '+e.message+'. Still views and downloads remain available.'}
  }
  if(interactive)viewer?.resize();
}
modeChanged();poll();setInterval(poll,1200);
