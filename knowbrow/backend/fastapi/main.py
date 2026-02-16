from fastapi import FastAPI, Query, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
import uvicorn
import httpx
from SPARQLWrapper import SPARQLWrapper, JSON
from datetime import datetime
import os
import re
from pathlib import Path
from urllib.parse import urlparse, urlencode
from pydantic import BaseModel

# Import adapter system
from adapters import (
    DataSourceAdapter, 
    QuickSearchResult, 
    MapNodeResult, 
    Relationship,
    MapNodeResponse
)
from adapters.wikidata import WikidataAdapter
from multi_source import QueryRequest
from config_endpoints import add_config_endpoints, adapter_registry
from ols_endpoints import router as ols_router
from reconciliation_endpoints import router as reconciliation_router
from aggregation_endpoints import router as aggregation_router

app = FastAPI()
PLUGIN_CONTRACT_VERSION = "2026-02-16"

_raw_allowed_origins = os.getenv("ALLOWED_ORIGINS", "").strip()
if _raw_allowed_origins:
    _configured_origins = [origin.strip().rstrip("/") for origin in _raw_allowed_origins.split(",") if origin.strip()]
else:
    _configured_origins = ["http://localhost:3000", "http://localhost:5173"]
_allow_wildcard_origin = "*" in _configured_origins
_cors_allow_origins = ["*"] if _allow_wildcard_origin else _configured_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allow_origins,
    allow_credentials=not _allow_wildcard_origin,
    allow_methods=["*"],
    allow_headers=["*"],
)

DJANGO_API_URL = os.getenv("DJANGO_API_URL", "http://django:8000")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")
DJANGO_USER = os.getenv("DJANGO_USER", "")
DJANGO_PASSWORD = os.getenv("DJANGO_PASSWORD", "")
ONTOP_RUNTIME_PROPERTIES_PATH = os.getenv("ONTOP_RUNTIME_PROPERTIES_PATH", "/ontop/runtime/active.properties")
ONTOP_MAPPING_FILE = os.getenv("ONTOP_MAPPING_FILE", "/ontop/mappings/knowbrow_fixed.obda")
ONTOP_ONTOLOGY_FILE = os.getenv("ONTOP_ONTOLOGY_FILE", "/ontop/ontology/knowbrow.ttl")
ONTOP_AUTO_RESTART = os.getenv("ONTOP_AUTO_RESTART", "false").lower() in {"1", "true", "yes"}
ONTOP_CONTAINER_NAME = os.getenv("ONTOP_CONTAINER_NAME", "knowbrow-ontop-1")


def _auth_tuple():
    return (DJANGO_USER, DJANGO_PASSWORD)


def _extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1].strip():
        return parts[1].strip()
    return None


def _normalize_source_name(name: str) -> str:
    return (name or "").strip().lower().replace(" ", "_")

def _is_public_source_record(source: Dict[str, Any]) -> bool:
    source_type = (source.get('type') or source.get('source_type') or '').strip().lower()
    policy = source.get('security_policy') or {}

    if bool(policy.get('is_public')):
        return True

    query_domains = policy.get('query_domains') or []
    if isinstance(query_domains, str):
        query_domains = [query_domains]
    normalized_domains = {str(d).strip().lower() for d in query_domains if str(d).strip()}
    if '*' in normalized_domains or 'public' in normalized_domains:
        return True

    # Product decision: OLS data sources are public by default unless explicitly disabled.
    if source_type == 'ols':
        return policy.get('is_public', True) is not False

    return _normalize_source_name(source.get('name', '')) == 'wikidata'


def _is_sparql_query(query_text: str) -> bool:
    return bool(re.match(r"^\s*(prefix|select|ask|construct|describe)\b", query_text, flags=re.IGNORECASE))


def _is_sql_select(query_text: str) -> bool:
    return bool(re.match(r"^\s*select\b", query_text, flags=re.IGNORECASE)) and ";" not in query_text


def _to_term_from_pattern(pattern: str) -> str:
    return re.sub(r"[%*_]", "", str(pattern or "").strip().lower())


def _query_mentions_admin_term(query_text: str, terms: List[str]) -> bool:
    lowered = (query_text or "").lower()
    for term in terms:
        normalized = str(term or "").strip().lower()
        if normalized and normalized in lowered:
            return True
    return False


