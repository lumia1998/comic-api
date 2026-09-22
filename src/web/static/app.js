'use strict';
const $ = id => document.getElementById(id);
const state = {sources: [], tab: 'browse', books: [], detail: null, reader: null, browseRequest: 0, detailRequest: 0, readerRequest: 0};
const enc = encodeURIComponent;
const statuses = {queued:'排队中',running:'执行中',cancelling:'正在取消',cancelled:'已取消',failed:'失败',completed:'已完成',fetching:'获取章节',downloading:'下载图片',packaging:'打包 PDF',interrupted:'重启中断'};
function node(tag, text, className) {const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(className)n.className=className;return n;}
function button(text, action, className) {const n=node('button',text,className);n.type='button';n.onclick=()=>run(action,n);return n;}
const icons={star:'<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>','book-open':'<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',download:'<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>','refresh-cw':'<polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>',tag:'<path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.83z"/><line x1="7" y1="7" x2="7.01" y2="7"/>','trash-2':'<polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/>',x:'<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',settings:'<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>',key:'<path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/>',unlink:'<path d="m18.84 12.25 1.72-1.71h-.02a5.004 5.004 0 0 0-.12-7.07 5.006 5.006 0 0 0-6.95 0l-1.72 1.71"/><path d="m5.17 11.75-1.71 1.71a5.004 5.004 0 0 0 .12 7.07 5.006 5.006 0 0 0 6.95 0l1.71-1.71"/><line x1="8" y1="2" x2="8" y2="5"/><line x1="2" y1="8" x2="5" y2="8"/><line x1="16" y1="19" x2="16" y2="22"/><line x1="19" y1="16" x2="22" y2="16"/>','arrow-left':'<line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>'};
const svgIcon=name=>`<svg viewBox="0 0 24 24">${icons[name]}</svg>`;
function iconBtn(name, label, action, className) {const n=node('button',undefined,(className?className+' ':'')+'icon-btn');n.type='button';n.title=label;n.setAttribute('aria-label',label);n.innerHTML=svgIcon(name);n.onclick=()=>run(action,n);return n;}
function iconLink(name, label, href) {const n=node('a',undefined,'icon-btn');n.title=label;n.setAttribute('aria-label',label);n.innerHTML=svgIcon(name);n.href=href;return n;}
async function run(action, control) {if(control)control.disabled=true;try{return await action();}catch(e){if(e.name!=='AbortError')toast(e.message);}finally{if(control)control.disabled=false;}}
function toast(message) {$('toast').textContent=message;$('toast').hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('toast').hidden=true,5000);}
async function api(path, options={}) {const response=await fetch(path,{...options,headers:{'Content-Type':'application/json',...options.headers}});const data=await response.json();if(!response.ok)throw new Error(data.error?.message||data.detail||`请求失败 (${response.status})`);return data;}
const write=(method,data)=>({method,body:JSON.stringify(data)});
const sourceName=id=>state.sources.find(s=>s.id===id)?.name||id;
const bookPath=b=>`/api/library/${enc(b.source)}/${enc(b.id)}`;
function options(select, values, selected) {select.replaceChildren(...values.map(v=>{const n=node('option',v.label);n.value=v.value;return n;}));if(values.some(v=>v.value===selected))select.value=selected;}
function readLocal(key) {try{return JSON.parse(localStorage.getItem(key));}catch{return null;}}
function saveLocal(key,value) {try{localStorage.setItem(key,JSON.stringify(value));}catch{if(!saveLocal.warned){toast('浏览器无法保存进度，请检查存储权限');saveLocal.warned=true;}}}
function progressKey(b,chapter) {return 'comic:progress:'+JSON.stringify([b.source,b.id,chapter]);}
function lastKey(b) {return 'comic:last:'+JSON.stringify([b.source,b.id]);}
function safeImage(url) {try {const u=new URL(url,location.origin);return ['http:','https:'].includes(u.protocol)?u.href:'';}catch{return '';}}
function image(url, alt, className) {const n=node('img',undefined,className);n.alt=alt;n.loading='lazy';const safe=safeImage(url);if(safe)n.src=safe;n.onerror=()=>{n.removeAttribute('src');n.alt='封面暂不可用';};return n;}

