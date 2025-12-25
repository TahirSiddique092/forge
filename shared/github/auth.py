import time
import requests
from dotenv import load_dotenv
import os
import jwt

load_dotenv()

GITHUB_APP_ID = os.getenv("GITHUB_APP_ID")
GITHUB_PRIVATE_KEY = os.getenv("GITHUB_PRIVATE_KEY")

def get_app_jwt():
    if not GITHUB_APP_ID:
        raise Exception("GITHUB_APP_ID not set")

    if not GITHUB_PRIVATE_KEY:
        raise Exception("GITHUB_PRIVATE_KEY not set")

    payload = {
        "iat": int(time.time()) - 60,
        "exp": int(time.time()) + 9 * 60,
        "iss": GITHUB_APP_ID,
    }

    token = jwt.encode(
        payload,
        GITHUB_PRIVATE_KEY,
        algorithm="RS256"
    )

    return token


def get_installation_token(installation_id: int):
    jwt_token = get_app_jwt()

    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github+json",
    }

    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"

    res = requests.post(url, headers=headers)
    res.raise_for_status()

    return res.json()["token"]