def _parse_db_connection_config(connection_config: Dict[str, Any]) -> Dict[str, str]:
    rdbms = str(connection_config.get("rdbms_connection_string") or "").strip()
    jdbc_url = str(connection_config.get("jdbc_url") or "").strip()
    db_user = str(connection_config.get("db_user") or "").strip()
    db_password = str(connection_config.get("db_password") or "").strip()
    db_driver = str(connection_config.get("db_driver") or "org.postgresql.Driver").strip()

    if jdbc_url:
        return {
            "jdbc_url": jdbc_url,
            "db_user": db_user,
            "db_password": db_password,
            "db_driver": db_driver,
        }
    if rdbms.startswith("jdbc:"):
        return {
            "jdbc_url": rdbms,
            "db_user": db_user,
            "db_password": db_password,
            "db_driver": db_driver,
        }
    if rdbms.startswith("postgres://") or rdbms.startswith("postgresql://"):
        parsed = urlparse(rdbms)
        host = parsed.hostname or "db"
        port = parsed.port or 5432
        database = (parsed.path or "/").lstrip("/") or "sparql_db"
        query = dict()
        if parsed.query:
            for pair in parsed.query.split("&"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    query[k] = v
        jdbc_query = f"?{urlencode(query)}" if query else ""
        return {
            "jdbc_url": f"jdbc:postgresql://{host}:{port}/{database}{jdbc_query}",
            "db_user": db_user or (parsed.username or ""),
            "db_password": db_password or (parsed.password or ""),
            "db_driver": db_driver,
        }
    # Fallback to defaults from compose network.
    return {
        "jdbc_url": "jdbc:postgresql://db:5432/sparql_db",
        "db_user": db_user,
        "db_password": db_password,
        "db_driver": db_driver,
    }


def _write_ontop_runtime_properties(connection_config: Dict[str, Any]) -> str:
    db = _parse_db_connection_config(connection_config)
    lines = [
        "# Auto-generated by FastAPI Ontop config apply",
        f"jdbc.url={db['jdbc_url']}",
        f"jdbc.driver={db['db_driver']}",
        f"ontop.mapping.file={ONTOP_MAPPING_FILE}",
        f"ontop.ontology.file={ONTOP_ONTOLOGY_FILE}",
    ]
    if db["db_user"]:
        lines.append(f"jdbc.user={db['db_user']}")
    if db["db_password"]:
        lines.append(f"jdbc.password={db['db_password']}")
    rendered = "\n".join(lines) + "\n"
    props_path = Path(ONTOP_RUNTIME_PROPERTIES_PATH)
    props_path.parent.mkdir(parents=True, exist_ok=True)
    props_path.write_text(rendered, encoding="utf-8")
    return str(props_path)


def _restart_ontop_container() -> None:
    try:
        import docker as docker_sdk
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"Docker SDK unavailable: {exc}") from exc
    try:
        client = docker_sdk.from_env()
        container = client.containers.get(ONTOP_CONTAINER_NAME)
        container.restart(timeout=15)
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"Failed to restart Ontop container '{ONTOP_CONTAINER_NAME}': {exc}") from exc


async def _validate_user_token(client: httpx.AsyncClient, token: str) -> Dict[str, Any]:
    response = await client.post(
        f"{DJANGO_API_URL}/api/internal/auth/validate/",
        json={"token": token},
        headers={"X-Internal-API-Key": INTERNAL_API_KEY},
    )
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid token")
    payload = response.json()
    return payload.get("data", payload)


async def _fetch_data_source_for_user(
    client: httpx.AsyncClient,
    source_id: int,
    user_id: Optional[int],
) -> Dict[str, Any]:
    headers = {"X-Internal-API-Key": INTERNAL_API_KEY}
    if user_id:
        headers["X-User-ID"] = str(user_id)
    response = await client.get(
        f"{DJANGO_API_URL}/api/datasources/{source_id}/",
        auth=_auth_tuple(),
        headers=headers,
    )
    if response.status_code != 200:
        raise HTTPException(status_code=404, detail=f"Data source {source_id} not found or inaccessible")
    payload = response.json()
    return payload.get("data", payload)


async def _fetch_accessible_sources_for_user(
    client: httpx.AsyncClient,
    user_id: Optional[int],
) -> List[Dict[str, Any]]:
    headers = {"X-Internal-API-Key": INTERNAL_API_KEY}
    if user_id:
        headers["X-User-ID"] = str(user_id)
    response = await client.get(
        f"{DJANGO_API_URL}/api/datasources/",
        auth=_auth_tuple(),
        headers=headers,
    )
    if response.status_code != 200:
        return []
    payload = response.json()
    data = payload.get("data", payload)
    return data if isinstance(data, list) else []


def _ensure_adapter_for_source(source: Dict[str, Any]) -> None:
    source_name = _normalize_source_name(source.get("name", ""))
    if not source_name:
        return
    if source_name in adapter_registry.adapters:
        return
    source_type = source.get("type") or source.get("source_type")
    if source_type == "fuseki":
        source_type = "oxigraph"
    adapter_class = adapter_registry._adapter_classes.get(source_type)
    if adapter_class is None:
        return
    config = dict(source)
    connection_config = source.get("connection_config") or {}
    config.update(connection_config)
    config["name"] = source_name
    config["source_type"] = source_type
    if "endpoint_url" not in config and "api_url" in config:
        config["endpoint_url"] = config.get("api_url")
    adapter_registry.adapters[source_name] = adapter_class(config)