async function loadSources() {
  state.sources=(await api('/api/sources')).sources;
  renderSourceList();
  if(state.settingsSource)renderSourceSettings();
}
function showTab(tab) {state.tab=tab;for(const id of ['browse','library','downloads'])$(id).hidden=id!==tab;document.querySelectorAll('[data-tab]').forEach(n=>n.classList.toggle('active',n.dataset.tab===tab));if(tab==='library')run(loadLibrary);if(tab==='downloads')run(loadTasks);}
function renderCards(container, items, library=false) {
  container.replaceChildren();
  if(!items.length){container.append(node('p','暂无漫画','empty'));return;}
  for(const item of items){
    const card=node('article',undefined,'card');const open=button('',()=>openComic(item),'card-open');
    open.append(image(item.cover,item.title,'cover'));
    const info=node('div',undefined,'card-info');info.append(node('span',sourceName(item.source),'badge'),node('h3',item.title),node('p',item.author||'佚名'));
    const last=readLocal(lastKey(item));if(last)info.append(node('p',`本机读至 ${last.chapterName} · 第 ${last.index+1} 页`));
    if(library)info.append(node('p',`${item.library_category||'未分类'} · ${item.chapters?.length||0} 章`));
    open.append(info);card.append(open);
    if(library){const controls=node('div',undefined,'card-actions');controls.append(
      iconBtn('refresh-cw','检查更新',async()=>{const result=await api(bookPath(item)+'/refresh',{method:'POST'});toast(`新增 ${result.new_chapters} 章`);await loadLibrary();}),
      iconBtn('tag','分类',async()=>{const category=prompt('分类名称（留空为未分类）',item.library_category);if(category===null)return;await api(bookPath(item),write('PATCH',{category}));await loadLibrary();}),
      iconBtn('trash-2','移出书库',async()=>{await api(bookPath(item),{method:'DELETE'});await loadLibrary();}));card.append(controls);}
    container.append(card);
  }
}
async function browse(event) {
  event.preventDefault();const request=++state.browseRequest;
  state.browseAbort?.abort();state.browseAbort=new AbortController();
  const keyword=$('keyword').value.trim();
  if(!keyword){toast('请输入关键词');return;}
  $('browse-status').textContent='正在加载…';$('results').replaceChildren();
  try{
    const data=await api('/api/search?'+new URLSearchParams({keyword}),{signal:state.browseAbort.signal});
    if(request!==state.browseRequest)return;
    renderCards($('results'),data.items);
    const errors=Object.entries(data.errors||{}).map(([id,error])=>`${sourceName(id)}：${error.message}`);
    $('browse-status').textContent=`找到 ${data.items.length} 部漫画${errors.length?'\n部分图源失败：'+errors.join('；'):''}`;
  }catch(e){if(request===state.browseRequest&&e.name!=='AbortError')$('browse-status').textContent=e.message;}
}
async function loadLibrary() {const data=await api('/api/library');state.books=data.items;options($('library-category'),[{value:'*',label:'全部分类'},{value:'',label:'未分类'},...data.categories.map(v=>({value:v,label:v}))],$('library-category').value);filterBooks();}
function filterBooks(){const category=$('library-category').value;renderCards($('books'),state.books.filter(b=>category==='*'||b.library_category===category),true);}
async function openComic(item) {
  const request=++state.detailRequest;state.detail=null;$('detail-title').textContent=item.title||'漫画详情';$('detail-body').textContent='正在加载…';if(!$('detail-dialog').open)$('detail-dialog').showModal();
  try{const detail=await api(`/api/comic/${enc(item.source)}/${enc(item.id)}`);if(request!==state.detailRequest)return;state.detail=detail;renderDetail();}
  catch(e){if(request===state.detailRequest){if(item.chapters){state.detail=item;renderDetail();$('detail-body').prepend(node('p','图源不可用，显示书库缓存：'+e.message,'error'));}else $('detail-body').textContent=e.message;}}
}
function renderDetail() {
  const detail=state.detail,body=$('detail-body');$('detail-title').textContent=detail.title;body.replaceChildren();
  const cover=node('div',undefined,'cover-wrap');cover.append(image(detail.cover,detail.title),node('p',`共 ${detail.chapters.length} 章`,'cover-count'));const summary=node('div',undefined,'detail-summary');summary.append(cover);const text=node('div',undefined,'detail-text');text.append(node('p',`${sourceName(detail.source)} · ${detail.author||'佚名'}`),node('p',detail.description||'暂无简介'));summary.append(text);body.append(summary);
  const controls=node('div',undefined,'actions');
  controls.append(iconBtn('star','收藏到书库',async()=>{const existing=state.books.find(b=>b.source===detail.source&&b.id===detail.id);const category=prompt('收藏分类（可留空）',existing?.library_category||'');if(category===null)return;await api(bookPath(detail),write('PUT',{category}));toast('已加入书库');await loadLibrary();},'primary'));
  const last=readLocal(lastKey(detail));if(last&&detail.chapters.some(c=>String(c.id)===last.chapterId))controls.append(iconBtn('book-open',`继续阅读 · ${last.chapterName}`,()=>openReader(last.chapterId)));
  text.append(controls);
  for(const chapter of detail.chapters){const row=node('div',undefined,'chapter');const progress=readLocal(progressKey(detail,String(chapter.id)));row.append(node('span',chapter.name+(progress?` · 本机第 ${progress.index+1} 页`:'')),iconBtn('book-open','阅读',()=>openReader(String(chapter.id))),iconBtn('download','下载 PDF',()=>queueDownload(detail,chapter)));body.append(row);}
}
async function queueDownload(detail,chapter){await api('/api/downloads',write('POST',{source:detail.source,comic_id:String(detail.id),chapter_id:String(chapter.id),title:detail.title,chapter:chapter.name}));toast('已加入下载任务，可在任务中心查看');}
async function loadTasks(){
  const {tasks}=await api('/api/downloads');$('tasks').replaceChildren();if(!tasks.length)$('tasks').append(node('p','尚无下载任务。在章节列表中选择下载 PDF。','empty'));
  for(const task of tasks){const card=node('article',undefined,'task');card.append(node('h3',`${task.title||task.comic_id} · ${task.chapter||task.chapter_id}`),node('p',`${sourceName(task.source)} · ${statuses[task.status]} · ${statuses[task.stage]||task.stage} · ${task.completed}/${task.total} 张`));
    const progress=node('progress');progress.max=task.total||1;progress.value=task.completed;card.append(progress);
    if(task.error)card.append(node('p',task.error,'error'));const controls=node('div',undefined,'actions');
    if(['queued','running'].includes(task.status))controls.append(iconBtn('x','取消',async()=>{await api(`/api/downloads/${task.id}/cancel`,{method:'POST'});await loadTasks();}));
    if(['failed','cancelled'].includes(task.status))controls.append(iconBtn('refresh-cw','重新下载',async()=>{await api(`/api/downloads/${task.id}/retry`,{method:'POST'});await loadTasks();}));
    if(task.status==='completed'){const link=iconLink('download','下载 PDF',`/api/downloads/${task.id}/file`);controls.append(link,node('span',`密码：${task.password}`));}
    if(['failed','cancelled','completed'].includes(task.status))controls.append(iconBtn('trash-2','删除任务及文件',async()=>{if(!confirm('删除这条任务及服务器上的 PDF 文件？'))return;await api(`/api/downloads/${task.id}`,{method:'DELETE'});await loadTasks();}));
    card.append(controls);$('tasks').append(card);
  }
}
function accountLabel(plugin){return !plugin.capabilities.includes('login')?'无需登录':plugin.account.authenticated?'会话已保存':plugin.account.configured?'凭证已保存':'未绑定账号';}
function renderSourceList(){
  const list=$('source-list');list.replaceChildren();
  for(const plugin of state.sources){const row=node('article',undefined,'source-row'),info=node('div');info.append(node('h3',plugin.name),node('p',accountLabel(plugin),'muted'));row.append(info,iconBtn('settings','设置',()=>{state.settingsSource=plugin.id;renderSourceSettings();$('source-settings-dialog').showModal();}));list.append(row);}
}
function renderSourceSettings(){
  const plugin=state.sources.find(s=>s.id===state.settingsSource),body=$('source-settings-body');body.replaceChildren();if(!plugin)return;
  $('source-settings-title').textContent=plugin.name+' · 设置';
  for(const field of plugin.settings_fields||[]){const section=node('section',undefined,'setting-section');section.append(node('h3',field.label),node('p',field.description||'','muted'));
    const form=node('form',undefined,'settings-form'),label=node('label',field.label),input=node('input');input.name=field.name;input.type=field.type==='url'?'url':'text';input.value=plugin.settings?.[field.name]||'';label.append(input);
    const submit=node('button','保存服务器地址','primary');submit.type='submit';form.append(label,submit);form.onsubmit=event=>{event.preventDefault();run(async()=>{await api(`/api/sources/${enc(plugin.id)}/settings`,write('PUT',{...plugin.settings,[field.name]:input.value}));await loadSources();toast('设置已保存，后续请求使用新地址');},submit);};section.append(form);body.append(section);}
  if(plugin.capabilities.includes('login')){const section=node('section',undefined,'setting-section');section.append(node('h3','登录凭证'),node('p',accountLabel(plugin),'muted'),iconBtn('key','管理登录凭证',()=>{configureAccount();$('credentials-dialog').showModal();}));body.append(section);}
  if(!(plugin.settings_fields||[]).length&&!plugin.capabilities.includes('login'))body.append(node('p','此图源使用自动服务器配置，无需登录，暂无可修改选项。','muted'));
}
function configureAccount(){
  const plugin=state.sources.find(s=>s.id===state.settingsSource),form=$('login-form');form.replaceChildren();if(!plugin)return;
  $('credentials-title').textContent=plugin.name+' · 登录凭证';
  if(!plugin.capabilities.includes('login')){$('account-state').textContent='此图源插件不提供登录功能。';return;}
  $('account-state').textContent=plugin.account.authenticated?'会话已保存':plugin.account.configured?'账号已保存，将在请求时恢复会话':'尚未绑定账号';
  for(const field of plugin.login_fields){const label=node('label',field.label);const input=node('input');input.name=field.name;input.type=field.type==='password'?'password':'text';input.autocomplete=field.type==='password'?'current-password':'username';input.required=true;label.append(input);form.append(label);}
  const submit=node('button','登录并保存','primary');submit.type='submit';form.append(submit);
  if(plugin.account.configured||plugin.account.authenticated)form.append(iconBtn('unlink','解除绑定',async()=>{await api(`/api/sources/${enc(plugin.id)}/account`,{method:'DELETE'});await loadSources();configureAccount();toast('已解除绑定');}));
}

