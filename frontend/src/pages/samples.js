import{title,grade,consignment,options,input,isViewer,isSupervisor}from'../components/tickets.js';
import{esc,data}from'../utils/format.js';
import{perform,bindActions}from'../utils/actions.js';
import{SAMPLE_STATES}from'../constants.js';
const VERSION_LABEL={'v1-synthetic':'旧版 · 合成训练 v1','v2-sealed':'新版 · 封存终点 v2'};
const VERSION_STATE={active:'生效中',candidate:'候选',archived:'已归档'};
const vtag=v=>v?`<span class="vtag">${esc(VERSION_LABEL[v]||v)}</span>`:'';
function modelPanel(s){
  const d=s.data,versions=d.model_versions||[],evals=d.model_evaluations||[];
  const active=versions.find(v=>v.state==='active');
  const consCode=id=>d.consignments.find(c=>c.id===id)?.code||('#'+id);
  const holdoutIds=d.holdout_consignment_ids||active?.holdout_consignment_ids||[];
  const last=d.latest_evaluation||null;
  const compareBand=last?`<div class="compare-band ${last.switched?'ok':'no'}"><div><small>最近一次固定留出对比（${esc(last.at)}）</small><h3>${last.switched?'新版不劣于旧版，已切换':'新版劣于旧版，沿用旧版'}</h3></div><div class="mae-pair"><div><b>${last.old_mae_days}</b><small>旧版 MAE / 天</small></div><div><b>${last.new_mae_days}</b><small>新版 MAE / 天</small></div></div></div>`:'';
  return `<section class="paper model-panel"><h2>估级版本与换版</h2>
    <p class="note">新版用<b>已封存瓶插终点</b>训练；按到场批固定留出一组留样，两版都不拿它训练，在同一组留样上比平均绝对误差（MAE）。新版 MAE 不劣于旧版才切换，否则沿用旧版。留样送估时即固定当时生效版本，中断重试不改版本、不重复出结果。</p>
    ${compareBand}
    <div class="version-grid">${versions.map(v=>`<article class="version-card ${v.state==='active'?'is-active':''}"><small>${esc(VERSION_STATE[v.state]||v.state)}</small><h3>${esc(VERSION_LABEL[v.code]||v.code)}</h3><p>${esc(v.label||'')}</p><dl><dt>固定留出 MAE</dt><dd>${v.holdout_mae_days??'—'} 天</dd><dt>训练样本</dt><dd>${v.trained_rows??'—'} 条</dd><dt>最近评估</dt><dd>${esc(v.last_evaluated_at||'尚未评估')}</dd></dl>${v.note?`<p class="note">${esc(v.note)}</p>`:''}</article>`).join('')}</div>
    <div class="holdout-band"><b>当前固定留出到场批</b><span>${holdoutIds.length?holdoutIds.map(consCode).map(esc).join('、'):'暂无足够封存留样'}</span><small>封存留样 ${d.sealed_sample_count??'?'} 条 · 留出留样 ${(d.holdout_sample_ids||[]).length} 条 · 训练留样 ${(d.training_sample_ids||[]).length} 条 · 留出/训练各至少2条</small></div>
    <div class="actions"><button type="button" data-action="/models/switch" data-message="换版评估已完成" ${!isSupervisor(s)?'disabled':''}>发起换版评估（主管）</button>${active?`<span class="actual-version">实际用版：${esc(VERSION_LABEL[active.code]||active.code)}</span>`:''}</div>
    <h3>换版评估记录</h3>${evals.length?`<table class="eval-table"><thead><tr><th>时间</th><th>比较</th><th>旧版 MAE</th><th>新版 MAE</th><th>结果</th><th>说明</th></tr></thead><tbody>${evals.map(e=>`<tr><td>${esc(e.at)}</td><td>${esc(VERSION_LABEL[e.old_version]||e.old_version)}<br><small>对 ${esc(VERSION_LABEL[e.new_version]||e.new_version)}</small></td><td>${e.old_mae_days} 天</td><td>${e.new_mae_days} 天</td><td><span class="verdict ${e.switched?'ok':'no'}">${e.switched?'已切换':'沿用旧版'}</span></td><td>${esc(e.reason)}<small>留出批 ${(e.holdout_consignment_ids||[]).map(consCode).map(esc).join('、')}</small></td></tr>`).join('')}</tbody></table>`:'<p class="empty">尚无换版评估。封存终点样本充足后由主管发起。</p>'}
  </section>`;
}
export function render(s){
  let d=s.data;
  return title('02 / VASE TRIAL','留一枝，见花期。','worker用成熟度、杆长、采后小时和冷藏记录估算瓶插寿命；实际终点观察封存后用于训练新版与争议复判。')
  +`<div class="sample-layout"><section>${d.vase_samples.map(x=>`<article class="sample-sheet"><div class="sample-head">${grade(x.approved_grade||x.prediction?.suggested_grade)}<div><small>${esc(x.code)} · ${SAMPLE_STATES[x.state]}</small><h2>${esc(d.consignments.find(c=>c.id===x.consignment_id)?.variety)}</h2>${vtag(x.model_version||x.prediction?.model_version)}</div><span class="vase">♧</span></div><div class="pair"><p>成熟度 ${x.maturity}<br>杆长 ${x.stem_cm}cm<br>冷藏 ${x.cold_hours}小时</p><p>实际瓶插终点<br><b>${x.observed_days??'尚未封存'} 天</b></p></div>${x.prediction?`<div class="model-result"><b>${x.prediction.vase_days}<small>预测天数</small></b><p>留出MAE ${x.prediction.holdout_mae_days}天<br>${x.prediction.train_rows}训练 / ${x.prediction.holdout_rows}留出 · seed35<br>用版 ${esc(VERSION_LABEL[x.prediction.model_version]||x.prediction.model_version||'—')} · 固定合成/封存数据，仅辅助验级</p></div>`:''}${x.error?`<p class="error">${esc(x.error)}</p>`:''}<div class="actions"><button data-action="/samples/${x.id}/estimate" data-message="留样已送交估级，版本已固定" ${isViewer(s)||!['recorded','failed'].includes(x.state)?'disabled':''}>送交寿命估级</button>${x.model_version?`<span class="actual-version">固定用版：${esc(VERSION_LABEL[x.model_version]||x.model_version)}</span>`:''}</div>${x.state==='ready'?`<form class="grade-form" data-id="${x.id}"><label>主管核级 / A≥10天 · B≥7天</label><select name="grade">${['A','B','C'].map(g=>`<option>${g}</option>`).join('')}</select><input name="note" value="结合现场验花与估级结果核定" required><button ${!isSupervisor(s)?'disabled':''}>签署等级</button></form>`:''}${x.observed_days===null?`<form class="observation-form" data-id="${x.id}"><label>实际瓶插终点 / 天</label><input name="observed_days" type="number" min="1" max="30" step=".1" value="6"><button ${isViewer(s)?'disabled':''}>封存终点观察</button></form>`:`<p class="note">观察证据已封存，后续不能覆盖；已核定等级与原估级依据照旧保留。</p>`}</article>`).join('')}</section><aside class="paper"><h2>建立瓶插留样</h2><form id="sample-form"><label>到场批次</label><select name="consignment_id">${options(d.consignments,c=>c.code+' / '+c.variety)}</select>${input('code','留样签号','text','FLS-NEW','required')}${input('maturity','成熟度 / 0至1','number',.3,'step=".01" min="0" max="1"')}${input('stem_cm','实测杆长 / cm','number',72,'min="15" max="120"')}${input('cold_hours','采后冷藏 / 小时','number',2,'step=".1" min="0" max="48"')}<button class="primary" ${isViewer(s)?'disabled':''}>留样登记</button></form><p class="note">A最低80元/筐，B最低55元/筐，C最低30元/筐。主管核级与模型建议均保留。</p></aside></div>${modelPanel(s)}`;
}
export function bind(s,reload){
  bindActions(reload);
  document.querySelector('#sample-form').onsubmit=e=>{e.preventDefault();perform('/samples','POST',data(e.target,['consignment_id','maturity','stem_cm','cold_hours']),reload,'留样已登记')};
  document.querySelectorAll('.grade-form').forEach(f=>f.onsubmit=e=>{e.preventDefault();perform('/samples/'+f.dataset.id+'/approve','POST',data(f),reload,'主管等级已封存')});
  document.querySelectorAll('.observation-form').forEach(f=>f.onsubmit=e=>{e.preventDefault();perform('/samples/'+f.dataset.id+'/observation','PUT',data(f,['observed_days']),reload,'实际瓶插天数已封存')});
}