# Add configuration endpoints
add_config_endpoints(app)

# Add OLS endpoints
app.include_router(ols_router)
# Add reconciliation endpoints
app.include_router(reconciliation_router)
# Add aggregation endpoints
app.include_router(aggregation_router)

# Initialize default adapters on startup
@app.on_event("startup")
async def startup_event():
    """Initialize adapters on application startup"""
    try:
        adapter_registry._initialize_default_adapters()
        print(f"Initialized {len(adapter_registry.get_available_sources())} data sources: {adapter_registry.get_available_sources()}")
    except Exception as e:
        print(f"Failed to initialize adapters on startup: {e}")

@app.get("/")
async def read_root():
    return {"Hello": "World"}

@app.get("/sparql")
async def sparql_endpoint(query: str = Query(..., description="SPARQL query to execute")):
    # Query Wikidata
    sparql = SPARQLWrapper("https://query.wikidata.org/sparql")
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    try:
        results = sparql.query().convert()
        return JSONResponse(
            content=results,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            }
        )
    except Exception as e:
        return JSONResponse(
            content={"error": str(e)},
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            }
        )

@app.get("/api/related")
async def get_related(
    item_id: str = Query(..., description="Wikidata item ID (e.g., Q42)"),
    limit: int = Query(20, ge=1, le=50, description="Maximum number of related items to return")
):
    """Get related items (1 degree of freedom)"""
    try:
        wikidata_adapter = adapter_registry.get_adapter('wikidata')
        
        # Use the adapter to get related items
        result = await wikidata_adapter.get_related_items(item_id, limit)
        
        return result  # The adapter already returns the correct format
    except Exception as e:
        print(f"Error in related endpoint: {str(e)}")
        # Return empty relationships instead of error
        return {"itemId": item_id, "relationships": []}

# Multi-Source Integration Endpoints
@app.post("/internal/query")
async def unified_query(request: QueryRequest):
    """Unified query endpoint for all data sources"""

    async with httpx.AsyncClient() as client:
        try:
            user_payload = await _validate_user_token(client, request.token)
            user_id = user_payload.get("user_id")
            source_data = await _fetch_data_source_for_user(client, request.source_id, user_id)
            _ensure_adapter_for_source(source_data)
            source_type = source_data.get("type") or source_data.get("source_type")

            # Adapter-driven search mode
            if request.query_type.upper() == "SEARCH" or request.query.lower().startswith("search:"):
                search_text = request.query.split(":", 1)[1].strip() if request.query.lower().startswith("search:") else request.query
                source_name = source_data.get("name", "").strip().lower().replace(" ", "_")
                try:
                    adapter = adapter_registry.get_adapter(source_name)
                    results = await adapter.search(search_text, limit=20)
                    return {
                        "results": [r.dict() for r in results],
                        "total": len(results),
                        "source_type": source_type,
                        "status": "success",
                    }
                except Exception as exc:
                    return {"error": "Search failed", "detail": str(exc)}

            if source_type == "django_db":
                return await query_django_db(request.query, user_payload, client)
            if source_type in {"fuseki", "oxigraph"}:
                return await query_oxigraph(request.query, user_payload, client, source_data)
            if source_type == "external_api":
                return await query_external_api(request.query, user_payload, client, source_data)
            if source_type == "ontop":
                return await query_ontop(request.query, user_payload, client, source_data)
            return {"error": "Unsupported source", "detail": f"Source type {source_type} not supported"}

        except httpx.RequestError as e:
            return {"error": "Service unavailable", "detail": str(e)}
        except HTTPException as e:
            return {"error": e.detail}
        except Exception as e:
            return {"error": "Internal error", "detail": str(e)}


class WriteBackPayload(BaseModel):
    source_id: int
    operation: str
    table_name: str
    primary_key: Optional[str] = None
    old_values: Optional[Dict[str, Any]] = None
    new_values: Dict[str, Any]
    token: str


class PluginCapabilitiesResponse(BaseModel):
    contract_version: str
    authenticated: bool
    mode: str
    user: Optional[Dict[str, Any]]
    features: Dict[str, bool]
    sources: Dict[str, List[str]]


@app.post("/internal/write-back")
async def create_write_back(payload: WriteBackPayload):
    """Create a write-back request through Django approval workflow."""
    async with httpx.AsyncClient() as client:
        try:
            user_payload = await _validate_user_token(client, payload.token)
            user_id = user_payload.get("user_id")
            request_body = {
                "source_id": payload.source_id,
                "operation": payload.operation,
                "table_name": payload.table_name,
                "primary_key": payload.primary_key or "",
                "old_values": payload.old_values,
                "new_values": payload.new_values,
            }
            response = await client.post(
                f"{DJANGO_API_URL}/api/write-back-requests/",
                auth=_auth_tuple(),
                headers={"X-User-ID": str(user_id)},
                json=request_body,
            )
            if response.status_code not in (200, 201):
                return {"error": "Write-back request failed", "detail": response.text}
            data = response.json()
            return data.get("data", data)
        except HTTPException as e:
            return {"error": e.detail}
        except Exception as e:
            return {"error": "Service unavailable", "detail": str(e)}

