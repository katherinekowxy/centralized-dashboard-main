"""Interactive 2x2 module wall embedded in the existing Streamlit application."""

from __future__ import annotations

import json

from demo import brand

WORKSPACE_TEMPLATE = r"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root {font-family:__FONT__;color:__INK__;background:__PAGE__;font-synthesis:none}
* {box-sizing:border-box}
body {margin:0;background:__PAGE__;font-size:13px}
button,a {font:inherit}
button {cursor:pointer}
.topbar {display:flex;align-items:center;justify-content:space-between;gap:12px;margin:0 0 14px}
.top-title {display:flex;align-items:baseline;gap:10px;min-width:0}
.top-title strong {font-size:15px;font-weight:700;color:__INK__}
.top-title span {font-size:12px;color:__MUTED__}
.toolbar {display:flex;flex-wrap:wrap;justify-content:flex-end;gap:7px}
.toolbar button,.exit {border:1px solid __LINE__;border-radius:5px;background:white;color:__INK__;padding:7px 10px;text-decoration:none}
.toolbar button:hover,.exit:hover {border-color:__PINK__;color:__PINK_DARK__}
.toolbar .save {background:__PINK__;border-color:__PINK__;color:white}
.toolbar .save:hover {background:__PINK_DARK__;color:white}
.status {min-height:16px;color:__MUTED__;font-size:11px;text-align:right;margin:-7px 0 8px}
.workspace {display:grid;grid-template-columns:225px minmax(0,1fr);gap:14px;align-items:start}
.library {background:white;border:1px solid __LINE__;border-radius:7px;padding:12px;max-height:calc(100vh - 88px);overflow:auto}
.library h2 {font-size:14px;margin:0 0 4px;color:__INK__}
.library p {font-size:11px;color:__MUTED__;margin:0 0 10px;line-height:1.4}
.module-list {display:grid;gap:7px}
.module {background:__SURFACE__;border:1px solid __LINE__;border-radius:5px;padding:9px 10px;cursor:grab;user-select:none;touch-action:none}
.module:hover {border-color:__PINK__;background:__PINK_TINT__}
.module:active {cursor:grabbing}
.module b {display:block;font-size:12px;font-weight:650}
.module small {display:block;color:__MUTED__;font-size:10px;margin-top:3px;line-height:1.35}
.wall-wrap {min-width:0}
.wall-heading {display:flex;justify-content:space-between;align-items:baseline;margin:0 0 8px}
.wall-heading strong {font-size:13px}
.wall-heading span {font-size:11px;color:__MUTED__}
.wall {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.display {min-width:0;aspect-ratio:16/9;padding:6px;border-radius:8px;background:#24272A;border:1px solid #111315;box-shadow:0 2px 8px rgba(36,39,42,.14);display:flex;flex-direction:column}
.display.drag-over {outline:3px solid __PINK__;outline-offset:2px}
.screen-top {height:28px;flex:none;display:flex;align-items:center;justify-content:space-between;gap:7px;padding:0 4px;color:white;cursor:grab;touch-action:none}
.screen-top:active {cursor:grabbing}
.dragging .screen-view iframe {pointer-events:none}
.screen-name {font-size:10px;font-weight:700;white-space:nowrap}
.screen-module {font-size:10px;color:#D7D9DB;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-left:auto}
.screen-actions {display:flex;align-items:center;gap:5px;flex:none}
.screen-actions a,.screen-actions button {border:0;border-radius:3px;padding:3px 5px;background:transparent;color:#F3F5F6;font-size:10px;text-decoration:none}
.screen-actions a:hover,.screen-actions button:hover {background:#414548}
.screen-view {position:relative;flex:1;min-height:0;overflow:hidden;border-radius:4px;background:white}
.screen-view iframe {display:block;width:100%;height:100%;border:0;background:white}
.empty {height:100%;display:grid;place-content:center;text-align:center;color:#777D81;background:#F5F6F7}
.empty b {font-size:12px;font-weight:600}
.empty span {font-size:10px;margin-top:4px}
.presentation .library {display:none}
.presentation .workspace {grid-template-columns:minmax(0,1fr)}
.presentation .topbar {margin-bottom:7px}
.presentation .top-title span {display:none}
.presentation .wall-heading {display:none}
.presentation .wall {height:calc(100vh - 62px);grid-template-rows:repeat(2,minmax(0,1fr));gap:8px}
.presentation .display {height:100%;min-height:0;aspect-ratio:auto}
.presentation .screen-top {height:24px}
@media (max-width:900px) {
  .workspace {grid-template-columns:1fr}
  .library {max-height:220px}
  .module-list {grid-template-columns:repeat(2,minmax(0,1fr))}
  .wall {gap:8px}
  .display {padding:4px}
  .screen-top {height:24px}
  .screen-actions a {display:none}
}
@media (max-width:560px) {
  .topbar {align-items:flex-start;flex-direction:column}
  .toolbar {justify-content:flex-start}
  .wall {grid-template-columns:1fr}
  .display {aspect-ratio:16/9}
}
</style></head>
<body class="__PRESENTATION__">
<div class="topbar">
  <div class="top-title"><strong>2×2 Display Wall</strong><span>Four 55-inch screens</span></div>
  <div class="toolbar" id="toolbar"></div>
</div>
<div class="status" id="status" aria-live="polite"></div>
<div class="workspace">
  <aside class="library" id="library">
    <h2>Module library</h2>
    <p>Drag a module into a screen. Drop a screen onto another to swap them.</p>
    <div class="module-list" id="module-list"></div>
  </aside>
  <main class="wall-wrap">
    <div class="wall-heading"><strong>Displays</strong><span>16:9 · drag to assign or swap</span></div>
    <div class="wall" id="wall"></div>
  </main>
</div>
<script>
const DATA = __DATA__;
const STORAGE_KEY = 'gbb-ioc-demo-workspace-layout-v1';
const DRAFT_KEY = 'gbb-ioc-demo-workspace-draft-v1';
const DEFAULT_LAYOUT = ['overview', 'ptw-map', 'fault-log', 'event-power'];
const MODULES = new Map(DATA.modules.map(item => [item.key, item]));
const validLayout = layout => Array.isArray(layout) && layout.length === 4
  ? layout.map(key => MODULES.has(key) ? key : null) : null;
const savedLayout = readSaved();
let layout = validLayout(savedLayout?.layout || savedLayout) || DEFAULT_LAYOUT.map(key => MODULES.has(key) ? key : null);
let pointerDrag = null;

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
}
function readSaved() {
  try {
    const draft = JSON.parse(sessionStorage.getItem(DRAFT_KEY) || 'null');
    if (draft) return draft;
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
  } catch (_) { return null; }
}
function route(key, embedded = false) {
  const url = new URL(DATA.baseUrl);
  url.search = '';
  url.searchParams.set('view', key);
  if (embedded) url.searchParams.set('workspace_embed', '1');
  return url.toString();
}
function say(message) { document.getElementById('status').textContent = message; }
function setLayout(next) {
  layout = next;
  try { sessionStorage.setItem(DRAFT_KEY, JSON.stringify({layout})); } catch (_) {}
  renderWall();
}
function beginPointerDrag(event, source) {
  if (DATA.presentation || event.button !== 0 || event.target.closest('.screen-actions')) return;
  pointerDrag = {source, startX:event.clientX, startY:event.clientY, active:false};
  const move = moveEvent => {
    if (!pointerDrag) return;
    const delta = Math.hypot(moveEvent.clientX - pointerDrag.startX, moveEvent.clientY - pointerDrag.startY);
    if (!pointerDrag.active && delta > 6) {
      pointerDrag.active = true;
      document.body.classList.add('dragging');
    }
    if (pointerDrag.active) {
      document.querySelectorAll('.display').forEach(screen => screen.classList.remove('drag-over'));
      document.elementFromPoint(moveEvent.clientX, moveEvent.clientY)?.closest('.display')?.classList.add('drag-over');
    }
  };
  const finish = finishEvent => {
    document.removeEventListener('pointermove', move);
    document.removeEventListener('pointerup', finish);
    document.removeEventListener('pointercancel', cancel);
    document.body.classList.remove('dragging');
    document.querySelectorAll('.display').forEach(screen => screen.classList.remove('drag-over'));
    if (pointerDrag?.active) {
      const target = document.elementFromPoint(finishEvent.clientX, finishEvent.clientY)?.closest('.display');
      if (target) {
        const targetIndex = Number(target.dataset.display);
        const next = [...layout];
        if (pointerDrag.source.type === 'module') next[targetIndex] = pointerDrag.source.key;
        else if (pointerDrag.source.index !== targetIndex) [next[targetIndex], next[pointerDrag.source.index]] = [next[pointerDrag.source.index], next[targetIndex]];
        setLayout(next);
        say('Display layout updated.');
      }
      pointerDrag.suppressClick = true;
    }
    pointerDrag = null;
  };
  const cancel = () => {
    document.removeEventListener('pointermove', move);
    document.removeEventListener('pointerup', finish);
    document.removeEventListener('pointercancel', cancel);
    document.body.classList.remove('dragging');
    document.querySelectorAll('.display').forEach(screen => screen.classList.remove('drag-over'));
    pointerDrag = null;
  };
  document.addEventListener('pointermove', move);
  document.addEventListener('pointerup', finish);
  document.addEventListener('pointercancel', cancel);
}
function renderLibrary() {
  const target = document.getElementById('module-list');
  target.innerHTML = DATA.modules.map(item => `<div class="module" role="button" tabindex="${DATA.presentation ? '-1' : '0'}" data-module="${esc(item.key)}">
    <b>${esc(item.label)}</b><small>${esc(item.area)}</small></div>`).join('');
  target.querySelectorAll('.module').forEach(card => {
    card.addEventListener('pointerdown', event => beginPointerDrag(event, {type:'module', key:card.dataset.module}));
    card.addEventListener('click', () => {
      if (pointerDrag?.suppressClick) { pointerDrag.suppressClick = false; return; }
      if (DATA.presentation) return;
      const empty = layout.indexOf(null);
      if (empty >= 0) { const next = [...layout]; next[empty] = card.dataset.module; setLayout(next); }
    });
    card.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); card.click(); }
    });
  });
}
function renderWall() {
  const wall = document.getElementById('wall');
  wall.innerHTML = layout.map((key, index) => {
    const item = key ? MODULES.get(key) : null;
    const frame = item ? `<iframe loading="lazy" title="Display ${index + 1}: ${esc(item.label)}" src="${esc(route(item.key, true))}"></iframe>`
      : '<div class="empty"><b>Drop a module here</b><span>Display will open the selected page</span></div>';
    const fullPage = item ? `<a href="${esc(route(item.key))}" target="_blank" rel="noopener">Open full page</a>` : '';
    const clear = item && !DATA.presentation ? `<button type="button" data-clear="${index}" aria-label="Clear display ${index + 1}">Clear</button>` : '';
    return `<section class="display" data-display="${index}">
      <div class="screen-top"><b class="screen-name">Display ${index + 1}</b><span class="screen-module">${item ? esc(item.label) : 'Empty'}</span>
        <div class="screen-actions">${fullPage}${clear}</div></div><div class="screen-view">${frame}</div></section>`;
  }).join('');
  wall.querySelectorAll('.display').forEach(screen => {
    const index = Number(screen.dataset.display);
    screen.querySelector('.screen-top').addEventListener('pointerdown', event => {
      if (layout[index]) beginPointerDrag(event, {type:'display', index});
    });
  });
  wall.querySelectorAll('[data-clear]').forEach(button => button.addEventListener('click', event => {
    event.stopPropagation();
    const next = [...layout]; next[Number(button.dataset.clear)] = null; setLayout(next);
  }));
}
function persistLayout() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({layout, savedAt:new Date().toISOString()}));
    sessionStorage.setItem(DRAFT_KEY, JSON.stringify({layout}));
    return true;
  } catch (_) { say('This browser could not save the layout.'); }
  return false;
}
function saveLayout() {
  say(persistLayout() ? 'Layout saved in this browser.' : 'This browser could not save the layout.');
}
function renderToolbar() {
  const toolbar = document.getElementById('toolbar');
  toolbar.innerHTML = DATA.presentation ? ''
    : '<button type="button" id="load-default">Load default layout</button><button type="button" id="clear-layout">Clear layout</button><button type="button" class="save" id="save-layout">Save layout</button>';
  document.getElementById('load-default')?.addEventListener('click', () => { setLayout(DEFAULT_LAYOUT.map(key => MODULES.has(key) ? key : null)); say('Default layout loaded.'); });
  document.getElementById('clear-layout')?.addEventListener('click', () => { setLayout([null, null, null, null]); say('All displays cleared.'); });
  document.getElementById('save-layout')?.addEventListener('click', saveLayout);
}
renderLibrary();
renderWall();
renderToolbar();
</script></body></html>"""


def page_html(modules: list[dict[str, str]], base_url: str, presentation: bool = False) -> str:
    payload = json.dumps({"modules": modules, "baseUrl": base_url, "presentation": presentation}, separators=(",", ":"))
    return (WORKSPACE_TEMPLATE.replace("__FONT__", brand.FONT).replace("__INK__", brand.INK)
            .replace("__MUTED__", brand.INK_2).replace("__LINE__", brand.LINE).replace("__PAGE__", brand.PAGE)
            .replace("__SURFACE__", brand.SURFACE_2).replace("__PINK__", brand.PINK)
            .replace("__PINK_DARK__", brand.PINK_DARK).replace("__PINK_TINT__", brand.PINK_TINT)
            .replace("__PRESENTATION__", "presentation" if presentation else "")
            .replace("__DATA__", payload.replace("</", "<\\/")))