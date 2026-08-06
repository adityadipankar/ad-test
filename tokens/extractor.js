// NID page extractor — runs inside Figma via use_figma.
// Walks each page board and emits a CMS content record. Kept in the repo so the
// extraction is reproducible rather than a one-off.
// Set SLICE_FROM / SLICE_TO to page through the boards within the tool's
// response-size limit.

const SLICE_FROM = 0, SLICE_TO = 4;

const main = figma.getNodeById("0:1"); await main.loadAsync();

function rg(b){ let best=null; const s=[b]; while(s.length){ const n=s.pop();
  if(n.layoutMode==="GRID"&&(!best||n.width>best.width)) best=n;
  let ch=null; try{ch=n.children;}catch(e){} if(ch) for(const k of ch) s.push(k); } return best; }
function slug(s){ return s.toLowerCase().replace(/[’'`]/g,"").replace(/&/g,"and")
  .replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,""); }
function pageSlug(name){
  const parts=name.split("/").map(p=>p.trim());
  parts[0]=parts[0].replace(/^\d+\s*/,"");
  const last=parts.length-1;
  parts[last]=parts[last].replace(/\s*[—-]\s*Landing\s*$/i,"");
  if(!parts[last]) parts.pop();
  return parts.map(slug).join("/");
}
function comp(n){ if(n.type!=="INSTANCE") return null; let m=null; try{m=n.mainComponent;}catch(e){}
  if(!m) return null; return (m.parent&&m.parent.type==="COMPONENT_SET")?m.parent.name:m.name; }
function styleName(n){ if(!n.textStyleId) return "";
  const st=figma.getStyleById(n.textStyleId); return st?st.name:""; }
function textNodes(n){ const o=[]; (function w(x){
  if(x.visible===false) return;
  if(x.type==="TEXT") o.push({v:x.characters,s:styleName(x)});
  let c=null; try{c=x.children;}catch(e){} if(c) for(const k of c) w(k); })(n); return o; }
function destSlug(n){ let rx=null; try{rx=n.reactions;}catch(e){return null;}
  for(const r of (rx||[])) for(const a of (r.actions||[])) if(a.destinationId){
    const d=figma.getNodeById(a.destinationId);
    if(d&&d.parent&&d.parent.type==="PAGE"&&/^\d\d /.test(d.name)) return pageSlug(d.name); }
  return null; }
function isImg(n){ let f=null; try{f=n.fills;}catch(e){return false;}
  return Array.isArray(f)&&f.some(x=>x.type==="IMAGE"); }
function fullBody(cell){
  if(cell.type==="TEXT") return cell.characters;
  let hid=null; try{ hid=cell.findOne(x=>x.name==="Full text"); }catch(e){}
  if(hid) return hid.characters;
  const t=textNodes(cell); return t.length?t[0].v:"";
}
function cta(n){ const t=textNodes(n).filter(x=>x.v.trim()); if(!t.length) return null;
  const o={label:t[0].v.trim()}; const d=destSlug(n); if(d) o.page=d;
  if(/\(PDF\)|Handbook|Report|Catalogue/i.test(o.label)) o.targetType="document";
  else if(/@/.test(o.label)) { o.targetType="email"; o.address=o.label; }
  else if(/^\+?[\d\s-]{8,}$/.test(o.label)) { o.targetType="phone"; o.address=o.label; }
  else if(/\.(edu|in|com|org)(\/|$)/i.test(o.label)) { o.targetType="external"; o.url="https://"+o.label; }
  return o; }
function findAll(n,fn){ try{ return n.findAll(fn); }catch(e){ return []; } }

// Classify the text inside a card by the style it carries, rather than by order.
function card(n, extraName){
  const t=textNodes(n).filter(x=>x.v.trim());
  const o={};
  for(const x of t){
    const v=x.v.trim();
    if(/Label\/Overline/.test(x.s) && !o.overline) o.overline=v;
    else if(/Heading\//.test(x.s) && !o.name) o.name=v;
    else if(/Label\/(Small|Meta)/.test(x.s) && !o.meta) o.meta=v;
    else if(/Label\/Micro|Body\//.test(x.s) && !o.note) o.note=v;
    else if(!o.name) o.name=v;
  }
  if(!o.name && t.length) o.name=t[0].v.trim();
  o.asset=slug((extraName||"")+"-"+(o.name||"")).slice(0,48);
  const d=destSlug(n); if(d) o.page=d;
  return o;
}

function extract(board){
  const G=rg(board); if(!G) return null;
  const cols=G.gridColumnCount;
  const rows={};
  for(const c of G.children){ const r=c.gridRowAnchorIndex;
    (rows[r]=rows[r]||[]).push({r,c:c.gridColumnAnchorIndex,cs:c.gridColumnSpan,n:c}); }
  const rowIdx=Object.keys(rows).map(Number).sort((a,b)=>a-b);
  for(const r of rowIdx) rows[r].sort((a,z)=>a.c-z.c);

  const page={title:"",slug:pageSlug(board.name),board:board.name,sections:[]};
  const isSep=r=>rows[r].some(x=>/Separator/.test(x.n.name));
  const isFooter=r=>rows[r].some(x=>/Footer/i.test(x.n.name));

  // parent-derived back navigation, per the model: the label is the parent's title
  const segs=page.slug.split("/");
  if(segs.length>1) page.parent=segs.slice(0,-1).join("/");

  const first=rows[rowIdx[0]]||[];
  const t0=first.find(x=>x.c===0&&comp(x.n)==="Title");
  if(t0) page.title=(textNodes(t0.n)[0]||{v:""}).v.trim();
  if(!page.title) page.title=segs[segs.length-1].replace(/-/g," ");

  let cursor=1;
  const r1=rows[rowIdx[1]]||[];
  const rail=r1.find(x=>x.c===0);
  if(rail){
    const ctas=findAll(rail.n,x=>comp(x)==="Call to actions");
    const infos=findAll(rail.n,x=>comp(x)==="Information");
    if(ctas.length && !infos.length){ page.subPages=ctas.map(cta).filter(Boolean); }
    else if(infos.length||/Key Info|Frame 2\d\d/.test(rail.n.name)){
      const t=textNodes(rail.n).filter(x=>x.v.trim()); page.keyInfo=[];
      for(let i=0;i+1<t.length;i+=2) page.keyInfo.push({label:t[i].v.trim(),value:t[i+1].v.trim()});
    }
  }
  const hero=r1.find(x=>x.c>=1);
  if(hero) page.hero={asset:slug(hero.n.name).slice(0,48),placeholder:!isImg(hero.n)};
  cursor=2;

  const r2=rows[rowIdx[2]]||[];
  const introCell=r2.find(x=>x.c>=1&&(x.n.type==="TEXT"||/Intro/i.test(x.n.name)));
  if(introCell && !isSep(rowIdx[2])){ page.intro=fullBody(introCell.n); cursor=3; }

  let group=[];
  const flush=()=>{
    if(!group.length){ return; }
    const flat=group.flat();
    const titleCell=flat.find(x=>x.c===0&&comp(x.n)==="Title");
    const aside=flat.filter(x=>x.c>=cols-1&&x.c>0);
    const body=flat.filter(x=>x.c>0&&x.c<cols-1);
    const cardCells=flat.filter(x=>["Thumb","Person","News Article","Campuses"].indexOf(comp(x.n))>=0);
    const sec={title:titleCell?((textNodes(titleCell.n)[0]||{v:""}).v.trim()):"",type:"text"};

    if(cardCells.length){
      const kind=comp(cardCells[0].n);
      sec.type = kind==="News Article" ? "mosaic" : "cards";
      if(kind==="Person") sec.variant="person";
      if(kind==="Campuses") sec.variant="campus";
      if(kind==="Thumb") sec.variant="thumb";
      sec.items=cardCells.map(x=>{ const o=card(x.n,kind); if(x.cs>1) o.featured=true; return o; });
    } else {
      // a content cell that is only links is a links section
      const linkFrames=body.filter(x=>{
        if(comp(x.n)==="Call to actions") return true;
        const cs=findAll(x.n,y=>comp(y)==="Call to actions");
        return cs.length>0 && x.n.type==="FRAME";
      });
      const textCell=body.find(x=>x.n.type==="TEXT"||/Body|body/i.test(x.n.name));
      if(linkFrames.length && !textCell){
        sec.type="links"; sec.items=[];
        for(const lf of linkFrames){
          if(comp(lf.n)==="Call to actions") sec.items.push(cta(lf.n));
          else for(const c of findAll(lf.n,y=>comp(y)==="Call to actions")) sec.items.push(cta(c));
        }
        sec.items=sec.items.filter(Boolean);
      } else {
        if(textCell) sec.body=fullBody(textCell.n);
        const imgCell=body.find(x=>x.n.type==="RECTANGLE");
        if(imgCell) sec.image={asset:slug(imgCell.n.name).slice(0,48),placeholder:!isImg(imgCell.n)};
      }
    }
    const links=[];
    for(const a of aside){
      if(comp(a.n)==="Call to actions") links.push(cta(a.n));
      else for(const c of findAll(a.n,y=>comp(y)==="Call to actions")) links.push(cta(c));
    }
    const L=links.filter(Boolean);
    if(L.length) sec.links=L;
    if(sec.title||sec.body||sec.items||sec.links) page.sections.push(sec);
    group=[];
  };

  for(let i=cursor;i<rowIdx.length;i++){
    const r=rowIdx[i];
    if(isFooter(r)) break;
    if(isSep(r)){ flush(); continue; }
    group.push(rows[r]);
  }
  flush();
  return page;
}

const boards=main.children
  .filter(b=>/^\d\d /.test(b.name) && Math.round(b.width)===1440)
  .sort((a,b)=>a.name.localeCompare(b.name));

const out=boards.slice(SLICE_FROM,SLICE_TO).map(b=>extract(b)).filter(Boolean);
const s=JSON.stringify({total:boards.length,from:SLICE_FROM,to:SLICE_TO,pages:out});
return s.length>17500 ? JSON.stringify({total:boards.length,from:SLICE_FROM,to:SLICE_TO,
  oversize:true,len:s.length,names:out.map(p=>p.slug)}) : s;
