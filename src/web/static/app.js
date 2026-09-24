'use strict';
const $ = id => document.getElementById(id);
const enc = encodeURIComponent;
const state = {
  sources: [], tab: 'browse', books: [], categories: [], detail: null, detailItem: null, reader: null,
  discover: {source: '', action: 'latest', page: 1, name: '', sort: '', mode: 'day'}, search: null, searchCounts: null, view: 'home',
  health: {}, healthDots: {}, chapterDesc: readLocal('comic:chapter-desc') === true,
  browseRequest: 0, shelfRequest: 0, detailRequest: 0, readerRequest: 0, resultItems: [], resultShown: 0, activeTasks: 0,
};
const BROWSE_ACTIONS = {latest: '最新更新', category: '分类浏览', leaderboard: '排行榜', random: '随机推荐'};
const BROWSE_ORDER = ['latest', 'category', 'leaderboard', 'random'];
const statuses = {queued:'排队中',running:'下载中',cancelling:'正在取消',cancelled:'已取消',failed:'失败',completed:'已完成',fetching:'获取章节',downloading:'下载图片',packaging:'打包 PDF',interrupted:'重启中断'};
const TONES = {queued:'muted',running:'info',cancelling:'warn',cancelled:'muted',failed:'danger',interrupted:'danger',completed:'ok'};
const CAP_LABELS = {search:'搜索',latest:'最新',category:'分类',leaderboard:'排行',random:'随机',login:'账号'};

const icons = {
  star:'<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
  'book-open':'<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
  download:'<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>',
  'refresh-cw':'<polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>',
  tag:'<path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.83z"/><line x1="7" y1="7" x2="7.01" y2="7"/>',
  'trash-2':'<polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/>',
  x:'<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
  settings:'<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
  key:'<path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/>',
  unlink:'<path d="m18.84 12.25 1.72-1.71h-.02a5.004 5.004 0 0 0-.12-7.07 5.006 5.006 0 0 0-6.95 0l-1.72 1.71"/><path d="m5.17 11.75-1.71 1.71a5.004 5.004 0 0 0 .12 7.07 5.006 5.006 0 0 0 6.95 0l1.71-1.71"/><line x1="8" y1="2" x2="8" y2="5"/><line x1="2" y1="8" x2="5" y2="8"/><line x1="16" y1="19" x2="16" y2="22"/><line x1="19" y1="16" x2="22" y2="16"/>',
  copy:'<rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
  play:'<polygon points="6 3 20 12 6 21 6 3"/>',
  check:'<polyline points="20 6 9 17 4 12"/>',
  sort:'<path d="M11 5h10M11 9h7M11 13h4"/><path d="M3 17l3 3 3-3M6 20V4"/>',
  'chevron-left':'<polyline points="15 18 9 12 15 6"/>',
  'chevron-right':'<polyline points="9 18 15 12 9 6"/>',
  'chevrons-right':'<polyline points="13 17 18 12 13 7"/><polyline points="6 17 11 12 6 7"/>',
  list:'<line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>',
  compass:'<circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>',
  search:'<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
  alert:'<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>',
  inbox:'<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
  bookmark:'<path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>',
  user:'<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
};
const svgIcon = name => `<svg viewBox="0 0 24 24" aria-hidden="true">${icons[name]}</svg>`;

function node(tag, text, className) {const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(className)n.className=className;return n;}
function button(text, action, className) {const n=node('button',text,className);n.type='button';n.onclick=()=>run(action,n);return n;}
function iconBtn(name, label, action, className) {const n=node('button',undefined,(className?className+' ':'')+'icon-btn');n.type='button';n.title=label;n.setAttribute('aria-label',label);n.innerHTML=svgIcon(name);n.onclick=()=>run(action,n);return n;}
function labelBtn(icon, text, action, className) {const n=button('',action,className);n.innerHTML=svgIcon(icon);n.append(node('span',text));return n;}
async function run(action, control) {if(control)control.disabled=true;try{return await action();}catch(e){if(e.name!=='AbortError')toast(e.message,{tone:'error'});}finally{if(control)control.disabled=false;}}

// The toast is a manual popover so it renders above open modal dialogs.
function toast(message, opts={}) {
  const t=$('toast');t.replaceChildren(node('span',message));t.className=opts.tone||'';
  if(opts.action){const b=node('button',opts.action.label,'toast-action');b.type='button';b.onclick=()=>{hideToast();opts.action.run();};t.append(b);}
  if(POPOVER){if(t.matches(':popover-open'))t.hidePopover();t.showPopover();}else t.hidden=false;
  clearTimeout(toast.timer);toast.timer=setTimeout(hideToast,opts.action?6500:4000);
}
const POPOVER=typeof HTMLElement.prototype.showPopover==='function';
function hideToast(){const t=$('toast');if(POPOVER){if(t.matches(':popover-open'))t.hidePopover();}else t.hidden=true;}
if(POPOVER)$('toast').hidden=false;

async function api(path, options={}) {
  const response=await fetch(path,{...options,headers:{'Content-Type':'application/json',...options.headers}});
  let data={};try{data=await response.json();}catch{}
  if(!response.ok){const err=new Error(data.error?.message||data.detail||`请求失败 (${response.status})`);err.code=data.error?.code;err.source=data.error?.source;throw err;}
  return data;
}
const write=(method,data)=>({method,body:JSON.stringify(data)});
const sourceName=id=>state.sources.find(s=>s.id===id)?.name||id;
const bookPath=b=>`/api/library/${enc(b.source)}/${enc(b.id)}`;
function options(select, values, selected) {select.replaceChildren(...values.map(v=>{const n=node('option',v.label);n.value=v.value;return n;}));if(values.some(v=>v.value===selected))select.value=selected;}
function readLocal(key) {try{return JSON.parse(localStorage.getItem(key));}catch{return null;}}
function saveLocal(key,value) {try{localStorage.setItem(key,JSON.stringify(value));}catch{if(!saveLocal.warned){toast('浏览器无法保存进度，请检查存储权限');saveLocal.warned=true;}}}
function progressKey(b,chapter) {return 'comic:progress:'+JSON.stringify([b.source,String(b.id),chapter]);}
function lastKey(b) {return 'comic:last:'+JSON.stringify([b.source,String(b.id)]);}
function safeImage(url) {try {const u=new URL(url,location.origin);return ['http:','https:'].includes(u.protocol)?u.href:'';}catch{return '';}}
// Route upstream covers through the image proxy so no direct request leaks to the CDN.
function coverFor(item) {const url=safeImage(item.cover);if(!url)return '';if(url.startsWith(location.origin))return url;return `/api/image/proxy?${new URLSearchParams({source:item.source,url})}`;}
function image(url, alt, className) {const n=node('img',undefined,className);n.alt=alt;n.loading='lazy';n.decoding='async';const safe=safeImage(url);if(safe)n.src=safe;else n.classList.add('broken');n.onerror=()=>{n.removeAttribute('src');n.classList.add('broken');};n.onload=()=>n.classList.add('ready');return n;}
// Cover box keeps its 3:4 slot and shows the title's first glyph when the image is missing.
function coverBox(item,className){const box=node('div',undefined,'cover'+(className?' '+className:''));box.dataset.initial=(item.title||'?').trim().slice(0,1)||'?';box.append(image(coverFor(item),item.title||''));return box;}
function skeletons(count){return Array.from({length:count},()=>{const n=node('div',undefined,'card skeleton');n.append(node('i'),node('b'),node('b'));return n;});}
function emptyState(title,hint,action,icon='inbox'){
  const box=node('div',undefined,'empty-state');const art=node('div',undefined,'empty-icon');art.innerHTML=svgIcon(icon);
  box.append(art,node('h3',title));if(hint)box.append(node('p',hint,'muted'));if(action)box.append(action);return box;
}
function timeAgo(value){
  const t=Date.parse(String(value||'').replace(' ','T')+(/[zZ+]/.test(value||'')?'':'Z'));if(!t)return '';
  const s=Math.max(0,(Date.now()-t)/1000);
  if(s<60)return '刚刚';if(s<3600)return `${Math.floor(s/60)} 分钟前`;if(s<86400)return `${Math.floor(s/3600)} 小时前`;if(s<86400*30)return `${Math.floor(s/86400)} 天前`;
  return new Date(t).toLocaleDateString();
}
async function copyText(text){
  try{await navigator.clipboard.writeText(text);return;}catch{}
  const area=node('textarea');area.value=text;area.style.cssText='position:fixed;opacity:0';document.body.append(area);area.select();
  try{document.execCommand('copy');}finally{area.remove();}
}

// Styled replacement for prompt()/confirm(). Resolves to the entered text / true, or null / false when dismissed.
function ask({title,message='',input=false,value='',placeholder='',choices=[],ok='确定',danger=false}){
  return new Promise(resolve=>{
    const dlg=$('ask-dialog'),field=$('ask-input');
    $('ask-title').textContent=title;$('ask-message').textContent=message;$('ask-message').hidden=!message;
    field.hidden=!input;field.value=value;field.placeholder=placeholder;
    $('ask-options').replaceChildren(...choices.map(v=>{const o=node('option');o.value=v;return o;}));
    $('ask-ok').textContent=ok;$('ask-ok').classList.toggle('danger',danger);
    let settled=false;
    const done=result=>{if(settled)return;settled=true;dlg.onclose=null;if(dlg.open)dlg.close();resolve(result);};
    $('ask-form').onsubmit=event=>{event.preventDefault();done(input?field.value.trim():true);};
    $('ask-cancel').onclick=()=>done(input?null:false);
    dlg.onclose=()=>done(input?null:false);
    dlg.showModal();
    if(input){field.focus();field.select();}else $('ask-ok').focus();
  });
}

