from sqlalchemy import Column, Integer, String, DateTime, BigInteger, Text
from sqlalchemy.sql import func
from app.core.database import Base

class Run(Base):
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True)

    # Public project id (proj_xxxx)
    project_id = Column(String, index=True, nullable=False)

    commit_sha = Column(String, nullable=False)
    status = Column(String, default="queued")

    # GitHub
    check_run_id = Column(BigInteger, nullable=True)
    installation_id = Column(BigInteger, nullable=False)
    
    stdout = Column(Text, nullable=True)
    stderr = Column(Text, nullable=True)
    
    commit_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
