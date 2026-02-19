const refreshBtn = document.getElementById('refreshBtn');
const vizSvg = document.getElementById('vizSvg');
const nodesContainer = document.getElementById('nodesContainer');
const detailTitle = document.getElementById('detailTitle');
const detailBody = document.getElementById('detailBody');
const rawJson = document.getElementById('rawJson');

// Apply stored theme from dashboard (so visualizer matches user's choice)
try{
  const t = localStorage.getItem('theme');
  if(t) document.body.setAttribute('data-theme', t);
}catch(e){ }

// Small helper renderers (self-contained so visualizer page doesn't depend on app.js)
function createList(arr){
  const ul = document.createElement('ul');
  for(const it of arr){ const li = document.createElement('li'); li.textContent = typeof it === 'object' ? JSON.stringify(it) : String(it); ul.appendChild(li); }
  return ul;
}
function createKV(obj){
  const wrap = document.createElement('div'); wrap.style.display='grid'; wrap.style.gridTemplateColumns='140px 1fr'; wrap.style.gap='6px';
  for(const k of Object.keys(obj)){ const key = document.createElement('div'); key.classList.add('muted'); key.textContent = toLabel(k);
    const val = document.createElement('div'); val.style.fontWeight='600'; val.textContent = formatValue(obj[k]); wrap.appendChild(key); wrap.appendChild(val); }
  return wrap;
}
function createTableAuto(rows){
  const table = document.createElement('table'); table.style.width='100%'; table.style.borderCollapse='collapse';
  if(!Array.isArray(rows) || rows.length===0){ const div = document.createElement('div'); div.textContent='No rows'; return div; }
  const keys = new Set(); for(const r of rows){ if(r && typeof r === 'object') Object.keys(r).forEach(k=>keys.add(k)); }
  const headers = Array.from(keys);
  const thead = document.createElement('thead'); const thr = document.createElement('tr');
  headers.forEach(h=>{ const th = document.createElement('th'); th.textContent = toLabel(h); th.style.textAlign='left'; th.style.padding='6px'; thr.appendChild(th); }); thead.appendChild(thr); table.appendChild(thead);
  const tbody = document.createElement('tbody');
  for(const r of rows){ const tr = document.createElement('tr'); for(const h of headers){ const td = document.createElement('td'); td.style.padding='6px'; let v = r && typeof r === 'object' ? (r[h] ?? '') : ''; if(Array.isArray(v)){ td.appendChild(createList(v)); } else if(typeof v === 'object' && v !== null){ td.textContent = JSON.stringify(v); } else { td.textContent = formatValue(v); } tr.appendChild(td); } tbody.appendChild(tr); }
  table.appendChild(tbody); return table;
}