async def query_django_db(sql: str, user_info: dict, client: httpx.AsyncClient):
    """Query Django PostgreSQL via internal read-only SQL API."""
    try:
        if not _is_sql_select(sql):
            return {"error": "Unsupported query", "detail": "Only single SELECT SQL is supported for django_db"}
        
        start_time = datetime.now().timestamp()
        
        # Query Django internal API
        response = await client.post(
            f"{DJANGO_API_URL}/api/internal/sql-query/",
            auth=_auth_tuple(),
            headers={"X-Internal-API-Key": INTERNAL_API_KEY},
            json={"sql": sql, "user_id": user_info.get('user_id')}
        )
        
        execution_time = datetime.now().timestamp() - start_time
        
        if response.status_code != 200:
            return {"error": "Query failed", "detail": response.text}
        
        data = response.json()
        
        return {
            "results": data.get("results", []),
            "total": data.get("total", 0),
            "source_type": "django_db",
            "execution_time": execution_time,
            "status": "success"
        }
        
    except Exception as e:
        return {"error": "Django query failed", "detail": str(e)}

async def query_oxigraph(sparql: str, user_info: dict, client: httpx.AsyncClient, source_data: dict):
    """Query Oxigraph with basic authentication."""
    try:
        if not _is_sparql_query(sparql):
            return {"error": "Unsupported query", "detail": "Oxigraph expects SPARQL query text"}
        start_time = datetime.now().timestamp()
        
        # Query triple store (simplified - no auth integration yet)
        connection_config = source_data.get("connection_config") or {}
        oxigraph_endpoint = (
            connection_config.get("endpoint")
            or connection_config.get("endpoint_url")
            or connection_config.get("api_url")
            or "http://oxigraph:7878/query"
        )
        query_url = oxigraph_endpoint.rstrip("/")
        if not query_url.endswith("/sparql") and not query_url.endswith("/query"):
            query_url = f"{query_url}/query"
        response = await client.post(
            query_url,
            headers={"Content-Type": "application/sparql-query"},
            content=sparql.encode()
        )
        
        execution_time = datetime.now().timestamp() - start_time
        
        if response.status_code != 200:
            return {"error": "Oxigraph query failed", "detail": response.text}
        
        # Parse SPARQL results (simplified)
        results = []
        if response.headers.get("content-type", "").startswith("application/sparql-results+json"):
            data = response.json()
            for binding in data.get("results", {}).get("bindings", []):
                result = {}
                for var, value in binding.items():
                    result[var] = value.get("value")
                results.append(result)
        
        source_type = source_data.get("type") or source_data.get("source_type") or "oxigraph"
        if source_type == "fuseki":
            source_type = "oxigraph"
        return {
            "results": results,
            "total": len(results),
            "source_type": source_type,
            "execution_time": execution_time,
            "status": "success"
        }
        
    except Exception as e:
        return {"error": "Oxigraph query failed", "detail": str(e)}

async def query_external_api(sparql: str, user_info: dict, client: httpx.AsyncClient, source_data: dict):
    """Query external API (e.g., Wikidata)"""
    try:
        connection_config = source_data.get("connection_config") or {}
        source_name = (source_data.get("name") or "").lower()
        api_url = connection_config.get("api_url", "")
        is_wikidata = "wikidata" in source_name or "wikidata" in api_url

        if is_wikidata and _is_sparql_query(sparql):
            # Convert SPARQL to Wikidata endpoint
            wd_sparql = sparql.replace("knowbrow:", "http://www.wikidata.org/entity/")
            sparql_url = connection_config.get("sparql_url", "https://query.wikidata.org/sparql")
            start_time = datetime.now().timestamp()
            response = await client.post(
                sparql_url,
                headers={
                    "Content-Type": "application/sparql-query",
                    "User-Agent": "Knowbrow/1.0"
                },
                content=wd_sparql.encode()
            )
            execution_time = datetime.now().timestamp() - start_time
            
            if response.status_code != 200:
                return {"error": "External API query failed", "detail": response.text}
            
            # Parse results
            data = response.json()
            results = []
            for binding in data.get("results", {}).get("bindings", []):
                result = {}
                for var, value in binding.items():
                    result[var] = value.get("value")
                results.append(result)
            
            return {
                "results": results,
                "total": len(results),
                "source_type": "external_api",
                "execution_time": execution_time,
                "status": "success"
            }
        if is_wikidata:
            # Fallback to adapter search semantics when the query is plain text.
            adapter = adapter_registry.get_adapter("wikidata")
            results = await adapter.search(sparql, limit=20)
            return {
                "results": [r.dict() for r in results],
                "total": len(results),
                "source_type": "external_api",
                "execution_time": 0,
                "status": "success",
            }
        else:
            return {"error": "Unsupported API", "detail": "Only Wikidata external API is currently supported"}
            
    except Exception as e:
        return {"error": "External API query failed", "detail": str(e)}


