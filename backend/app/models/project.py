from sqlalchemy import Column, Integer, String, JSON, ForeignKey
from app.core.database import Base

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    project_id = Column(String, unique=True, index=True)
    name = Column(String)
    owner_id = Column(Integer, ForeignKey("users.id"))
    spec = Column(JSON) 
    deployment_metadata = Column(JSON, nullable=True, default={})