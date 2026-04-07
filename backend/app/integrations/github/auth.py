import jwt
import time
import requests
import os
from dotenv import load_dotenv

load_dotenv()

GITHUB_APP_ID = os.getenv("GITHUB_APP_ID")
GITHUB_PRIVATE_KEY = os.getenv("GITHUB_PRIVATE_KEY").replace('\\n', '\n')

def get_app_jwt():
    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + (10 * 60),
        "iss": int(GITHUB_APP_ID),
    }
    token = jwt.encode(payload, GITHUB_PRIVATE_KEY, algorithm="RS256")
    
    # DEBUG LOGS (Remove after fixing)
    print(f"DEBUG: Key starts with: {GITHUB_PRIVATE_KEY[:20]}")
    print(f"DEBUG: Token type: {type(token)}")
    print(f"DEBUG: Token starts with: {str(token)[:15]}")
    
    return token.decode('utf-8') if isinstance(token, bytes) else token


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
        print(f"GitHub API Error: {res.status_code} - {res.text}") 
        res.raise_for_status()

    res.raise_for_status()
    return res.json()["token"]
