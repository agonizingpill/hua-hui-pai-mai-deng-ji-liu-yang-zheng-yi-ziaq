from datetime import datetime
import numpy as np
from sklearn.metrics import mean_absolute_error
from sqlalchemy import select
from fastapi import HTTPException
from .models import ModelVersion,ModelEvaluation,VaseSample,Consignment,Clock
from .common import lock,pack,audit,stamp
from . import grading
from .constants import MIN_HOLDOUT_SAMPLES,MIN_TRAINING_SAMPLES
def _sealed_rows(s):
    # 只使用已封存实际瓶插终点的样本；holdout按到场批固定，整批不进训练
    rows=[]
    for sample in s.scalars(select(VaseSample).where(VaseSample.observed_days.is_not(None)).order_by(VaseSample.id)):
        cons=s.get(Consignment,sample.consignment_id)
        rows.append({'sample_id':sample.id,'consignment_id':cons.id,'consignment_code':cons.code,'features':grading.features_of(sample,cons),'observed_days':float(sample.observed_days)})
    return rows
def holdout_consignment_ids(rows):
    # 确定性固定留出：封存样本最多的到场批入选，并列取到场单id最小者
    counts={}
    for r in rows:counts[r['consignment_id']]=counts.get(r['consignment_id'],0)+1
    if not counts:return []
    top=max(counts.values())
    return sorted(cid for cid,n in counts.items() if n==top)[:1]
def resolve_holdout(s,rows):
    # 固定留出批一旦在首次评估选定，后续评估沿用同一到场批，保证两版始终在同一组留样上比较
    last=s.scalar(select(ModelEvaluation).order_by(ModelEvaluation.id.desc()))
    present={r['consignment_id']for r in rows}
    if last and last.holdout_consignment_ids:
        kept=[cid for cid in last.holdout_consignment_ids if cid in present]
        if kept:return kept
    return holdout_consignment_ids(rows)
def _split(rows,holdout_ids):
    holdout=[r for r in rows if r['consignment_id'] in holdout_ids]
    train=[r for r in rows if r['consignment_id'] not in holdout_ids]
    return train,holdout
def ensure_registry(s):
    if not s.scalar(select(ModelVersion.id)):
        _,meta=grading.train_v1()
        s.add(ModelVersion(code=grading.V1_CODE,label='旧版 · 合成花卉观测训练（seed35）',state='active',holdout_mae_days=meta['synthetic_holdout_mae_days'],trained_rows=150,note='现行估级版本，留样送估时默认沿用'))
        s.add(ModelVersion(code=grading.V2_CODE,label='新版 · 已封存瓶插终点训练',state='candidate',note='按到场批固定留出评估，MAE不劣于旧版才可切换'))
        s.flush()
def active_version(s):
    return s.scalar(select(ModelVersion).where(ModelVersion.state=='active'))
def comparison(s):
    ensure_registry(s)
    rows=_sealed_rows(s);holdout_ids=resolve_holdout(s,rows)
    train,holdout=_split(rows,holdout_ids)
    last=s.scalar(select(ModelEvaluation).order_by(ModelEvaluation.id.desc()))
    return {'model_versions':[pack(m)for m in s.scalars(select(ModelVersion).order_by(ModelVersion.id))],'active_version':active_version(s).code,'holdout_consignment_ids':holdout_ids,'holdout_sample_ids':[r['sample_id']for r in holdout],'training_sample_ids':[r['sample_id']for r in train],'sealed_sample_count':len(rows),'min_holdout_samples':MIN_HOLDOUT_SAMPLES,'min_training_samples':MIN_TRAINING_SAMPLES,'latest_evaluation':pack(last) if last else None,'evaluations':[pack(e)for e in s.scalars(select(ModelEvaluation).order_by(ModelEvaluation.id.desc()))]}
def switch(s,u):
    lock(s,Clock,1)  # 与其它写动作共用业务时钟父锁，避免并发换版
    ensure_registry(s)
    old=s.scalar(select(ModelVersion).where(ModelVersion.code==grading.V1_CODE))
    new=s.scalar(select(ModelVersion).where(ModelVersion.code==grading.V2_CODE))
    if new.state=='active':raise HTTPException(409,'新版已切换生效，无需再次换版')
    rows=_sealed_rows(s);holdout_ids=resolve_holdout(s,rows)
    train,holdout=_split(rows,holdout_ids)
    if len(holdout)<MIN_HOLDOUT_SAMPLES:raise HTTPException(409,f'固定留出批封存留样不足{MIN_HOLDOUT_SAMPLES}条，无法可靠比较MAE')
    if len(train)<MIN_TRAINING_SAMPLES:raise HTTPException(409,f'非留出批封存留样不足{MIN_TRAINING_SAMPLES}条，无法训练新版')
    # 两版在同一组固定留出样本上比较平均绝对误差
    v1_model,v1_meta=grading.train_v1()
    xh=np.array([r['features']for r in holdout]);yh=np.array([r['observed_days']for r in holdout])
    old_mae=float(mean_absolute_error(yh,v1_model.predict(xh)))
    new_mae,checksum=grading.real_holdout_mae(train,holdout)
    switched=new_mae<=old_mae
    reason='新版固定留出MAE不劣于旧版，切换新版' if switched else f'新版固定留出MAE {round(new_mae,4)} 天劣于旧版 {round(old_mae,4)} 天，沿用旧版'
    now=stamp(datetime.now())
    old.last_evaluated_at=now;old.holdout_consignment_ids=holdout_ids
    old.training_snapshot={'synthetic_holdout_mae_days':v1_meta['synthetic_holdout_mae_days'],'real_holdout_mae_days':round(old_mae,4),'holdout_sample_ids':[r['sample_id']for r in holdout]}
    old.holdout_mae_days=round(old_mae,4)  # 与新版同口径：固定留出批上的MAE
    new.trained_rows=len(train);new.holdout_mae_days=round(new_mae,4);new.holdout_consignment_ids=holdout_ids;new.last_evaluated_at=now
    new.training_snapshot={'sample_ids':[r['sample_id']for r in train],'consignment_ids':sorted({r['consignment_id']for r in train}),'rows':train,'source_checksum':checksum}
    if switched:
        new.state='active';new.note='已切换：固定留出MAE不劣于旧版'
        old.state='archived';old.note='已被新版替代，历史留样仍保留其估级依据'
    s.add(ModelEvaluation(at=now,old_version=old.code,new_version=new.code,old_mae_days=round(old_mae,4),new_mae_days=round(new_mae,4),switched=switched,reason=reason,holdout_consignment_ids=holdout_ids,holdout_sample_ids=[r['sample_id']for r in holdout],actor=u.email))
    audit(s,u,('换版成功 ' if switched else '换版失败沿用旧版 ')+f'旧MAE {round(old_mae,4)} / 新MAE {round(new_mae,4)}')
    return switched,reason