/* ---------- sources & discovery state ---------- */
async function loadSources() {
  state.sources=(await api('/api/sources')).sources;
  renderSourceList();
  if(state.settingsSource)renderSourceSettings();
  if(!state.browseReady)initBrowse();
  else if(state.view==='results')renderFilters();
  else if(state.shelfBlocked)run(loadShelves);
}
function sourcePlugin(id){return state.sources.find(s=>s.id===id);}
function discoverActions(p){return BROWSE_ORDER.filter(a=>p&&(p.capabilities||[]).includes(a));}
function browsable(){return state.sources.filter(p=>discoverActions(p).length);}
function needsLogin(p){return !!p&&(p.capabilities||[]).includes('login')&&!p.account?.authenticated&&!p.account?.configured;}
// Default to a source that can list without an account, so discovery is never empty on first visit.
function discoverPlugin(){const list=browsable();return list.find(p=>p.id===state.discover.source)||list.find(p=>!needsLogin(p))||list[0];}
function sortsFor(p,action){return action==='category'?(p.sorts||[]):action==='latest'?(p.latest_sorts||[]):[];}
function pick(values,value){return values.some(v=>v.value===value)?value:(values[0]?.value??'');}
function normalizeDiscover(){
  const d=state.discover,p=discoverPlugin();if(!p)return null;d.source=p.id;
  const actions=discoverActions(p);if(!actions.includes(d.action))d.action=actions[0];
  d.name=d.action==='category'?pick(p.categories||[],d.name):'';
  d.mode=d.action==='leaderboard'?pick(p.leaderboard_modes||[],d.mode):'day';
  d.sort=pick(sortsFor(p,d.action),d.sort);
  return p;
}

/* ---------- browse views & history ---------- */
// The browse tab has two views: home (search + shelves) and a results view that owns all filters.
function setView(view){
  state.view=view;
  $('browse').classList.toggle('view-home',view==='home');
  $('browse').classList.toggle('view-results',view==='results');
  $('home-feed').hidden=view!=='home';
  $('results-view').hidden=view!=='results';
}
function viewURL(){
  if(state.view!=='results')return location.pathname;
  const params=new URLSearchParams();
  if(state.search){params.set('q',state.search.keyword);if(state.search.source)params.set('source',state.search.source);}
  else{params.set('browse',state.discover.action);params.set('source',state.discover.source);}
  return '?'+params;
}
function syncHistory(push){
  const snap={view:state.view,search:state.search&&{...state.search},discover:{...state.discover}};
  try{history[push?'pushState':'replaceState'](snap,'',viewURL());}catch{}
  document.title=state.view==='results'?`${state.search?state.search.keyword:BROWSE_ACTIONS[state.discover.action]} · Comic`:'Comic · 聚合漫画';
}
function openResults(){
  const push=state.view!=='results';
  setView('results');
  syncHistory(push);
  if(push)state.pushedResults=true;
  window.scrollTo({top:0});
  return run(state.search?loadSearch:loadDiscover);
}
function showHome(){
  state.search=null;state.browseAbort?.abort();++state.browseRequest;state.pushedResults=false;
  $('keyword').value='';syncClear();
  setView('home');renderContinue();renderRecent();
  if(!state.shelvesLoaded||state.shelfBlocked||state.shelfFailed)run(loadShelves);
}
function goHome(){
  if(state.view==='results'&&state.pushedResults&&history.state?.view==='results'){history.back();return;}
  showHome();syncHistory(false);
}
function initBrowse(){
  state.browseReady=true;
  const saved=readLocal('comic:discover');if(saved&&typeof saved==='object')Object.assign(state.discover,saved,{page:1});
  renderQuick();renderRecent();renderContinue();
  const params=new URLSearchParams(location.search);
  const q=(params.get('q')||'').trim().slice(0,200),src=params.get('source'),action=params.get('browse');
  if(q){
    state.search={keyword:q,source:sourcePlugin(src)?src:'',page:1,sort:''};
    $('keyword').value=q;syncClear();setView('results');syncHistory(false);run(loadSearch);return;
  }
  if(BROWSE_ORDER.includes(action)){
    if(sourcePlugin(src))state.discover.source=src;
    Object.assign(state.discover,{action,page:1});setView('results');syncHistory(false);run(loadDiscover);return;
  }
  setView('home');syncHistory(false);run(loadShelves);
}
function renderQuick(){
  const box=$('quick');box.replaceChildren();
  for(const a of BROWSE_ORDER.filter(a=>browsable().some(p=>discoverActions(p).includes(a))))box.append(button(BROWSE_ACTIONS[a],()=>browseAction(a),'quick-link'));
}
function browseAction(action,sourceId){
  if(sourceId)state.discover.source=sourceId;
  const p=discoverPlugin();
  if(!discoverActions(p).includes(action)){const alt=browsable().find(x=>discoverActions(x).includes(action));if(alt)state.discover.source=alt.id;}
  state.search=null;Object.assign(state.discover,{action,page:1});
  if(state.tab!=='browse')showTab('browse');
  $('keyword').value='';syncClear();
  return openResults();
}

/* ---------- recent searches & reading history ---------- */
function readRecent(){const list=readLocal('comic:recent');return Array.isArray(list)?list.filter(x=>typeof x==='string'):[];}
function addRecent(keyword){saveLocal('comic:recent',[keyword,...readRecent().filter(x=>x!==keyword)].slice(0,10));}
function renderRecent(){
  const list=readRecent();$('recent').hidden=!list.length;
  $('recent-list').replaceChildren(...list.map(k=>button(k,()=>startSearch(k),'recent-chip')));
}
function readHistory(){const list=readLocal('comic:history');return Array.isArray(list)?list.filter(h=>h&&h.source&&h.id):[];}
function recordHistory(r){
  const b=r.book,entry={source:b.source,id:String(b.id),title:b.title||'',cover:b.cover||'',author:b.author||'',chapterId:r.chapterId,chapterName:r.chapterName,index:r.index,total:r.images.length,updatedAt:Date.now()};
  saveLocal('comic:history',[entry,...readHistory().filter(h=>!(h.source===entry.source&&String(h.id)===entry.id))].slice(0,40));
}
function renderContinue(){
  const list=readHistory().slice(0,24),row=$('continue-row');
  $('continue-shelf').hidden=!list.length;
  row.replaceChildren(...list.map(h=>card(h,{history:h})));
  state.continueScroller?.syncArrows();
}

/* ---------- home shelves ---------- */
function scrollerFor(row){
  const wrap=node('div',undefined,'scroller');
  const step=dir=>row.scrollBy({left:dir*row.clientWidth*0.85,behavior:'smooth'});
  const prev=iconBtn('chevron-left','向左滚动',()=>step(-1),'scroll-btn prev'),next=iconBtn('chevron-right','向右滚动',()=>step(1),'scroll-btn next');
  const sync=()=>{prev.hidden=row.scrollLeft<=4;next.hidden=row.scrollLeft+row.clientWidth>=row.scrollWidth-4;};
  row.addEventListener('scroll',sync,{passive:true});
  wrap.syncArrows=()=>requestAnimationFrame(sync);
  wrap.append(row,prev,next);sync();return wrap;
}
const SHELF_SIZE=18;
async function loadShelves(){
  const request=++state.shelfRequest,box=$('source-shelves');
  state.shelvesLoaded=true;state.shelfBlocked=state.shelfFailed=false;
  const current=discoverPlugin(),list=browsable().sort((a,b)=>(b===current)-(a===current));
  box.replaceChildren();
  if(!list.length){box.append(emptyState('暂无可浏览的图源','请先在右上角的「图源管理」中配置图源。'));return;}
  const jobs=[];
  for(const p of list){
    jobs.push(loadShelf(p,request));
    // A leaderboard shelf makes the home feed feel like a real product.
    if((p.capabilities||[]).includes('leaderboard'))jobs.push(loadShelf(p,request,'leaderboard','日榜'));
  }
  await Promise.all(jobs);
}
async function loadShelf(p,request,action,label){
  const box=$('source-shelves');action=action||discoverActions(p)[0];
  const section=node('section',undefined,'shelf');section.dataset.source=p.id;if(label)section.dataset.action=action;
  const head=node('div',undefined,'shelf-head'),more=button('',()=>browseAction(action,p.id),'link-btn');
  more.append(node('span','查看更多'));more.insertAdjacentHTML('beforeend',svgIcon('chevron-right'));
  head.append(node('h2',p.name),node('span',label||BROWSE_ACTIONS[action],'pill'),more);
  const status=node('div',undefined,'status');status.setAttribute('role','status');
  const row=node('div',undefined,'row'),scroller=scrollerFor(row);
  section.append(head,status,scroller);
  const old=[...box.children].find(n=>n.dataset.source===p.id&&n.dataset.action===(label?action:undefined));
  old?old.replaceWith(section):box.append(section);
  if(needsLogin(p)){
    state.shelfBlocked=true;scroller.hidden=true;
    status.classList.add('notice');status.append(node('span',`${p.name}需要登录账号后才能浏览。`),bindButton(p.id));return;
  }
  row.replaceChildren(...skeletons(8));
  try{
    const params=new URLSearchParams({page:1});
    if(action==='leaderboard')params.set('mode','day');
    const sorts=sortsFor(p,action);if(sorts.length)params.set('sort',sorts[0].value);
    const data=await api(`/api/${enc(p.id)}/${action}?`+params);
    if(request!==state.shelfRequest)return;
    const items=(data.data||[]).slice(0,SHELF_SIZE);
    if(!items.length){scroller.hidden=true;status.textContent='此图源暂无内容';return;}
    row.replaceChildren(...items.map(item=>card(item,{showSource:false})));
    scroller.syncArrows();
  }catch(e){
    if(request!==state.shelfRequest)return;
    if(label){section.remove();return;}// bonus shelves fail quietly
    scroller.hidden=true;state.shelfFailed=true;if(e.code==='login_required')state.shelfBlocked=true;
    showError(status,e,()=>loadShelf(p,state.shelfRequest));
  }
}

