import os
from cryptography.fernet import Fernet

MASTER_KEY = os.getenv("FORGE_ENCRYPTION_KEY")
fernet = Fernet(MASTER_KEY.encode()) if MASTER_KEY else None

def encrypt_token(token: str) -> str:
    if not fernet:
        raise RuntimeError("ENCRYPTION_KEY not set")
    return fernet.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str) -> str:
    if not fernet:
        raise RuntimeError("ENCRYPTION_KEY not set")
    return fernet.decrypt(encrypted_token.encode()).decode()