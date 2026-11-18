import os,time,json,logging
from pathlib import Path
import redis
from .db import Session
from .models import VaseSample,Consignment
from .common import lock
from .grading import predict
q=redis.Redis.from_url(os.environ['REDIS_URL'],decode_responses=True)
while True:
    Path('/tmp/floral-heartbeat').touch()
    try:
        item=q.blpop('floral-grade',timeout=2)
        if not item:continue
        with Session()as s:
            sample=lock(s,VaseSample,int(item[1]))
            if sample.state!='queued':continue
            sample.state='running';s.commit()
            try:
                result=predict(sample,s.get(Consignment,sample.consignment_id));sample.prediction=result;sample.state='ready';sample.error=None;Path(f'/artifacts/grade-{sample.id}.json').write_text(json.dumps(result,ensure_ascii=False));s.commit()
            except Exception as ex:sample.state='failed';sample.error=str(ex)[:450];s.commit();logging.exception('grade failed')
    except Exception:logging.exception('queue unavailable');time.sleep(1)
