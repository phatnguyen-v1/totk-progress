'use strict';

// key must match savefile.CATEGORIES; data = map_data.json key
const CATS = [
  { key: 'hidden_korok', data: 'hidden_koroks', label: 'Korok seeds (hidden)', icon: 'korok_hidden', group: 'Koroks & shrines', size: 20 },
  { key: 'carry_korok', data: 'carry_koroks', label: 'Korok friends', icon: 'korok_carry', group: 'Koroks & shrines', size: 22 },
  { key: 'shrine', data: 'shrines', label: 'Shrines', icon: 'shrine', group: 'Koroks & shrines' },
  { key: 'lightroot', data: 'lightroots', label: 'Lightroots', icon: 'lightroot', group: 'Koroks & shrines' },
  { key: 'cave', data: 'caves', label: 'Caves', icon: 'cave', group: 'Places' },
  { key: 'bubbul', data: 'bubbuls', label: 'Bubbul frogs', icon: 'bubbul', group: 'Places' },
  { key: 'well', data: 'wells', label: 'Wells', icon: 'well', group: 'Places' },
  { key: 'chasm', data: 'chasms', label: 'Chasms', icon: 'chasm', group: 'Places' },
  { key: 'location', data: 'locations', label: 'Locations', icon: 'location', group: 'Places', off: true },
  { key: 'hinox', data: 'hinoxes', label: 'Hinoxes', icon: 'hinox', group: 'Bosses' },
  { key: 'talus', data: 'taluses', label: 'Taluses', icon: 'talus', group: 'Bosses' },
  { key: 'molduga', data: 'moldugas', label: 'Moldugas', icon: 'molduga', group: 'Bosses' },
  { key: 'flux_construct', data: 'flux_constructs', label: 'Flux Constructs', icon: 'flux_construct', group: 'Bosses' },
  { key: 'frox', data: 'froxes', label: 'Froxes', icon: 'frox', group: 'Bosses' },
  { key: 'gleeok', data: 'gleeoks', label: 'Gleeoks', icon: 'gleeok', group: 'Bosses' },
  { key: 'sages_will', data: 'sages_wills', label: "Sage's Wills", icon: 'sages_will', group: 'Collectibles' },
  { key: 'old_map', data: 'old_maps', label: 'Old maps', icon: 'old_map', group: 'Collectibles' },
  { key: 'addison_sign', data: 'addison_signposts', label: "Addison's signs", icon: 'addison_sign', group: 'Collectibles' },
  { key: 'schema_stone', data: 'schema_stones', label: 'Schema stones', icon: 'schema_stone', group: 'Collectibles' },
  { key: 'yiga_schematic', data: 'yiga_schematics', label: 'Yiga schematics', icon: 'yiga_schematic', group: 'Collectibles' },
];
const SKY_Y = 750, DEPTHS_Y = -50, SIZE = 1500;
const POLL_MS = 4000;

const store = {
  get(k, d) { try { const v = localStorage.getItem('totkp.' + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem('totkp.' + k, JSON.stringify(v)); } catch {} },
};

const state = {
  data: null,
  progress: null,
  slot: store.get('slot', 'latest'),
  layer: store.get('layer', 'surface'),
  mode: store.get('mode', 'missing'),
  off: new Set(store.get('off', CATS.filter(c => c.off).map(c => c.key))),
  search: '',
  lastMtime: null,
  tab: store.get('tab', 'map'),
  qmode: store.get('qmode', 'active'),
  qtargets: store.get('qtargets', true),
  qstarts: store.get('qstarts', false),
  quests: null,      // definitions from /data/quests.json
  openQuest: null,
};
const QCATS = [
  ['main', 'Main Quests'], ['side_adventure', 'Side Adventures'], ['side_quest', 'Side Quests'], ['shrine', 'Shrine Quests'],
];
const QSTATUS = { active: 'In progress', available: 'Not started', queued: 'Queued', locked: 'Locked', done: 'Done' };

const $ = s => document.querySelector(s);
const layerOf = y => (y >= SKY_Y ? 'sky' : y < DEPTHS_Y ? 'depths' : 'surface');
const toLatLng = p => [-(SIZE / 2 + p.z / 8), SIZE / 2 + p.x / 8];
const fmtTime = s => { const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60); return h ? `${h} h ${m} min` : `${m} min`; };
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

