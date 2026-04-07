import jwt
import time
import requests
import os
from dotenv import load_dotenv

load_dotenv()

# 1. Clean the App ID and Private Key immediately
GITHUB_APP_ID = os.getenv("GITHUB_APP_ID", "").strip()
# This removes accidental quotes and handles both literal and escaped newlines
raw_key = os.getenv("GITHUB_PRIVATE_KEY", "").strip().strip('"').strip("'")
GITHUB_PRIVATE_KEY = raw_key.replace('\\n', '\n')

def get_app_jwt():
    if not GITHUB_APP_ID or not GITHUB_PRIVATE_KEY:
        print("CRITICAL: Missing GitHub Credentials", flush=True)
        return None

    now = int(time.time())
    payload = {
        # iat: 60s ago to be safe against clock drift
        "iat": now - 60,
        # exp: 5 minutes is plenty (GitHub max is 10)
        "exp": now + (5 * 60),
        # iss: MUST be an integer App ID
        "iss": int(GITHUB_APP_ID), 
    }
    
    # Generate the token
    token = jwt.encode(payload, GITHUB_PRIVATE_KEY, algorithm="RS256")
    
    # Ensure it is a clean string with no hidden whitespace
    if isinstance(token, bytes):
        token = token.decode('utf-8')
    
    return token.strip()

def get_installation_token(installation_id: int) -> str:
    jwt_token = get_app_jwt()

    # The headers must be extremely clean
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28" # Recommended by GitHub
    }

    res = requests.post(
        f"https://api.github.com/app/installations/{installation_id}/access_tokens",
        headers=headers,
    )
    
    if res.status_code != 201:
        print(f"GitHub API Error: {res.status_code} - {res.text}", flush=True) 
        res.raise_for_status()

    return res.json()["token"]