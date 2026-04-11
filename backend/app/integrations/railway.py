"""
Railway deployment integration.

Uses the Railway GraphQL API v2.
Docs: https://docs.railway.app/reference/public-api
"""

import requests
import re
import logging

logger = logging.getLogger(__name__)

RAILWAY_API = "https://backboard.railway.app/graphql/v2"


# ── Internal GQL helper ───────────────────────────────────────────────────────

def _gql(api_key: str, query: str, variables: dict = None) -> dict:
    """
    Execute a Railway GraphQL query/mutation.

    Raises a descriptive Exception on any failure, including Railway's
    own error messages so the caller can surface them to the user.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
    }
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    resp = requests.post(RAILWAY_API, json=payload, headers=headers, timeout=30)

    # Always parse the body first — Railway returns error detail as JSON
    # even on 4xx, so raise_for_status() alone loses the message.
    try:
        body = resp.json()
    except Exception:
        raise Exception(
            f"Railway API returned non-JSON response "
            f"(HTTP {resp.status_code}): {resp.text[:400]}"
        )

    # HTTP-level error — extract Railway's message before raising
    if not resp.ok:
        errors = body.get("errors") or []
        if errors:
            messages = [e.get("message", str(e)) for e in errors]
            raise Exception(
                f"Railway API error (HTTP {resp.status_code}): "
                f"{'; '.join(messages)}"
            )
        raise Exception(
            f"Railway API HTTP {resp.status_code}: {resp.text[:400]}"
        )

    # HTTP 200 but GraphQL-level errors
    if "errors" in body:
        messages = [e.get("message", str(e)) for e in body["errors"]]
        raise Exception(f"Railway GraphQL error: {'; '.join(messages)}")

    return body.get("data", {})


# ── Name sanitisation ─────────────────────────────────────────────────────────

def sanitize_railway_name(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9\-]", "-", name)
    name = re.sub(r"-{2,}", "-", name)
    return name.strip("-")[:32]


# ── Project ───────────────────────────────────────────────────────────────────

def ensure_railway_project(project_name: str, api_key: str) -> str:
    safe_name = sanitize_railway_name(project_name)

    data = _gql(api_key, """
        query {
            projects {
                edges {
                    node { id  name }
                }
            }
        }
    """)

    for edge in data.get("projects", {}).get("edges", []):
        if edge["node"]["name"] == safe_name:
            logger.info(f"Railway: found existing project '{safe_name}'")
            return edge["node"]["id"]

    data = _gql(api_key, """
        mutation projectCreate($input: ProjectCreateInput!) {
            projectCreate(input: $input) {
                id
                name
            }
        }
    """, {"input": {"name": safe_name}})

    project_id = data["projectCreate"]["id"]
    logger.info(f"Railway: created project '{safe_name}' ({project_id})")
    return project_id


# ── Environment ───────────────────────────────────────────────────────────────

def get_production_environment_id(project_id: str, api_key: str) -> str:
    data = _gql(api_key, """
        query projectEnvironments($id: String!) {
            project(id: $id) {
                environments {
                    edges {
                        node { id  name }
                    }
                }
            }
        }
    """, {"id": project_id})

    edges = data["project"]["environments"]["edges"]
    for edge in edges:
        if edge["node"]["name"].lower() == "production":
            return edge["node"]["id"]

    if edges:
        return edges[0]["node"]["id"]

    raise Exception(f"No environments found for Railway project {project_id}")


# ── Service ───────────────────────────────────────────────────────────────────

def ensure_railway_service(project_id: str, component_name: str, api_key: str) -> str:
    safe_name = sanitize_railway_name(component_name)

    data = _gql(api_key, """
        query projectServices($id: String!) {
            project(id: $id) {
                services {
                    edges {
                        node { id  name }
                    }
                }
            }
        }
    """, {"id": project_id})

    for edge in data["project"]["services"]["edges"]:
        if edge["node"]["name"] == safe_name:
            logger.info(f"Railway: found existing service '{safe_name}'")
            return edge["node"]["id"]

    data = _gql(api_key, """
        mutation serviceCreate($input: ServiceCreateInput!) {
            serviceCreate(input: $input) {
                id
                name
            }
        }
    """, {"input": {"projectId": project_id, "name": safe_name}})

    service_id = data["serviceCreate"]["id"]
    logger.info(f"Railway: created service '{safe_name}' ({service_id})")
    return service_id


# ── GitHub source ─────────────────────────────────────────────────────────────

def connect_service_to_github(
    service_id:     str,
    repo_full_name: str,
    root_dir:       str,
    branch:         str,
    api_key:        str,
) -> None:
    """
    Connect a Railway service to a GitHub repository via serviceUpdate.

    Requires the Railway GitHub App to be installed and granted access
    to the target repository before this will succeed:
      https://github.com/apps/railway
    """
    source: dict = {
        "repo":   repo_full_name,
        "branch": branch or "main",
    }
    if root_dir:
        source["rootDirectory"] = root_dir.lstrip("/")

    # Error message fragments Railway returns when GitHub is not connected
    _GITHUB_HINTS = (
        "could not find",
        "repo not found",
        "repository not found",
        "not found",
        "github",
        "integration",
        "access",
        "permission",
    )

    try:
        _gql(api_key, """
            mutation serviceUpdate($id: String!, $input: ServiceUpdateInput!) {
                serviceUpdate(id: $id, input: $input) {
                    id
                }
            }
        """, {
            "id": service_id,
            "input": {
                "source": {
                    "github": source
                }
            }
        })
    except Exception as e:
        err_lower = str(e).lower()
        if any(hint in err_lower for hint in _GITHUB_HINTS):
            raise Exception(
                f"Railway GitHub Integration missing or repository not accessible.\n"
                f"\n"
                f"  1. Install the Railway GitHub App:\n"
                f"     https://github.com/apps/railway\n"
                f"\n"
                f"  2. Grant it access to the repository: {repo_full_name}\n"
                f"\n"
                f"  3. Re-run `forge deploy` once the app is installed.\n"
                f"\n"
                f"  Original Railway error: {e}"
            )
        raise

    logger.info(f"Railway: connected service {service_id} to {repo_full_name}")



# ── Env vars ──────────────────────────────────────────────────────────────────

def set_service_env_vars(
    project_id:     str,
    environment_id: str,
    service_id:     str,
    env_vars:       dict,
    api_key:        str,
) -> None:
    if not env_vars:
        return

    variables_input = [
        {"name": k, "value": str(v)}
        for k, v in env_vars.items()
    ]

    # variableCollectionUpsert returns Boolean — no selection set.
    _gql(api_key, """
        mutation variableCollectionUpsert($input: VariableCollectionUpsertInput!) {
            variableCollectionUpsert(input: $input)
        }
    """, {
        "input": {
            "projectId":     project_id,
            "environmentId": environment_id,
            "serviceId":     service_id,
            "variables":     variables_input,
        }
    })

    logger.info(f"Railway: set {len(env_vars)} env vars on service {service_id}")


# ── Build config ──────────────────────────────────────────────────────────────

def set_service_build_config(
    service_id:     str,
    environment_id: str,
    start_command:  str | None,
    build_command:  str | None,
    api_key:        str,
) -> None:
    settings: dict = {}
    if start_command:
        settings["startCommand"] = start_command
    if build_command:
        settings["buildCommand"] = build_command

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

    logger.info(f"Railway: updated build config on service {service_id}")


# ── Domain ────────────────────────────────────────────────────────────────────

def ensure_service_domain(
    project_id:     str,
    environment_id: str,
    service_id:     str,
    api_key:        str,
) -> str | None:
    """
    Returns the public domain for a service.
    Creates a Railway-generated domain if none exists yet.
    """
    # serviceInstance domain query — no projectId needed.
    try:
        data = _gql(api_key, """
            query serviceInstanceDomains(
                $environmentId: String!,
                $serviceId:     String!
            ) {
                serviceInstance(
                    environmentId: $environmentId,
                    serviceId:     $serviceId
                ) {
                    domains {
                        serviceDomains { domain }
                        customDomains  { domain }
                    }
                }
            }
        """, {
            "environmentId": environment_id,
            "serviceId":     service_id,
        })

        instance = data.get("serviceInstance") or {}
        domains  = instance.get("domains") or {}

        for d in domains.get("customDomains", []):
            if d.get("domain"):
                return f"https://{d['domain']}"
        for d in domains.get("serviceDomains", []):
            if d.get("domain"):
                return f"https://{d['domain']}"

    except Exception as e:
        logger.warning(f"Railway: could not query existing domains: {e}")

    # serviceDomainCreate takes a single ServiceDomainCreateInput object —
    # not separate positional arguments.
    data = _gql(api_key, """
        mutation serviceDomainCreate($input: ServiceDomainCreateInput!) {
            serviceDomainCreate(input: $input) {
                domain
            }
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
    environment_id: str,
    service_id:     str,
    api_key:        str,
) -> None:
    # serviceInstanceRedeploy returns Boolean — no selection set.
    _gql(api_key, """
        mutation serviceInstanceRedeploy(
            $environmentId: String!,
            $serviceId:     String!
        ) {
            serviceInstanceRedeploy(
                environmentId: $environmentId,
                serviceId:     $serviceId
            )
        }
    """, {
        "environmentId": environment_id,
        "serviceId":     service_id,
    })

    logger.info(f"Railway: triggered deploy for service {service_id}")


# ── High-level entry point (called by orchestrator) ───────────────────────────

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
    """
    Full idempotent deploy sequence for one backend component.

    Steps:
      1. Ensure Railway project exists
      2. Ensure service exists within that project
      3. Connect service to GitHub repo
      4. Set env vars
      5. Set build / start commands
      6. Provision a public domain if none exists
      7. Trigger deploy
      8. Return the public HTTPS URL
    """
    logger.info(
        f"Railway deploy: project='{project_name}' "
        f"component='{component_name}' repo='{repo_full_name}'"
    )

    project_id = ensure_railway_project(project_name, api_key)
    env_id     = get_production_environment_id(project_id, api_key)
    service_id = ensure_railway_service(project_id, component_name, api_key)

    connect_service_to_github(service_id, repo_full_name, root_dir, branch, api_key)
    set_service_env_vars(project_id, env_id, service_id, env_vars, api_key)
    set_service_build_config(service_id, env_id, start_command, build_command, api_key)

    url = ensure_service_domain(project_id, env_id, service_id, api_key)

    trigger_railway_deploy(env_id, service_id, api_key)

    logger.info(f"Railway deploy triggered — {url}")
    return url or ""