async def query_ontop(sparql: str, user_info: dict, client: httpx.AsyncClient, source_data: dict):
    """Query Ontop SPARQL endpoint."""
    try:
        if not _is_sparql_query(sparql):
            return {"error": "Unsupported query", "detail": "Ontop expects SPARQL query text"}
        security_policy = source_data.get("security_policy") or {}
        admin_only_terms = security_policy.get("admin_only_sparql_terms") or []
        if not admin_only_terms:
            admin_only_terms = [
                _to_term_from_pattern(pattern)
                for pattern in security_policy.get("admin_only_table_patterns", [])
            ]
            admin_only_terms = [term for term in admin_only_terms if term]
        if admin_only_terms and not source_data.get("can_admin", False):
            if _query_mentions_admin_term(sparql, admin_only_terms):
                return {
                    "error": "Ontop policy restriction",
                    "detail": "This query targets admin-only mapped tables and requires datasource admin rights.",
                }
        start_time = datetime.now().timestamp()

        connection_config = source_data.get("connection_config") or {}
        ontop_endpoint = (
            connection_config.get("endpoint")
            or connection_config.get("endpoint_url")
            or connection_config.get("api_url")
            or "http://ontop:8080/sparql"
        )
        query_url = ontop_endpoint.rstrip("/")
        if not query_url.endswith("/sparql") and not query_url.endswith("/query"):
            query_url = f"{query_url}/sparql"
        response = await client.post(
            query_url,
            headers={
                "Content-Type": "application/sparql-query",
                "Accept": "application/sparql-results+json",
            },
            content=sparql.encode()
        )

        execution_time = datetime.now().timestamp() - start_time

        if response.status_code != 200:
            return {"error": "Ontop query failed", "detail": response.text}

        results = []
        if response.headers.get("content-type", "").startswith("application/sparql-results+json"):
            data = response.json()
            for binding in data.get("results", {}).get("bindings", []):
                result = {}
                for var, value in binding.items():
                    result[var] = value.get("value")
                results.append(result)

        return {
            "results": results,
            "total": len(results),
            "source_type": "ontop",
            "execution_time": execution_time,
            "status": "success"
        }
    except Exception as e:
        return {"error": "Ontop query failed", "detail": str(e)}

@app.get("/internal/data-sources")
async def list_data_sources(token: str):
    """List available data sources"""

    async with httpx.AsyncClient() as client:
        try:
            user_payload = await _validate_user_token(client, token)
            sources = await _fetch_accessible_sources_for_user(client, user_payload.get("user_id"))
            return {"data_sources": sources}
        except HTTPException as e:
            return {"error": e.detail}
        except Exception as e:
            return {"error": "Service unavailable", "detail": str(e)}


def _sorted_unique(values: List[str]) -> List[str]:
    return sorted({v for v in values if v})


@app.get("/api/capabilities", response_model=PluginCapabilitiesResponse)
async def get_capabilities(authorization: Optional[str] = Header(None)):
    """
    Capability contract for plugin frontends.
    - Unauthenticated clients: demo mode + public sources only.
    - Authenticated clients: integrated mode + all accessible sources.
    """
    token = _extract_bearer_token(authorization)
    user_payload: Optional[Dict[str, Any]] = None
    if token:
        async with httpx.AsyncClient() as client:
            user_payload = await _validate_user_token(client, token)

    async with httpx.AsyncClient() as client:
        accessible_sources = await _fetch_accessible_sources_for_user(
            client,
            user_payload.get("user_id") if user_payload else None,
        )

    accessible_names = _sorted_unique(
        [_normalize_source_name(source.get("name", "")) for source in accessible_sources]
    )

    public_names = _sorted_unique(
        [
            _normalize_source_name(source.get("name", ""))
            for source in accessible_sources
            if _is_public_source_record(source)
        ]
    )
    private_names = _sorted_unique([name for name in accessible_names if name not in set(public_names)])

    can_write_back = any(
        bool(source.get("allow_write_back"))
        and bool(source.get("can_admin") or source.get("can_manage"))
        for source in accessible_sources
    )
    can_manage_sources = any(
        bool(source.get("can_admin") or source.get("can_manage"))
        for source in accessible_sources
    )

    authenticated = user_payload is not None
    effective_sources = accessible_names if authenticated else public_names
    return {
        "contract_version": PLUGIN_CONTRACT_VERSION,
        "authenticated": authenticated,
        "mode": "integrated" if authenticated else "demo",
        "user": (
            {
                "user_id": user_payload.get("user_id"),
                "username": user_payload.get("username"),
            }
            if authenticated
            else None
        ),
        "features": {
            "can_view_public": True,
            "can_view_private": bool(authenticated and private_names),
            # Plugin-level UX capability defaults. Source-level authorization still applies server-side.
            "can_save_graphs": authenticated,
            "can_share_graphs": authenticated,
            "can_write_back": bool(authenticated and can_write_back),
            "can_manage_sources": bool(authenticated and can_manage_sources),
        },
        "sources": {
            "public": public_names,
            "private": private_names if authenticated else [],
            "accessible": effective_sources,
        },
    }

