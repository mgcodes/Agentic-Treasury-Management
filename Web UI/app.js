const fetchBtn = document.getElementById('fetchBtn');
const kpiBar = document.getElementById('kpiBar');
const agentsList = document.getElementById('agentsList');
const lastUpdated = document.getElementById('lastUpdated');
const spinner = document.getElementById('spinner');

// Theme initialization and toggle
function initTheme(){
  try{
    const t = localStorage.getItem('theme') || 'light';
    document.body.setAttribute('data-theme', t);
    const btn = document.getElementById('themeToggle');
    if(btn) btn.textContent = t === 'dark' ? 'Light' : 'Dark';
    if(btn) btn.addEventListener('click', ()=>{
      const cur = document.body.getAttribute('data-theme') || 'light';
      const next = cur === 'dark' ? 'light' : 'dark';
      document.body.setAttribute('data-theme', next);
      localStorage.setItem('theme', next);
      btn.textContent = next === 'dark' ? 'Light' : 'Dark';
    });
  }catch(e){/* ignore */}
}

document.addEventListener('DOMContentLoaded', initTheme);

function showSpinner(){ if(spinner){ spinner.hidden = false; spinner.setAttribute('aria-hidden','false'); } }
function hideSpinner(){ if(spinner){ spinner.hidden = true; spinner.setAttribute('aria-hidden','true'); } }

async function fetchSample(){
  // Try calling backend orchestrator endpoint using example payload, otherwise fall back to bundled sample
  try{
    showSpinner();
    // load example payload if available - prefer heavy payload then agentic_input
    let payload = {};
    try{
      // try heavy payload first
      let p = await fetch('../examples/heavy_payload.json');
      if(p.ok){ payload = await p.json(); console.debug('Using examples/heavy_payload.json'); }
      else {
        p = await fetch('../examples/agentic_input.json');
        if(p.ok){ payload = await p.json(); console.debug('Using examples/agentic_input.json'); }
      }
    }catch(_){ /* ignore */ }

    // Try backend endpoint at localhost:8000 only. Avoid same-origin POSTs
    // which will return 404 when the UI is served by a static server.
    const endpoints = [ 'http://localhost:8000/orchestrator/run' ];
    let resp = null;
    for(const url of endpoints){
      try{
        resp = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
        // If server explicitly rejects POST (e.g. static file server returns 501), try next.
        if(resp && resp.status === 501){
          resp = null; // ignore and continue
          continue;
        }
        break; // got a response (may be ok or an error) - exit loop
      }catch(err){
        // network error - try next endpoint
        resp = null;
        continue;
      }
    }

    if(resp && resp.ok){
      const data = await resp.json();
      // If backend returned node_outputs, normalize to same shape as sample_output
      const out = {
        kpis: data.kpis || {},
        agents: data.node_outputs || data.agents || {}
      };
      try{ sessionStorage.setItem('agentic_last_output', JSON.stringify(out)); }catch(_){ }
      renderDashboard(out);
      lastUpdated.textContent = 'Last: ' + new Date().toLocaleString();
      hideSpinner();
      return;
    }

    // fallback to bundled sample file
    const fallback = await fetch('sample_output.json', {cache:'no-store'});
    if(!fallback.ok) throw new Error('Failed to fetch fallback sample JSON');
    const data = await fallback.json();
    // normalize fallback shape (some saved outputs use `node_outputs` at top-level)
    const out = {
      kpis: data.kpis || {},
      agents: data.node_outputs || data.agents || {}
    };
    try{ sessionStorage.setItem('agentic_last_output', JSON.stringify(out)); }catch(_){ }
    renderDashboard(out);
    lastUpdated.textContent = 'Last: ' + new Date().toLocaleString();
    hideSpinner();
  }catch(e){
    hideSpinner();
    alert('Error fetching orchestrator/sample: ' + e.message);
  }
}