function bindButton(id){return button(`绑定${sourceName(id)}账号`,async()=>{await loadSources();state.settingsSource=id;configureAccount();$('credentials-dialog').showModal();},'small');}
// Failures get a retry button; login-required errors also get a bind shortcut.
function showError(target,e,retry){
  target.classList.add('warn');target.replaceChildren(node('span',e.message));
  if(e.code==='login_required'&&e.source)target.append(bindButton(e.source));
  if(retry)target.append(button('重试',retry,'small'));
}
function clearStatus(target){target.classList.remove('warn','notice');target.replaceChildren();}

/* ---------- results: filters, pagination ---------- */
function chipGroup(label,values,selected,onpick){
  const row=node('div',undefined,'filter-row'),list=node('div',undefined,'chips');
  list.setAttribute('role','radiogroup');list.setAttribute('aria-label',label);
  for(const v of values){
    const chip=node('button',v.label,'chip'+(v.value===selected?' active':'')+(v.warn?' warn':''));chip.type='button';
    if(v.count!==undefined)chip.append(node('span',String(v.count),'chip-count'));
    if(v.warn)chip.title=v.warn;
    chip.setAttribute('role','radio');chip.setAttribute('aria-checked',String(v.value===selected));
    chip.onclick=()=>{if(v.value!==selected)onpick(v.value);};list.append(chip);
  }
  row.append(node('span',label,'filter-label'),list);return row;
}
function renderFilters(){
  const box=$('filters');box.replaceChildren();
  const s=state.search,d=state.discover;
  if(s){
    const searchable=state.sources.filter(p=>(p.capabilities||[]).includes('search'));
    const c=state.searchCounts?.keyword===s.keyword?state.searchCounts:null;
    if(searchable.length>1)box.append(chipGroup('图源',[
      {value:'',label:'全部',count:c?Object.values(c.counts).reduce((a,b)=>a+b,0):undefined},
      ...searchable.map(p=>({value:p.id,label:p.name,count:c?(c.errors[p.id]?'!':c.counts[p.id]??0):undefined,warn:c?.errors[p.id]?.message}))],
      s.source,v=>{Object.assign(s,{source:v,page:1,sort:''});run(loadSearch);}));
    const sorts=sourcePlugin(s.source)?.search_sorts||[];
    if(sorts.length)box.append(chipGroup('排序',sorts,s.sort,v=>{Object.assign(s,{sort:v,page:1});run(loadSearch);}));
  }else{
    const p=discoverPlugin();if(!p)return;
    const reload=patch=>{Object.assign(d,patch,{page:1});run(loadDiscover);};
    const list=browsable();
    if(list.length>1)box.append(chipGroup('图源',list.map(x=>({value:x.id,label:x.name})),d.source,v=>reload({source:v,name:'',sort:'',mode:'day'})));
    box.append(chipGroup('浏览',discoverActions(p).map(a=>({value:a,label:BROWSE_ACTIONS[a]})),d.action,v=>reload({action:v})));
    if(d.action==='category'&&(p.categories||[]).length)box.append(chipGroup('分类',p.categories,d.name,v=>reload({name:v})));
    if(d.action==='leaderboard'&&(p.leaderboard_modes||[]).length)box.append(chipGroup('榜单',p.leaderboard_modes,d.mode,v=>reload({mode:v})));
    const sorts=sortsFor(p,d.action);
    if(sorts.length)box.append(chipGroup('排序',sorts,d.sort,v=>reload({sort:v})));
  }
  box.hidden=!box.children.length;
}
// One pager below the results serves browse lists and searches alike; random lists get "换一批" instead.
function renderPager(count){
  const s=state.search,d=state.discover,random=!s&&d.action==='random',page=s?s.page:d.page;
  for(const id of ['discover-prev','discover-page','discover-next'])$(id).hidden=random;
  $('discover-again').hidden=!random;
  $('discover-page').textContent=`第 ${page} 页`;
  $('discover-prev').disabled=page<=1;
  $('discover-next').disabled=!count;
  $('pager').hidden=!random&&page<=1&&!count;
}
function beginResults(){
  state.browseAbort?.abort();state.browseAbort=new AbortController();
  clearStatus($('browse-status'));state.resultItems=[];state.resultShown=0;
  $('results').replaceChildren(...skeletons(14));$('pager').hidden=true;$('results-more').hidden=true;
  return ++state.browseRequest;
}
// Large aggregate result sets render in chunks as the user scrolls.
const RESULT_CHUNK=35;
function expectedSource(){return state.search?(state.search.source||null):discoverPlugin()?.id;}
function showResults(items,emptyTitle,emptyHint){
  state.resultItems=items;state.resultShown=0;$('results').replaceChildren();
  if(!items.length){$('results').append(emptyState(emptyTitle,emptyHint,undefined,'search'));$('results-more').hidden=true;$('pager').classList.remove('deferred');return;}
  showMoreResults();
}
function showMoreResults(){
  const exp=expectedSource(),next=state.resultItems.slice(state.resultShown,state.resultShown+RESULT_CHUNK);
  $('results').append(...next.map(item=>card(item,{showSource:!!item.source&&item.source!==exp})));
  state.resultShown+=next.length;
  const left=state.resultItems.length-state.resultShown;
  $('results-more').hidden=left<=0;$('results-more-btn').textContent=`显示更多（还有 ${left} 部）`;
  $('pager').classList.toggle('deferred',left>0);
}
async function loadDiscover(){
  const p=normalizeDiscover();if(!p)return;
  const d=state.discover;
  saveLocal('comic:discover',d);syncHistory(false);
  $('results-title').textContent=BROWSE_ACTIONS[d.action];
  $('results-meta').textContent=p.name+(d.action==='random'?'':` · 第 ${d.page} 页`);
  renderFilters();
  const request=beginResults();
  try{
    const params=new URLSearchParams({page:d.page});
    if(d.sort)params.set('sort',d.sort);
    if(d.action==='leaderboard')params.set('mode',d.mode);
    if(d.name)params.set('name',d.name);
    const data=await api(`/api/${enc(d.source)}/${d.action}?`+params,{signal:state.browseAbort.signal});
    if(request!==state.browseRequest)return;
    const items=data.data||[];
    showResults(items,d.page>1?'已经到最后一页了':'此图源暂无内容',d.page>1?'':'换个分类或图源看看');
    renderPager(items.length);
  }catch(e){if(request===state.browseRequest&&e.name!=='AbortError'){$('results').replaceChildren();showError($('browse-status'),e,loadDiscover);}}
}
async function loadSearch(){
  const s=state.search;if(!s)return;
  s.sort=pick(sourcePlugin(s.source)?.search_sorts||[],s.sort);
  syncHistory(false);
  const scope=s.source?sourceName(s.source):'全部图源';
  $('results-title').textContent=`“${s.keyword}”`;
  $('results-meta').textContent=`${scope} · 搜索中…`;
  renderFilters();
  const request=beginResults();
  try{
    const params=new URLSearchParams({keyword:s.keyword,page:s.page});
    if(s.source)params.set('source',s.source);
    if(s.sort)params.set('sort',s.sort);
    const data=await api('/api/search?'+params,{signal:state.browseAbort.signal});
    if(request!==state.browseRequest)return;
    if(!s.source)state.searchCounts={keyword:s.keyword,counts:Object.fromEntries(Object.entries(data.all_results||{}).map(([k,v])=>[k,v.length])),errors:data.errors||{}};
    renderFilters();
    showResults(data.items,s.page>1?'已经到最后一页了':'没有找到相关漫画','换个关键词，或切换到其他图源试试');
    $('results-meta').textContent=`${scope} · 第 ${s.page} 页 · ${data.items.length} 部`;
    renderPager(data.items.length);
    const errors=Object.entries(data.errors||{}),status=$('browse-status');
    if(errors.length){
      status.classList.add('warn');
      status.append(node('span','部分图源暂不可用：'+errors.map(([id,error])=>`${sourceName(id)}（${error.message}）`).join('；')));
      for(const [id,error] of errors)if(error.code==='login_required')status.append(bindButton(id));
    }
  }catch(e){if(request===state.browseRequest&&e.name!=='AbortError'){$('results').replaceChildren();$('results-meta').textContent=scope;showError($('browse-status'),e,loadSearch);}}
}
function startSearch(keyword,source=''){
  keyword=keyword.trim().slice(0,200);if(!keyword)return;
  if(state.tab!=='browse')showTab('browse');
  $('keyword').value=keyword;syncClear();addRecent(keyword);renderRecent();
  state.search={keyword,source,page:1,sort:''};
  return openResults();
}
function browse(event) {
  event.preventDefault();
  const keyword=$('keyword').value.trim();
  if(!keyword){$('keyword').focus();toast('请输入关键词');return;}
  if(matchMedia('(pointer:coarse)').matches)$('keyword').blur();
  // Keep the chosen source scope when refining a search from the results view.
  startSearch(keyword,state.search?.source||'');
}
function turnPage(delta){
  const ctx=state.search||state.discover,page=ctx.page+delta;if(page<1)return;
  ctx.page=page;window.scrollTo({top:0,behavior:'smooth'});run(state.search?loadSearch:loadDiscover);
}
// Strip leading [group]/(tag) prefixes so a title search finds the same work on other sources.
function searchableTitle(title){
  const t=String(title||'').replace(/^(\s*[\[【(（][^\]】)）]*[\]】)）])+\s*/,'').trim();
  return (t||String(title||'')).slice(0,60);
}
function searchElsewhere(title){
  if($('reader-dialog').open)closeReader(true);
  ++state.detailRequest;if($('detail-dialog').open)$('detail-dialog').close();
  return startSearch(searchableTitle(title));
}

