from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.auth import get_current_user, get_db
from app.models.user import User
from app.models.credential import UserCredential
from app.utils.security import encrypt_token
from pydantic import BaseModel

router = APIRouter(prefix="/credentials")

VALID_PROVIDERS = {"railway", "vercel"}


class CredentialRequest(BaseModel):
    provider: str
    token: str


@router.post("")
def save_credential(
    data: CredentialRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if data.provider not in VALID_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid provider '{data.provider}'. Valid options: {', '.join(sorted(VALID_PROVIDERS))}",
        )

    encrypted = encrypt_token(data.token)

    cred = db.query(UserCredential).filter(
        UserCredential.user_id == current_user.id,
        UserCredential.provider == data.provider,
    ).first()

    if cred:
        cred.encrypted_token = encrypted
    else:
        cred = UserCredential(
            user_id=current_user.id,
            provider=data.provider,
            encrypted_token=encrypted,
        )
        db.add(cred)

    db.commit()
    return {"message": f"{data.provider} credentials saved successfully"}