function renderDashboard(data){
  // Prefer one discovered non-zero numeric KPI per agent; fallback to broader discovery, provided KPIs, or computed KPIs
  let kpis = {};
  // try per-agent first so each agent contributes at most one KPI
  kpis = discoverOneKPIperAgent(data.agents || {});
  // if that produced nothing, fall back to a broader discovery across agents (top N)
  if(!kpis || Object.keys(kpis).length===0){
    kpis = discoverKPIs(data.agents || {}, 6);
  }
  // then fall back to explicit kpis from the run
  if(!kpis || Object.keys(kpis).length===0){
    kpis = data.kpis || {};
  }
  // final fallback: compute heuristics
  if(!kpis || Object.keys(kpis).length===0){
    kpis = computeKPIs(data.agents || {});
  }
  renderKPIs(kpis || {});
  renderAgents(data.agents || {});
}

// Compute common KPIs from agent outputs when explicit KPIs are not provided
function computeKPIs(agents){
  const get = (obj, ...path)=>{
    try{ let cur = obj; for(const p of path){ if(cur==null) return undefined; cur = cur[p]; } return cur; }catch{ return undefined; }
  };

  const total_from_paths = [
    ['reporting','output','dashboard','total_balance'],
    ['liquidity','output','overview','total_balance'],
    ['cash_position','output','overview','total_balance']
  ];
  let total_cash = undefined;
  for(const p of total_from_paths){ const v = get(agents, ...p); if(typeof v === 'number'){ total_cash = v; break; } }

  // projected cash 7d: try reporting forecast then cash_forecast
  const forecast_daily = get(agents,'reporting','output','dashboard','forecast','daily') || get(agents,'cash_forecast','output','forecast','daily');
  let projected_cash_7d = undefined;
  if(Array.isArray(forecast_daily)){
    projected_cash_7d = forecast_daily.slice(0,7).reduce((s,d)=>s + (d && typeof d.net==='number'? d.net:0), 0);
  }

  // net investments: sum positions amounts or use provided net
  let net_investments = undefined;
  const inv_positions = get(agents,'investment','output','positions') || get(agents,'investment','output','holdings');
  if(Array.isArray(inv_positions)){
    net_investments = inv_positions.reduce((s,p)=> s + (p && (p.amount||p.balance||p.value) ? (p.amount||p.balance||p.value):0), 0);
  }else{
    const inv_net = get(agents,'investment','output','net') || get(agents,'investment','output','net_investments');
    if(typeof inv_net === 'number') net_investments = inv_net;
  }

  // liquidity ratio: available / required if present
  let liquidity_ratio = undefined;
  const available = get(agents,'liquidity','output','available') || get(agents,'liquidity','output','overview','available') || get(agents,'liquidity','output','overview','total_balance');
  const required = get(agents,'liquidity','output','required') || get(agents,'liquidity','output','overview','required');
  if(typeof available==='number' && typeof required==='number' && required!==0){ liquidity_ratio = available/required; }

  // sweep amount
  let sweep_amount = get(agents,'sweep','output','swept') || get(agents,'sweep','output','summary','total_excess') || get(agents,'sweep','output','summary','swept');

  return {
    total_cash: total_cash ?? null,
    projected_cash_7d: projected_cash_7d ?? null,
    net_investments: net_investments ?? null,
    liquidity_ratio: liquidity_ratio ?? null,
    sweep_amount: sweep_amount ?? null,
  };
}

function discoverKPIs(agents, limit=6){
  const results = {};
  const seen = new Set();
  function walk(obj, prefix){
    if(results && Object.keys(results).length>=limit) return;
    if(obj && typeof obj === 'object'){
      for(const k of Object.keys(obj)){
        if(k === 'human_summary' || k === 'llm' || k === 'summary' || k === 'output') continue;
        const v = obj[k];
        const path = prefix ? (prefix + '.' + k) : k;
        if(typeof v === 'number' && !isNaN(v) && v !== 0){
          const label = toLabel(path);
          if(!seen.has(label)){
            results[label] = v;
            seen.add(label);
            if(Object.keys(results).length>=limit) return;
          }
        } else if(Array.isArray(v)){
          for(const it of v.slice(0,3)){ walk(it, path); if(Object.keys(results).length>=limit) return; }
        } else if(typeof v === 'object' && v !== null){
          walk(v, path); if(Object.keys(results).length>=limit) return;
        }
      }
    }
  }
  for(const name of Object.keys(agents || {})){
    if(Object.keys(results).length>=limit) break;
    const node = agents[name];
    const out = node && node.output ? node.output : node;
    walk(out, name);
  }
  return results;
}

