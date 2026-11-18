from sqlalchemy import select,func
from .db import Base,engine,Session
from .models import *
from .auth import hashed

def seed():
    Base.metadata.create_all(engine)
    with Session()as s:
        for role in ('operator','supervisor','viewer'):
            if not s.scalar(select(User.id).where(User.email==role+'@chenlu.demo')):s.add(User(email=role+'@chenlu.demo',password_hash=hashed('Flowers2026!'),role=role))
        if not s.get(Clock,1):s.add(Clock(id=1,now='2026-11-18T08:00:00'))
        c=s.scalar(select(Consignment).where(Consignment.code=='FL031'))
        if not c:c=Consignment(code='FL031',grower='露禾花圃',variety='洋桔梗·晨雾白',cut_at='2026-11-18T04:30:00',arrived_at='2026-11-18T07:30:00',crates=18,stems_per_crate=40,note='18筐逐筐验收，筐贴FL031-01至18');s.add(c);s.flush()
        sample=s.scalar(select(VaseSample).where(VaseSample.code=='FLS31'))
        if not sample:sample=VaseSample(consignment_id=c.id,code='FLS31',maturity=.35,stem_cm=72,cold_hours=2,observed_days=6,state='approved',approved_grade='A',review_note='历史已核级签，样本后续观察6天');s.add(sample);s.flush()
        session=s.scalar(select(AuctionSession).where(AuctionSession.code=='HISTORY-031'))
        if not session:session=AuctionSession(code='HISTORY-031',opens_at='2026-11-18T07:40:00',closes_at='2026-11-18T07:50:00');s.add(session);s.flush()
        lot=s.scalar(select(AuctionLot).where(AuctionLot.code=='HIST-LOT031'))
        if not lot:lot=AuctionLot(code='HIST-LOT031',consignment_id=c.id,sample_id=sample.id,session_id=session.id,crates=2,reserve_cents=8000,state='sold',grade_snapshot='A');s.add(lot);s.flush()
        bid=s.scalar(select(Bid).where(Bid.lot_id==lot.id))
        if not bid:bid=Bid(lot_id=lot.id,buyer='巷口花店',unit_cents=10000,at='2026-11-18T07:45:00');s.add(bid);s.flush()
        deal=s.scalar(select(Deal).where(Deal.lot_id==lot.id))
        if not deal:deal=Deal(lot_id=lot.id,bid_id=bid.id,buyer=bid.buyer,crates=2,unit_cents=10000,original_grade='A',effective_grade='A',revision=1,at='2026-11-18T07:50:00');s.add(deal);s.flush()
        if not s.scalar(select(Dispute.id).where(Dispute.deal_id==deal.id)):s.add(Dispute(deal_id=deal.id,reason='历史留样仅6天，买方请求按留样复判',state='opened',sample_snapshot={c.name:getattr(sample,c.name)for c in sample.__table__.columns}))
        # 多到场批已封存瓶插终点：按到场批固定留出，用于新版估级训练与MAE比较
        demo_batches=[
            ('FL032','露禾花圃','洋桔梗·雾粉','2026-11-17T05:00:00','2026-11-17T07:40:00',[
                ('FLS32-A',.42,68,3,7.5),('FLS32-B',.55,60,4,6.2)]),
            ('FL033','青岚花圃','洋桔梗·晨雾白','2026-11-17T04:40:00','2026-11-17T07:20:00',[
                ('FLS33-A',.30,78,2,9.8),('FLS33-B',.48,64,5,7.1),('FLS33-C',.62,55,3,5.4)]),
            ('FL034','青岚花圃','洋桔梗·雾粉','2026-11-17T05:20:00','2026-11-17T08:10:00',[
                ('FLS34-A',.38,74,2,8.6)]),
        ]
        for ccode,grower,variety,cut,arrived,samples_ in demo_batches:
            bc=s.scalar(select(Consignment).where(Consignment.code==ccode))
            if not bc:
                bc=Consignment(code=ccode,grower=grower,variety=variety,cut_at=cut,arrived_at=arrived,crates=12,stems_per_crate=40,note='封存终点留样批次');s.add(bc);s.flush()
            for scode,mat,stem,cold,days in samples_:
                if not s.scalar(select(VaseSample.id).where(VaseSample.code==scode)):
                    s.add(VaseSample(consignment_id=bc.id,code=scode,maturity=mat,stem_cm=stem,cold_hours=cold,observed_days=days,state='recorded'))
        # 可送估的新留样（无封存终点，不进训练/留出）
        if not s.scalar(select(VaseSample.id).where(VaseSample.code=='FLS-NEW-DEMO')):
            s.add(VaseSample(consignment_id=c.id,code='FLS-NEW-DEMO',maturity=.3,stem_cm=72,cold_hours=2,state='recorded'))
        s.commit();return {m.__tablename__:s.scalar(select(func.count()).select_from(m))for m in (User,Consignment,VaseSample,AuctionSession,AuctionLot,Bid,Deal,Dispute,Settlement,ModelVersion,ModelEvaluation)}
