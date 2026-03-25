from sqlalchemy import Column, Integer, String, Text, ForeignKey
from app.core.database import Base

class UserCredential(Base):
    __tablename__ = "user_credentials"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    provider = Column(String, nullable=False) 
    encrypted_token = Column(Text, nullable=False)