// Discover one non-zero numeric KPI per agent
function discoverOneKPIperAgent(agents){
  const kpis = {};
  for(const name of Object.keys(agents || {})){
    try{
      const node = agents[name];
      const out = node && node.output ? node.output : node || {};
      // depth-first search for first numeric non-zero value, then any numeric, then counts/status
      let found = null;
      const visited = new Set();
      function walk(obj, path, allowZero=false){
        if(found) return;
        if(obj && typeof obj === 'object' && !visited.has(obj)){
          visited.add(obj);
          for(const k of Object.keys(obj)){
            if(k === 'human_summary' || k === 'llm' || k === 'summary') continue;
            const v = obj[k];
            const p = path ? (path + '.' + k) : k;
            if(typeof v === 'number' && !isNaN(v) && (allowZero ? true : v !== 0)){
              found = {label: toLabel(k), value: v}; return;
            }
            if(Array.isArray(v)){
              // prefer numeric values inside arrays first
              for(const it of v.slice(0,10)){ walk(it, p, allowZero); if(found) return; }
              // fallback: use array length as a KPI
              if(!found && v.length >= 0){ found = {label: toLabel(k + ' count'), value: v.length}; return; }
            } else if(typeof v === 'object' && v !== null){ walk(v, p, allowZero); if(found) return; }
          }
        }
      }
      // first pass: prefer non-zero numeric
      walk(out, '', false);
      // second pass: accept numeric zeros or any numeric
      if(!found) walk(out, '', true);
      // third: common counts or status fallbacks
      if(!found){
        if(Array.isArray(out.accounts) && out.accounts.length) found = {label: 'Accounts', value: out.accounts.length};
        else if(Array.isArray(out.positions) && out.positions.length) found = {label: 'Positions', value: out.positions.length};
        else if(Array.isArray(out.forecast) && out.forecast.length) found = {label: 'Forecast', value: out.forecast.length};
        else if(Array.isArray(out.forecast_7d) && out.forecast_7d.length) found = {label: 'Forecast 7d', value: out.forecast_7d.length};
        else if(out && out.status) found = {label: 'Status', value: String(out.status)};
      }
      const agentLabel = toLabel(name);
      if(found){
        kpis[`${agentLabel}` + (found.label ? (' — ' + found.label) : '')] = found.value;
      } else {
        kpis[agentLabel] = '—';
      }
    }catch(e){
      kpis[toLabel(name)] = '—';
    }
  }
  return kpis;
}

function renderKPIs(kpis){
  const container = kpiBar.querySelector('.kpi-scroll');
  container.innerHTML = '';
  const entries = Object.entries(kpis);
  if(entries.length===0){
    container.innerHTML = '<div class="kpi">No KPIs available</div>';
    return;
  }
  for(const [key,val] of entries){
    const card = document.createElement('div');
    card.className = 'kpi';
    card.innerHTML = `<div class="label">${toLabel(key)}</div><div class="value">${formatValue(val)}</div>`;
    container.appendChild(card);
  }
}

