/* Synthetic-only browser preview. The desktop Python planner remains authoritative. */
'use strict';
function demoPropose(data, options) {
  const o = {metric:'opens',days:7,folders:'flatten',capacity:8,pinned:[],widget_mode:'separate',page_limit:15,...options};
  if (!['opens','seconds','recent'].includes(o.metric) || ![7,30].includes(o.days) ||
      !Number.isInteger(o.capacity) || o.capacity<1 || o.capacity>24 ||
      !Number.isInteger(o.page_limit) || o.page_limit<1 || o.page_limit>15 ||
      !['flatten','preserve'].includes(o.folders) || !['keep','separate'].includes(o.widget_mode)) {
    throw Error('Choose 1–24 icons and a 1–15 page budget.');
  }
  const isWidget = a => Boolean(a.elements?.length) || ['custom','widget','Widget','stack'].includes(a.iconType);
  const id = a => a.bundleIdentifier || a.displayIdentifier || '';
  const flatten = pages => pages.flatMap(p=>p.flatMap(a=>isWidget(a)?[]:a.iconLists?flatten(a.iconLists):[a]));
  const slots = a => isWidget(a)?({small:4,medium:8,large:16}[a.gridSize]||24):1;
  const source = JSON.parse(JSON.stringify(data.current));
  const known = new Set(flatten(source).map(id));
  if (!Array.isArray(o.pinned) || new Set(o.pinned).size!==o.pinned.length || o.pinned.some(i=>!known.has(i))) {
    throw Error('Invalid pinned apps.');
  }
  const stats = data.usage.apps;
  const value = (a,field) => {
    const rows = flatten([[a]]).map(i=>stats[id(i)]||{});
    return field==='recent'?Math.max(0,...rows.map(r=>Date.parse(r.last_open)||0)):rows.reduce((sum,r)=>sum+Number(r[field]||0),0);
  };
  const score = a => {
    const pins = flatten([[a]]).map(id).map(i=>o.pinned.indexOf(i)).filter(i=>i>=0);
    return [pins.length?0:1,pins.length?Math.min(...pins):0,-value(a,o.metric),-value(a,o.metric==='opens'?'seconds':'opens')];
  };
  const compare = (a,b) => {
    const x=score(a),y=score(b);
    for(let i=0;i<x.length;i++)if(x[i]!==y[i])return x[i]-y[i];
    return 0;
  };
  let items;
  if(o.folders==='flatten')items=flatten(source.slice(1));
  else {
    items=source.slice(1).flat().filter(a=>!isWidget(a));
    for(const a of items)if(a.iconLists){
      const inner=flatten(a.iconLists).sort(compare);
      a.iconLists=[];
      for(let i=0;i<inner.length;i+=9)a.iconLists.push(inner.slice(i,i+9));
    }
  }
  items.sort(compare);
  const widgets=source.slice(1).flat().filter(isWidget);
  let budget;
  if(o.widget_mode==='separate')budget=(o.page_limit-(widgets.length?1:0))*o.capacity;
  else {
    if(source.slice(1).some((p,i)=>i>=o.page_limit&&p.some(isWidget)))throw Error('A widget page is beyond the page budget.');
    const lost=source.slice(1).reduce((sum,p)=>sum+Math.max(0,o.capacity-Math.min(o.capacity,24-p.filter(isWidget).reduce((s,a)=>s+slots(a),0))),0);
    budget=o.page_limit*o.capacity-lost;
  }
  if(items.length&&budget<1)throw Error('The page budget leaves no room for apps.');
  let tailFolder=null;
  if(items.length>budget){
    const count=items.length-budget+1,tail=items.slice(-count);
    if(tail.some(a=>a.iconLists))throw Error('Increase the page budget or flatten folders before grouping.');
    tailFolder={name:'末尾 App',apps:tail.map(a=>a.displayName||id(a))};
    const folder={displayName:tailFolder.name,iconLists:[]};
    for(let i=0;i<tail.length;i+=9)folder.iconLists.push(tail.slice(i,i+9));
    items=[...items.slice(0,-count),folder];
  }
  const layout=[source[0]];
  let remaining=[...items];
  if(o.widget_mode==='separate'&&widgets.length){
    if(widgets.reduce((sum,a)=>sum+slots(a),0)>24)throw Error('Widgets need more than one page. Keep current positions.');
    layout.push(widgets);
  }
  if(o.widget_mode==='keep')for(const p of source.slice(1)){
    const positions=new Map(p.flatMap((a,i)=>isWidget(a)?[[i,a]]:[]));
    const room=Math.min(o.capacity,24-[...positions.values()].reduce((s,a)=>s+slots(a),0));
    const selected=remaining.slice(0,room);remaining=remaining.slice(room);
    if(positions.size&&Math.max(...positions.keys())>=selected.length+positions.size)throw Error('Cannot preserve widget positions with this capacity.');
    const result=[],length=selected.length+positions.size;
    for(let i=0;i<length;i++)result.push(positions.has(i)?positions.get(i):selected.shift());
    if(result.length||positions.size)layout.push(result);
    else if(remaining.length)layout.push([]);
  }
  while(remaining.length){layout.push(remaining.slice(0,o.capacity));remaining=remaining.slice(o.capacity);}
  if(layout.length===1)layout.push([]);
  if(layout.length-1>o.page_limit)throw Error('The retained widget positions exceed the page budget.');
  const positions = pages => {
    const map=new Map();
    function walk(ps,prefix){ps.forEach((p,pi)=>p.forEach((a,ai)=>{
      const location=prefix+'/'+pi+'/'+ai;
      if(isWidget(a))return;
      if(a.iconLists)walk(a.iconLists,location+'/'+(a.displayName||''));
      else map.set(id(a),[location,a.displayName||id(a)]);
    }));}
    walk(pages,'');return map;
  };
  const before=positions(data.current),after=positions(layout);
  const moved=[...after].filter(([key,[position]])=>before.get(key)?.[0]!==position).map(([key,[,name]])=>({id:key,name}));
  return {layout,proposal:{...o,proposal_hash:'synthetic-preview',tail_folder:tailFolder,
    diff:{moved,count:moved.length,pages_before:data.current.length-1,pages_after:layout.length-1}}};
}
if(typeof module!=='undefined')module.exports={demoPropose};
