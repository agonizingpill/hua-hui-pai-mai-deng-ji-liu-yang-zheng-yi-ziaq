from sqlalchemy import Column,Integer,String,Float,Boolean,ForeignKey,JSON,UniqueConstraint,CheckConstraint
from .db import Base
from .constants import SAMPLE_STATES,LOT_STATES
class User(Base):
    __tablename__='users'
    id=Column(Integer,primary_key=True);email=Column(String(100),unique=True,nullable=False);password_hash=Column(String(220),nullable=False);role=Column(String(30),nullable=False)
class Audit(Base):
    __tablename__='audits'
    id=Column(Integer,primary_key=True);actor=Column(String(100));action=Column(String(300))
class Clock(Base):
    __tablename__='clock'
    id=Column(Integer,primary_key=True);now=Column(String(20),nullable=False)
class Consignment(Base):
    __tablename__='consignments'
    id=Column(Integer,primary_key=True);code=Column(String(60),unique=True,nullable=False);grower=Column(String(100),nullable=False);variety=Column(String(80),nullable=False);cut_at=Column(String(20),nullable=False);arrived_at=Column(String(20),nullable=False);crates=Column(Integer,nullable=False);stems_per_crate=Column(Integer,nullable=False);note=Column(String(250),default='')
    __table_args__=(CheckConstraint('crates>0 AND stems_per_crate>0'),)
class VaseSample(Base):
    __tablename__='vase_samples'
    id=Column(Integer,primary_key=True);consignment_id=Column(Integer,ForeignKey('consignments.id'),nullable=False);code=Column(String(60),unique=True,nullable=False);maturity=Column(Float,nullable=False);stem_cm=Column(Float,nullable=False);cold_hours=Column(Float,nullable=False);observed_days=Column(Float,nullable=True);state=Column(String(20),default=SAMPLE_STATES[0]);prediction=Column(JSON);error=Column(String(450));approved_grade=Column(String(2));review_note=Column(String(250));model_version=Column(String(20))
class AuctionSession(Base):
    __tablename__='auction_sessions'
    id=Column(Integer,primary_key=True);code=Column(String(60),unique=True,nullable=False);opens_at=Column(String(20),nullable=False);closes_at=Column(String(20),nullable=False)
class AuctionLot(Base):
    __tablename__='auction_lots'
    id=Column(Integer,primary_key=True);code=Column(String(60),unique=True,nullable=False);consignment_id=Column(Integer,ForeignKey('consignments.id'),nullable=False);sample_id=Column(Integer,ForeignKey('vase_samples.id'),nullable=False);session_id=Column(Integer,ForeignKey('auction_sessions.id'),nullable=False);crates=Column(Integer,nullable=False);reserve_cents=Column(Integer,nullable=False);state=Column(String(20),default=LOT_STATES[0]);grade_snapshot=Column(String(2),nullable=False)
    __table_args__=(CheckConstraint('crates>0 AND reserve_cents>0'),)
class Bid(Base):
    __tablename__='bids'
    id=Column(Integer,primary_key=True);lot_id=Column(Integer,ForeignKey('auction_lots.id'),nullable=False);buyer=Column(String(80),nullable=False);unit_cents=Column(Integer,nullable=False);at=Column(String(20),nullable=False)
class Deal(Base):
    __tablename__='deals'
    id=Column(Integer,primary_key=True);lot_id=Column(Integer,ForeignKey('auction_lots.id'),unique=True,nullable=False);bid_id=Column(Integer,ForeignKey('bids.id'),nullable=False);buyer=Column(String(80),nullable=False);crates=Column(Integer,nullable=False);unit_cents=Column(Integer,nullable=False);original_grade=Column(String(2),nullable=False);effective_grade=Column(String(2),nullable=False);revision=Column(Integer,default=1);at=Column(String(20),nullable=False)
class Dispute(Base):
    __tablename__='disputes'
    id=Column(Integer,primary_key=True);deal_id=Column(Integer,ForeignKey('deals.id'),nullable=False);reason=Column(String(250),nullable=False);state=Column(String(20),default='opened');decision_note=Column(String(250));revised_grade=Column(String(2));sample_snapshot=Column(JSON)
class Settlement(Base):
    __tablename__='settlements'
    id=Column(Integer,primary_key=True);deal_id=Column(Integer,ForeignKey('deals.id'),nullable=False);revision=Column(Integer,nullable=False);kind=Column(String(20),nullable=False);gross_cents=Column(Integer,nullable=False);commission_cents=Column(Integer,nullable=False);target_cents=Column(Integer,nullable=False);delta_cents=Column(Integer,nullable=False);state=Column(String(20),default='draft');snapshot=Column(JSON);receipt=Column(String(80))
    __table_args__=(UniqueConstraint('deal_id','revision'),)
class ModelVersion(Base):
    __tablename__='model_versions'
    id=Column(Integer,primary_key=True);code=Column(String(20),unique=True,nullable=False);label=Column(String(100),nullable=False);state=Column(String(20),nullable=False);holdout_mae_days=Column(Float);trained_rows=Column(Integer);training_snapshot=Column(JSON);holdout_consignment_ids=Column(JSON);last_evaluated_at=Column(String(20));note=Column(String(250),default='')
class ModelEvaluation(Base):
    __tablename__='model_evaluations'
    id=Column(Integer,primary_key=True);at=Column(String(20),nullable=False);old_version=Column(String(20),nullable=False);new_version=Column(String(20),nullable=False);old_mae_days=Column(Float,nullable=False);new_mae_days=Column(Float,nullable=False);switched=Column(Boolean,nullable=False);reason=Column(String(250),nullable=False);holdout_consignment_ids=Column(JSON);holdout_sample_ids=Column(JSON);actor=Column(String(100))