// ---------- map ----------
const map = L.map('map', { crs: L.CRS.Simple, minZoom: -1.5, maxZoom: 3, zoomSnap: 0.25, attributionControl: false, zoomControl: true });
const bounds = [[-SIZE, 0], [0, SIZE]];
const overlays = {};
for (const l of ['surface', 'sky', 'depths']) overlays[l] = L.imageOverlay(`/assets/map/${l}.png`, bounds);
map.fitBounds(bounds);
map.setMaxBounds(L.latLngBounds(bounds).pad(0.2));
const markerLayer = L.layerGroup().addTo(map);
const questLayer = L.layerGroup().addTo(map);
const scaleIcons = () => {
  const z = map.getZoom(); // -1.5 (whole map) .. 3
  const s = z <= -1 ? 0.5 : z <= 0 ? 0.65 : z <= 1 ? 0.85 : z <= 2 ? 1 : 1.15;
  map.getContainer().style.setProperty('--s', s);
};
map.on('zoomend', scaleIcons);
scaleIcons();
const pathLayer = L.layerGroup().addTo(map);
const iconCache = {};

function icon(cat, done) {
  const k = cat.key + (done ? ':d' : '');
  if (!iconCache[k]) {
    const s = cat.size || 24;
    iconCache[k] = L.divIcon({
      className: 'mk' + (done ? ' done' : ''),
      html: `<img src="/assets/icons/${cat.icon}.png" alt="">`,
      iconSize: [s, s], iconAnchor: [s / 2, s / 2], popupAnchor: [0, -s / 2],
    });
  }
  return iconCache[k];
}

const SINGULAR = {
  hidden_korok: 'Korok seed', carry_korok: 'Korok friends', hinox: 'Hinox', talus: 'Talus', molduga: 'Molduga',
  flux_construct: 'Flux Construct', frox: 'Frox', gleeok: 'Gleeok', sages_will: "Sage's Will", old_map: 'Old map',
  addison_sign: "Addison's sign",
};
function objName(cat, o) {
  if (o.display_name) return o.display_name;
  const one = SINGULAR[cat.key] || cat.label;
  return o.type ? `${one}: ${o.type}` : one;
}

function popupHtml(cat, o, done) {
  const p = o.position;
  return `<div class="pop"><h3>${esc(objName(cat, o))}</h3>
    <div class="row">${esc(cat.label)} · ${layerOf(p.y)}</div>
    <div class="row">Status: <span class="st ${done ? 'yes' : 'no'}">${done ? 'Done' : 'Not yet'}</span></div>
    <div class="row">x ${Math.round(p.x)} · y ${Math.round(p.y)} · z ${Math.round(p.z)}</div></div>`;
}

// ---------- render ----------
function render() {
  markerLayer.clearLayers();
  pathLayer.clearLayers();
  if (!state.data) return;
  const q = state.tab === 'map' ? state.search.trim().toLowerCase() : '';
  const done = state.progress ? state.progress.done : {};
  for (const cat of CATS) {
    if (state.off.has(cat.key)) continue;
    const list = state.data[cat.data] || [];
    const flags = done[cat.key] || [];
    list.forEach((o, i) => {
      const isDone = !!flags[i];
      if (state.mode === 'missing' && isDone) return;
      if (state.mode === 'done' && !isDone) return;
      if (layerOf(o.position.y) !== state.layer) return;
      if (q && !(objName(cat, o).toLowerCase().includes(q))) return;
      const m = L.marker(toLatLng(o.position), { icon: icon(cat, isDone), riseOnHover: true, keyboard: false });
      m.bindPopup(() => popupHtml(cat, o, isDone));
      markerLayer.addLayer(m);
      const path = o.path && (o.path.flowers ? o.path.flowers.map(f => f.position) : o.path.start && [o.path.start, o.path.end]);
      if (path && !isDone) {
        pathLayer.addLayer(L.polyline(path.map(toLatLng), { color: cat.key === 'carry_korok' ? '#e3c27a' : '#6fd3c2', weight: 2, opacity: 0.8, dashArray: '4 4', interactive: false }));
        if (o.path.flowers) for (const f of path) pathLayer.addLayer(L.circleMarker(toLatLng(f), { radius: 2.5, color: '#f5a3d0', weight: 1, fillOpacity: 1, interactive: false }));
      }
    });
  }
}

