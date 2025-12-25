import requests

def create_check_run(token, repo, sha):
    res = requests.post(
        f"https://api.github.com/repos/{repo}/check-runs",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        json={
            "name": "forge / build",
            "head_sha": sha,
            "status": "in_progress",
        },
    )
    res.raise_for_status()
    return res.json()["id"]

def complete_check_run(token, repo, check_run_id, conclusion, output=None):
    res = requests.patch(
        f"https://api.github.com/repos/{repo}/check-runs/{check_run_id}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        json={
            "status": "completed",
            "conclusion": conclusion,
            "output": output or {
                "title": "forge CI",
                "summary": f"Build {conclusion}",
            },
        },
    )
    res.raise_for_status()