/* ---------- tabs & cards ---------- */
function showTab(tab) {
  const changed=state.tab!==tab;state.tab=tab;
  for(const id of ['browse','library','downloads'])$(id).hidden=id!==tab;
  document.querySelectorAll('[data-tab]').forEach(n=>{const on=n.dataset.tab===tab;n.classList.toggle('active',on);n.setAttribute('aria-current',on?'page':'false');});
  if(changed)window.scrollTo({top:0});
  if(tab==='browse'&&state.view==='home')renderContinue();
  if(tab==='library')run(loadLibrary);
  if(tab==='downloads')run(loadTasks);
}
function card(item,{showSource=true,library=false,history=null}={}){
  const el=node('article',undefined,'card'+(history?' card-history':''));
  const open=button('',()=>openComic(item,{resume:!!history}),'card-open');open.title=item.title||'';
  const cover=coverBox(item);
  if(showSource&&item.source)cover.append(node('span',sourceName(item.source),'cover-source'));
  if(history){
    const bar=node('i',undefined,'cover-progress');bar.style.setProperty('--p',history.total?Math.min(1,(history.index+1)/history.total):0);
    const play=node('span',undefined,'cover-play');play.innerHTML=svgIcon('play');cover.append(bar,play);
  }else{
    const last=readLocal(lastKey(item));if(last?.chapterName)cover.append(node('span',`读至 ${last.chapterName}`,'cover-tag'));
  }
  const info=node('div',undefined,'card-info');
  info.append(node('h3',item.title||'未命名'));
  if(history)info.append(node('p',`${history.chapterName||''} · ${history.index+1}/${history.total} 页`,'card-sub accent'));
  else info.append(node('p',item.author||'佚名','card-sub'));
  if(library)info.append(node('p',`${item.library_category||'未分类'} · ${item.chapters?.length||0} 章`,'card-sub'));
  open.append(cover,info);el.append(open);
  if(library)el.append(libraryActions(item));
  return el;
}
function libraryActions(item){
  const controls=node('div',undefined,'card-actions');
  controls.append(
    iconBtn('refresh-cw','检查更新',async()=>{const result=await api(bookPath(item)+'/refresh',{method:'POST'});toast(result.new_chapters?`《${item.title}》新增 ${result.new_chapters} 章`:'暂无新章节');await loadLibrary();}),
    iconBtn('tag','设置分类',()=>editCategory(item)),
    iconBtn('trash-2','移出书库',async()=>{if(!await ask({title:'移出书库',message:`确定将《${item.title}》移出书库吗？阅读进度会保留。`,ok:'移出',danger:true}))return;await api(bookPath(item),{method:'DELETE'});toast('已移出书库');await loadLibrary();}));
  return controls;
}
async function editCategory(item){
  const category=await ask({title:'设置分类',message:`《${item.title}》`,input:true,value:item.library_category||'',placeholder:'留空为未分类',choices:state.categories});
  if(category===null)return;
  await api(bookPath(item),write('PATCH',{category}));toast(category?`已移至「${category}」`:'已设为未分类');await loadLibrary();
}

/* ---------- library ---------- */
async function loadLibrary() {
  const data=await api('/api/library');state.books=data.items;state.categories=data.categories||[];
  options($('library-category'),[{value:'*',label:'全部分类'},{value:'',label:'未分类'},...state.categories.map(v=>({value:v,label:v}))],$('library-category').value);
  $('library-count').textContent=state.books.length?String(state.books.length):'';
  filterBooks();
}
function filterBooks(){
  const category=$('library-category').value,sort=$('library-sort').value,needle=($('library-filter').value||'').trim().toLowerCase(),box=$('books');
  if(!state.books.length){box.replaceChildren(emptyState('书库还是空的','在漫画详情中点击「收藏」即可加入书库，方便追更和继续阅读。',labelBtn('compass','去发现漫画',()=>showTab('browse'),'primary'),'bookmark'));return;}
  const lastRead=new Map(readHistory().map(h=>[h.source+':'+h.id,h.updatedAt||0]));
  const items=state.books.filter(b=>(category==='*'||b.library_category===category)&&(!needle||(b.title||'').toLowerCase().includes(needle)||(b.author||'').toLowerCase().includes(needle)));
  if(sort==='read')items.sort((a,b)=>(lastRead.get(b.source+':'+b.id)||0)-(lastRead.get(a.source+':'+a.id)||0));
  else if(sort==='title')items.sort((a,b)=>String(a.title||'').localeCompare(String(b.title||''),'zh'));
  if(!items.length){box.replaceChildren(emptyState('没有符合条件的漫画','试试其他分类或关键词',undefined,'search'));return;}
  box.replaceChildren(...items.map(b=>card(b,{library:true})));
}
const inLibrary=d=>state.books.some(b=>b.source===d.source&&String(b.id)===String(d.id));

