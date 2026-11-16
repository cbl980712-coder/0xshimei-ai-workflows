// 筛选核心（和 pick_sites.py 同一套规则，浏览器和 node 都能跑）
function parseCSV(text){
  text=text.replace(/^﻿/,''); const fl=text.trim().split('\n')[0]||''; const D=[',',';','\t'].reduce((a,b)=>fl.split(b).length>fl.split(a).length?b:a); const rows=[]; let row=[],f='',q=false;
  for(let i=0;i<text.length;i++){const c=text[i];
    if(q){ if(c=='"'){ if(text[i+1]=='"'){f+='"';i++} else q=false } else f+=c }
    else if(c=='"') q=true; else if(c==D){row.push(f);f=''}
    else if(c=='\n'||c=='\r'){ if(c=='\r'&&text[i+1]=='\n')i++; row.push(f);f=''; if(row.some(x=>x!==''))rows.push(row); row=[] }
    else f+=c }
  if(f!==''||row.length){row.push(f); if(row.some(x=>x!==''))rows.push(row)}
  return rows;
}
const COLS={name:['名称','网站','name','title','标题'],url:['网址','链接','url','link','href'],desc:['简介','描述','备注','description','desc','note','notes'],cat:['分类','标签','类别','category','tags','tag']};
function readRows(text){
  if(!text.trim()) throw new Error('输入是空的：请选择 CSV 文件，或把内容粘贴到文本框里。');
  const t=parseCSV(text);
  const head=t[0].map(h=>h.trim().toLowerCase()), pick={};
  for(const k in COLS){ for(const n of COLS[k]){ const i=head.indexOf(n.toLowerCase()); if(i>=0){pick[k]=i;break} } }
  if(pick.url===undefined) throw new Error('找不到网址列。第一行必须是表头，且包含「网址」/ url / link 之一。当前读到的表头：'+t[0].slice(0,6).join(' | '));
  const g=(r,k)=>pick[k]===undefined?'':(r[pick[k]]||'').trim();
  const out=t.slice(1).filter(r=>g(r,'url')).map(r=>({name:g(r,'name'),url:g(r,'url'),desc:g(r,'desc'),cat:g(r,'cat')}));
  if(!out.length) throw new Error('表头没问题，但没有任何一行填了网址。请在「网址」列里填内容后再试。');
  return out;
}
function normUrl(u){
  u=u.trim(); let x; try{x=new URL(u.includes('://')?u:'http://'+u)}catch(e){return u.toLowerCase()}
  let host=x.host.toLowerCase().replace(/^www\./,'');
  const q=[...x.searchParams].filter(([k])=>!/^(utm_|ref|fbclid)/i.test(k)).map(([k,v])=>k+'='+encodeURIComponent(v)).join('&');
  return host+x.pathname.replace(/\/+$/,'')+(q?'?'+q:'');
}
function merge(rows){
  const m=new Map();
  for(const r of rows){const k=normUrl(r.url);
    if(!m.has(k)) m.set(k,{...r,key:k,dup:0,cats:r.cat?[r.cat]:[]});
    else{const s=m.get(k);s.dup++; if(r.desc.length>s.desc.length)s.desc=r.desc; if(!s.name)s.name=r.name; if(r.cat&&!s.cats.includes(r.cat))s.cats.push(r.cat)}}
  return [...m.values()];
}
function has(text,w){w=w.toLowerCase();
  if(/^[a-z0-9 .\-]+$/.test(w)){const e=w.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'); return new RegExp('(?<![a-z0-9])'+e+'(?:s|es)?(?![a-z0-9])').test(text)}
  return text.includes(w)}
function tagSites(sites,R){
  for(const s of sites){
    const text=(s.name+' '+s.desc+' '+s.cats.join(' ')).toLowerCase();
    s.tags=Object.keys(R.purposes).filter(p=>R.purposes[p].some(w=>has(text,w)));
    const why=[]; if([...s.desc].length<R.min_desc_chars)why.push('简介少于'+R.min_desc_chars+'字');
    if(!s.tags.length)why.push('名称/简介/分类里没出现任何用途关键词');
    const bad=(R.exclude_phrases||[]).find(x=>text.includes(x)); if(bad)why.push('简介提示已不可用：'+bad);
    s.pending=why.join('；');
  } return sites;
}
function wantPurposes(R,ptype,stuck){
  const w={},low=stuck.toLowerCase();
  const hit=Object.keys(R.stuck_words).filter(p=>R.stuck_words[p].some(x=>low.includes(x.toLowerCase())));
  hit.forEach(p=>w[p]=(w[p]||0)+5);
  const pt=R.project_types[ptype]||{}; for(const p in pt) w[p]=(w[p]||0)+pt[p];
  return {w,hit};
}
function score(s,w,R){
  let sc=s.tags.reduce((a,t)=>a+(w[t]||0),0); const cl=s.cats.join(' ').toLowerCase();
  for(const p in R.purposes){ if(p in w && R.purposes[p].some(x=>has(cl,x))) sc+=2*w[p]; }
  if(!('学习教程' in w) && (R.demote_categories||[]).some(d=>cl.includes(d))) sc-=6;
  sc+=Math.min([...s.desc].length,160)/160; sc-=0.3*Math.max(0,s.tags.length-4); return sc;
}
function recommend(sites,w,hit,top,R){
  const ok=sites.filter(s=>!s.pending&&s.tags.some(t=>t in w));
  const ranked=ok.map(s=>[s,score(s,w,R)]).sort((a,b)=>b[1]-a[1]).map(x=>x[0]);
  const chosen=[],covered=new Set();
  const focus=hit.length?hit:Object.entries(w).sort((a,b)=>b[1]-a[1]).slice(0,2).map(x=>x[0]);
  for(const p of focus){
    const pool=ranked.filter(s=>s.tags.includes(p)&&!chosen.includes(s));
    const catHit=s=>R.purposes[p].some(x=>has(s.cats.join(' ').toLowerCase(),x))?1:0;
    pool.sort((a,b)=>(catHit(b)-catHit(a))||((a.tags.some(t=>covered.has(t))?1:0)-(b.tags.some(t=>covered.has(t))?1:0))||(score(b,w,R)-score(a,w,R)));
    if(pool.length&&chosen.length<top){chosen.push(pool[0]);pool[0].tags.forEach(t=>{if(focus.includes(t))covered.add(t)})}
  }
  for(const s of ranked){ if(chosen.length>=top)break; if(!chosen.includes(s))chosen.push(s) }
  return chosen;
}
function reason(s,w,hit){
  let f=s.tags.filter(t=>hit.length?hit.includes(t):t in w); if(!f.length)f=s.tags.slice(0,2);
  const d=[...s.desc].slice(0,110).join('')+([...s.desc].length>110?'…':'');
  return '适合解决：'+f.join('、')+'。依据（来自你清单里的简介）：'+d;
}
function runPick(csvText,ptype,stuck,R,top){
  const rows=readRows(csvText), sites=tagSites(merge(rows),R), {w,hit}=wantPurposes(R,ptype,stuck);
  const chosen=recommend(sites,w,hit,Math.min(top||3,3),R);
  return {rows:rows.length,sites,hit,chosen:chosen.map(s=>({name:s.name,url:s.url,tags:s.tags,reason:reason(s,w,hit)})),pending:sites.filter(s=>s.pending)};
}
if(typeof module!=='undefined') module.exports={runPick};
