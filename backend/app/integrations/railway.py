"""
Railway deployment integration — GraphQL API v2.
https://docs.railway.app/reference/public-api
"""

import requests
import re
import logging

logger = logging.getLogger(__name__)

RAILWAY_API = "https://backboard.railway.app/graphql/v2"


# ── GQL helper ────────────────────────────────────────────────────────────────

def _gql(api_key: str, query: str, variables: dict = None) -> dict:
    """Execute a Railway GraphQL request."""
    resp = requests.post(
        RAILWAY_API,
        json={"query": query, **({"variables": variables} if variables else {})},
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/json",
        },
        timeout=30,
    )

    try:
        body = resp.json()
    except Exception:
        raise Exception(
            f"Railway returned non-JSON (HTTP {resp.status_code}): {resp.text[:300]}"
        )

    if not resp.ok:
        msgs = [e.get("message", str(e)) for e in (body.get("errors") or [])]
        raise Exception(
            f"Railway API error (HTTP {resp.status_code}): "
            + ("; ".join(msgs) if msgs else resp.text[:300])
        )

    if "errors" in body:
        msgs = [e.get("message", str(e)) for e in body["errors"]]
        raise Exception(f"Railway GraphQL error: {'; '.join(msgs)}")

    return body.get("data", {})


# ── Helpers ───────────────────────────────────────────────────────────────────

def sanitize_railway_name(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9\-]", "-", name)
    name = re.sub(r"-{2,}", "-", name)
    return name.strip("-")[:32]


# ── Project ───────────────────────────────────────────────────────────────────

def ensure_railway_project(project_name: str, api_key: str) -> str:
    safe_name = sanitize_railway_name(project_name)

    data = _gql(api_key, "query { projects { edges { node { id name } } } }")
    for edge in data.get("projects", {}).get("edges", []):
        if edge["node"]["name"] == safe_name:
            logger.info(f"Railway: existing project '{safe_name}'")
            return edge["node"]["id"]

    data = _gql(api_key, """
        mutation projectCreate($input: ProjectCreateInput!) {
            projectCreate(input: $input) { id name }
        }
    """, {"input": {"name": safe_name}})

    pid = data["projectCreate"]["id"]
    logger.info(f"Railway: created project '{safe_name}' → {pid}")
    return pid


# ── Environment ───────────────────────────────────────────────────────────────

def get_production_environment_id(project_id: str, api_key: str) -> str:
    data = _gql(api_key, """
        query($id: String!) {
            project(id: $id) {
                environments { edges { node { id name } } }
            }
        }
    """, {"id": project_id})

    edges = data["project"]["environments"]["edges"]
    for e in edges:
        if e["node"]["name"].lower() == "production":
            return e["node"]["id"]
    if edges:
        return edges[0]["node"]["id"]
    raise Exception(f"No environments found for Railway project {project_id}")


# ── Service ───────────────────────────────────────────────────────────────────

def ensure_railway_service(
    project_id:     str,
    component_name: str,
    repo_full_name: str,
    api_key:        str,
) -> str:
    """
    Return the service ID, creating it with a GitHub source if it doesn't exist.

    ServiceSourceInput is flat: { repo: "owner/repo" }
    rootDirectory and branch are set later via serviceInstanceUpdate.

    Any failure on serviceCreate when a repo source is provided is almost
    certainly a GitHub App access issue — Railway returns the generic
    "Problem processing request" (HTTP 400) for both schema errors and
    missing GitHub integration, so we always surface the actionable message.
    """
    safe_name = sanitize_railway_name(component_name)

    data = _gql(api_key, """
        query($id: String!) {
            project(id: $id) {
                services { edges { node { id name } } }
            }
        }
    """, {"id": project_id})

    for e in data["project"]["services"]["edges"]:
        if e["node"]["name"] == safe_name:
            logger.info(f"Railway: existing service '{safe_name}'")
            return e["node"]["id"]

    try:
        data = _gql(api_key, """
            mutation serviceCreate($input: ServiceCreateInput!) {
                serviceCreate(input: $input) { id name }
            }
        """, {
            "input": {
                "projectId": project_id,
                "name":      safe_name,
                "source": {
                    "repo": repo_full_name,
                },
            }
        })
    except Exception as e:
        # Railway returns the generic "Problem processing request" (HTTP 400)
        # for BOTH schema errors and missing GitHub App access. Since the
        # schema is correct, a 400 on serviceCreate with source.repo always
        # means the GitHub App is not installed or lacks repo permissions.
        raise Exception(
            f"GITHUB_INTEGRATION_MISSING: railway | {repo_full_name}"
        ) from e

    sid = data["serviceCreate"]["id"]
    logger.info(f"Railway: created service '{safe_name}' → {sid}")
    return sid


# ── Env vars ──────────────────────────────────────────────────────────────────

