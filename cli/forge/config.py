import json
from pathlib import Path

CONFIG_PATH = Path(".forge/config.json")

def load_config():
    if not CONFIG_PATH.exists():
        raise RuntimeError("Not a forge project. Run `forge init` first.")
    return json.loads(CONFIG_PATH.read_text())

def save_config(data: dict):
    CONFIG_PATH.parent.mkdir(exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(data, indent=2))

def get_auth_headers():
    cfg = load_config()
    token = cfg.get("session_token")
    if not token:
        raise RuntimeError("Not logged in. Run `forge login`.")
    return {"Authorization": f"Bearer {token}"}