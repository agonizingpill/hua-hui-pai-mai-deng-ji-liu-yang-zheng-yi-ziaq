import{esc}from'../utils/format.js';
export const money=n=>'¥'+(n/100).toFixed(2);
export function title(number,name,description){return `<div class="heading"><span>CHENLU AUCTION HOUSE / ${number}</span><h1>${name}</h1><p>${description}</p></div>`}
export function grade(value){return `<strong class="grade grade-${esc(value||'U')}">${esc(value||'?')}</strong>`}
export function consignment(c){return `<div class="batch"><small>CONSIGNMENT / ${esc(c.code)}</small><h2>${esc(c.variety)}</h2><span>${esc(c.grower)} · ${c.crates}筐 × ${c.stems_per_crate}支</span></div>`}
export function tape(bids){return bids.length?`<ol class="bidtape">${[...bids].reverse().map(b=>`<li><time>${esc(b.at.slice(11))}</time><span>${esc(b.buyer)}</span><b>${money(b.unit_cents)}<small>/筐</small></b></li>`).join('')}</ol>`:'<p class="empty">开场后录入买方席位与筐价，出价会依次留在拍价带。</p>'}
export function options(items,label,selected){return items.map(x=>`<option value="${x.id}" ${x.id===Number(selected)?'selected':''}>${esc(label(x))}</option>`).join('')}
export function input(name,label,type='text',value='',extra=''){return `<label>${label}</label><input name="${name}" type="${type}" value="${esc(value)}" ${extra}>`}
export function button(path,label,disabled=false){return `<button type="button" data-action="${path}" ${disabled?'disabled':''}>${label}</button>`}
export function isViewer(s){return s.user.role==='viewer'}
export function isSupervisor(s){return s.user.role==='supervisor'}