def set_service_env_vars(
    project_id: str, environment_id: str, service_id: str,
    env_vars: dict, api_key: str,
) -> None:
    if not env_vars:
        return

    # VariableCollectionUpsertInput.variables is ServiceVariablesInput,
    # which is a JSON scalar (plain dict of {key: value}) — not an array.
    _gql(api_key, """
        mutation variableCollectionUpsert($input: VariableCollectionUpsertInput!) {
            variableCollectionUpsert(input: $input)
        }
    """, {
        "input": {
            "projectId":     project_id,
            "environmentId": environment_id,
            "serviceId":     service_id,
            "variables":     {k: str(v) for k, v in env_vars.items()},
        }
    })
    logger.info(f"Railway: set {len(env_vars)} env vars on {service_id}")


# ── Build / start config ──────────────────────────────────────────────────────

def set_service_build_config(
    service_id: str, environment_id: str,
    start_command: str | None, build_command: str | None,
    root_dir: str | None, branch: str | None,
    api_key: str,
) -> None:
    settings: dict = {}
    if start_command:
        settings["startCommand"]  = start_command
    if build_command:
        settings["buildCommand"]  = build_command
    if root_dir:
        settings["rootDirectory"] = root_dir.lstrip("/")
    if branch:
        settings["sourceBranch"]  = branch

    if not settings:
        return

    # serviceInstanceUpdate returns Boolean — no selection set.
    _gql(api_key, """
        mutation serviceInstanceUpdate(
            $serviceId:     String!,
            $environmentId: String!,
            $input:         ServiceInstanceUpdateInput!
        ) {
            serviceInstanceUpdate(
                serviceId:     $serviceId,
                environmentId: $environmentId,
                input:         $input
            )
        }
    """, {
        "serviceId":     service_id,
        "environmentId": environment_id,
        "input":         settings,
    })
    logger.info(f"Railway: build config set on {service_id} → {list(settings.keys())}")


# ── Domain ────────────────────────────────────────────────────────────────────

def ensure_service_domain(
    project_id: str, environment_id: str, service_id: str, api_key: str,
) -> str | None:
    try:
        data = _gql(api_key, """
            query($environmentId: String!, $serviceId: String!) {
                serviceInstance(environmentId: $environmentId, serviceId: $serviceId) {
                    domains {
                        serviceDomains { domain }
                        customDomains  { domain }
                    }
                }
            }
        """, {"environmentId": environment_id, "serviceId": service_id})

        inst    = data.get("serviceInstance") or {}
        domains = inst.get("domains") or {}
        for d in domains.get("customDomains", []):
            if d.get("domain"):
                return f"https://{d['domain']}"
        for d in domains.get("serviceDomains", []):
            if d.get("domain"):
                return f"https://{d['domain']}"
    except Exception as e:
        logger.warning(f"Railway: domain query failed (non-fatal): {e}")

    # serviceDomainCreate returns Boolean — no selection set.
    data = _gql(api_key, """
        mutation serviceDomainCreate($input: ServiceDomainCreateInput!) {
            serviceDomainCreate(input: $input) { domain }
        }
    """, {
        "input": {
            "environmentId": environment_id,
            "serviceId":     service_id,
        }
    })

    domain = (data.get("serviceDomainCreate") or {}).get("domain")
    if domain:
        logger.info(f"Railway: provisioned domain {domain}")
        return f"https://{domain}"
    return None


# ── Deploy trigger ────────────────────────────────────────────────────────────

def trigger_railway_deploy(
    environment_id: str, service_id: str,
    api_key: str, repo_full_name: str,
) -> None:
    try:
        # serviceInstanceRedeploy returns Boolean — no selection set.
        _gql(api_key, """
            mutation serviceInstanceRedeploy(
                $environmentId: String!, $serviceId: String!
            ) {
                serviceInstanceRedeploy(
                    environmentId: $environmentId, serviceId: $serviceId
                )
            }
        """, {"environmentId": environment_id, "serviceId": service_id})
    except Exception as e:
        # Surface GitHub access issues at the deploy-trigger stage too
        raise Exception(
            f"GITHUB_INTEGRATION_MISSING: railway | {repo_full_name}"
        ) from e
    logger.info(f"Railway: deploy triggered for {service_id}")


# ── Entry point ───────────────────────────────────────────────────────────────

def deploy_to_railway(
    project_name:   str,
    component_name: str,
    repo_full_name: str,
    root_dir:       str,
    branch:         str,
    start_command:  str | None,
    build_command:  str | None,
    env_vars:       dict,
    api_key:        str,
) -> str:
    logger.info(
        f"Railway deploy — project='{project_name}' "
        f"component='{component_name}' repo='{repo_full_name}'"
    )

    project_id = ensure_railway_project(project_name, api_key)
    env_id     = get_production_environment_id(project_id, api_key)
    service_id = ensure_railway_service(
        project_id, component_name, repo_full_name, api_key
    )

    set_service_env_vars(project_id, env_id, service_id, env_vars, api_key)
    set_service_build_config(
        service_id, env_id,
        start_command, build_command,
        root_dir, branch,
        api_key,
    )

    url = ensure_service_domain(project_id, env_id, service_id, api_key)
    trigger_railway_deploy(env_id, service_id, api_key, repo_full_name)

    logger.info(f"Railway deploy triggered — {url}")
    return url or ""