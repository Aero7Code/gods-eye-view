'use strict';
(()=>{
const root=document.getElementById('godsEye');if(!root)return;
const $=s=>root.querySelector(s), frame=$('#gev-frame'), origin='http://127.0.0.1:4173';
let resultText='',revision=-1,selected=null,ready=false,full=false,catalog=[],activeFlight='',flightBusy=false;
async function request(path,data){const r=await fetch(path,{method:data===undefined?'GET':'POST',headers:{'Content-Type':'application/json'},body:data===undefined?undefined:JSON.stringify(data)});const v=await r.json();if(!r.ok)throw Error(v.error||'Request failed');return v;}
function load(){if(!frame.src){ready=false;frame.src=origin+'/?embed=1';}}
function apply(){if(ready&&selected)frame.contentWindow.postMessage({type:'gev:view',id:String(selected.revision),view:selected.view},origin);}
async function sync(){try{const state=await request('/api/gods-eye');if(state.latest_result){const text=JSON.stringify(state.latest_result,null,2);if(text!==resultText){resultText=text;$('#gev-details').textContent=text;$('#gev-report').textContent=state.latest_result.answer||'';}}if(state.selected&&state.revision!==revision){revision=state.revision;selected=state.selected;if(state.latest_result){$('#gev-details').textContent=JSON.stringify(state.latest_result,null,2);$('#gev-report').textContent=state.latest_result.answer||'';}$('#gev-status').textContent=selected.summary||'Digi updated the globe.';if(!root.hidden){load();apply();}}}catch(e){if(!root.hidden)$('#gev-status').textContent=e.message;}}
function show(){window.view('godsEye');document.getElementById('viewTitle').textContent='God’s Eye View';load();sync();}
window.addEventListener('message',e=>{if(e.origin!==origin||e.source!==frame.contentWindow)return;if(e.data?.type==='gev:camera'){request('/api/gods-eye/observe',{camera:e.data.camera}).catch(()=>{});}if(e.data?.type==='gev:ready'){ready=true;apply();}if(e.data?.type==='gev:view-applied')$('#gev-status').textContent=e.data.ok?'Globe updated.':"The globe could not apply every requested layer; check feed availability.";});
async function query(data){$('#gev-status').textContent='Reading live resources…';try{const result=await request('/api/gods-eye/query',data);$('#gev-details').textContent=JSON.stringify(result,null,2);$('#gev-report').textContent=result.answer||'';$('#gev-status').textContent=result.summary||'Query completed.';await sync();return result;}catch(e){$('#gev-status').textContent=e.message;}}
$('#gev-place-form').onsubmit=e=>{e.preventDefault();query({operation:'query',tool:'show_in_gods_eye_view',arguments_json:JSON.stringify({area:{place:$('#gev-place').value},layers:['flights']})});};
async function flight(){if(flightBusy||!activeFlight)return;flightBusy=true;try{await query({operation:'flight',flight:activeFlight});}finally{flightBusy=false;}}
$('#gev-flight-form').onsubmit=e=>{e.preventDefault();activeFlight=$('#gev-flight').value;flight();};
$('#gev-controls').onclick=()=>{$('#gev-status').textContent='Loading map controls…';full=!full;ready=false;frame.src=origin+'/?embed=1'+(full?'&controls=1':'');$('#gev-controls').textContent=full?'Clean globe':'Full controls';};
$('#gev-load-tools').onclick=async()=>{try{catalog=(await request('/api/gods-eye/catalog')).tools;$('#gev-tool').replaceChildren(...catalog.map(t=>{const o=document.createElement('option');o.value=t.name;o.textContent=t.title||t.name;return o;}));$('#gev-tool').dispatchEvent(new Event('change'));}catch(e){$('#gev-status').textContent=e.message;}};
$('#gev-tool').onchange=()=>{const t=catalog.find(t=>t.name===$('#gev-tool').value);$('#gev-schema').textContent=t?t.description+'\n'+JSON.stringify(t.inputSchema,null,2):'';};
$('#gev-run').onclick=()=>query({operation:'query',tool:$('#gev-tool').value,arguments_json:$('#gev-args').value});
document.addEventListener('click',e=>{if(e.target.closest('[data-view=godsEye]'))show();});
setInterval(()=>{if(!root.hidden&&!document.hidden)sync();},2000);
setInterval(()=>{if(!root.hidden&&!document.hidden&&$('#gev-live').checked)flight();},30000);
// Chat polling attaches a reviewable link to each completed globe action.
const observer=new MutationObserver(()=>{document.querySelectorAll('#messages .message.assistant').forEach(node=>{if(node.querySelector('.gev-show'))return;const body=node.querySelector('.body')?.textContent||'';if(/God’s Eye View|Feed evidence:/.test(body)){const b=document.createElement('button');b.textContent='Show globe';b.className='gev-show';b.onclick=show;node.append(b);}});});observer.observe(document.getElementById('messages'),{childList:true,subtree:true,characterData:true});
if(location.hash==='#godsEye')show();
})();
