import os,logging
from contextlib import asynccontextmanager
import redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from fastapi import FastAPI,Depends,HTTPException
from fastapi.responses import JSONResponse
from .db import session
from .models import *
from .schemas import *
from .common import lock,pack,add,audit,stamp
from .auth import current,writer,supervisor,verify,token
from .middleware import Trace,Burst
from . import auction_service as auction,dispute_service as dispute
q=redis.Redis.from_url(os.environ['REDIS_URL'],decode_responses=True)
@asynccontextmanager
async def lifespan(app):
    if os.getenv('SEED_DEMO','true').lower()=='true':
        try:
            from .seed_service import seed
            seed()
        except Exception:logging.exception('seed failed')
    yield
app=FastAPI(title='晨露花市·拍价留样簿',lifespan=lifespan);app.add_middleware(Trace);app.add_middleware(Burst)
@app.exception_handler(IntegrityError)
async def duplicate(r,e):return JSONResponse({'detail':'编号或该成交修订版结算已存在，不能重复登记'},409)
@app.get('/health')
def health(s=Depends(session)):s.execute(select(1));q.ping();return {'status':'ok'}
@app.post('/auth/login')
def login(d:Login,s=Depends(session)):
    u=s.scalar(select(User).where(User.email==d.email))
    if not u or not verify(d.password,u.password_hash):raise HTTPException(401,'邮箱或口令错误')
    return {'token':token(u),'user':{'email':u.email,'role':u.role}}
@app.get('/me')
def me(u=Depends(current)):return {'email':u.email,'role':u.role}
@app.get('/archive')
def archive(s=Depends(session),u=Depends(current)):
    return {m.__tablename__:[pack(x)for x in s.scalars(select(m).order_by(m.id))]for m in (Clock,Consignment,VaseSample,AuctionSession,AuctionLot,Bid,Deal,Dispute,Settlement)}
@app.get('/audits')
def audits(s=Depends(session),u=Depends(current)):return [pack(x)for x in s.scalars(select(Audit).order_by(Audit.id.desc()).limit(50))]
@app.post('/consignments')
def consignment(d:ConsignmentInput,s=Depends(session),u=Depends(writer)):
    if stamp(d.arrived_at)>s.get(Clock,1).now:raise HTTPException(409,'到场不可晚于业务时钟')
    x=add(s,Consignment(**d.model_dump(exclude={'cut_at','arrived_at'}),cut_at=stamp(d.cut_at),arrived_at=stamp(d.arrived_at)));audit(s,u,'到场分筐 '+d.code);s.commit();return x
@app.put('/consignments/{id}/note')
def note(id:int,d:NoteInput,s=Depends(session),u=Depends(supervisor)):
    x=lock(s,Consignment,id);x.note=d.note;audit(s,u,'核对筐贴说明 '+x.code);s.commit();return pack(x)
@app.post('/samples')
def sample(d:SampleInput,s=Depends(session),u=Depends(writer)):
    c=lock(s,Consignment,d.consignment_id)
    from datetime import datetime
    hours=(datetime.fromisoformat(c.arrived_at)-datetime.fromisoformat(c.cut_at)).total_seconds()/3600
    if d.cold_hours>hours:raise HTTPException(409,'冷藏时长不可超过采后到场时长')
    x=add(s,VaseSample(**d.model_dump()));audit(s,u,'瓶插留样 '+d.code);s.commit();return x
@app.post('/samples/{id}/estimate')
def estimate(id:int,s=Depends(session),u=Depends(writer)):
    x=lock(s,VaseSample,id)
    if x.state not in ('recorded','failed'):raise HTTPException(409,'仅新留样或失败评估可估级')
    x.state='queued';x.error=None;s.commit()
    try:q.rpush('floral-grade',id)
    except Exception:x.state='failed';x.error='队列不可用，恢复后可重试';s.commit();raise HTTPException(503,x.error)
    return pack(x)
@app.post('/samples/{id}/approve')
def grade(id:int,d:GradeInput,s=Depends(session),u=Depends(supervisor)):
    x=lock(s,VaseSample,id)
    if x.state!='ready' or not x.prediction:raise HTTPException(409,'先完成worker寿命估级')
    x.approved_grade=d.grade;x.review_note=d.note;x.state='approved';audit(s,u,'主管核定等级 '+d.grade);s.commit();return pack(x)
@app.put('/samples/{id}/observation')
def observation(id:int,d:ObservationInput,s=Depends(session),u=Depends(writer)):
    x=lock(s,VaseSample,id)
    if x.observed_days is not None:raise HTTPException(409,'瓶插终点观察已封存，不可覆盖争议证据')
    x.observed_days=d.observed_days;audit(s,u,'封存实际瓶插观察');s.commit();return pack(x)
@app.post('/sessions')
def session_new(d:SessionInput,s=Depends(session),u=Depends(supervisor)):
    x=auction.session_create(s,d,u);s.commit();return x
@app.put('/clock')
def clock(d:ClockInput,s=Depends(session),u=Depends(supervisor)):
    x=lock(s,Clock,1)
    if stamp(d.now)<=x.now:raise HTTPException(409,'业务时钟只能向前，不能重开已截止竞价')
    x.now=stamp(d.now);audit(s,u,'推进业务时钟 '+x.now);s.commit();return pack(x)
@app.post('/lots')
def offer(d:LotInput,s=Depends(session),u=Depends(writer)):
    x=auction.offer(s,d,u);s.commit();return x
@app.post('/lots/{id}/bids')
def bid(id:int,d:BidInput,s=Depends(session),u=Depends(writer)):
    x=auction.bid(s,id,d,u);s.commit();return x
@app.post('/lots/{id}/close')
def close(id:int,s=Depends(session),u=Depends(supervisor)):
    x=auction.close(s,id,u);s.commit();return x
@app.post('/lots/{id}/cancel')
def cancel(id:int,s=Depends(session),u=Depends(supervisor)):
    x=auction.cancel(s,id,u);s.commit();return x
@app.post('/disputes')
def claim(d:DisputeInput,s=Depends(session),u=Depends(writer)):
    x=dispute.open_dispute(s,d,u);s.commit();return x
@app.post('/disputes/{id}/decide')
def decide(id:int,d:DecisionInput,s=Depends(session),u=Depends(supervisor)):
    x=dispute.decide(s,id,d,u);s.commit();return x
@app.post('/deals/{id}/settlements')
def settlement(id:int,s=Depends(session),u=Depends(supervisor)):
    x=dispute.draft(s,id,u);s.commit();return x
@app.post('/settlements/{id}/pay')
def pay(id:int,d:ReceiptInput,s=Depends(session),u=Depends(supervisor)):
    x=dispute.pay(s,id,d,u);s.commit();return x
