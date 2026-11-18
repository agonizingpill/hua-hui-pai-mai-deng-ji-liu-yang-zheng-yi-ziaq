import hashlib
from datetime import datetime
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
FEATURES=('maturity','stem_cm','postcut_hours','cold_hours')
GRADE_THRESHOLDS={'A':10,'B':7,'C':0}
V1_CODE='v1-synthetic';V2_CODE='v2-sealed'
def synthetic_dataset():
    rng=np.random.default_rng(35);x=np.column_stack([rng.uniform(.1,1,200),rng.uniform(35,90,200),rng.uniform(1,40,200),rng.uniform(0,25,200)])
    y=np.clip(14-6*x[:,0]+.04*(x[:,1]-50)-.13*x[:,2]+.09*x[:,3]+rng.normal(0,.35,200),2,20)
    return x,y
def postcut_hours(cons):
    return (datetime.fromisoformat(cons.arrived_at)-datetime.fromisoformat(cons.cut_at)).total_seconds()/3600
def features_of(sample,cons):
    return [sample.maturity,sample.stem_cm,postcut_hours(cons),sample.cold_hours]
def grade_of(days):
    return 'A'if days>=10 else 'B'if days>=7 else 'C'
def _new_model():
    return GradientBoostingRegressor(n_estimators=80,max_depth=2,random_state=35)
def train_v1():
    x,y=synthetic_dataset()
    tr,te=train_test_split(np.arange(200),test_size=.25,random_state=35)
    model=_new_model();model.fit(x[tr],y[tr])
    mae=float(mean_absolute_error(y[te],model.predict(x[te])))
    meta={'model':'GradientBoostingRegressor','seed':35,'train_rows':150,'holdout_rows':50,'train_indices':tr.tolist(),'holdout_indices':te.tolist(),'source_checksum':hashlib.sha256(np.column_stack([x,y]).tobytes()).hexdigest(),'synthetic_holdout_mae_days':round(mae,4)}
    return model,meta
def _rows_to_xy(rows):
    return np.array([r['features']for r in rows],dtype=float),np.array([r['observed_days']for r in rows],dtype=float)
def train_v2(train_rows):
    x,y=_rows_to_xy(train_rows)
    model=_new_model();model.fit(x,y)
    checksum=hashlib.sha256(np.column_stack([x,y]).tobytes()).hexdigest()
    return model,checksum
def real_holdout_mae(train_rows,holdout_rows):
    model,checksum=train_v2(train_rows)
    xh,yh=_rows_to_xy(holdout_rows)
    return float(mean_absolute_error(yh,model.predict(xh))),checksum
def predict_with_version(sample,cons,model_row):
    feats=features_of(sample,cons)
    if model_row.code==V1_CODE:
        model,meta=train_v1()
        estimate=float(model.predict([feats])[0])
        return {'model':meta['model'],'seed':meta['seed'],'model_code':V1_CODE,'model_version':V1_CODE,'train_rows':meta['train_rows'],'holdout_rows':meta['holdout_rows'],'train_indices':meta['train_indices'],'holdout_indices':meta['holdout_indices'],'source_checksum':meta['source_checksum'],'input_snapshot':dict(zip(FEATURES,feats)),'vase_days':round(estimate,3),'suggested_grade':grade_of(estimate),'holdout_mae_days':meta['synthetic_holdout_mae_days'],'threshold_days':GRADE_THRESHOLDS}
    snap=model_row.training_snapshot or {}
    train_rows=snap.get('rows',[])
    if not train_rows:raise RuntimeError('新版模型训练快照缺失，无法估级')
    model,_=train_v2(train_rows)
    estimate=float(model.predict([feats])[0])
    return {'model':'GradientBoostingRegressor','seed':35,'model_code':V2_CODE,'model_version':V2_CODE,'training_source':'sealed-vase-endpoint','train_rows':len(train_rows),'holdout_rows':len(model_row.holdout_consignment_ids or []),'trained_sample_ids':snap.get('sample_ids',[]),'trained_consignment_ids':snap.get('consignment_ids',[]),'source_checksum':snap.get('source_checksum'),'input_snapshot':dict(zip(FEATURES,feats)),'vase_days':round(estimate,3),'suggested_grade':grade_of(estimate),'holdout_mae_days':round(model_row.holdout_mae_days,4)if model_row.holdout_mae_days is not None else None,'threshold_days':GRADE_THRESHOLDS}
def predict(sample,cons):
    class _V1:
        code=V1_CODE;training_snapshot=None;holdout_consignment_ids=None;holdout_mae_days=None
    return predict_with_version(sample,cons,_V1())