function renderAgents(agents){
  agentsList.innerHTML = '';
  const menu = document.getElementById('agentMenu');
  menu.innerHTML = '';
  // Exclude reporting and llm outputs from the UI as requested
  const names = Object.keys(agents || {}).filter(n => n !== 'reporting' && n !== 'llm');
  if(names.length===0){
    agentsList.innerHTML = '<div class="agent-card">No agent outputs found</div>';
    return;
  }

  // create menu buttons
  const allBtn = document.createElement('button');
  allBtn.textContent = 'All';
  allBtn.className = 'active';
  allBtn.addEventListener('click',()=>{ setActiveMenu(null); renderCards(names); });
  menu.appendChild(allBtn);

  for(const name of names){
    const btn = document.createElement('button');
    btn.textContent = toLabel(name);
    btn.addEventListener('click',()=>{ setActiveMenu(name); renderCards([name]); });
    menu.appendChild(btn);
  }

  function setActiveMenu(activeName){
    Array.from(menu.querySelectorAll('button')).forEach(b=>{
      if(activeName===null && b.textContent==='All') b.classList.add('active');
      else if(activeName!==null && b.textContent===toLabel(activeName)) b.classList.add('active');
      else b.classList.remove('active');
    });
  }

  // render all by default
  renderCards(names);

  function renderCards(list){
    agentsList.innerHTML = '';
    for(const name of list){
      const rawOut = agents[name];
      // shallow-safe deep copy so we can remove presentation-only keys
      let out = rawOut;
      try{ out = JSON.parse(JSON.stringify(rawOut)); }catch(e){ out = rawOut; }
      // Remove large human-readable summaries from dashboard rendering
      if(out && out.output && out.output.human_summary) delete out.output.human_summary;
      const card = document.createElement('div');
      card.className = 'agent-card';
      // simple status formatter — show original status text (capitalized) when displayed
      function displayStatus(s){
        if(!s) return 'Unknown';
        const str = String(s);
        return str.charAt(0).toUpperCase() + str.slice(1);
      }
      // Hide the status label when status is 'success' or 'ok' to keep dashboard concise
      const showStatus = out && out.status && !['success','ok'].includes(String(out.status).toLowerCase());
      const statusPart = showStatus ? `Status: ${displayStatus(out.status)} • ` : '';
      card.innerHTML = `<h3>${toLabel(name)}</h3><div class="meta">${statusPart}Agent: ${name}</div><div class="body"></div>`;
      const body = card.querySelector('.body');

      // Render content based on agent type
      switch(name){
        case 'cash_position_agent':
          body.appendChild(createTable(['Account','Balance'], out.accounts || []));
          break;
        case 'cashflow_agent':
          body.appendChild(createKV({Inflows: out.inflows, Outflows: out.outflows, Net: out.net}));
          break;
        case 'cashflow_forecast_agent':
          body.appendChild(createTable(['Date','Net'], out.forecast_7d || []));
          break;
        case 'investment_agent':
          body.appendChild(createTable(['Ticker','Amount','Maturity'], out.positions || []));
          break;
        case 'liquidity_agent':
          body.appendChild(createKV({Available: out.available, Required: out.required}));
          break;
        case 'reconciliation_agent':
          body.appendChild(createKV({Unmatched: out.unmatched_items}));
          if(Array.isArray(out.details)) body.appendChild(createTable(['ID','Reason'], out.details));
          break;
        case 'reporting_agent':
          body.appendChild(createList(out.reports || []));
          break;
        case 'sweep_agent':
          body.appendChild(createKV({Swept: out.swept}));
          if(Array.isArray(out.targets)) body.appendChild(createList(out.targets));
          break;
        default:
          // Render unknown structures in a readable way (tables / kv / lists)
          body.appendChild(renderData(out));
      }

      agentsList.appendChild(card);
    }
  }
}