function saveProgress(){const r=state.reader;if(!r||!r.images.length)return;const value={chapterId:r.chapterId,chapterName:r.chapterName,index:r.index,updatedAt:Date.now()};saveLocal(progressKey(r.book,r.chapterId),value);saveLocal(lastKey(r.book),value);}
async function openReader(chapterId){
  saveProgress();const book=state.detail,chapter=book.chapters.find(c=>String(c.id)===chapterId);if(!chapter)return;
  const request=++state.readerRequest;state.readerAbort?.abort();state.readerAbort=new AbortController();state.reader=null;
  $('reader-title').textContent=`${book.title} · ${chapter.name}`;$('reader-pages').textContent='正在获取章节…';$('page-status').textContent='';
  if(!$('reader-dialog').open)$('reader-dialog').showModal();
  try{const data=await api(`/api/chapter/${enc(book.source)}/${enc(book.id)}/${enc(chapterId)}`,{signal:state.readerAbort.signal});if(request!==state.readerRequest)return;
    const saved=readLocal(progressKey(book,chapterId));state.reader={book,chapterId,chapterName:chapter.name,images:data.images,index:Math.max(0,Math.min(Number(saved?.index)||0,data.images.length-1))};renderReader();
  }catch(e){if(request===state.readerRequest&&e.name!=='AbortError')$('reader-pages').textContent=e.message;}
}
function renderReader(){
  state.observer?.disconnect();const r=state.reader,container=$('reader-pages');if(!r)return;container.replaceChildren();container.scrollTop=0;
  const paged=$('reader-mode').value==='page';container.classList.toggle('paged',paged);
  $('page-status').textContent=`${r.images.length?r.index+1:0} / ${r.images.length}`;
  if(!r.images.length){container.textContent='该章节暂无图片';return;}
  const makeImage=index=>{const wrapper=node('div');wrapper.dataset.index=index;const img=image(r.images[index],`第 ${index+1} 页`);img.loading=paged||Math.abs(index-r.index)<2?'eager':'lazy';img.addEventListener('load',()=>img.classList.toggle('tall',img.naturalHeight>img.naturalWidth*2.5));img.onerror=()=>{wrapper.replaceChildren(node('p',`第 ${index+1} 页加载失败`,'image-error'),iconBtn('refresh-cw','重试图片',()=>{wrapper.replaceWith(makeImage(index));}));};wrapper.append(img);return wrapper;};
  if(paged){container.append(makeImage(r.index));if(r.index+1<r.images.length){const preload=new Image();preload.src=r.images[r.index+1];}}
  else{
    r.images.forEach((_,index)=>container.append(makeImage(index)));
    // Wait for the target page to load before observing, so restoring does not overwrite saved progress.
    const target=container.children[r.index];target.scrollIntoView({block:'start'});
    let restored=false;const restore=()=>{if(restored||state.reader!==r||$('reader-mode').value!=='scroll')return;restored=true;target.scrollIntoView({block:'start'});state.observer=new IntersectionObserver(entries=>{const visible=entries.filter(e=>e.isIntersecting).sort((a,b)=>a.boundingClientRect.top-b.boundingClientRect.top);if(visible.length){r.index=Number(visible[0].target.dataset.index);$('page-status').textContent=`${r.index+1} / ${r.images.length}`;saveProgress();}},{root:container,rootMargin:'0px 0px -70% 0px',threshold:0});[...container.children].forEach(n=>state.observer.observe(n));};
    const img=target.querySelector('img');img.addEventListener('load',restore,{once:true});img.addEventListener('error',restore,{once:true});if(img.complete)restore();
  }
  saveProgress();
}
function movePage(delta){const r=state.reader;if(!r)return;const index=r.index+delta;if(index<0||index>=r.images.length){moveChapter(delta);return;}r.index=index;if($('reader-mode').value==='page')renderReader();else{$('reader-pages').children[index]?.scrollIntoView({block:'start',behavior:'smooth'});saveProgress();}}
function moveChapter(delta){const r=state.reader;if(!r)return;const chapters=r.book.chapters,index=chapters.findIndex(c=>String(c.id)===r.chapterId);if(chapters[index+delta])run(()=>openReader(String(chapters[index+delta].id)));else toast('没有更多章节');}
function closeReader(){saveProgress();state.readerAbort?.abort();++state.readerRequest;state.observer?.disconnect();state.reader=null;$('reader-dialog').close();$('reader-pages').replaceChildren();if(state.detail)renderDetail();}