# NEW ADAPTER-BASED ENDPOINTS

async def _resolve_request_user(authorization: Optional[str]) -> Optional[Dict[str, Any]]:
    token = _extract_bearer_token(authorization)
    if not token:
        return None
    async with httpx.AsyncClient() as client:
        return await _validate_user_token(client, token)


async def _resolve_sources_for_request(
    requested_sources: Optional[List[str]],
    authorization: Optional[str],
) -> List[str]:
    user_payload = await _resolve_request_user(authorization)

    normalized_requested = None
    if requested_sources:
        normalized_requested = [
            _normalize_source_name(source)
            for source in requested_sources
            if source and source.strip()
        ]

    if not user_payload:
        async with httpx.AsyncClient() as client:
            candidates = await _fetch_accessible_sources_for_user(client, None)
        public_sources = []
        for source in candidates:
            if _is_public_source_record(source):
                _ensure_adapter_for_source(source)
                public_sources.append(_normalize_source_name(source.get('name', '')))

        public_sources = [name for name in public_sources if name]
        public_set = set(public_sources)

        if normalized_requested is not None:
            forbidden = [source for source in normalized_requested if source not in public_set]
            if forbidden:
                raise HTTPException(status_code=401, detail=f"Authentication required for sources: {', '.join(forbidden)}")
            return [source for source in normalized_requested if source in public_set]

        return sorted(public_set)

    async with httpx.AsyncClient() as client:
        accessible = await _fetch_accessible_sources_for_user(client, user_payload.get("user_id"))
    for source in accessible:
        _ensure_adapter_for_source(source)

    accessible_names = {
        _normalize_source_name(source.get("name", ""))
        for source in accessible
        if source.get("name")
    }

    if normalized_requested is not None:
        forbidden = [source for source in normalized_requested if source not in accessible_names]
        if forbidden:
            raise HTTPException(status_code=403, detail=f"Access denied for sources: {', '.join(forbidden)}")
        return [source for source in normalized_requested if source in accessible_names]

    return sorted(accessible_names)

