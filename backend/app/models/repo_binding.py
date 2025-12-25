from sqlalchemy import Column, Integer, String, ForeignKey
from app.core.database import Base

class RepoBinding(Base):
    __tablename__ = "repo_bindings"

    id = Column(Integer, primary_key=True, index=True)

    repo_full_name = Column(String, unique=True, index=True, nullable=False)

    project_id = Column(
        String,
        ForeignKey("projects.project_id"),
        nullable=False
    )
