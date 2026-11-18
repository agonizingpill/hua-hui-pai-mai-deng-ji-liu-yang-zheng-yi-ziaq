from sqlalchemy import select
from fastapi import HTTPException
from .models import Audit
def pack(x):return {c.name:getattr(x,c.name)for c in x.__table__.columns}
def lock(s,cls,id):
    x=s.scalar(select(cls).where(cls.id==id).with_for_update().execution_options(populate_existing=True))
    if not x:raise HTTPException(404,'业务记录不存在')
    return x
def add(s,x):s.add(x);s.flush();return pack(x)
def audit(s,u,text):s.add(Audit(actor=u.email,action=text))
def stamp(d):return d.replace(tzinfo=None).isoformat(timespec='seconds')
