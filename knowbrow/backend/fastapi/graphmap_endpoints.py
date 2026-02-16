"""
GraphMap API endpoints for FastAPI.

Proxies GraphMapConfig CRUD, sharing, and versioning to Django's DRF endpoints.
Also provides anonymous share-token resolution and public config access.

Wired in via: config_endpoints.py → add_config_endpoints() → add_graphmap_endpoints(app)
"""

from fastapi import FastAPI, Query, HTTPException, Header, Body
from typing import Optional, Dict, Any, List
import httpx
import os
from datetime import datetime, timezone


DJANGO_API_URL = os.getenv("DJANGO_API_URL", "http://django:8000")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")
DJANGO_USER = os.getenv("DJANGO_USER", "")
DJANGO_PASSWORD = os.getenv("DJANGO_PASSWORD", "")


def _auth_tuple():
    return (DJANGO_USER, DJANGO_PASSWORD)


def _extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1].strip():
        return parts[1].strip()
    return None


async def _validate_and_get_user(client: httpx.AsyncClient, token: str) -> Dict[str, Any]:
    """Validate JWT via Django internal endpoint, return user payload."""
    response = await client.post(
        f"{DJANGO_API_URL}/api/internal/auth/validate/",
        json={"token": token},
        headers={"X-Internal-API-Key": INTERNAL_API_KEY},
    )
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    payload = response.json()
    return payload.get("data", payload)


async def _proxy_to_django(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    token: Optional[str] = None,
    json_body: Optional[Dict] = None,
    params: Optional[Dict] = None,
) -> httpx.Response:
    """
    Proxy a request to Django DRF, authenticating as the internal service user
    and forwarding the real user's identity via X-User-ID.
    """
    headers = {"X-Internal-API-Key": INTERNAL_API_KEY}

    # If we have a user token, validate it and pass user context
    if token:
        user_payload = await _validate_and_get_user(client, token)
        headers["X-User-ID"] = str(user_payload.get("user_id"))
        # DRF endpoints require session/basic auth; we use basic auth for the
        # service account and pass the real user via header.
        headers["Authorization"] = f"Bearer {token}"

    url = f"{DJANGO_API_URL}{path}"
    kwargs = {
        "headers": headers,
        "auth": _auth_tuple(),
    }
    if json_body is not None:
        kwargs["json"] = json_body
    if params is not None:
        kwargs["params"] = params

    if method == "GET":
        return await client.get(url, **kwargs)
    elif method == "POST":
        return await client.post(url, **kwargs)
    elif method == "PUT":
        return await client.put(url, **kwargs)
    elif method == "PATCH":
        return await client.patch(url, **kwargs)
    elif method == "DELETE":
        return await client.delete(url, **kwargs)
    else:
        raise ValueError(f"Unsupported method: {method}")


def _forward_response(response: httpx.Response):
    """Convert Django response to FastAPI-friendly dict, raising on errors."""
    if response.status_code == 204:
        return {"success": True}
    try:
        data = response.json()
    except Exception:
        data = {"detail": response.text}
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=data)
    return data


