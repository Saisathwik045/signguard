'use strict';
const labels = Object.freeze({genuine_signed:'Genuine signed',tampered:'Tampered signed bytes',shadow_modified:'Shadow-modified',visual_only:'Visual-only signature',unsigned:'Unsigned'});
const descriptions = {genuine_signed:'Valid signed bytes · trust unknown',tampered:'Cryptographic integrity failure',shadow_modified:'Signed vs current appearance',visual_only:'Unverified visual candidate',unsigned:'No cryptographic signature'};
const $ = id => document.getElementById(id);
const titleCase = value => value.replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());
let selection = 0, activeReport = null, activeId = null, catalogue;
function download(bytes,type,suffix){if(!activeReport)return;const url=URL.createObjectURL(new Blob([bytes],{type}));const a=document.createElement('a');a.href=url;a.download=`signguard-${activeId}.${suffix}`;a.click();setTimeout(()=>URL.revokeObjectURL(url),2000);}
$('json-download').onclick=()=>download(JSON.stringify(activeReport,null,2),'application/json','json');
$('pdf-download').onclick=()=>{if(activeReport){const value=Uint8Array.from(atob(activeReport.pdf_report.base64),c=>c.charCodeAt(0));download(value,'application/pdf','pdf');}};
async function show(id){
  if(!Object.hasOwn(labels,id))throw new Error('Unknown bundled example');
  const version=++selection;activeReport=null;activeId=null;$('result').hidden=true;$('loading').hidden=false;$('error').hidden=true;
  document.querySelector('.report').setAttribute('aria-busy','true');
  document.querySelectorAll('#cases button').forEach(b=>b.setAttribute('aria-current',String(b.dataset.id===id)));
  try{
    const response=await fetch(`/reports/${id}.json`,{credentials:'same-origin',cache:'no-store',redirect:'error'});
    if(!response.ok)throw new Error('Report unavailable');
    const raw=await response.arrayBuffer();
    const digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',raw))].map(b=>b.toString(16).padStart(2,'0')).join('');
    if(digest!==catalogue.cases[id].report_sha256)throw new Error('Report hash mismatch');
    const report=JSON.parse(new TextDecoder().decode(raw));
    if(report.sha256!==catalogue.cases[id].pdf_sha256||report.execution_controls.isolation!=='docker_disposable')throw new Error('Provenance mismatch');
    if(version!==selection)return;
    activeId=id;activeReport=report;
    $('case-title').textContent=labels[id];$('classification').textContent=report.structure.refined_classification;
    $('status').textContent=titleCase(report.assessment.analysis_status);$('verdict').textContent=titleCase(report.assessment.verdict);
    $('verdict').className=`verdict ${report.assessment.verdict}`;
    $('reasons').replaceChildren(...report.assessment.reasons.map(reason=>{const li=document.createElement('li');li.textContent=reason;return li;}));
    $('evidence').replaceChildren(...report.visual_evidence.map(item=>{const figure=document.createElement('figure'),img=document.createElement('img'),caption=document.createElement('figcaption');img.src=`data:image/png;base64,${item.base64}`;img.alt=`${item.label}, page ${item.page}`;caption.textContent=`${item.label} · Page ${item.page}`;figure.append(img,caption);return figure;}));
    $('comparisons').textContent=JSON.stringify({visual_comparisons:report.visual_comparisons,revision_analysis:report.revision_analysis,image_forensics:report.image_forensics},null,2);
    $('provenance').textContent=JSON.stringify({pdf_sha256:report.sha256,report_sha256:digest,worker_image_id:catalogue.worker_image_id,scope:'Precomputed trusted synthetic fixture; no live analysis; no identity assertion',findings:report.assessment.findings},null,2);
    $('shown').textContent=`Report shown: ${labels[id]} · Evidence verified against bundle SHA-256.`;
    $('loading').hidden=true;$('result').hidden=false;document.querySelector('.report').setAttribute('aria-busy','false');
  }catch(error){if(version!==selection)return;activeReport=null;activeId=null;$('loading').hidden=true;$('error').hidden=false;$('error').textContent='The verified report could not be loaded. Reload to retry. No analysis fallback is available.';document.querySelector('.report').setAttribute('aria-busy','false');}
}
async function start(){try{const r=await fetch('/catalogue.json',{credentials:'same-origin',cache:'no-store',redirect:'error'});if(!r.ok)throw new Error('Catalogue unavailable');catalogue=await r.json();if(Object.keys(catalogue.cases).sort().join()!==Object.keys(labels).sort().join())throw new Error('Invalid catalogue');for(const[id,label]of Object.entries(labels)){const button=document.createElement('button');button.type='button';button.dataset.id=id;button.textContent=label;const description=document.createElement('span');description.textContent=descriptions[id];button.append(description);button.onclick=()=>show(id);$('cases').append(button);}await show('genuine_signed');}catch(error){$('loading').hidden=true;$('error').hidden=false;$('error').textContent='Verified synthetic catalogue is unavailable. No uploads or analysis are enabled.';}}
start();
