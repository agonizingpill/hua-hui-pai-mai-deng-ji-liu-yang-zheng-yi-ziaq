import hashlib,json
from datetime import datetime
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
def predict(sample,cons):
    rng=np.random.default_rng(35);x=np.column_stack([rng.uniform(.1,1,200),rng.uniform(35,90,200),rng.uniform(1,40,200),rng.uniform(0,25,200)])
    y=np.clip(14-6*x[:,0]+.04*(x[:,1]-50)-.13*x[:,2]+.09*x[:,3]+rng.normal(0,.35,200),2,20)
    tr,te=train_test_split(np.arange(200),test_size=.25,random_state=35);model=GradientBoostingRegressor(n_estimators=80,max_depth=2,random_state=35);model.fit(x[tr],y[tr]);hours=(datetime.fromisoformat(cons.arrived_at)-datetime.fromisoformat(cons.cut_at)).total_seconds()/3600
    features=[sample.maturity,sample.stem_cm,hours,sample.cold_hours];estimate=float(model.predict([features])[0]);mae=float(mean_absolute_error(y[te],model.predict(x[te])))
    return {'model':'GradientBoostingRegressor','seed':35,'train_rows':150,'holdout_rows':50,'train_indices':tr.tolist(),'holdout_indices':te.tolist(),'source_checksum':hashlib.sha256(np.column_stack([x,y]).tobytes()).hexdigest(),'input_snapshot':dict(zip(['maturity','stem_cm','postcut_hours','cold_hours'],features)),'vase_days':round(estimate,3),'suggested_grade':'A'if estimate>=10 else'B'if estimate>=7 else'C','holdout_mae_days':round(mae,4),'threshold_days':{'A':10,'B':7,'C':0}}