/* ---------- detail ---------- */
function detailHero(item,loading){
  const hero=node('div',undefined,'detail-hero'+(loading?' loading':''));
  const backdrop=node('div',undefined,'detail-backdrop'),url=coverFor(item);
  if(url)backdrop.style.backgroundImage=`url("${url.replace(/"/g,'%22')}")`;
  const text=node('div',undefined,'detail-text');
  text.append(node('h2',item.title||'未命名','detail-name'));
  hero.append(backdrop,coverBox(item,'detail-cover'),text);
  if(loading)text.append(node('i',undefined,'line'),node('i',undefined,'line short'),node('i',undefined,'line'));
  return {hero,text};
}
async function openComic(item,opts={}) {
  const request=++state.detailRequest,dlg=$('detail-dialog');state.detail=null;state.detailItem=item;
  $('detail-title').textContent=item.title||'漫画详情';
  $('detail-body').replaceChildren(detailHero(item,true).hero);
  if(!dlg.open)dlg.showModal();dlg.scrollTop=0;syncDetailHead();
  try{
    const detail=await api(`/api/comic/${enc(item.source)}/${enc(item.id)}`);if(request!==state.detailRequest)return;
    state.detail={...detail,cover:detail.cover||item.cover,category:detail.category||item.category};renderDetail();
    if(opts.resume){const last=readLocal(lastKey(state.detail));if(last&&state.detail.chapters.some(c=>String(c.id)===last.chapterId))openReader(last.chapterId);}
  }catch(e){
    if(request!==state.detailRequest)return;
    if(item.chapters){state.detail=item;renderDetail();$('detail-body').querySelector('.detail-hero')?.after(errorPanel('图源暂不可用，以下为书库缓存',e,item,true));}
    else $('detail-body').replaceChildren(detailHero(item,false).hero,errorPanel('无法加载漫画详情',e,item));
  }
}
function errorPanel(title,e,item,compact){
  const box=node('div',undefined,'error-panel'+(compact?' compact':''));const icon=node('span',undefined,'error-icon');icon.innerHTML=svgIcon('alert');
  const text=node('div',undefined,'error-text');text.append(node('strong',title),node('p',e.message));
  const actions=node('div',undefined,'error-actions');
  if(!compact)actions.append(labelBtn('refresh-cw','重试',()=>openComic(item),'small'));
  if(e.code==='login_required'&&e.source)actions.append(bindButton(e.source));
  actions.append(labelBtn('search','在其他图源搜索',()=>searchElsewhere(item.title),'small'));
  box.append(icon,text,actions);return box;
}
const CHAPTER_PAGE=60;
function chapterRow(detail,chapter,lastId){
  const id=String(chapter.id),progress=readLocal(progressKey(detail,id));
  const row=node('div',undefined,'chapter'+(id===lastId?' current':progress?' read':''));row.tabIndex=0;row.setAttribute('role','button');
  const label=node('div',undefined,'chapter-name');label.append(node('span',chapter.name||`第 ${chapter.order||''} 话`));
  if(id===lastId)label.append(node('small',`上次读到第 ${(progress?.index??0)+1} 页`));
  else if(progress)label.append(node('small',`读到第 ${progress.index+1} 页`));
  row.append(label,iconBtn('download','下载 PDF',()=>queueDownload(detail,chapter),'ghost'));
  row.onclick=event=>{if(event.target.closest('button,a'))return;openReader(id);};
  row.onkeydown=event=>{if((event.key==='Enter'||event.key===' ')&&event.target===row){event.preventDefault();openReader(id);}};
  return row;
}
// Chapters render in chunks so books with hundreds of episodes stay responsive.
function drawChapters(reset){
  const detail=state.detail,list=$('chapter-list');if(!detail||!list)return;
  if(reset){state.chapterView={shown:CHAPTER_PAGE,needle:($('chapter-filter')?.value||'').trim().toLowerCase()};list.replaceChildren();}
  const view=state.chapterView,lastId=readLocal(lastKey(detail))?.chapterId;
  const matched=(detail.chapters||[]).filter(c=>!view.needle||(c.name||'').toLowerCase().includes(view.needle));
  if(state.chapterDesc)matched.reverse();
  list.querySelector('.more-row')?.remove();
  for(const chapter of matched.slice(list.children.length,view.shown))list.append(chapterRow(detail,chapter,lastId));
  if(!matched.length)list.append(node('p',detail.chapters?.length?'没有匹配的章节':'暂无章节','empty'));
  else if(matched.length>list.children.length){const more=node('div',undefined,'more-row');more.append(button(`显示更多（还有 ${matched.length-list.children.length} 章）`,()=>{view.shown+=CHAPTER_PAGE;drawChapters();}));list.append(more);}
}
function syncChapterSort(){const b=$('chapter-sort');if(!b)return;b.innerHTML=svgIcon('sort');b.append(node('span',state.chapterDesc?'倒序':'正序'));b.title=state.chapterDesc?'切换为正序':'切换为倒序';}
function renderDetail() {
  const detail=state.detail,body=$('detail-body');detail.chapters=detail.chapters||[];$('detail-title').textContent=detail.title;body.replaceChildren();
  const {hero,text}=detailHero(detail,false);
  const meta=node('div',undefined,'detail-meta');
  meta.append(node('span',sourceName(detail.source),'badge accent'));
  if(detail.author){const a=node('span',undefined,'meta-item');a.innerHTML=svgIcon('user');a.append(node('span',detail.author));meta.append(a);}
  const n=node('span',undefined,'meta-item');n.innerHTML=svgIcon('list');n.append(node('span',`共 ${detail.chapters.length} 章`));meta.append(n);
  text.append(meta);
  const tags=String(detail.category||'').split(/[·,，、/|]/).map(t=>t.trim()).filter(Boolean).slice(0,10);
  if(tags.length){const box=node('div',undefined,'tags');box.append(...tags.map(t=>node('span',t,'tag')));text.append(box);}
  const desc=node('p',detail.description||'暂无简介','detail-desc');text.append(desc);
  const controls=node('div',undefined,'detail-actions');
  const last=readLocal(lastKey(detail));
  if(last&&detail.chapters.some(c=>String(c.id)===last.chapterId))controls.append(labelBtn('book-open',`继续阅读 · ${last.chapterName}`,()=>openReader(last.chapterId),'primary'));
  else if(detail.chapters.length)controls.append(labelBtn('play','开始阅读',()=>openReader(String(detail.chapters[0].id)),'primary'));
  const fav=button('',()=>toggleFavorite(detail).then(syncFav));
  const syncFav=()=>{const saved=inLibrary(detail);fav.innerHTML=svgIcon(saved?'check':'star');fav.append(node('span',saved?'已收藏':'收藏'));fav.classList.toggle('on',saved);fav.title=saved?'移出书库':'加入书库';};
  syncFav();controls.append(fav);
  if(detail.chapters.length)controls.append(labelBtn('download','下载全部',()=>downloadAll(detail)));
  controls.append(iconBtn('search','在其他图源搜索同名漫画',()=>searchElsewhere(detail.title)));
  text.append(controls);
  const section=node('section',undefined,'chapters'),head=node('div',undefined,'chapters-head'),tools=node('div',undefined,'chapters-tools');
  head.append(node('h3','章节'),node('span',String(detail.chapters.length),'count'),tools);
  if(detail.chapters.length>15){const filter=node('input');filter.id='chapter-filter';filter.type='search';filter.placeholder='筛选章节';filter.maxLength=50;filter.setAttribute('aria-label','筛选章节');filter.oninput=()=>drawChapters(true);tools.append(filter);}
  if(detail.chapters.length>1){const sort=node('button',undefined,'small');sort.id='chapter-sort';sort.type='button';sort.onclick=()=>{state.chapterDesc=!state.chapterDesc;saveLocal('comic:chapter-desc',state.chapterDesc);syncChapterSort();drawChapters(true);};tools.append(sort);}
  const list=node('div',undefined,'chapter-list');list.id='chapter-list';section.append(head,list);
  body.append(hero,section);syncChapterSort();drawChapters(true);
  // Long synopses collapse to a few lines with an explicit toggle.
  requestAnimationFrame(()=>{if(desc.scrollHeight>desc.clientHeight+2){const more=node('button','展开简介','link-btn');more.type='button';more.onclick=()=>{const open=desc.classList.toggle('open');more.textContent=open?'收起简介':'展开简介';};desc.after(more);}});
}
async function toggleFavorite(detail){
  if(inLibrary(detail)){
    if(!await ask({title:'移出书库',message:`确定将《${detail.title}》移出书库吗？`,ok:'移出',danger:true}))return;
    await api(bookPath(detail),{method:'DELETE'});await loadLibrary();toast('已移出书库');return;
  }
  await api(bookPath(detail),write('PUT',{category:''}));await loadLibrary();
  const book=state.books.find(b=>b.source===detail.source&&String(b.id)===String(detail.id));
  toast('已加入书库',{action:{label:'设置分类',run:()=>book&&run(()=>editCategory(book))}});
}
function syncDetailHead(){const dlg=$('detail-dialog');dlg.querySelector('.dialog-head').classList.toggle('scrolled',dlg.scrollTop>150);}
const taskPayload=(detail,chapter)=>write('POST',{source:detail.source,comic_id:String(detail.id),chapter_id:String(chapter.id),title:detail.title,chapter:chapter.name});
async function queueDownload(detail,chapter){await api('/api/downloads',taskPayload(detail,chapter));toast(`已加入下载：${chapter.name}`,{action:{label:'查看',run:openDownloads}});refreshTaskDot();}
async function downloadAll(detail){
  if(!await ask({title:'下载全部章节',message:`将《${detail.title}》全部 ${detail.chapters.length} 章加入下载队列？每章会单独打包为加密 PDF。`,ok:'开始下载'}))return;
  let queued=0,failed=0;
  for(const chapter of detail.chapters){try{await api('/api/downloads',taskPayload(detail,chapter));queued++;}catch{failed++;}}
  toast(`已加入 ${queued} 个任务${failed?`，${failed} 个失败（队列可能已满）`:''}`,{action:{label:'查看',run:openDownloads}});refreshTaskDot();
}
function openDownloads(){for(const id of ['reader-dialog','detail-dialog'])if($(id).open)id==='reader-dialog'?closeReader(true):$(id).close();showTab('downloads');}

/* ---------- downloads ---------- */
async function loadTasks(){
  const {tasks}=await api('/api/downloads');
  const active=tasks.filter(t=>['queued','running','cancelling'].includes(t.status)).length,done=tasks.filter(t=>t.status==='completed').length;
  state.activeTasks=active;document.querySelectorAll('[data-downloads-dot]').forEach(d=>d.hidden=!active);
  $('tasks-summary').textContent=tasks.length?`${active} 进行中 · ${done} 已完成 · 共 ${tasks.length}`:'';
  const sig=JSON.stringify(tasks),box=$('tasks');
  if(sig===state.taskSig&&box.children.length)return;state.taskSig=sig;
  if(!tasks.length){box.replaceChildren(emptyState('还没有下载任务','在漫画详情的章节列表中点击下载图标，即可把章节打包为 PDF。',labelBtn('compass','去发现漫画',()=>showTab('browse'),'primary'),'download'));return;}
  box.replaceChildren(...tasks.map(taskCard));
}
function refreshTaskDot(){loadTasks().catch(()=>{});}
function taskCard(task){
  const tone=TONES[task.status]||'info',card=node('article',undefined,'task '+tone);
  const head=node('div',undefined,'task-head'),titles=node('div',undefined,'task-titles');
  titles.append(node('h3',task.title||task.comic_id),node('p',task.chapter||task.chapter_id,'task-chapter'));
  head.append(titles,node('span',statuses[task.status]||task.status,'status-pill '+tone));
  const pct=task.status==='completed'?100:task.total?Math.round(task.completed/task.total*100):0;
  const bar=node('div',undefined,'bar'),fill=node('i');fill.style.width=pct+'%';bar.append(fill);
  const meta=node('p',undefined,'task-meta');
  meta.append(node('span',sourceName(task.source)));
  if(task.status==='running'&&statuses[task.stage])meta.append(node('span',statuses[task.stage]));
  meta.append(node('span',`${task.completed}/${task.total||'?'} 张 · ${pct}%`),node('span',timeAgo(task.updated_at||task.created_at)));
  card.append(head,meta,bar);
  if(task.error)card.append(node('p',task.error,'error'));
  const controls=node('div',undefined,'task-actions');
  if(task.status==='completed'){
    const link=node('a',undefined,'button primary small');link.href=`/api/downloads/${task.id}/file`;link.innerHTML=svgIcon('download');link.append(node('span','下载 PDF'));
    const pwd=node('span',undefined,'password');pwd.append(node('span','密码'),node('code',task.password));
    controls.append(link,pwd,iconBtn('copy','复制密码',async()=>{await copyText(task.password);toast('密码已复制');},'ghost'));
  }
  if(['queued','running'].includes(task.status))controls.append(labelBtn('x','取消',async()=>{await api(`/api/downloads/${task.id}/cancel`,{method:'POST'});await loadTasks();},'small'));
  if(['failed','cancelled','interrupted'].includes(task.status))controls.append(labelBtn('refresh-cw','重新下载',async()=>{await api(`/api/downloads/${task.id}/retry`,{method:'POST'});await loadTasks();},'small'));
  if(['failed','cancelled','completed','interrupted'].includes(task.status))controls.append(iconBtn('trash-2','删除任务及文件',async()=>{if(!await ask({title:'删除任务',message:'删除这条任务及服务器上的 PDF 文件？',ok:'删除',danger:true}))return;await api(`/api/downloads/${task.id}`,{method:'DELETE'});await loadTasks();},'ghost push'));
  card.append(controls);return card;
}

