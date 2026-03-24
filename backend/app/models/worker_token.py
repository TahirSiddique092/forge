from app.core.database import Base
from sqlalchemy import Column, Integer, String

class WorkerToken(Base):
    __tablename__ = "worker_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True)
    project_id = Column(String)