async function fetchForViz(){
  // Try reusing last output from main dashboard (sessionStorage) first, otherwise try backend then fallback
  try{
    const stored = sessionStorage.getItem('agentic_last_output');
    if(stored){ window._viz_data_source = 'session'; return JSON.parse(stored); }
  }catch(_){ }

  // Try backend first, fallback to bundled sample
  let payload = {};
  try{ const p = await fetch('../examples/agentic_input.json'); if(p.ok) payload = await p.json(); }catch(e){}
  try{
    const resp = await fetch('http://localhost:8000/orchestrator/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    if(resp.ok){ const d = await resp.json(); window._viz_data_source = 'backend'; return normalize(d); }
  }catch(e){ /* ignore */ }
  const fb = await fetch('sample_output.json',{cache:'no-store'});
  const d = await fb.json(); window._viz_data_source = 'fallback'; return normalize(d);
}

function normalize(data){
  return { agents: data.node_outputs || data.agents || {}, kpis: data.kpis || {} };
}

function clearDiagram(){ nodesContainer.innerHTML = ''; vizSvg.innerHTML = ''; detailTitle.textContent='Select an agent'; detailBody.textContent='Click a node to view outputs'; rawJson.hidden=true; }

function renderViz(data){
  clearDiagram();
  const statusEl = document.getElementById('vizStatus');
  const agents = Object.keys(data.agents || {});
  // show source and agent count
  try{ if(statusEl) statusEl.textContent = `Source: ${window._viz_data_source||'unknown'} — Agents: ${agents.length}`; }catch(_){ }
  if(agents.length===0){ detailBody.textContent='No agents found in payload/output'; return; }

  // layout: horizontal evenly spaced
  const width = nodesContainer.clientWidth || 800;
  const height = nodesContainer.clientHeight || 300;
  const step = Math.max(160, Math.floor((width-80)/agents.length));

  // create SVG lines between nodes
  vizSvg.setAttribute('width','100%'); vizSvg.setAttribute('height','100%');

  agents.forEach((name,i)=>{
    const nodeWrap = document.createElement('div');
    nodeWrap.className = 'agent-node status-unknown';
    nodeWrap.style.flex = '0 0 160px';
    nodeWrap.dataset.name = name;
    const title = document.createElement('div'); title.className='title'; title.textContent = toLabel(name);
    nodeWrap.appendChild(title);

    const out = data.agents[name] || {};
    console.debug('Viz node raw', name, out);
    const status = out.status || (out.output ? 'success' : 'unknown');
    nodeWrap.classList.remove('status-unknown','status-success','status-failed');
    nodeWrap.classList.add(status==='success' ? 'status-success' : (status==='failed' ? 'status-failed' : 'status-unknown'));

    // No meta/overview label on nodes — nodes show only title and hero KPIs

    // show hero KPIs inside node
    const kpis = extractKPIs(out, name);
    if(!kpis || kpis.length===0){
      const o = out && out.output ? out.output : out || {};
      console.warn('No KPIs found for', name, ' — output keys:', Object.keys(o));
    }
    console.debug('Viz KPI for', name, kpis);
    if(kpis && kpis.length){
      const hero = document.createElement('div'); hero.className = 'hero';
      for(const kp of kpis){
        const kpEl = document.createElement('div'); kpEl.className = 'kp';
        const lbl = document.createElement('div'); lbl.className='klabel'; lbl.textContent = kp.label;
        const val = document.createElement('div'); val.className='kval'; val.textContent = formatValue(kp.value);
        kpEl.appendChild(lbl); kpEl.appendChild(val); hero.appendChild(kpEl);
      }
      nodeWrap.appendChild(hero);
    }

    nodeWrap.addEventListener('click', ()=>{ showDetails(name, out); highlightNode(name); });

    nodesContainer.appendChild(nodeWrap);
  });

  // draw connectors using SVG paths between centers of nodes
  requestAnimationFrame(()=>{
    const nodeEls = Array.from(nodesContainer.querySelectorAll('.agent-node'));
    vizSvg.innerHTML = '';
    for(let i=0;i<nodeEls.length-1;i++){
      const a = nodeEls[i].getBoundingClientRect();
      const b = nodeEls[i+1].getBoundingClientRect();
      const parentRect = nodesContainer.getBoundingClientRect();
      const x1 = a.left + a.width/2 - parentRect.left;
      const y1 = a.top + a.height/2 - parentRect.top;
      const x2 = b.left + b.width/2 - parentRect.left;
      const y2 = b.top + b.height/2 - parentRect.top;
      const path = document.createElementNS('http://www.w3.org/2000/svg','path');
      const dx = Math.abs(x2-x1)/2;
      const d = `M ${x1} ${y1} C ${x1+dx} ${y1} ${x2-dx} ${y2} ${x2} ${y2}`;
      path.setAttribute('d',d);
      path.setAttribute('fill','none'); path.setAttribute('stroke-width','2');
      path.classList.add('connector');
      vizSvg.appendChild(path);
    }
  });
}

function highlightNode(name){ Array.from(nodesContainer.querySelectorAll('.agent-node')).forEach(n=>{ n.style.opacity = n.dataset.name===name ? '1' : '0.38'; }); }

function showDetails(name,out){
  detailTitle.textContent = toLabel(name);
  detailBody.innerHTML = '';
  rawJson.hidden = true;

  // Hero KPIs
  const kpis = extractKPIs(out, name);
    if(kpis && kpis.length){
    const hero = document.createElement('div'); hero.style.display='flex'; hero.style.gap='8px'; hero.style.marginBottom='10px';
    for(const kp of kpis){
      const kpEl = document.createElement('div'); kpEl.classList.add('kp-card');
      const lbl = document.createElement('div'); lbl.style.fontSize='12px'; lbl.classList.add('muted'); lbl.textContent = kp.label;
      const val = document.createElement('div'); val.style.fontWeight='700'; val.style.marginTop='6px'; val.textContent = formatValue(kp.value);
      kpEl.appendChild(lbl); kpEl.appendChild(val); hero.appendChild(kpEl);
    }
    detailBody.appendChild(hero);
  }

  // Summary / primitive keys
  const o = out && out.output ? out.output : (out || {});
  const primKeys = Object.keys(o).filter(k=>{ const v=o[k]; return v===null || ['string','number','boolean'].includes(typeof v); });
  if(primKeys.length){
    const kv = document.createElement('div'); kv.style.display='grid'; kv.style.gridTemplateColumns='140px 1fr'; kv.style.gap='6px';
    for(const k of primKeys){ const keyEl = document.createElement('div'); keyEl.classList.add('muted'); keyEl.textContent = toLabel(k);
      const valEl = document.createElement('div'); valEl.style.fontWeight='600'; valEl.textContent = formatValue(o[k]); kv.appendChild(keyEl); kv.appendChild(valEl); }
    detailBody.appendChild(kv);
  }

  // Complex props (arrays/objects) as collapsible sections and small tables/lists
  for(const k of Object.keys(o)){
    const v = o[k];
    if(v===null || ['string','number','boolean'].includes(typeof v)) continue;
    const section = document.createElement('div'); section.style.marginTop='10px';
    const header = document.createElement('div'); header.style.display='flex'; header.style.justifyContent='space-between'; header.style.alignItems='center';
    const htitle = document.createElement('div'); htitle.style.fontWeight='600'; htitle.textContent = toLabel(k);
    const toggle = document.createElement('button'); toggle.textContent = 'Show'; toggle.classList.add('toggle-btn');
    header.appendChild(htitle); header.appendChild(toggle); section.appendChild(header);

    const content = document.createElement('div'); content.style.marginTop='8px'; content.hidden = true;

    if(Array.isArray(v)){
      // if array of objects -> table
      if(v.length && v.every(it => typeof it === 'object')){
        content.appendChild(createTableAuto(v));
      } else {
        content.appendChild(createList(v));
      }
    } else if(typeof v === 'object'){
      // show key/primitive pairs and allow expand raw
      const prim = {};
      for(const kk of Object.keys(v)){ if(v[kk]===null || ['string','number','boolean'].includes(typeof v[kk])) prim[kk]=v[kk]; }
      if(Object.keys(prim).length) content.appendChild(createKV(prim));
      // small preview for nested arrays
      if(Object.keys(v).length===0) content.appendChild(document.createTextNode('Empty object'));
    }

    toggle.addEventListener('click', ()=>{ if(content.hidden){ content.hidden=false; toggle.textContent='Hide'; rawJson.hidden=true; } else { content.hidden=true; toggle.textContent='Show'; } });
    section.appendChild(content);
    detailBody.appendChild(section);
  }

  // add a small button to view raw json
  const rawBtn = document.createElement('button'); rawBtn.textContent='View Raw JSON'; rawBtn.style.marginTop='12px'; rawBtn.style.padding='6px 10px'; rawBtn.style.borderRadius='6px'; rawBtn.style.cursor='pointer';
  rawBtn.addEventListener('click', ()=>{ rawJson.hidden = !rawJson.hidden; if(!rawJson.hidden){ rawJson.textContent = JSON.stringify(out, null, 2); } });
  detailBody.appendChild(rawBtn);
}

function toLabel(s){ return s.replace(/[_-]/g,' ').replace(/\b\w/g,c=>c.toUpperCase()); }

function formatValue(v){
  if(v === null || v === undefined) return '—';
  if(typeof v === 'number') return v.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
  return String(v);
}

// extract small set of KPIs from agent output for hero display
function extractKPIs(out, name){
  const o = out && out.output ? out.output : (out || {});
  const res = [];
  const pushIf = (label, val)=>{ if(val!==undefined && val!==null) res.push({label, value: val}); };

  // Cash position: total_balance & account_count
  if(o.overview && (o.overview.total_balance !== undefined || o.overview.per_account !== undefined || o.overview.account_count !== undefined)){
    if(typeof o.overview.total_balance === 'number') pushIf('Total Balance', o.overview.total_balance);
    else if(typeof o.total_balance === 'number') pushIf('Total Balance', o.total_balance);
    else if(o.overview.per_account && typeof o.overview.per_account === 'object'){
      let sum=0, found=false; for(const k of Object.keys(o.overview.per_account)){ const v=o.overview.per_account[k]; const bal = v && (v.balance ?? v.amount); if(typeof bal==='number'){ sum+=bal; found=true; } }
      if(found) pushIf('Total Balance', sum);
    }
    if(typeof o.overview.account_count === 'number') pushIf('Account Count', o.overview.account_count);
    else if(o.overview.per_account) pushIf('Account Count', Array.isArray(o.overview.per_account)? o.overview.per_account.length : Object.keys(o.overview.per_account).length);
    if(res.length) return res.slice(0,3);
  }

  // Cashflow: inflows/outflows/net
  if(o.total_inflows !== undefined || o.total_outflows !== undefined || o.net_forecast !== undefined || o.net !== undefined){
    pushIf('Inflows', o.total_inflows ?? o.total_inflow);
    pushIf('Outflows', o.total_outflows ?? o.total_outflow);
    pushIf('Net', o.net_forecast ?? o.net ?? o.ending_cash);
    if(res.length) return res.slice(0,3);
  }

  // Liquidity
  if(o.overview && (o.overview.total_balance !== undefined || o.overview.available !== undefined)){
    if(typeof o.overview.total_balance === 'number') pushIf('Total Balance', o.overview.total_balance);
    if(typeof o.overview.available === 'number') pushIf('Available', o.overview.available);
    if(res.length) return res.slice(0,3);
  }

  // Sweep
  if(o.summary && (o.summary.total_excess !== undefined || o.summary.moves_count !== undefined)){
    pushIf('Total Excess', o.summary.total_excess ?? o.summary.excess ?? o.summary.total);
    pushIf('Moves', o.summary.moves_count ?? (o.moves? o.moves.length : undefined));
    if(res.length) return res.slice(0,3);
  }

  // Investment
  if(o.summary && (o.summary.total_allocated !== undefined || o.summary.remaining_cash !== undefined)){
    pushIf('Allocated', o.summary.total_allocated ?? o.summary.allocated);
    pushIf('Remaining', o.summary.remaining_cash ?? o.summary.remaining);
    if(res.length) return res.slice(0,3);
  }

  // Reconciliation
  if(o.overview && (o.overview.matched_count !== undefined || o.overview.unmatched_bank !== undefined || o.overview.exceptions !== undefined)){
    if(typeof o.overview.matched_count === 'number') pushIf('Matched', o.overview.matched_count);
    if(Array.isArray(o.overview.unmatched_bank)) pushIf('Unmatched Bank', o.overview.unmatched_bank.length);
    if(Array.isArray(o.overview.exceptions)) pushIf('Exceptions', o.overview.exceptions.length);
    if(res.length) return res.slice(0,3);
  }

  // Reporting dashboard
  if(o.dashboard && typeof o.dashboard.total_balance === 'number'){
    pushIf('Total Balance', o.dashboard.total_balance);
    if(res.length) return res.slice(0,3);
  }

  // Cash forecast: daily net
  if(o.forecast && Array.isArray(o.forecast.daily) && o.forecast.daily.length){
    pushIf('Day0 Net', o.forecast.daily[0].net ?? o.forecast.daily[0].value);
    if(res.length) return res.slice(0,3);
  }

  // fallback: deep numeric search
  const found = findNumericFields(o, 3);
  for(const f of found) pushIf(toLabel(f.key), f.value);
  return res.slice(0,3);
}

// recursively find numeric fields (key path and value) up to `limit`
function findNumericFields(obj, limit){
  const results = [];
  const visited = new Set();
  function walk(cur, path){
    if(results.length>=limit) return;
    if(cur && typeof cur === 'object' && !visited.has(cur)){
      visited.add(cur);
      for(const k of Object.keys(cur)){
        const v = cur[k];
        const p = path ? (path + '.' + k) : k;
        if(typeof v === 'number'){
          results.push({key:p, value:v}); if(results.length>=limit) return;
        }else if(Array.isArray(v)){
          // prefer numeric in first array element
          if(v.length && typeof v[0] === 'number'){ results.push({key:p, value:v[0]}); if(results.length>=limit) return; }
          for(const it of v){ if(typeof it === 'object') walk(it, p); if(results.length>=limit) return; }
        }else if(typeof v === 'object' && v !== null){
          walk(v, p); if(results.length>=limit) return;
        }
      }
    }
  }
  walk(obj, '');
  return results;
}

refreshBtn.addEventListener('click', async ()=>{ refreshBtn.disabled=true; refreshBtn.textContent='Loading...'; try{ const d = await fetchForViz(); renderViz(d); }catch(e){ detailBody.textContent = 'Error: '+e.message } finally{ refreshBtn.disabled=false; refreshBtn.textContent='Fetch / Refresh' } });

// initial render from bundled sample
(async ()=>{ try{ const d = await fetchForViz(); renderViz(d); }catch(e){ detailBody.textContent = 'Failed to load initial data: '+e.message; } })();