/* ---------- source management ---------- */
function accountLabel(plugin){return !plugin.capabilities.includes('login')?'无需登录':plugin.account.authenticated?'已登录':plugin.account.configured?'凭证已保存':'未绑定账号';}
function renderSourceList(){
  const list=$('source-list');list.replaceChildren();state.healthDots={};
  for(const plugin of state.sources){
    const row=node('article',undefined,'source-row'),info=node('div',undefined,'source-info');
    const h3=node('h3');const dot=node('span',undefined,'health-dot');syncHealthDot(plugin.id,dot);h3.append(dot,document.createTextNode(plugin.name));
    const account=node('span',accountLabel(plugin),'account-state'+(needsLogin(plugin)?' warn':''));
    const caps=node('div',undefined,'caps');caps.append(account,...plugin.capabilities.filter(c=>CAP_LABELS[c]&&c!=='login').map(c=>node('span',CAP_LABELS[c],'cap')));
    info.append(h3,caps);
    row.append(info,iconBtn('settings',`${plugin.name}设置`,()=>{state.settingsSource=plugin.id;renderSourceSettings();$('source-settings-dialog').showModal();}));list.append(row);
  }
}
function syncHealthDot(id,dot){
  dot.dataset.source=id;state.healthDots[id]=dot;
  const status=state.health[id];
  dot.classList.toggle('ok',status==='ok');dot.classList.toggle('down',status==='down');dot.classList.toggle('checking',status==='checking');
  dot.title=status==='ok'?'图源连通':status==='down'?'图源不可用':status==='checking'?'正在检测…':'未检测';
}
// Probe each source with its lightest listing; results land on the row dots.
async function checkSourceHealth(id){
  state.health[id]='checking';if(state.healthDots[id])syncHealthDot(id,state.healthDots[id]);
  try{
    const caps=sourcePlugin(id)?.capabilities||[];
    const probe=caps.includes('latest')?`/api/${enc(id)}/latest?page=1`:`/api/search?${new URLSearchParams({keyword:' ',source:id})}`;
    await api(probe,{signal:AbortSignal.timeout(15000)});
    state.health[id]='ok';
  }catch{state.health[id]='down';}
  if(state.healthDots[id])syncHealthDot(id,state.healthDots[id]);
}
function runHealthChecks(force){for(const plugin of state.sources)if(state.health[plugin.id]!=='checking'&&(force||!state.health[plugin.id]))checkSourceHealth(plugin.id);}
function renderSourceSettings(){
  const plugin=state.sources.find(s=>s.id===state.settingsSource),body=$('source-settings-body');body.replaceChildren();if(!plugin)return;
  $('source-settings-title').textContent=plugin.name+' · 设置';
  for(const field of plugin.settings_fields||[]){const section=node('section',undefined,'setting-section');section.append(node('h3',field.label),node('p',field.description||'','muted'));
    const form=node('form',undefined,'settings-form'),label=node('label',field.label),input=node('input');input.name=field.name;input.type=field.type==='url'?'url':'text';input.value=plugin.settings?.[field.name]||'';label.append(input);
    const submit=node('button','保存服务器地址','primary');submit.type='submit';form.append(label,submit);form.onsubmit=event=>{event.preventDefault();run(async()=>{await api(`/api/sources/${enc(plugin.id)}/settings`,write('PUT',{...plugin.settings,[field.name]:input.value}));await loadSources();toast('设置已保存，后续请求使用新地址');},submit);};section.append(form);body.append(section);}
  if(plugin.capabilities.includes('login')){const section=node('section',undefined,'setting-section');section.append(node('h3','登录凭证'),node('p',accountLabel(plugin),'muted'),labelBtn('key','管理登录凭证',()=>{configureAccount();$('credentials-dialog').showModal();}));body.append(section);}
  if(!(plugin.settings_fields||[]).length&&!plugin.capabilities.includes('login'))body.append(node('p','此图源使用自动服务器配置，无需登录，暂无可修改选项。','muted'));
}
function configureAccount(){
  const plugin=state.sources.find(s=>s.id===state.settingsSource),form=$('login-form');form.replaceChildren();if(!plugin)return;
  $('credentials-title').textContent=plugin.name+' · 登录凭证';
  if(!plugin.capabilities.includes('login')){$('account-state').textContent='此图源插件不提供登录功能。';return;}
  $('account-state').textContent=plugin.account.authenticated?'会话已保存，可直接使用。':plugin.account.configured?'账号已保存，将在请求时自动恢复会话。':'尚未绑定账号。凭证仅加密保存在本服务器。';
  for(const field of plugin.login_fields){const label=node('label',field.label);const input=node('input');input.name=field.name;input.type=field.type==='password'?'password':'text';input.autocomplete=field.type==='password'?'current-password':'username';input.required=true;label.append(input);form.append(label);}
  const actions=node('div',undefined,'form-actions');
  const submit=node('button','登录并保存','primary');submit.type='submit';actions.append(submit);
  if(plugin.account.configured||plugin.account.authenticated)actions.append(labelBtn('unlink','解除绑定',async()=>{if(!await ask({title:'解除绑定',message:`删除已保存的${plugin.name}账号与会话？`,ok:'解除',danger:true}))return;await api(`/api/sources/${enc(plugin.id)}/account`,{method:'DELETE'});await loadSources();configureAccount();toast('已解除绑定');}));
  form.append(actions);
}

