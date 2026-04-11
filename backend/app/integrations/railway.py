"""
Railway deployment integration.

Uses the Railway GraphQL API v2.
Docs: https://docs.railway.app/reference/public-api

All mutations are idempotent-safe:
  - Projects are looked up by name before creation.
  - Services are looked up by name within a project before creation.
  - Domains are provisioned only if not already present.
"""

import requests
import re
import time

RAILWAY_API = "https://backboard.railway.app/graphql/v2"


# ── Internal GQL helper ───────────────────────────────────────────────────────

def _gql(api_key: str, query: str, variables: dict = None) -> dict:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
    }
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    resp = requests.post(RAILWAY_API, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()

    body = resp.json()
    if "errors" in body:
        messages = [e.get("message", str(e)) for e in body["errors"]]
        raise Exception(f"Railway API error: {'; '.join(messages)}")

    return body.get("data", {})


# ── Name sanitisation ─────────────────────────────────────────────────────────

def sanitize_railway_name(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9\-]", "-", name)
    name = re.sub(r"-{2,}", "-", name)
    return name.strip("-")[:32]


# ── Account lookup ────────────────────────────────────────────────────────────

def get_default_team_id(api_key: str) -> str | None:
    """
    Returns the personal workspace team ID, or None if the account
    uses a personal project context (no team required for personal accounts).
    """
    data = _gql(api_key, """
        query {
            teams {
                edges {
                    node { id  name }
                }
            }
        }
    """)
    edges = data.get("teams", {}).get("edges", [])
    if edges:
        return edges[0]["node"]["id"]
    return None


# ── Project ───────────────────────────────────────────────────────────────────

def ensure_railway_project(project_name: str, api_key: str) -> str:
    """
    Returns the Railway project ID, creating it if it does not exist.
    Projects are identified by name — safe to call on every deploy.
    """
    safe_name = sanitize_railway_name(project_name)

    # 1. Check if a project with this name already exists
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
            return edge["node"]["id"]

    # 2. Create it
    data = _gql(api_key, """
        mutation projectCreate($input: ProjectCreateInput!) {
            projectCreate(input: $input) {
                id
                name
            }
        }
    """, {"input": {"name": safe_name}})

    return data["projectCreate"]["id"]


# ── Environment ───────────────────────────────────────────────────────────────

def get_production_environment_id(project_id: str, api_key: str) -> str:
    """Returns the ID of the 'production' environment for a project."""
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

    for edge in data["project"]["environments"]["edges"]:
        node = edge["node"]
        if node["name"].lower() == "production":
            return node["id"]

    # Fallback: return the first environment
    edges = data["project"]["environments"]["edges"]
    if edges:
        return edges[0]["node"]["id"]

    raise Exception(f"No environments found for Railway project {project_id}")


# ── Service ───────────────────────────────────────────────────────────────────

def ensure_railway_service(
    project_id:      str,
    component_name:  str,
    api_key:         str,
) -> str:
    """
    Returns the Railway service ID for a component, creating it if needed.
    """
    safe_name = sanitize_railway_name(component_name)

    # 1. Check if service already exists in this project
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
            return edge["node"]["id"]

    # 2. Create the service (no source yet — source is set via GitHub connect)
    data = _gql(api_key, """
        mutation serviceCreate($input: ServiceCreateInput!) {
            serviceCreate(input: $input) {
                id
                name
            }
        }
    """, {"input": {"projectId": project_id, "name": safe_name}})

    return data["serviceCreate"]["id"]


# ── GitHub source ─────────────────────────────────────────────────────────────

def connect_service_to_github(
    service_id:     str,
    repo_full_name: str,   # "owner/repo"
    root_dir:       str,
    branch:         str,
    api_key:        str,
) -> None:
    """
    Connect a Railway service to a GitHub repository.
    Safe to call repeatedly — Railway handles the idempotency.
    """
    source_input = {
        "repo":   repo_full_name,
        "branch": branch or "main",
    }
    if root_dir:
        source_input["rootDirectory"] = root_dir.lstrip("/")

    _gql(api_key, """
        mutation serviceConnect($id: String!, $input: ServiceConnectInput!) {
            serviceConnect(id: $id, input: $input) {
                id
            }
        }
    """, {"id": service_id, "input": {"source": {"github": source_input}}})


# ── Env vars ──────────────────────────────────────────────────────────────────

def set_service_env_vars(
    project_id:     str,
    environment_id: str,
    service_id:     str,
    env_vars:       dict,
    api_key:        str,
) -> None:
    """Upserts env vars for a service in a given environment."""
    if not env_vars:
        return

    variables_input = [
        {"name": k, "value": str(v)}
        for k, v in env_vars.items()
    ]

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


# ── Build config ──────────────────────────────────────────────────────────────

def set_service_build_config(
    service_id:      str,
    environment_id:  str,
    start_command:   str | None,
    build_command:   str | None,
    api_key:         str,
) -> None:
    """Sets the build and start commands on a service instance."""
    settings = {}
    if start_command:
        settings["startCommand"] = start_command
    if build_command:
        settings["buildCommand"] = build_command

    if not settings:
        return

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
    # 1. Check for existing domains
    data = _gql(api_key, """
        query serviceInstanceDomains(
            $projectId:     String!,
            $environmentId: String!,
            $serviceId:     String!
        ) {
            serviceInstance(
                projectId:     $projectId,
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
        "projectId":     project_id,
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

    # 2. Create a Railway-generated domain
    data = _gql(api_key, """
        mutation serviceInstanceDomainCreate(
            $environmentId: String!,
            $serviceId:     String!
        ) {
            serviceDomainCreate(
                environmentId: $environmentId,
                serviceId:     $serviceId
            ) {
                domain
            }
        }
    """, {
        "environmentId": environment_id,
        "serviceId":     service_id,
    })

    domain = data.get("serviceDomainCreate", {}).get("domain")
    return f"https://{domain}" if domain else None


# ── Deploy ────────────────────────────────────────────────────────────────────

def trigger_railway_deploy(
    environment_id: str,
    service_id:     str,
    api_key:        str,
) -> None:
    """Triggers a redeployment of the latest source for a service."""
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
    Full deploy sequence for one backend component:
      1. Ensure project exists
      2. Ensure service exists
      3. Connect to GitHub
      4. Set env vars
      5. Set build/start commands
      6. Ensure public domain exists
      7. Trigger deploy
      8. Return the service URL

    Returns the public HTTPS URL of the deployed service.
    """
    project_id = ensure_railway_project(project_name, api_key)
    env_id     = get_production_environment_id(project_id, api_key)
    service_id = ensure_railway_service(project_id, component_name, api_key)

    connect_service_to_github(service_id, repo_full_name, root_dir, branch, api_key)
    set_service_env_vars(project_id, env_id, service_id, env_vars, api_key)
    set_service_build_config(service_id, env_id, start_command, build_command, api_key)

    url = ensure_service_domain(project_id, env_id, service_id, api_key)

    trigger_railway_deploy(env_id, service_id, api_key)

    return url