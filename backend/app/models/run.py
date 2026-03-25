from sqlalchemy import Column, Integer, String, DateTime, BigInteger, Text, JSON
from sqlalchemy.sql import func
from app.core.database import Base

class Run(Base):
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True)
    project_id = Column(String, index=True, nullable=False)
    commit_sha = Column(String, nullable=False)
    commit_message = Column(Text, nullable=True)
    status = Column(String, default="queued") 

    check_run_id = Column(BigInteger, nullable=True)
    installation_id = Column(BigInteger, nullable=False)

    component_results = Column(JSON, nullable=True, default={})

    created_at = Column(DateTime(timezone=True), server_default=func.now())