/* ---------- reader ---------- */
function saveProgress(){const r=state.reader;if(!r||!r.images.length)return;const value={chapterId:r.chapterId,chapterName:r.chapterName,index:r.index,updatedAt:Date.now()};saveLocal(progressKey(r.book,r.chapterId),value);saveLocal(lastKey(r.book),value);recordHistory(r);}
function readerMessage(text,loading){const box=node('div',undefined,'reader-message');if(loading)box.append(node('span',undefined,'spinner'));box.append(node('p',text));return box;}
function syncPageStatus(){
  const r=state.reader,slider=$('page-slider');if(!r)return;const n=r.images.length;
  $('page-status').textContent=`${n?r.index+1:0} / ${n}`;slider.max=String(Math.max(1,n));slider.value=String(r.index+1);slider.disabled=n<2;
  slider.style.setProperty('--p',n>1?r.index/(n-1):1);
}
function fillChapterSelect(book,chapterId){
  const select=$('reader-chapter');
  if(state.readerSelectBook!==book){state.readerSelectBook=book;select.replaceChildren(...book.chapters.map(c=>{const o=node('option',c.name);o.value=String(c.id);return o;}));}
  select.value=chapterId;select.hidden=book.chapters.length<2;
}
async function openReader(chapterId,startAt){
  saveProgress();const book=state.detail;if(!book)return;book.chapters=book.chapters||[];const chapter=book.chapters.find(c=>String(c.id)===chapterId);if(!chapter)return;
  const request=++state.readerRequest;state.readerAbort?.abort();state.readerAbort=new AbortController();state.reader=null;
  state.observer?.disconnect();state.mounter?.disconnect();
  $('reader-comic').textContent=book.title;$('reader-title').textContent=chapter.name;fillChapterSelect(book,chapterId);
  $('reader-pages').replaceChildren(readerMessage('正在获取章节…',true));$('page-status').textContent='';
  const index=book.chapters.indexOf(chapter);$('chapter-prev').disabled=index<=0;$('chapter-next').disabled=index>=book.chapters.length-1;
  $('reader-dialog').classList.add('ui-open','ui-pinned');
  if(!$('reader-dialog').open)$('reader-dialog').showModal();
  try{const data=await api(`/api/chapter/${enc(book.source)}/${enc(book.id)}/${enc(chapterId)}`,{signal:state.readerAbort.signal});if(request!==state.readerRequest)return;
    const saved=readLocal(progressKey(book,chapterId));const resume=Math.max(0,Math.min(Number(saved?.index)||0,data.images.length-1));
    state.reader={book,chapterId,chapterName:chapter.name,images:data.images,index:typeof startAt==='number'?(startAt<0?Math.max(0,data.images.length-1):0):resume};renderReader();
  }catch(e){
    if(request!==state.readerRequest||e.name==='AbortError')return;
    const box=readerMessage(e.message);const actions=node('div',undefined,'reader-actions');
    actions.append(labelBtn('refresh-cw','重试',()=>openReader(chapterId,startAt)));
    if(e.code==='login_required'&&e.source)actions.append(bindButton(e.source));
    actions.append(labelBtn('search','在其他图源搜索',()=>searchElsewhere(book.title)));
    box.append(actions);$('reader-pages').replaceChildren(box);
  }
}
function chapterEnd(r){
  const box=node('div',undefined,'chapter-end'),chapters=r.book.chapters,i=chapters.findIndex(c=>String(c.id)===r.chapterId),next=chapters[i+1];
  box.append(node('p','本章完','chapter-end-title'),node('p',next?`下一章：${next.name}`:'已经是最后一章了','muted'));
  const actions=node('div',undefined,'reader-actions');
  if(next)actions.append(labelBtn('chevrons-right','阅读下一章',()=>moveChapter(1,true),'primary'));
  actions.append(labelBtn('list','返回目录',()=>closeReader()));
  box.append(actions);return box;
}
function renderReader(){
  state.observer?.disconnect();state.mounter?.disconnect();const r=state.reader,container=$('reader-pages');if(!r)return;container.replaceChildren();container.scrollTop=0;
  state.readerQuietUntil=Date.now()+900;
  const paged=$('reader-mode').value==='page';container.classList.toggle('paged',paged);
  syncPageStatus();
  if(!r.images.length){container.replaceChildren(readerMessage('该章节暂无图片'));return;}
  const makeImage=index=>{const wrapper=node('div','','page');wrapper.dataset.index=index;const img=image(r.images[index],`第 ${index+1} 页`);img.loading='eager';img.addEventListener('load',()=>img.classList.toggle('tall',img.naturalHeight>img.naturalWidth*2.5));img.onerror=()=>{const fail=node('div',undefined,'image-error');fail.append(node('p',`第 ${index+1} 页加载失败`),labelBtn('refresh-cw','重新加载',()=>{wrapper.replaceWith(makeImage(index));},'small'));wrapper.replaceChildren(fail);};wrapper.append(img);return wrapper;};
  if(paged){container.append(makeImage(r.index));for(const ahead of [r.index+1,r.index+2,r.index-1]){if(ahead>=0&&ahead<r.images.length){const preload=new Image();preload.src=r.images[ahead];}}}
  else{
    // Mount placeholders for every page; real <img> nodes are created only near the viewport.
    const mount=el=>{const real=makeImage(Number(el.dataset.index));state.mounter?.unobserve(el);state.observer?.unobserve(el);state.observer?.observe(real);el.replaceWith(real);};
    for(let i=0;i<r.images.length;i++){const ph=node('div',undefined,'ph');ph.dataset.index=i;container.append(ph);}
    container.append(chapterEnd(r));
    const pages=()=>[...container.children].filter(n=>n.dataset.index!==undefined);
    state.mounter=new IntersectionObserver(entries=>{for(const entry of entries)if(entry.isIntersecting&&entry.target.classList.contains('ph'))mount(entry.target);},{root:container,rootMargin:'250% 0px'});
    pages().forEach(n=>state.mounter.observe(n));
    mount(container.children[r.index]);
    for(const near of [r.index+1,r.index-1]){const el=container.children[near];if(el?.classList.contains('ph'))mount(el);}
    container.children[r.index]?.scrollIntoView({block:'start'});
    // Wait for the target page to load before observing, so restoring does not overwrite saved progress.
    let restored=false;const restore=()=>{if(restored||state.reader!==r||$('reader-mode').value!=='scroll')return;restored=true;state.readerQuietUntil=Date.now()+600;container.children[r.index]?.scrollIntoView({block:'start'});state.observer=new IntersectionObserver(entries=>{const visible=entries.filter(e=>e.isIntersecting).sort((a,b)=>a.boundingClientRect.top-b.boundingClientRect.top);if(visible.length){r.index=Number(visible[0].target.dataset.index);syncPageStatus();saveProgress();}},{root:container,rootMargin:'0px 0px -70% 0px',threshold:0});pages().forEach(n=>state.observer.observe(n));};
    const img=container.children[r.index]?.querySelector('img');
    if(img){img.addEventListener('load',restore,{once:true});img.addEventListener('error',restore,{once:true});if(img.complete)restore();}else restore();
  }
  saveProgress();
  syncReaderProgress();
}
// Pinch/drag zoom for reader images. Zoom state lives on the img element.
const pinch={pointers:new Map(),g:null,suppress:false};
function zoomApply(img){const z=img._zoom||{s:1,x:0,y:0};img.style.transform=`translate(${z.x}px,${z.y}px) scale(${z.s})`;img.classList.toggle('zoomed',z.s>1.01);}
function resetZoom(img){img._zoom={s:1,x:0,y:0};zoomApply(img);}
function zoomAround(img,s,px,py){const z=img._zoom||{s:1,x:0,y:0};const ns=Math.max(1,Math.min(6,z.s*s));const f=ns/z.s;z.x=px-(px-z.x)*f;z.y=py-(py-z.y)*f;z.s=ns;img._zoom=z;zoomApply(img);}
$('reader-pages').addEventListener('pointerdown',event=>{
  const img=event.target.closest('img');if(!img)return;
  pinch.pointers.set(event.pointerId,{x:event.clientX,y:event.clientY,img});
  if(pinch.pointers.size===1)pinch.g={img};
  else if(pinch.pointers.size===2){const [a,b]=[...pinch.pointers.values()];pinch.g={d0:Math.hypot(a.x-b.x,a.y-b.y)||1,img:a.img===b.img?a.img:null};}
  try{$('reader-pages').setPointerCapture(event.pointerId);}catch{}
});
$('reader-pages').addEventListener('pointermove',event=>{
  const p=pinch.pointers.get(event.pointerId);if(!p)return;
  const dx=event.clientX-p.x,dy=event.clientY-p.y;
  p.x=event.clientX;p.y=event.clientY;
  if(pinch.pointers.size===2&&pinch.g&&pinch.g.img){
    const [a,b]=[...pinch.pointers.values()];const d=Math.hypot(a.x-b.x,a.y-b.y)||1;
    zoomAround(pinch.g.img,d/pinch.g.d0,(a.x+b.x)/2,(a.y+b.y)/2);pinch.g.d0=d;pinch.suppress=true;
  }else if(pinch.pointers.size===1){
    const img=p.img,z=img&&img._zoom;
    if(z&&z.s>1.01&&(dx||dy)){z.x+=dx;z.y+=dy;zoomApply(img);pinch.suppress=true;}
  }
});
const pinchEnd=event=>{
  pinch.pointers.delete(event.pointerId);
  const img=pinch.g?.img;
  if(pinch.pointers.size<2&&img&&img._zoom&&img._zoom.s<=1.05)resetZoom(img);
  if(pinch.pointers.size===1)pinch.g={img:[...pinch.pointers.values()][0].img};
  if(!pinch.pointers.size)pinch.g=null;
  setTimeout(()=>pinch.suppress=false,50);
};
$('reader-pages').addEventListener('pointerup',pinchEnd);
$('reader-pages').addEventListener('pointercancel',pinchEnd);
// Thin progress line along the toolbar bottom; scroll mode tracks the container, paged mode the index.
function syncReaderProgress(){const r=state.reader,el=$('reader-progress');if(!r||!el)return;const c=$('reader-pages');
  const p=$('reader-mode').value==='page'?(r.images.length>1?r.index/(r.images.length-1):1):(c.scrollTop/(c.scrollHeight-c.clientHeight||1));
  el.style.setProperty('--p',Math.max(0,Math.min(1,p)));}
// Scrolling down hides the reader chrome, scrolling up brings it back.
$('reader-pages').addEventListener('scroll',()=>{
  syncReaderProgress();
  const c=$('reader-pages'),dlg=$('reader-dialog'),y=c.scrollTop,dy=y-(state.lastReaderY??y);state.lastReaderY=y;
  if(Date.now()<(state.readerQuietUntil||0)||$('reader-mode').value!=='scroll'||dlg.querySelector(':focus-within select,:focus-within input'))return;
  if(dy>24){dlg.classList.remove('ui-open','ui-pinned');}
  else if(dy<-36){dlg.classList.add('ui-open');}
},{passive:true});
function gotoPage(index){const r=state.reader;if(!r||index<0||index>=r.images.length)return;const from=r.index;r.index=index;if($('reader-mode').value==='page')renderReader();else{const el=$('reader-pages').children[index];if(el?.classList.contains('ph')){state.readerQuietUntil=Date.now()+900;}el?.scrollIntoView({block:'start',behavior:Math.abs(index-from)>3?'auto':'smooth'});syncPageStatus();saveProgress();}syncReaderProgress();}
function movePage(delta){const r=state.reader;if(!r)return;const index=r.index+delta;if(index<0||index>=r.images.length){moveChapter(delta,true);return;}gotoPage(index);}
function moveChapter(delta,turn){const r=state.reader,book=r?.book||state.detail;if(!book)return;const chapters=book.chapters,current=r?r.chapterId:$('reader-chapter').value,index=chapters.findIndex(c=>String(c.id)===current);if(chapters[index+delta])run(()=>openReader(String(chapters[index+delta].id),turn?(delta>0?0:-1):undefined));else toast(delta>0?'已经是最后一章了':'已经是第一章了');}
function closeReader(silent){
  saveProgress();state.readerAbort?.abort();++state.readerRequest;state.observer?.disconnect();state.mounter?.disconnect();state.reader=null;
  if(document.fullscreenElement)document.exitFullscreen().catch(()=>{});
  $('reader-dialog').close();$('reader-pages').replaceChildren();renderContinue();
  if(!silent&&state.detail&&$('detail-dialog').open){const dlg=$('detail-dialog'),top=dlg.scrollTop;renderDetail();dlg.scrollTop=top;}
}

