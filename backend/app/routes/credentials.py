from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.auth import get_current_user, get_db
from app.models.user import User
from app.models.credential import UserCredential
from app.utils.security import encrypt_token
from pydantic import BaseModel

router = APIRouter(prefix="/credentials")

class CredentialRequest(BaseModel):
    provider: str
    token: str

@router.post("")
def save_credential(data: CredentialRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if data.provider not in ["render", "vercel"]:
        raise HTTPException(status_code=400, detail="Invalid provider")

    encrypted = encrypt_token(data.token)
    
    cred = db.query(UserCredential).filter(
        UserCredential.user_id == current_user.id,
        UserCredential.provider == data.provider
    ).first()

    if cred:
        cred.encrypted_token = encrypted
    else:
        cred = UserCredential(
            user_id=current_user.id,
            provider=data.provider,
            encrypted_token=encrypted
        )
        db.add(cred)

    db.commit()
    return {"message": f"{data.provider} token saved successfully"}