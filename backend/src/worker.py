import os,time,json,logging
from pathlib import Path
import redis
from sqlalchemy import select
from .db import Session,ensure_schema
from .models import VaseSample,Consignment,ModelVersion
from .common import lock
from . import grading
from . import model_service
ensure_schema()
q=redis.Redis.from_url(os.environ['REDIS_URL'],decode_responses=True)
def process_one(sample_id):
    # 单条留样处理；中断重试同一留样时，非排队态直接跳过，不重复出结果
    with Session()as s:
        sample=lock(s,VaseSample,int(sample_id))
        if sample.state!='queued':return 'skipped'
        sample.state='running';s.commit()
        try:
            model_service.ensure_registry(s)
            code=sample.model_version or model_service.active_version(s).code  # 送估时固定的版本，重试不更换
            model_row=s.scalar(select(ModelVersion).where(ModelVersion.code==code))
            if not model_row:raise RuntimeError(f'留样固定的估级版本 {code} 不存在')
            result=grading.predict_with_version(sample,s.get(Consignment,sample.consignment_id),model_row)
            sample.model_version=code  # 回写实际用版，保证可追溯且重试沿用同一版本
            sample.prediction=result;sample.state='ready';sample.error=None
            Path(f'/artifacts/grade-{sample.id}.json').write_text(json.dumps(result,ensure_ascii=False))
            s.commit();return 'ready'
        except Exception as ex:
            sample.state='failed';sample.error=str(ex)[:450];s.commit();logging.exception('grade failed');return 'failed'
def main():
    while True:
        Path('/tmp/floral-heartbeat').touch()
        try:
            item=q.blpop('floral-grade',timeout=2)
            if not item:continue
            process_one(item[1])
        except Exception:logging.exception('queue unavailable');time.sleep(1)
if __name__=='__main__':main()