def add_graphmap_endpoints(app: FastAPI):
    """Register GraphMap CRUD + sharing endpoints on the FastAPI app."""

    # ------------------------------------------------------------------
    # List / Create graph map configs
    # ------------------------------------------------------------------

    @app.get("/api/graphmaps")
    async def list_graphmaps(
        authorization: Optional[str] = Header(None),
    ):
        """
        List graph map configs accessible to the authenticated user.
        Returns own + shared + public configs.
        """
        token = _extract_bearer_token(authorization)
        if not token:
            raise HTTPException(status_code=401, detail="Authentication required")
        async with httpx.AsyncClient() as client:
            resp = await _proxy_to_django(client, "GET", "/api/graph-configs/", token=token)
            return _forward_response(resp)

    @app.post("/api/graphmaps")
    async def create_graphmap(
        body: Dict[str, Any] = Body(...),
        authorization: Optional[str] = Header(None),
    ):
        """
        Create a new graph map config.
        Body: { title, description?, config_data, graph_name?, fuseki_graph_name?, is_public? }
        Note: `graph_name` is canonical; `fuseki_graph_name` is a legacy alias.
        """
        token = _extract_bearer_token(authorization)
        if not token:
            raise HTTPException(status_code=401, detail="Authentication required")
        async with httpx.AsyncClient() as client:
            resp = await _proxy_to_django(
                client, "POST", "/api/graph-configs/", token=token, json_body=body
            )
            return _forward_response(resp)

    # ------------------------------------------------------------------
    # Single config: retrieve / update / delete
    # ------------------------------------------------------------------

    @app.get("/api/graphmaps/{config_id}")
    async def get_graphmap(
        config_id: int,
        authorization: Optional[str] = Header(None),
    ):
        """
        Get a single graph map config by ID.
        Public configs are accessible without auth.
        """
        token = _extract_bearer_token(authorization)
        async with httpx.AsyncClient() as client:
            resp = await _proxy_to_django(
                client, "GET", f"/api/graph-configs/{config_id}/", token=token
            )
            return _forward_response(resp)

    @app.put("/api/graphmaps/{config_id}")
    async def update_graphmap(
        config_id: int,
        body: Dict[str, Any] = Body(...),
        authorization: Optional[str] = Header(None),
    ):
        """Full update of a graph map config."""
        token = _extract_bearer_token(authorization)
        if not token:
            raise HTTPException(status_code=401, detail="Authentication required")
        async with httpx.AsyncClient() as client:
            resp = await _proxy_to_django(
                client, "PUT", f"/api/graph-configs/{config_id}/", token=token, json_body=body
            )
            return _forward_response(resp)

    @app.patch("/api/graphmaps/{config_id}")
    async def patch_graphmap(
        config_id: int,
        body: Dict[str, Any] = Body(...),
        authorization: Optional[str] = Header(None),
    ):
        """Partial update of a graph map config (e.g. just config_data or title)."""
        token = _extract_bearer_token(authorization)
        if not token:
            raise HTTPException(status_code=401, detail="Authentication required")
        async with httpx.AsyncClient() as client:
            resp = await _proxy_to_django(
                client, "PATCH", f"/api/graph-configs/{config_id}/", token=token, json_body=body
            )
            return _forward_response(resp)

    @app.delete("/api/graphmaps/{config_id}")
    async def delete_graphmap(
        config_id: int,
        authorization: Optional[str] = Header(None),
    ):
        """Delete a graph map config (owner or admin only)."""
        token = _extract_bearer_token(authorization)
        if not token:
            raise HTTPException(status_code=401, detail="Authentication required")
        async with httpx.AsyncClient() as client:
            resp = await _proxy_to_django(
                client, "DELETE", f"/api/graph-configs/{config_id}/", token=token
            )
            return _forward_response(resp)

    # ------------------------------------------------------------------
    # Versioning
    # ------------------------------------------------------------------

    @app.post("/api/graphmaps/{config_id}/versions")
    async def create_version(
        config_id: int,
        body: Dict[str, Any] = Body(default={}),
        authorization: Optional[str] = Header(None),
    ):
        """
        Snapshot the current config_data as a new version.
        Body: { description?: string }
        """
        token = _extract_bearer_token(authorization)
        if not token:
            raise HTTPException(status_code=401, detail="Authentication required")
        async with httpx.AsyncClient() as client:
            resp = await _proxy_to_django(
                client,
                "POST",
                f"/api/graph-configs/{config_id}/create_version/",
                token=token,
                json_body=body,
            )
            return _forward_response(resp)

    @app.get("/api/graphmaps/{config_id}/versions")
    async def list_versions(
        config_id: int,
        authorization: Optional[str] = Header(None),
    ):
        """List version history for a graph map config."""
        token = _extract_bearer_token(authorization)
        async with httpx.AsyncClient() as client:
            resp = await _proxy_to_django(
                client,
                "GET",
                "/api/graph-config-versions/",
                token=token,
                params={"graph_config": config_id},
            )
            return _forward_response(resp)

    # ------------------------------------------------------------------
    # Sharing
    # ------------------------------------------------------------------

    @app.post("/api/graphmaps/{config_id}/share")
    async def share_graphmap(
        config_id: int,
        body: Dict[str, Any] = Body(default={}),
        authorization: Optional[str] = Header(None),
    ):
        """
        Create a share link for a graph map config.
        Body: { permission?: 'view'|'edit', expires_at?: ISO datetime }
        """
        token = _extract_bearer_token(authorization)
        if not token:
            raise HTTPException(status_code=401, detail="Authentication required")
        async with httpx.AsyncClient() as client:
            resp = await _proxy_to_django(
                client,
                "POST",
                f"/api/graph-configs/{config_id}/share/",
                token=token,
                json_body=body,
            )
            return _forward_response(resp)

    @app.get("/api/graphmaps/{config_id}/permissions")
    async def get_graphmap_permissions(
        config_id: int,
        authorization: Optional[str] = Header(None),
    ):
        """List permissions for a graph map config."""
        token = _extract_bearer_token(authorization)
        if not token:
            raise HTTPException(status_code=401, detail="Authentication required")
        async with httpx.AsyncClient() as client:
            resp = await _proxy_to_django(
                client,
                "GET",
                f"/api/graph-configs/{config_id}/permissions/",
                token=token,
            )
            return _forward_response(resp)

    # ------------------------------------------------------------------
    # Share-token resolution (anonymous access)
    # ------------------------------------------------------------------

    @app.get("/api/graphmaps/shared/{share_token}")
    async def resolve_share_token(share_token: str):
        """
        Resolve a share token to a graph map config.
        No authentication required — the token itself is the credential.
        Returns the config if the share is valid and not expired.
        """
        async with httpx.AsyncClient() as client:
            # Query Django's share endpoint to find the config
            resp = await client.get(
                f"{DJANGO_API_URL}/api/graph-config-shares/",
                auth=_auth_tuple(),
                params={"share_token": share_token},
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=404, detail="Share not found")

            data = resp.json()
            results = data.get("results", data) if isinstance(data, dict) else data
            if isinstance(results, list):
                # Find matching share
                share = next(
                    (s for s in results if s.get("share_token") == share_token),
                    None,
                )
            else:
                share = results if results.get("share_token") == share_token else None

            if not share:
                raise HTTPException(status_code=404, detail="Share token not found or expired")

            expires_at = share.get("expires_at")
            if expires_at:
                try:
                    expiry = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
                    if expiry <= datetime.now(timezone.utc):
                        raise HTTPException(status_code=410, detail="Share token expired")
                except ValueError:
                    # Ignore malformed expiry values and let Django-side ACLs handle access.
                    pass

            # Fetch the actual config
            config_data = share.get("graph_config")
            if isinstance(config_data, int):
                # Only got the ID, fetch full config
                config_resp = await client.get(
                    f"{DJANGO_API_URL}/api/graph-configs/{config_data}/",
                    auth=_auth_tuple(),
                )
                if config_resp.status_code != 200:
                    raise HTTPException(status_code=404, detail="Config not found")
                config_data = config_resp.json()

            return {
                "share": {
                    "token": share.get("share_token"),
                    "permission": share.get("permission", "view"),
                    "expires_at": share.get("expires_at"),
                },
                "config": config_data,
            }
