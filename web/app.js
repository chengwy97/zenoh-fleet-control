const state = { token:null, username:null, devices:[], selected:null, cwd:'.', timer:null };
const $ = id => document.getElementById(id);
const api = async (path, options={}) => {
  const headers = {'Content-Type':'application/json', ...(options.headers||{})};
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const res = await fetch(path, {...options, headers});
  const text = await res.text();
  let data; try { data = text ? JSON.parse(text) : {}; } catch { data = {detail:text}; }
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data;
};
function showApp() { $('loginView').classList.add('hidden'); $('appView').classList.remove('hidden'); $('logout').classList.remove('hidden'); }
function showError(message) { $('globalError').textContent = message || ''; }
function renderDevices() {
  $('deviceList').innerHTML = state.devices.map((d,i) => `<button class="device ${state.selected===i?'selected':''}" data-index="${i}"><div class="device-name"><span class="dot ${d.status||''}"></span>${escapeHtml(d.device_id)}</div><div class="device-meta">${escapeHtml(d.status||'unknown')} · ${escapeHtml(d.active_session_id||d.session_id||'no session')}</div><div class="device-meta">${escapeHtml(d.cwd||'')}</div></button>`).join('') || '<p class="muted">No online terminals.</p>';
  document.querySelectorAll('.device').forEach(b => b.onclick = () => selectDevice(Number(b.dataset.index)));
}
async function refreshDevices() {
  try { state.devices = (await api('/v1/devices')).items || []; renderDevices(); if (state.selected === null && state.devices.length) selectDevice(0); else if (state.selected !== null && state.devices[state.selected]) await refreshSession(); } catch(e) { showError(e.message); }
}
function selectedTarget() { const d=state.devices[state.selected]; return d ? {device:d.device_id, session:d.active_session_id||d.session_id||`sess_${d.device_id}`} : null; }
async function selectDevice(index) { state.selected=index; renderDevices(); await refreshSession(); }
async function refreshSession() {
  const t=selectedTarget(); if (!t) return;
  try { const s=await api(`/v1/sessions/${encodeURIComponent(state.username)}/${encodeURIComponent(t.device)}/${encodeURIComponent(t.session)}`); $('sessionTitle').textContent=t.device; $('sessionMeta').textContent=`${t.session} · ${s.cwd||state.devices[state.selected].cwd||''}`; $('sessionState').textContent=s.status||s.state||'unknown'; state.cwd=s.cwd||state.devices[state.selected].cwd||'.'; $('cwd').textContent=state.cwd; await refreshEvents(); await refreshDirectory(state.cwd); } catch(e) { showError(e.message); }
}
async function refreshEvents() { const t=selectedTarget(); if(!t)return; try { const data=await api(`/v1/sessions/${encodeURIComponent(state.username)}/${encodeURIComponent(t.device)}/${encodeURIComponent(t.session)}/events?after_seq=0`); renderTimeline(data); } catch(e){showError(e.message);} }
function renderTimeline(data) { const items=data.items||[]; const results=Object.values(data.results||{}); const html=[...items.map(e=>`<article class="event ${e.kind==='error'?'error':e.kind==='message'?'message':''}"><div class="event-kind">${escapeHtml(e.kind||'event')}</div>${escapeHtml(contentText(e.content))}</article>`), ...results.map(r=>`<article class="event"><div class="event-kind">result · ${escapeHtml(r.status||'')}</div>${escapeHtml(JSON.stringify(r.output||r.summary||r))}</article>`)]; $('timeline').innerHTML=html.join('')||'<p class="empty">No events yet.</p>'; }
async function refreshDirectory(path) { const t=selectedTarget(); if(!t)return; try { const data=await api(`/v1/sessions/${encodeURIComponent(state.username)}/${encodeURIComponent(t.device)}/${encodeURIComponent(t.session)}/directory?path=${encodeURIComponent(path)}`); state.cwd=data.path||path; $('cwd').textContent=state.cwd; $('directory').innerHTML=(data.entries||[]).map(e=>`<div class="entry"><span class="entry-name">${e.kind==='directory'?'[dir]':'[file]'} ${escapeHtml(e.name)}</span>${e.kind==='directory'?`<button data-path="${escapeHtml(e.path||e.relative_path)}">Open</button>`:''}</div>`).join('')||'<p class="empty">Empty directory.</p>'; document.querySelectorAll('.entry button').forEach(b=>b.onclick=()=>sendCwd(b.dataset.path)); } catch(e){showError(e.message);} }
async function sendCwd(path) { const t=selectedTarget(); if(!t)return; try { await api(`/v1/sessions/${encodeURIComponent(state.username)}/${encodeURIComponent(t.device)}/${encodeURIComponent(t.session)}/commands`, {method:'POST',body:JSON.stringify({username:state.username,device_id:t.device,session_id:t.session,type:'set_cwd',payload:{path}})}); await refreshSession(); } catch(e){showError(e.message);} }
async function sendCommand(event) { event.preventDefault(); const t=selectedTarget(); const prompt=$('prompt').value.trim(); if(!t||!prompt)return; const tool=$('tool').value; const payload=tool==='shell'?{command:prompt}:{tool,prompt,mode:'exec',options:{sandbox:'workspace-write',approval:'never'}}; $('prompt').value=''; $('busyHint').textContent='sending'; try { await api(`/v1/sessions/${encodeURIComponent(state.username)}/${encodeURIComponent(t.device)}/${encodeURIComponent(t.session)}/commands`, {method:'POST',body:JSON.stringify({username:state.username,device_id:t.device,session_id:t.session,type:tool==='shell'?'run_shell':'run_ai',payload})}); await refreshSession(); } catch(e){showError(e.message);} finally {$('busyHint').textContent='';} }
async function control(type) { const t=selectedTarget(); if(!t)return; try { await api(`/v1/sessions/${encodeURIComponent(state.username)}/${encodeURIComponent(t.device)}/${encodeURIComponent(t.session)}/control`, {method:'POST',body:JSON.stringify({username:state.username,device_id:t.device,session_id:t.session,type,payload:{}})}); await refreshSession(); } catch(e){showError(e.message);} }
function contentText(c) { return c && typeof c==='object' ? (c.text || JSON.stringify(c)) : String(c||''); }
function escapeHtml(s) { return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
$('loginForm').onsubmit=async e=>{e.preventDefault(); showError(''); try { const r=await api('/v1/auth/login',{method:'POST',body:JSON.stringify({username:$('username').value,password:$('password').value})}); state.token=r.access_token; state.username=$('username').value; showApp(); await refreshDevices(); state.timer=setInterval(()=>{refreshDevices();refreshEvents();},2000); } catch(err){$('loginError').textContent=err.message;} };
$('logout').onclick=()=>{state.token=null;clearInterval(state.timer);location.reload();}; $('refreshDevices').onclick=refreshDevices; $('commandForm').onsubmit=sendCommand; $('cancel').onclick=()=>control('cancel'); $('end').onclick=()=>control('end_session'); $('parentDir').onclick=()=>sendCwd(state.cwd.split('/').slice(0,-1).join('/')||'/');
document.querySelectorAll('.tab').forEach(tab=>tab.onclick=()=>{document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('active',x===tab)); $('chatTab').classList.toggle('hidden',tab.dataset.tab!=='chat'); $('filesTab').classList.toggle('hidden',tab.dataset.tab!=='files');});
