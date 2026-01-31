from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from app.core.database import Base

class RunStep(Base):
    __tablename__ = "run_steps"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("runs.id", ondelete="CASCADE"))

    name = Column(String, nullable=False)           # e.g. "Clone repo"
    step_order = Column(Integer, nullable=False)    # 1, 2, 3...

    status = Column(String, nullable=False)          # running / success / failed

    stdout = Column(Text)
    stderr = Column(Text)

    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True))