function renderLegend() {
  const done = state.progress ? state.progress.done : {};
  const el = $('#legend');
  el.innerHTML = '';
  let group = null;
  for (const cat of CATS) {
    if (cat.group !== group) { group = cat.group; el.insertAdjacentHTML('beforeend', `<h2>${esc(group)}</h2>`); }
    const total = (state.data[cat.data] || []).length;
    const n = (done[cat.key] || []).filter(Boolean).length;
    const b = document.createElement('button');
    b.className = 'cat' + (state.off.has(cat.key) ? ' off' : '') + (total && n === total ? ' complete' : '');
    b.title = state.off.has(cat.key) ? 'Show on map' : 'Hide from map';
    b.innerHTML = `<img src="/assets/icons/${cat.icon}.png" alt=""><span>${esc(cat.label)}</span><span class="n">${n} / ${total}</span>
      <span class="bar"><i style="width:${total ? (100 * n / total).toFixed(1) : 0}%"></i></span>`;
    b.onclick = () => { state.off.has(cat.key) ? state.off.delete(cat.key) : state.off.add(cat.key); store.set('off', [...state.off]); renderLegend(); render(); };
    el.appendChild(b);
  }
}

function renderSummary() {
  const d = state.progress ? state.progress.done : {};
  const cnt = k => (d[k] || []).filter(Boolean).length;
  const items = [
    ['Korok seeds', cnt('hidden_korok') + cnt('carry_korok'), 900],
    ['Shrines', cnt('shrine'), 152],
    ['Lightroots', cnt('lightroot'), 120],
    ['Play time', state.progress ? fmtTime(state.progress.playtime) : '–', null],
  ];
  $('#summary').innerHTML = items.map(([l, n, t]) =>
    `<div class="big"><b>${t == null ? esc(n) : `${n}<small style="color:var(--muted);font-size:12px"> / ${t}</small>`}</b><span>${esc(l)}</span></div>`).join('');
}

// ---------- quests ----------
const ptLatLng = p => toLatLng({ x: p[0], z: p[2] });
const rawStatus = q => (state.progress && state.progress.quests && state.progress.quests[q.id]) || ['locked', 'NotReady'];
// "queued": unlocked, but its giver hands out the previous quest of the series first
function qStatus(q) {
  const s = rawStatus(q);
  if (s[0] === 'available' && q.after) {
    const prev = state.quests.find(x => x.id === q.after);
    if (prev && rawStatus(prev)[0] !== 'done') return ['queued', s[1], false];
  }
  return s;
}
const qStep = (q, name) => q.steps.find(s => s.name === name);
const humanize = s => s.replace(/_/g, ' ').replace(/([a-z])([A-Z0-9])/g, '$1 $2');

const questName = id => (state.quests.find(q => q.id === id) || {}).name || humanize(id);
const startPoints = q => (q.start && q.start.points) || [];
const whoWhere = q => [q.giver && `talk to ${q.giver}`, q.region && `in ${q.region}`].filter(Boolean).join(' ');

