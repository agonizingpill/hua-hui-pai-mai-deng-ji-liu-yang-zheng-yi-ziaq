from datetime import datetime
from typing import Literal
from pydantic import BaseModel,Field,model_validator
class Login(BaseModel):email:str;password:str
class ConsignmentInput(BaseModel):
    code:str=Field(min_length=3,max_length=60);grower:str=Field(min_length=2,max_length=100);variety:str=Field(min_length=2,max_length=80);cut_at:datetime;arrived_at:datetime;crates:int=Field(ge=1,le=10000);stems_per_crate:int=Field(ge=1,le=500);note:str=Field(default='',max_length=250)
    @model_validator(mode='after')
    def valid(self):
        if self.arrived_at<self.cut_at or (self.arrived_at-self.cut_at).total_seconds()>172800:raise ValueError('到场须在采切后48小时内')
        return self
class NoteInput(BaseModel):note:str=Field(min_length=2,max_length=250)
class SampleInput(BaseModel):
    consignment_id:int;code:str=Field(min_length=3,max_length=60);maturity:float=Field(ge=0,le=1,allow_inf_nan=False);stem_cm:float=Field(ge=15,le=120,allow_inf_nan=False);cold_hours:float=Field(ge=0,le=48,allow_inf_nan=False)
class ObservationInput(BaseModel):observed_days:float=Field(ge=1,le=30,allow_inf_nan=False)
class GradeInput(BaseModel):grade:Literal['A','B','C'];note:str=Field(min_length=4,max_length=250)
class SessionInput(BaseModel):
    code:str=Field(min_length=3,max_length=60);opens_at:datetime;closes_at:datetime
    @model_validator(mode='after')
    def valid(self):
        if self.closes_at<=self.opens_at or (self.closes_at-self.opens_at).total_seconds()>86400:raise ValueError('场次关闭须在开场后24小时内')
        return self
class ClockInput(BaseModel):now:datetime
class LotInput(BaseModel):
    code:str=Field(min_length=3,max_length=60);consignment_id:int;sample_id:int;session_id:int;crates:int=Field(ge=1,le=10000);reserve_cents:int=Field(ge=100,le=10000000)
class BidInput(BaseModel):buyer:str=Field(min_length=2,max_length=80);unit_cents:int=Field(ge=100,le=10000000)
class DisputeInput(BaseModel):deal_id:int;reason:str=Field(min_length=6,max_length=250)
class DecisionInput(BaseModel):grade:Literal['A','B','C'];note:str=Field(min_length=6,max_length=250)
class ReceiptInput(BaseModel):receipt:str=Field(min_length=4,max_length=80)