// helpers
function createTable(headers, rows){
  const table = document.createElement('table');
  table.className = 'table';
  const thead = document.createElement('thead');
  const thr = document.createElement('tr');
  headers.forEach(h=>{ const th = document.createElement('th'); th.textContent = h; thr.appendChild(th); });
  thead.appendChild(thr);
  table.appendChild(thead);
  const tbody = document.createElement('tbody');
  for(const r of rows){
    const tr = document.createElement('tr');
    for(const h of headers){
      const key = h.toLowerCase();
      const td = document.createElement('td');
      // map header to property names heuristically
      if(key.includes('account')) td.textContent = r.account || r.acc || '';
      else if(key.includes('balance')|| key.includes('amount')|| key.includes('net')) td.textContent = formatValue(r.balance ?? r.amount ?? r.net ?? r[key] ?? r[key.trim()]);
      else if(key.includes('date')) td.textContent = r.date || r[0] || '';
      else if(key.includes('ticker')) td.textContent = r.ticker || '';
      else if(key.includes('maturity')) td.textContent = r.maturity || '';
      else if(key.includes('reason')) td.textContent = r.reason || '';
      else td.textContent = r[key] ?? '';
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  return table;
}

function createKV(obj){
  const wrap = document.createElement('div');
  wrap.className = 'kv';
  for(const k of Object.keys(obj)){
    const key = document.createElement('div'); key.className = 'k'; key.textContent = k;
    const val = document.createElement('div'); val.className = 'v'; val.textContent = formatValue(obj[k]);
    wrap.appendChild(key); wrap.appendChild(val);
  }
  return wrap;
}

function createList(arr){
  const ul = document.createElement('ul');
  for(const it of arr){ const li = document.createElement('li'); li.textContent = typeof it === 'object' ? JSON.stringify(it) : String(it); ul.appendChild(li); }
  return ul;
}

// Create a table automatically from an array of objects (headers = union of keys)
function createTableAuto(rows){
  const table = document.createElement('table');
  table.className = 'table';
  const thead = document.createElement('thead');
  const tbody = document.createElement('tbody');
  if(!Array.isArray(rows) || rows.length===0){
    const div = document.createElement('div'); div.textContent = 'No rows'; return div;
  }
  const keys = new Set();
  for(const r of rows){ if(r && typeof r === 'object') Object.keys(r).forEach(k=>keys.add(k)); }
  const headers = Array.from(keys);
  const thr = document.createElement('tr'); headers.forEach(h=>{ const th = document.createElement('th'); th.textContent = toLabel(h); thr.appendChild(th); });
  thead.appendChild(thr);
  for(const r of rows){
    const tr = document.createElement('tr');
    for(const h of headers){ const td = document.createElement('td');
      let v = r && typeof r === 'object' ? (r[h] ?? '') : '';
      if(Array.isArray(v)){
        td.appendChild(createList(v));
      }else if(typeof v === 'object' && v !== null){
        td.appendChild(renderData(v));
      }else{
        td.textContent = formatValue(v);
      }
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  table.appendChild(thead); table.appendChild(tbody);
  return table;
}

// Render arbitrary data (primitives, arrays, objects) into DOM nodes
function renderData(data){
  if(data === null || data === undefined) return document.createTextNode('');
  if(Array.isArray(data)){
    // array of primitives?
    if(data.every(d => typeof d !== 'object')) return createList(data);
    // array of objects -> table
    if(data.every(d => typeof d === 'object')) return createTableAuto(data);
    const wrap = document.createElement('div');
    for(const it of data) wrap.appendChild(renderData(it));
    return wrap;
  }
  if(typeof data === 'object'){
    const wrap = document.createElement('div');
    // show primitive props as kv, complex props as sub-sections
    const prim = {};
    for(const k of Object.keys(data)){
      if(k === 'human_summary') continue; // omit large LLM summaries from dashboard
      const v = data[k];
      if(v === null || ['string','number','boolean'].includes(typeof v)) prim[k]=v;
    }
    if(Object.keys(prim).length) wrap.appendChild(createKV(prim));
    for(const k of Object.keys(data)){
      if(k === 'human_summary') continue;
      const v = data[k];
      if(v === null || ['string','number','boolean'].includes(typeof v)) continue;
      const section = document.createElement('div');
      const h = document.createElement('div'); h.style.fontWeight='600'; h.style.marginTop='8px'; h.textContent = toLabel(k);
      section.appendChild(h);
      section.appendChild(renderData(v));
      wrap.appendChild(section);
    }
    return wrap;
  }
  // primitive
  return document.createTextNode(formatValue(data));
}

function toLabel(s){
  return s.replace(/[_-]/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
}

function formatValue(v){
  if(typeof v === 'number') return v.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
  return String(v);
}

fetchBtn.addEventListener('click', fetchSample);