function questText(q) {
  const [st, step] = qStatus(q);
  const sp = startPoints(q), approx = q.start && !q.start.exact;
  if (st === 'locked') {
    const needs = ((q.requires && q.requires.quests) || []).filter(id => id !== q.id)
      .filter(id => { const s = state.quests.find(x => x.id === id); return !s || qStatus(s)[0] !== 'done'; });
    return {
      label: 'Locked',
      need: needs.length ? `Unlocks after progressing: ${needs.map(questName).join(', ')}.` : 'Unlocks later in the story.',
      points: sp, goto: sp.length ? (approx ? 'Show area on map' : 'Show quest giver on map') : '', kind: 'start',
    };
  }
  if (st === 'queued') {
    return {
      label: 'Queued',
      need: `${q.giver || 'The quest giver'} offers this after “${questName(q.after)}”.`,
      points: sp, goto: sp.length ? (approx ? 'Show area on map' : 'Show quest giver on map') : '', kind: 'start',
    };
  }
  if (st === 'available') {
    return {
      label: q.category === 'main' ? 'Not started · comes with the story' : 'Not started',
      need: whoWhere(q) ? `To start: ${whoWhere(q)}.` : '',
      hint: q.category === 'main' ? '' : 'Some quests only appear once their character shows up after story events.',
      points: sp, goto: sp.length ? (approx ? 'Show start area on map' : 'Show quest giver on map') : '', kind: 'start',
    };
  }
  const s = qStep(q, step);
  if (st === 'done') return { label: 'Completed', text: s ? s.text : '' };
  const pts = s ? s.points : [];
  return { label: `Current step: ${humanize(step)}`, text: (s && s.text) || '', points: pts, goto: pts.length ? 'Show on map' : '', kind: 'target' };
}

function renderQuests() {
  const el = $('#quests');
  if (!state.quests) { el.innerHTML = '<div class="empty">Quest data not built yet. Run <code>python build_quests.py</code> and restart.</div>'; return; }
  const q = state.search.trim().toLowerCase();
  const counts = { active: 0, available: 0, queued: 0, done: 0, locked: 0 };
  for (const x of state.quests) counts[qStatus(x)[0]]++;
  $('#qsummary').innerHTML = [['In progress', counts.active], ['Done', `${counts.done}<small style="color:var(--muted);font-size:12px"> / ${state.quests.length}</small>`],
    ['Ready to start', counts.available], ['Queued / locked', `${counts.queued + counts.locked}`]]
    .map(([l, n]) => `<div class="big"><b>${n}</b><span>${l}</span></div>`).join('');
  const open = store.get('qopen', { main: true, side_adventure: true, side_quest: true, shrine: true });
  let html = '', shown = 0;
  for (const [cat, label] of QCATS) {
    const all = state.quests.filter(x => x.category === cat);
    const list = all.filter(x => {
      const st = qStatus(x)[0];
      if (state.qmode === 'active' && st !== 'active') return false;
      if (state.qmode === 'available' && !['available', 'queued', 'locked'].includes(st)) return false;
      if (state.qmode === 'done' && st !== 'done') return false;
      return !q || `${x.name} ${x.giver} ${x.region}`.toLowerCase().includes(q);
    });
    if (!list.length) continue;
    shown += list.length;
    const done = all.filter(x => qStatus(x)[0] === 'done').length;
    html += `<details class="qgroup" data-cat="${cat}" ${open[cat] !== false ? 'open' : ''}><summary>${esc(label)}<span class="n">${done} / ${all.length} done</span></summary>`;
    for (const x of list) {
      const [st] = qStatus(x);
      const t = questText(x);
      html += `<div class="quest ${state.openQuest === x.id ? 'open' : ''}" data-id="${esc(x.id)}">
        <div class="t"><b>${esc(x.name)}</b><span class="chip ${st}">${QSTATUS[st]}</span></div>
        <div class="meta">${esc([x.giver, x.region].filter(Boolean).join(' · '))}</div>
        <div class="body"><div class="step">${esc(t.label)}</div>
        ${t.need ? `<div class="need">${esc(t.need)}</div>` : ''}${t.text ? `<div class="txt">${esc(t.text)}</div>` : ''}
        ${t.hint ? `<div class="hint">${esc(t.hint)}</div>` : ''}
        ${t.goto ? `<button class="goto" data-id="${esc(x.id)}">${esc(t.goto)}</button>` : ''}</div></div>`;
    }
    html += '</details>';
  }
  el.innerHTML = shown ? html : `<div class="empty">No quests here${q ? ' matching the search' : ''}.</div>`;
}