/* ---------- wiring ---------- */
document.querySelectorAll('[data-tab]').forEach(n=>n.onclick=()=>showTab(n.dataset.tab));
document.querySelectorAll('[data-close]').forEach(n=>n.onclick=()=>{if(n.dataset.close==='detail-dialog')++state.detailRequest;$(n.dataset.close).close();});
// Click on the dialog backdrop (outside its content) closes it, same as the close button.
document.querySelectorAll('dialog:not(#reader-dialog)').forEach(dlg=>dlg.addEventListener('click',event=>{if(event.target!==dlg)return;const r=dlg.getBoundingClientRect();if(event.clientX>=r.left&&event.clientX<=r.right&&event.clientY>=r.top&&event.clientY<=r.bottom)return;if(dlg.id==='detail-dialog')++state.detailRequest;dlg.close();}));
$('detail-dialog').addEventListener('scroll',syncDetailHead,{passive:true});
$('browse-form').onsubmit=browse;
function syncClear(){$('keyword-clear').hidden=!$('keyword').value;}
$('keyword').addEventListener('input',syncClear);
$('keyword').addEventListener('keydown',event=>{if(event.key==='Escape'&&$('keyword').value){event.preventDefault();$('keyword').value='';syncClear();}});
$('keyword-clear').onclick=()=>{$('keyword').value='';syncClear();$('keyword').focus();};
$('home-link').onclick=event=>{event.preventDefault();goHome();$('keyword').focus();};
$('brand').onclick=event=>{event.preventDefault();if(state.tab!=='browse')showTab('browse');goHome();};
$('results-back').onclick=goHome;
$('discover-prev').onclick=()=>turnPage(-1);$('discover-next').onclick=()=>turnPage(1);
$('discover-again').onclick=()=>run(loadDiscover,$('discover-again'));
$('results-more-btn').onclick=showMoreResults;
new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting)&&!$('results-more').hidden)showMoreResults();},{rootMargin:'800px 0px'}).observe($('results-more'));
$('recent-clear').onclick=()=>{saveLocal('comic:recent',[]);renderRecent();};
$('history-clear').onclick=()=>run(async()=>{if(!await ask({title:'清除阅读记录',message:'清空「继续阅读」列表？各章节的阅读进度会保留。',ok:'清除',danger:true}))return;saveLocal('comic:history',[]);renderContinue();});
{const row=$('continue-row'),shelf=row.parentElement;shelf.append(state.continueScroller=scrollerFor(row));}
window.addEventListener('resize',()=>document.querySelectorAll('.scroller').forEach(s=>s.syncArrows?.()),{passive:true});
// Back/forward moves between the home view and results, restoring the query and filters.
window.addEventListener('popstate',event=>{
  const snap=event.state;if(!state.browseReady)return;
  if(state.tab!=='browse')showTab('browse');
  if(snap?.view==='results'){
    state.search=snap.search?{...snap.search}:null;Object.assign(state.discover,snap.discover||{});
    $('keyword').value=state.search?.keyword||'';syncClear();setView('results');run(state.search?loadSearch:loadDiscover);
  }else showHome();
});
$('library-refresh').onclick=()=>run(loadLibrary,$('library-refresh'));$('library-category').onchange=filterBooks;$('library-sort').onchange=filterBooks;$('library-filter').oninput=filterBooks;$('tasks-refresh').onclick=()=>run(loadTasks,$('tasks-refresh'));
$('accounts').onclick=()=>run(async()=>{await loadSources();$('account-dialog').showModal();runHealthChecks(false);});
$('health-recheck').onclick=()=>runHealthChecks(true);
$('login-form').onsubmit=event=>{event.preventDefault();const source=state.settingsSource;run(async()=>{await api(`/api/sources/${enc(source)}/login`,write('POST',Object.fromEntries(new FormData(event.target))));await loadSources();configureAccount();toast('图源账号已保存');},event.submitter);};
$('reader-close').onclick=()=>closeReader();$('reader-dialog').addEventListener('cancel',event=>{event.preventDefault();closeReader();});
$('reader-download').onclick=()=>{const r=state.reader,book=r?.book||state.detail;if(!book)return;const chapter=(book.chapters||[]).find(c=>String(c.id)===(r?r.chapterId:$('reader-chapter').value));if(chapter)queueDownload(book,chapter);};
const toggleReaderUI=()=>{const dlg=$('reader-dialog');const on=!dlg.classList.contains('ui-open');dlg.classList.toggle('ui-open',on);dlg.classList.toggle('ui-pinned',on);};
const syncReaderUI=event=>{if(event.pointerType!=='mouse')return;const y=event.clientY;const dlg=$('reader-dialog');if(y<=70||y>=innerHeight-110)dlg.classList.add('ui-open');else if(!dlg.classList.contains('ui-pinned'))dlg.classList.remove('ui-open');};
$('reader-dialog').addEventListener('pointermove',syncReaderUI);$('reader-dialog').addEventListener('pointerleave',()=>{const dlg=$('reader-dialog');if(!dlg.classList.contains('ui-pinned'))dlg.classList.remove('ui-open');});
// Tap zones: in paged mode left/right thirds turn pages, middle toggles UI; in scroll mode any tap toggles UI.
$('reader-pages').addEventListener('click',event=>{if(pinch.suppress||event.target.closest('button,a,select,input'))return;const paged=$('reader-mode').value==='page';const third=event.clientX/innerWidth;if(!paged||third>0.33&&third<0.67){toggleReaderUI();return;}movePage(third<0.5?-1:1);});
$('reader-mode').value=readLocal('comic:reader-mode')==='page'?'page':'scroll';$('reader-mode').onchange=()=>{saveLocal('comic:reader-mode',$('reader-mode').value);renderReader();};
$('reader-chapter').onchange=()=>run(()=>openReader($('reader-chapter').value));
$('page-slider').oninput=()=>{const r=state.reader;if(r)$('page-status').textContent=`${$('page-slider').value} / ${r.images.length}`;};
$('page-slider').onchange=()=>gotoPage(Number($('page-slider').value)-1);
$('reader-fullscreen').onclick=()=>{if(document.fullscreenElement)document.exitFullscreen().catch(()=>{});else $('reader-dialog').requestFullscreen?.().catch(()=>toast('浏览器不支持全屏'));};
$('page-prev').onclick=()=>movePage(-1);$('page-next').onclick=()=>movePage(1);$('chapter-prev').onclick=()=>moveChapter(-1);$('chapter-next').onclick=()=>moveChapter(1);
window.addEventListener('keydown',event=>{
  if(!$('reader-dialog').open||['INPUT','SELECT','TEXTAREA'].includes(event.target.tagName)||$('ask-dialog').open)return;const r=state.reader;
  if(['ArrowRight','PageDown',' '].includes(event.key)){event.preventDefault();movePage(1);}
  else if(['ArrowLeft','PageUp'].includes(event.key)){event.preventDefault();movePage(-1);}
  else if(event.key==='Home'&&r){event.preventDefault();gotoPage(0);}
  else if(event.key==='End'&&r){event.preventDefault();gotoPage(r.images.length-1);}
  else if(event.key==='['){moveChapter(-1);}else if(event.key===']'){moveChapter(1);}
  else if(event.key==='f'){$('reader-fullscreen').click();}
});
// "/" focuses the search box from anywhere outside inputs and dialogs.
window.addEventListener('keydown',event=>{
  if(event.key!=='/'||event.ctrlKey||event.metaKey||event.altKey||document.querySelector('dialog[open]'))return;
  if(event.target.closest?.('input,textarea,select,[contenteditable="true"]'))return;
  event.preventDefault();if(state.tab!=='browse')showTab('browse');$('keyword').focus();$('keyword').select();
});
window.addEventListener('pagehide',saveProgress);
// Page-level scrollbar + floating back-to-top button.
window.addEventListener('scroll',()=>{
  const h=document.documentElement,p=h.scrollTop/(h.scrollHeight-h.clientHeight||1);
  $('scroll-progress').style.transform=`scaleX(${p})`;
  $('to-top').classList.toggle('show',h.scrollTop>600);
  document.body.classList.toggle('scrolled',h.scrollTop>8);
},{passive:true});
$('to-top').onclick=()=>window.scrollTo({top:0,behavior:'smooth'});
document.documentElement.classList.toggle('light',readLocal('comic:light')??!matchMedia('(prefers-color-scheme: dark)').matches);
matchMedia('(prefers-color-scheme: dark)').addEventListener('change',event=>{if(readLocal('comic:light')===null)document.documentElement.classList.toggle('light',!event.matches);});
function syncThemeColor(){document.querySelector('meta[name=theme-color]').content=document.documentElement.classList.contains('light')?'#f7f5f1':'#0e0e12';}
$('theme').onclick=()=>{saveLocal('comic:light',document.documentElement.classList.toggle('light'));syncThemeColor();};
syncThemeColor();
setInterval(()=>{if((state.tab==='downloads'||state.activeTasks)&&!document.hidden&&!loadTasks.busy){loadTasks.busy=true;loadTasks().catch(e=>{if(state.tab==='downloads')toast(e.message);}).finally(()=>loadTasks.busy=false);}},2500);
// autofocus pops the on-screen keyboard on touch devices; drop it there.
if(matchMedia('(pointer:coarse)').matches&&document.activeElement===$('keyword'))$('keyword').blur();
run(async()=>{await loadSources();await loadLibrary();refreshTaskDot();});
