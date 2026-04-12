import re
import logging
import requests

logger = logging.getLogger(__name__)

VERCEL_API = "https://api.vercel.com"


def sanitize_vercel_name(name: str) -> str:
    name = name.lower()
    name = name.replace(" ", "-").replace("_", "-")
    name = re.sub(r"[^a-z0-9.\-]", "", name)
    name = re.sub(r"-{2,}", "-", name)
    return name.strip("-")


# ── Project ───────────────────────────────────────────────────────────────────

def ensure_vercel_project(project_name: str, repo_full_name: str, token: str) -> None:
    """
    Creates the Vercel project if it doesn't already exist.
    Safe to call on every deploy — 409 is silently ignored.
    """
    safe_name = sanitize_vercel_name(project_name)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }

    response = requests.post(
        f"{VERCEL_API}/v9/projects",
        headers=headers,
        json={
            "name": safe_name,
            "gitRepository": {"type": "github", "repo": repo_full_name},
        },
    )

    if response.status_code == 409:
        return

    if not response.ok:
        try:
            err = response.json().get("error", {})
            if "install the GitHub integration first" in err.get("message", ""):
                raise Exception(
                    f"GITHUB_INTEGRATION_MISSING: vercel | {repo_full_name}"
                )
        except Exception as e:
            if "GITHUB_INTEGRATION_MISSING" in str(e):
                raise
        raise Exception(f"Vercel project creation failed: {response.text}")


# ── Env vars (project-level) ──────────────────────────────────────────────────

def upsert_vercel_env_vars(project_name: str, env_vars: dict, token: str) -> None:
    """
    Upsert environment variables at the Vercel project level for production.

    Must be called BEFORE triggering the deployment so the build process
    picks them up. Passing env vars only in the deployment payload is
    unreliable — they are single-deployment overrides, not project settings.

    Uses PATCH to update existing keys and POST to create new ones,
    avoiding duplicate key errors.
    """
    if not env_vars:
        return

    safe_name = sanitize_vercel_name(project_name)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }

    existing: dict[str, str] = {}
    resp = requests.get(
        f"{VERCEL_API}/v9/projects/{safe_name}/env",
        headers=headers,
    )
    if resp.ok:
        for env in resp.json().get("envs", []):
            # Only track production-targeted vars
            if "production" in env.get("target", []):
                existing[env["key"]] = env["id"]

    for key, value in env_vars.items():
        if key in existing:
            r = requests.patch(
                f"{VERCEL_API}/v9/projects/{safe_name}/env/{existing[key]}",
                headers=headers,
                json={
                    "value":  str(value),
                    "type":   "plain",
                    "target": ["production"],
                },
            )
        else:
            r = requests.post(
                f"{VERCEL_API}/v10/projects/{safe_name}/env",
                headers=headers,
                json={
                    "key":    key,
                    "value":  str(value),
                    "type":   "plain",
                    "target": ["production"],
                },
            )

        if not r.ok:
            logger.warning(
                f"Vercel: failed to set env var '{key}' "
                f"({r.status_code}): {r.text[:200]}"
            )
        else:
            logger.info(f"Vercel: upserted env var '{key}'")


# ── Stable domain ─────────────────────────────────────────────────────────────

def get_vercel_project_domain(project_name: str, token: str) -> str | None:
    safe_name = sanitize_vercel_name(project_name)
    headers = {"Authorization": f"Bearer {token}"}

    resp = requests.get(
        f"{VERCEL_API}/v9/projects/{safe_name}",
        headers=headers,
    )
    if not resp.ok:
        logger.warning(f"Vercel: could not fetch project domain ({resp.status_code})")
        return f"https://{safe_name}.vercel.app" # Fallback to default

    data = resp.json()
    
    targets = data.get("targets", {}).get("production", {})
    aliases = targets.get("alias", [])
    
    if not aliases:
        aliases = data.get("alias", [])

    if not aliases:
        return f"https://{safe_name}.vercel.app"

    domains = []
    for a in aliases:
        if isinstance(a, str):
            domains.append(a)
        elif isinstance(a, dict) and a.get("domain"):
            domains.append(a["domain"])

    if not domains:
        return f"https://{safe_name}.vercel.app"

    stable = min(domains, key=len)
    return f"https://{stable}"



def trigger_vercel_deploy(
    project_name:    str,
    repo_url:        str,
    env_vars:        dict,
    token:           str,
    root_dir:        str = None,
    build_command:   str = None,
    install_command: str = None,
) -> dict:
    """
    Set project-level env vars then trigger a production deployment.
    Returns a dict containing the stable project domain under 'url'.
    """
    safe_name = sanitize_vercel_name(project_name)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }

    upsert_vercel_env_vars(project_name, env_vars, token)

    proj_resp = requests.get(
        f"{VERCEL_API}/v9/projects/{safe_name}",
        headers=headers,
    )
    if not proj_resp.ok:
        raise Exception(
            f"Failed to fetch Vercel project to get repoId: {proj_resp.text}"
        )

    repo_id = proj_resp.json().get("link", {}).get("repoId")

    if not repo_id:
        repo_parts = repo_url.replace("https://github.com/", "").split("/")[-2:]
        if len(repo_parts) == 2:
            owner = repo_parts[0]
            repo  = repo_parts[1].replace(".git", "")
            gh    = requests.get(f"https://api.github.com/repos/{owner}/{repo}")
            if gh.ok:
                repo_id = gh.json().get("id")

    if not repo_id:
        raise Exception(
            "Vercel could not determine the GitHub repoId. "
            "Ensure the Vercel GitHub Integration is installed."
        )

    payload: dict = {
        "name":    safe_name,
        "project": safe_name,
        "target":  "production",
        "gitSource": {
            "type":   "github",
            "repoId": repo_id,
            "ref":    "main",
        },
        "projectSettings": {},
    }

    if root_dir:
        payload["projectSettings"]["rootDirectory"] = root_dir
    if build_command:
        payload["projectSettings"]["buildCommand"] = build_command
    if install_command:
        payload["projectSettings"]["installCommand"] = install_command

    if not payload["projectSettings"]:
        del payload["projectSettings"]

    response = requests.post(
        f"{VERCEL_API}/v13/deployments",
        headers=headers,
        json=payload,
    )

    if not response.ok:
        try:
            err = response.json().get("error", {})
            if "install the GitHub integration first" in err.get("message", ""):
                raise Exception(
                    f"GITHUB_INTEGRATION_MISSING: vercel | {repo_url}"
                )
        except Exception as e:
            if "GITHUB_INTEGRATION_MISSING" in str(e):
                raise
        raise Exception(
            f"Vercel deploy failed ({response.status_code}): {response.text}"
        )

    stable_url = get_vercel_project_domain(project_name, token)

    res_json = response.json()
    if stable_url:
        res_json["url"] = stable_url
        logger.info(f"Vercel: deployment triggered, stable URL = {stable_url}")
    else:
        deploy_url = res_json.get("url") or ""
        if deploy_url and not deploy_url.startswith("https://"):
            deploy_url = f"https://{deploy_url}"
        res_json["url"] = deploy_url
        logger.info(f"Vercel: deployment triggered, fallback URL = {deploy_url}")

    return res_json