function renderQuestTargets(focusId) {
  questLayer.clearLayers();
  if (!state.quests || !state.progress) return;
  for (const x of state.quests) {
    const [st, step] = qStatus(x);
    const focus = x.id === focusId;
    if (st === 'active' && (state.qtargets || focus)) {
      const s = qStep(x, step);
      for (const p of (s ? s.points : [])) {
        if (layerOf(p[1]) !== state.layer) continue;
        const m = L.marker(ptLatLng(p), { icon: L.divIcon({ className: 'qmk' + (focus ? ' focus' : ''), iconSize: [26, 26] }), zIndexOffset: 1000 });
        m.bindPopup(`<div class="pop"><h3>${esc(x.name)}</h3><div class="row">Current step: ${esc(humanize(step))}</div>
          <div class="row">${esc([x.giver, x.region].filter(Boolean).join(' · '))}</div></div>`);
        questLayer.addLayer(m);
      }
    } else if ((st === 'available' && state.qstarts) || (['available', 'queued', 'locked'].includes(st) && focus)) {
      const approx = x.start && !x.start.exact;
      for (const p of startPoints(x).slice(0, approx ? 1 : 4)) {
        if (layerOf(p[1]) !== state.layer) continue;
        const m = L.marker(ptLatLng(p), { icon: L.divIcon({ className: 'smk' + (approx ? ' approx' : '') + (focus ? ' focus' : ''), html: '!', iconSize: [22, 22] }), zIndexOffset: 900 });
        m.bindPopup(`<div class="pop"><h3>${esc(x.name)}</h3>
          <div class="row">${QSTATUS[st]}${x.giver ? ` · ${esc(x.giver)}` : ''}${x.region ? ` · ${esc(x.region)}` : ''}</div>
          <div class="row">${approx ? 'Approximate area (first step of the quest)' : 'Where the quest giver stands (may move during the day)'}</div></div>`);
        questLayer.addLayer(m);
      }
    }
  }
}

function showQuestOnMap(id) {
  const x = state.quests.find(q => q.id === id);
  const t = x && questText(x);
  if (!t || !t.points || !t.points.length) return;
  const p = t.points[0];
  if (layerOf(p[1]) !== state.layer) setLayer(layerOf(p[1]));
  renderQuestTargets(id);
  map.flyTo(ptLatLng(p), Math.max(map.getZoom(), 1.5), { duration: 0.6 });
  if (window.innerWidth <= 760) document.body.classList.remove('panel-open');
}

$('#quests').addEventListener('click', e => {
  const go = e.target.closest('.goto');
  if (go) { e.stopPropagation(); showQuestOnMap(go.dataset.id); return; }
  const card = e.target.closest('.quest');
  if (card) { state.openQuest = state.openQuest === card.dataset.id ? null : card.dataset.id; renderQuests(); }
});
$('#quests').addEventListener('toggle', e => {
  const d = e.target.closest('.qgroup');
  if (!d) return;
  const open = store.get('qopen', {}); open[d.dataset.cat] = d.open; store.set('qopen', open);
}, true);

function setTab(tab) {
  state.tab = tab; store.set('tab', tab);
  document.body.classList.toggle('tab-quests', tab === 'quests');
  document.querySelectorAll('#tabs button').forEach(b => b.classList.toggle('on', b.dataset.tab === tab));
  $('#search').placeholder = tab === 'quests' ? 'Search quests, people, places…' : 'Search names…';
  $('#search').value = '';
  state.search = '';
  render();
  renderQuests();
}

function setStatus(text, cls) { const s = $('#status'); s.textContent = text; s.className = 'status' + (cls ? ' ' + cls : ''); }

// ---------- data ----------
async function getJSON(url) {
  const r = await fetch(url, { cache: 'no-store' });
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
}

async function loadSlots() {
  const s = await getJSON('/api/slots');
  const sel = $('#slot');
  const cur = state.slot;
  sel.innerHTML = `<option value="latest">Latest save (slot ${s.latest ?? '–'})</option>` +
    s.slots.map(x => `<option value="${x.slot}" ${x.error ? 'disabled' : ''}>Slot ${x.slot} · ${x.error ? 'unreadable' : fmtTime(x.playtime)} · ${new Date(x.mtime * 1000).toLocaleString()}</option>`).join('');
  sel.value = [...sel.options].some(o => o.value === String(cur)) ? String(cur) : 'latest';
  state.slot = sel.value;
  return s;
}

