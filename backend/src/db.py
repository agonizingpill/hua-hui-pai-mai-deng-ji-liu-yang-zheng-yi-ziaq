import os
from sqlalchemy import create_engine,inspect,text
from sqlalchemy.orm import DeclarativeBase,sessionmaker
engine=create_engine(os.environ['DATABASE_URL'],pool_pre_ping=True,isolation_level='READ COMMITTED')
Session=sessionmaker(engine,expire_on_commit=False)
class Base(DeclarativeBase):pass
def session():
    with Session() as s:yield s
def ensure_schema():
    # 新表直接按模型创建；已存在的旧表只做幂等补列，演示环境无独立迁移框架
    from . import models
    Base.metadata.create_all(engine)
    insp=inspect(engine);existing={c['name']for c in insp.get_columns('vase_samples')}
    if 'model_version' not in existing:
        with engine.begin() as conn:
            conn.execute(text('ALTER TABLE vase_samples ADD COLUMN model_version VARCHAR(20)'))
