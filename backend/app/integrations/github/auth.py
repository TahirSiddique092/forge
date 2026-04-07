import jwt
import time
import requests
import os
import sys
from dotenv import load_dotenv

load_dotenv()

GITHUB_APP_ID = os.getenv("GITHUB_APP_ID")
# Strip leading/trailing whitespace AND potential quotes
raw_key = os.getenv("GITHUB_PRIVATE_KEY", "")
GITHUB_PRIVATE_KEY = raw_key.strip().strip('"').strip("'").replace('\\n', '\n')

def get_app_jwt():
    if not GITHUB_PRIVATE_KEY or not GITHUB_APP_ID:
        print("CRITICAL: Missing GitHub App Credentials!", flush=True)
        return None

    now = int(time.time())
    payload = {
        "iat": now - 60,           # Issued 60s ago to handle clock drift
        "exp": now + (10 * 60),    # 10 minute expiry
        "iss": int(GITHUB_APP_ID), # Must be an integer
    }
    
    # Generate the token
    token = jwt.encode(payload, GITHUB_PRIVATE_KEY, algorithm="RS256")
    
    # Ensure it is a clean string (No b'...' prefix)
    if isinstance(token, bytes):
        token = token.decode('utf-8')
    
    # Force logs to show on Render
    print(f"DEBUG: Key length: {len(GITHUB_PRIVATE_KEY)}", flush=True)
    print(f"DEBUG: Token Type: {type(token)}", flush=True)
    print(f"DEBUG: Token starts with: {token[:15]}", flush=True)
    
    return token.strip() # Strip any accidental newlines from the final token

def get_installation_token(installation_id: int) -> str:
    jwt_token = get_app_jwt()

    res = requests.post(
        f"https://api.github.com/app/installations/{installation_id}/access_tokens",
        headers={
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json",
        },
    )
    
    if res.status_code != 201:
        # This print works, so we know this part of the logs is visible
        print(f"GitHub API Error: {res.status_code} - {res.text}", flush=True) 
        res.raise_for_status()

    return res.json()["token"]