async function loadProgress() {
  const p = await getJSON('/api/progress?slot=' + encodeURIComponent(state.slot));
  state.progress = p;
  state.lastMtime = p.mtime;
  renderSummary(); renderLegend(); render(); renderQuests(); renderQuestTargets();
  setStatus(`Live · slot ${p.slot} · saved ${new Date(p.mtime * 1000).toLocaleTimeString()}`, 'live');
}

async function poll() {
  try {
    const s = await loadSlots();
    const slotNo = state.slot === 'latest' ? s.latest : Number(state.slot);
    const info = s.slots.find(x => x.slot === slotNo);
    if (info && (info.mtime !== state.lastMtime || !state.progress || state.progress.slot !== slotNo)) await loadProgress();
  } catch (e) {
    setStatus('Cannot read save: ' + e.message, 'err');
  } finally {
    setTimeout(poll, POLL_MS);
  }
}

// ---------- UI wiring ----------
function setLayer(l) {
  state.layer = l; store.set('layer', l);
  for (const k in overlays) map.hasLayer(overlays[k]) && map.removeLayer(overlays[k]);
  overlays[l].addTo(map).bringToBack();
  document.querySelectorAll('#layers button').forEach(b => b.classList.toggle('on', b.dataset.layer === l));
  render();
  renderQuestTargets();
}

document.querySelectorAll('#layers button').forEach(b => b.onclick = () => setLayer(b.dataset.layer));
document.querySelectorAll('#mode button').forEach(b => {
  b.classList.toggle('on', b.dataset.mode === state.mode);
  b.onclick = () => {
    state.mode = b.dataset.mode; store.set('mode', state.mode);
    document.querySelectorAll('#mode button').forEach(x => x.classList.toggle('on', x === b));
    render();
  };
});
$('#slot').onchange = e => { state.slot = e.target.value; store.set('slot', state.slot); loadProgress().catch(err => setStatus(err.message, 'err')); };
let searchTimer;
$('#search').oninput = e => { clearTimeout(searchTimer); searchTimer = setTimeout(() => { state.search = e.target.value; render(); renderQuests(); }, 150); };
document.querySelectorAll('#tabs button').forEach(b => b.onclick = () => setTab(b.dataset.tab));
document.querySelectorAll('#qmode button').forEach(b => {
  b.classList.toggle('on', b.dataset.q === state.qmode);
  b.onclick = () => {
    state.qmode = b.dataset.q; store.set('qmode', state.qmode);
    document.querySelectorAll('#qmode button').forEach(x => x.classList.toggle('on', x === b));
    renderQuests();
  };
});
$('#qtargets').checked = state.qtargets;
$('#qtargets').onchange = e => { state.qtargets = e.target.checked; store.set('qtargets', state.qtargets); renderQuestTargets(); };
$('#qstarts').checked = state.qstarts;
$('#qstarts').onchange = e => { state.qstarts = e.target.checked; store.set('qstarts', state.qstarts); renderQuestTargets(); };
$('#all-on').onclick = () => { state.off.clear(); store.set('off', []); renderLegend(); render(); };
$('#all-off').onclick = () => { CATS.forEach(c => state.off.add(c.key)); store.set('off', [...state.off]); renderLegend(); render(); };
$('#panel-toggle').onclick = () => document.body.classList.toggle('panel-open');

(async function init() {
  try {
    state.data = await getJSON('/data/map_data.json');
    try { state.quests = (await getJSON('/data/quests.json')).quests; } catch { state.quests = null; }
    setTab(state.tab);
    setLayer(state.layer);
    renderLegend(); renderSummary();
    await loadSlots();
    await loadProgress();
  } catch (e) {
    setStatus('Error: ' + e.message, 'err');
  }
  setTimeout(poll, POLL_MS);
})();