document.querySelectorAll('[data-tab]').forEach(n=>n.onclick=()=>showTab(n.dataset.tab));
document.querySelectorAll('[data-close]').forEach(n=>n.onclick=()=>{if(n.dataset.close==='detail-dialog')++state.detailRequest;$(n.dataset.close).close();});
$('browse-form').onsubmit=browse;
$('library-refresh').onclick=()=>run(loadLibrary);$('library-category').onchange=filterBooks;$('tasks-refresh').onclick=()=>run(loadTasks);
$('accounts').onclick=()=>run(async()=>{await loadSources();$('account-dialog').showModal();});
$('login-form').onsubmit=event=>{event.preventDefault();const source=state.settingsSource;run(async()=>{await api(`/api/sources/${enc(source)}/login`,write('POST',Object.fromEntries(new FormData(event.target))));await loadSources();configureAccount();toast('图源账号已保存');},event.submitter);};
$('reader-close').onclick=closeReader;$('reader-dialog').addEventListener('cancel',event=>{event.preventDefault();closeReader();});
const toggleToolbar=event=>$('reader-dialog').classList.toggle('show-toolbar',event.clientY!==undefined&&event.clientY<=70);$('reader-dialog').addEventListener('pointermove',toggleToolbar);$('reader-dialog').addEventListener('pointerdown',toggleToolbar);$('reader-dialog').addEventListener('pointerleave',()=>$('reader-dialog').classList.remove('show-toolbar'));
$('reader-mode').value=readLocal('comic:reader-mode')||'scroll';$('reader-mode').onchange=()=>{saveLocal('comic:reader-mode',$('reader-mode').value);renderReader();};
$('page-prev').onclick=()=>movePage(-1);$('page-next').onclick=()=>movePage(1);$('chapter-prev').onclick=()=>moveChapter(-1);$('chapter-next').onclick=()=>moveChapter(1);
window.addEventListener('keydown',event=>{if(!$('reader-dialog').open||['INPUT','SELECT'].includes(event.target.tagName))return;if(event.key==='ArrowRight'){event.preventDefault();movePage(1);}if(event.key==='ArrowLeft'){event.preventDefault();movePage(-1);}});
window.addEventListener('pagehide',saveProgress);
document.documentElement.classList.toggle('light',readLocal('comic:light')??!matchMedia('(prefers-color-scheme: dark)').matches);
$('theme').onclick=()=>saveLocal('comic:light',document.documentElement.classList.toggle('light'));
setInterval(()=>{if(state.tab==='downloads'&&!document.hidden&&!loadTasks.busy){loadTasks.busy=true;loadTasks().catch(e=>toast(e.message)).finally(()=>loadTasks.busy=false);}},2500);
run(async()=>{await loadSources();await loadLibrary();});