@app.get("/api/search", response_model=List[QuickSearchResult])
async def search(
    query: str = Query(..., min_length=2, description="Search query"),
    sources: Optional[List[str]] = Query(None, description="Data sources to search"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of results to return"),
    authorization: Optional[str] = Header(None),
):
    """
    Search across data sources with 4-field results
    Returns: label, id, description, author
    """
    try:
        sources = await _resolve_sources_for_request(sources, authorization)
        
        all_results = []
        
        # Query each source
        for source in sources:
            try:
                adapter = adapter_registry.get_adapter(source)
                results = await adapter.search(query, limit)
                all_results.extend(results)
            except Exception as e:
                continue
        
        # Sort by confidence/relevance and limit
        all_results.sort(key=lambda x: (x.confidence or 0, x.relevance_score or 0), reverse=True)
        return all_results[:limit]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.get("/api/map-nodes/{node_id}", response_model=MapNodeResponse)
async def get_map_nodes(
    node_id: str,
    sources: Optional[List[str]] = Query(None, description="Data sources to query"),
    include_metadata: bool = Query(True, description="Include metadata in response"),
    authorization: Optional[str] = Header(None),
):
    """
    Get node details and relationships for graph visualization
    Returns primary node, relationships, and bundled edges
    """
    try:
        sources = await _resolve_sources_for_request(sources, authorization)
        
        if len(sources) > 1:
            raise HTTPException(status_code=400, detail="Multiple sources not yet supported for map nodes")
        
        source = sources[0]
        adapter = adapter_registry.get_adapter(source)
        
        # Get node details and relationships concurrently
        primary_node = await adapter.get_node_details(node_id)
        relationships = await adapter.get_relationships(node_id)
        
        # Create bundled edges (simplified version for now)
        bundled_edges = []
        relation_groups = {}
        
        for rel in relationships:
            relation_type = rel.relation_type
            if relation_type not in relation_groups:
                relation_groups[relation_type] = []
            relation_groups[relation_type].append(rel)
        
        # Create bundle nodes for relations with multiple targets
        for relation_type, rels in relation_groups.items():
            if len(rels) > 1:
                bundle_id = f"bundle_{node_id}_{relation_type.replace(' ', '_')}"
                bundled_edges.append({
                    "id": bundle_id,
                    "label": f"{relation_type} ({len(rels)})",
                    "type": "edge-bundle",
                    "sourceNode": node_id,
                    "relationType": relation_type,
                    "count": len(rels),
                    "bundledEdges": [
                        {
                            "relatedItemId": rel.target_node.id,
                            "relatedItemLabel": rel.target_node.label,
                            "originalIndex": str(i)
                        }
                        for i, rel in enumerate(rels)
                    ]
                })
        
        return MapNodeResponse(
            primary_node=primary_node,
            relationships=relationships,
            bundled_edges=bundled_edges,
            metadata={"source": source, "query_time": datetime.now().isoformat()}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get map nodes: {str(e)}")

@app.get("/api/data-sources")
async def get_data_sources(authorization: Optional[str] = Header(None)):
    """Get list of available data sources"""
    try:
        user_payload = await _resolve_request_user(authorization)
        if user_payload:
            async with httpx.AsyncClient() as client:
                accessible_sources = await _fetch_accessible_sources_for_user(client, user_payload.get("user_id"))
            source_records = {
                source.get("name", "").strip().lower().replace(" ", "_"): source
                for source in accessible_sources
                if source.get("name")
            }
            accessible_names = set(source_records.keys())
            for source in accessible_sources:
                _ensure_adapter_for_source(source)
        else:
            async with httpx.AsyncClient() as client:
                candidates = await _fetch_accessible_sources_for_user(client, None)
            public_sources = []
            for source in candidates:
                if _is_public_source_record(source):
                    _ensure_adapter_for_source(source)
                    public_sources.append(source)
            source_records = {
                _normalize_source_name(source.get("name", "")): source
                for source in public_sources
                if source.get("name")
            }
            accessible_names = set(source_records.keys())

        sources = []
        source_names = sorted(accessible_names)
        for source_name in source_names:
            if source_name not in accessible_names:
                continue
            source_record = source_records.get(source_name, {})
            adapter = adapter_registry.adapters.get(source_name)
            if adapter:
                config = adapter.get_source_config()
                ui_config = adapter.get_ui_config()
            else:
                config = {
                    "source_type": source_record.get("source_type") or source_record.get("type") or "unknown"
                }
                ui_config = (source_record.get("ui_config") or {})
            source_payload = {
                "id": source_record.get("id"),
                "name": source_name,
                "type": source_record.get("source_type") or config.get("source_type", "unknown"),
                "active": True,
                "description": source_record.get("description") or ui_config.get("description", f"{source_name} data source"),
                "display_name": ui_config.get("display_name", source_record.get("name") or source_name),
                "icon": ui_config.get("icon", "📊"),
                "color": ui_config.get("color", "#000000"),
                "can_manage": bool(source_record.get("can_manage")),
                "can_admin": bool(source_record.get("can_admin")),
            }
            if source_name == "ontop" and source_payload["can_manage"]:
                source_payload["connection_config"] = source_record.get("connection_config", {})
                source_payload["security_policy"] = source_record.get("security_policy", {})
            sources.append(source_payload)
        return sources
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get data sources: {str(e)}")


class OntopConfigUpdateRequest(BaseModel):
    endpoint_url: Optional[str] = None
    rdbms_connection_string: Optional[str] = None
    query_domains: Optional[List[str]] = None
    manage_domains: Optional[List[str]] = None
    admin_only_table_patterns: Optional[List[str]] = None
    apply_runtime: bool = True
    restart_ontop: bool = True


class OntopSourceCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    endpoint_url: str
    rdbms_connection_string: Optional[str] = None
    query_domains: Optional[List[str]] = None
    manage_domains: Optional[List[str]] = None
    admin_only_table_patterns: Optional[List[str]] = None
    apply_runtime: bool = True
    restart_ontop: bool = True


@app.post("/api/data-sources/ontop")
async def create_ontop_source(
    payload: OntopSourceCreateRequest,
    authorization: Optional[str] = Header(None),
):
    """Create a new Ontop datasource for authorized users."""
    user_payload = await _resolve_request_user(authorization)
    if not user_payload:
        raise HTTPException(status_code=401, detail="Authentication required")

    async with httpx.AsyncClient() as client:
        security_policy: Dict[str, Any] = {}
        if payload.query_domains is not None:
            security_policy["query_domains"] = payload.query_domains
        if payload.manage_domains is not None:
            security_policy["manage_domains"] = payload.manage_domains
        if payload.admin_only_table_patterns is not None:
            security_policy["admin_only_table_patterns"] = payload.admin_only_table_patterns

        response = await client.post(
            f"{DJANGO_API_URL}/api/datasources/",
            auth=_auth_tuple(),
            headers={"X-User-ID": str(user_payload.get("user_id"))},
            json={
                "type": "ontop",
                "name": payload.name,
                "description": payload.description or "",
                "connection_config": {
                    "endpoint_url": payload.endpoint_url,
                    "api_url": payload.endpoint_url,
                    "rdbms_connection_string": payload.rdbms_connection_string or "",
                },
                "security_policy": security_policy,
                "ui_config": {
                    "display_name": payload.name,
                    "icon": "🧠",
                    "color": "#0ea5a4",
                    "description": payload.description or "Ontop Virtual RDF source",
                },
            },
        )
        if response.status_code not in (200, 201):
            raise HTTPException(status_code=response.status_code, detail=response.text)
        body = response.json()
        created = body.get("data", body)
        if isinstance(created, dict):
            _ensure_adapter_for_source(created)
            applied_path = None
            restarted = False
            if payload.apply_runtime:
                applied_path = _write_ontop_runtime_properties(created.get("connection_config") or {})
                if payload.restart_ontop and ONTOP_AUTO_RESTART:
                    _restart_ontop_container()
                    restarted = True
            return {
                **created,
                "runtime_applied": bool(applied_path),
                "runtime_properties_path": applied_path,
                "ontop_restarted": restarted,
                "ontop_restart_required": bool(payload.apply_runtime and payload.restart_ontop and not ONTOP_AUTO_RESTART),
            }
        return created


@app.post("/api/data-sources/{source_name}/ontop-config")
async def update_ontop_config(
    source_name: str,
    payload: OntopConfigUpdateRequest,
    authorization: Optional[str] = Header(None),
):
    """Update Ontop datasource connection and policy settings for authorized users."""
    normalized_name = source_name.strip().lower().replace(" ", "_")
    if not normalized_name:
        raise HTTPException(status_code=400, detail="Invalid source name")

    user_payload = await _resolve_request_user(authorization)
    if not user_payload:
        raise HTTPException(status_code=401, detail="Authentication required")

    async with httpx.AsyncClient() as client:
        accessible_sources = await _fetch_accessible_sources_for_user(client, user_payload.get("user_id"))
        source_record = next(
            (s for s in accessible_sources if (s.get("name", "").strip().lower().replace(" ", "_") == normalized_name)),
            None,
        )
        if not source_record:
            raise HTTPException(status_code=404, detail=f"Data source '{source_name}' not found")
        if (source_record.get("type") or source_record.get("source_type")) != "ontop":
            raise HTTPException(status_code=400, detail="Source is not an Ontop data source")
        if not source_record.get("can_manage"):
            raise HTTPException(status_code=403, detail="Manage permission denied for this Ontop source")
        wants_policy_update = any(
            value is not None
            for value in (
                payload.query_domains,
                payload.manage_domains,
                payload.admin_only_table_patterns,
            )
        )
        if wants_policy_update and not source_record.get("can_admin"):
            raise HTTPException(
                status_code=403,
                detail="Datasource admin rights required to update Ontop access policy fields.",
            )

        next_connection = dict(source_record.get("connection_config") or {})
        next_security = dict(source_record.get("security_policy") or {})

        if payload.endpoint_url is not None:
            next_connection["endpoint_url"] = payload.endpoint_url
            next_connection["api_url"] = payload.endpoint_url
        if payload.rdbms_connection_string is not None:
            next_connection["rdbms_connection_string"] = payload.rdbms_connection_string
        if payload.query_domains is not None:
            next_security["query_domains"] = payload.query_domains
        if payload.manage_domains is not None:
            next_security["manage_domains"] = payload.manage_domains
        if payload.admin_only_table_patterns is not None:
            next_security["admin_only_table_patterns"] = payload.admin_only_table_patterns

        response = await client.post(
            f"{DJANGO_API_URL}/api/datasources/{source_record['id']}/config/",
            auth=_auth_tuple(),
            headers={"X-User-ID": str(user_payload.get("user_id"))},
            json={
                "connection_config": next_connection,
                "security_policy": next_security,
            },
        )
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)

        body = response.json()
        updated = body.get("data", body)
        applied_path = None
        restarted = False
        if payload.apply_runtime and isinstance(updated, dict):
            applied_path = _write_ontop_runtime_properties(updated.get("connection_config") or {})
            if payload.restart_ontop and ONTOP_AUTO_RESTART:
                _restart_ontop_container()
                restarted = True
        if isinstance(updated, dict):
            return {
                **updated,
                "runtime_applied": bool(applied_path),
                "runtime_properties_path": applied_path,
                "ontop_restarted": restarted,
                "ontop_restart_required": bool(payload.apply_runtime and payload.restart_ontop and not ONTOP_AUTO_RESTART),
            }
        return updated

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
