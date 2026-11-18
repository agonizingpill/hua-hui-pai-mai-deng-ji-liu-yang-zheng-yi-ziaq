from sqlalchemy import select,func
from fastapi import HTTPException
from .models import Consignment,VaseSample,AuctionSession,AuctionLot,Bid,Deal,Clock
from .common import lock,pack,add,audit,stamp
FLOORS={'A':8000,'B':5500,'C':3000}
def session_create(s,d,u):
    clock=lock(s,Clock,1)
    if stamp(d.closes_at)<=clock.now:raise HTTPException(409,'场次必须晚于业务时钟结束')
    x=AuctionSession(code=d.code,opens_at=stamp(d.opens_at),closes_at=stamp(d.closes_at));audit(s,u,'建立拍卖场次 '+d.code);return add(s,x)
def offer(s,d,u):
    cons=lock(s,Consignment,d.consignment_id);session=lock(s,AuctionSession,d.session_id);clock=lock(s,Clock,1);sample=lock(s,VaseSample,d.sample_id)
    if sample.consignment_id!=cons.id or sample.state!='approved':raise HTTPException(409,'挂场须使用本到场批次已主管核定的留样等级')
    if session.closes_at<=clock.now:raise HTTPException(409,'场次已截止')
    if d.reserve_cents<FLOORS[sample.approved_grade]:raise HTTPException(409,'底价低于该等级最低筐价 '+str(FLOORS[sample.approved_grade]/100)+'元')
    occupied=s.scalar(select(func.coalesce(func.sum(AuctionLot.crates),0)).where(AuctionLot.consignment_id==cons.id,AuctionLot.state!='cancelled'))
    if occupied+d.crates>cons.crates:raise HTTPException(409,'到场筐数不足，已挂/已成交筐不可重复占用')
    x=AuctionLot(**d.model_dump(),grade_snapshot=sample.approved_grade);audit(s,u,'按等级挂场锁筐 '+d.code);return add(s,x)
def locked_lot(s,id):
    pre=s.get(AuctionLot,id)
    if not pre:raise HTTPException(404,'拍卖标的不存在')
    lock(s,Consignment,pre.consignment_id);session=lock(s,AuctionSession,pre.session_id);clock=lock(s,Clock,1);lot=lock(s,AuctionLot,id);return lot,session,clock
def bid(s,id,d,u):
    lot,session,clock=locked_lot(s,id)
    if lot.state!='offered' or not session.opens_at<=clock.now<session.closes_at:raise HTTPException(409,'标的未开场、已截止或已成交')
    highest=s.scalar(select(func.max(Bid.unit_cents)).where(Bid.lot_id==lot.id))or 0
    if d.unit_cents<lot.reserve_cents or d.unit_cents<=highest:raise HTTPException(409,'报价须达到底价并严格高于当前最高价')
    audit(s,u,'买方报价 '+d.buyer);return add(s,Bid(lot_id=lot.id,buyer=d.buyer,unit_cents=d.unit_cents,at=clock.now))
def close(s,id,u):
    lot,session,clock=locked_lot(s,id)
    if lot.state!='offered':raise HTTPException(409,'只能截标一次')
    if clock.now<session.closes_at:raise HTTPException(409,'场次尚未到截止时间')
    best=s.scalar(select(Bid).where(Bid.lot_id==lot.id).order_by(Bid.unit_cents.desc(),Bid.id).limit(1))
    if not best:raise HTTPException(409,'无有效出价，请撤下标的释放筐数')
    deal=Deal(lot_id=lot.id,bid_id=best.id,buyer=best.buyer,crates=lot.crates,unit_cents=best.unit_cents,original_grade=lot.grade_snapshot,effective_grade=lot.grade_snapshot,at=clock.now);lot.state='sold';audit(s,u,'截标成交 '+lot.code);return add(s,deal)
def cancel(s,id,u):
    lot,session,clock=locked_lot(s,id)
    if lot.state!='offered' or s.scalar(select(Bid.id).where(Bid.lot_id==lot.id)):raise HTTPException(409,'只有未成交且无出价标的可撤回')
    lot.state='cancelled';audit(s,u,'撤下未出价标的 '+lot.code);return pack(lot)
