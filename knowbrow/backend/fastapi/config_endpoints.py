from fastapi import FastAPI, Query, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
import uvicorn
import httpx
from datetime import datetime
import os
import asyncio

# Import adapter system
from adapters import (
    DataSourceAdapter, 
    QuickSearchResult, 
    MapNodeResult, 
    Relationship,
    MapNodeResponse
)
from adapters.wikidata import WikidataAdapter
from adapters.oxigraph import OxigraphAdapter
from adapters.ontop import OntopAdapter
from adapters.django_db import DjangoDBAdapter
from adapters.ols_adapter import OLSAdapter
from multi_source import QueryRequest

# Configuration endpoints
class ConfigService:
    """Service for managing data source configurations"""
    
    def __init__(self):
        self.django_api_url = os.getenv("DJANGO_API_URL", "http://django:8000")
        self.internal_api_key = os.getenv("INTERNAL_API_KEY", "")
        self.django_user = os.getenv("DJANGO_USER", "")
        self.django_password = os.getenv("DJANGO_PASSWORD", "")
    
    async def get_data_source_configs(self, user_token: str) -> List[Dict[str, Any]]:
        """Get all data source configurations from Django"""
        async with httpx.AsyncClient() as client:
            try:
                # Validate user token and get user info
                response = await client.post(
                    f"{self.django_api_url}/api/internal/auth/validate/",
                    json={"token": user_token},
                    headers={"X-Internal-API-Key": self.internal_api_key},
                )
                if response.status_code != 200:
                    raise HTTPException(status_code=401, detail="Invalid token")
                
                user_info = response.json()
                
                # Get data source configurations
                response = await client.get(
                    f"{self.django_api_url}/graphs/api/config/",
                    auth=(self.django_user, self.django_password),
                    headers={"X-User-ID": str(user_info['user_id'])}
                )
                if response.status_code != 200:
                    raise HTTPException(status_code=500, detail="Failed to fetch configurations")
                
                return response.json().get('data', [])
                
            except httpx.RequestError as e:
                raise HTTPException(status_code=503, detail=f"Django service unavailable: {str(e)}")
    
    async def get_data_source_config(self, source_id: int, user_token: str) -> Optional[Dict[str, Any]]:
        """Get specific data source configuration"""
        async with httpx.AsyncClient() as client:
            try:
                # Validate user token
                response = await client.post(
                    f"{self.django_api_url}/api/internal/auth/validate/",
                    json={"token": user_token},
                    headers={"X-Internal-API-Key": self.internal_api_key},
                )
                if response.status_code != 200:
                    raise HTTPException(status_code=401, detail="Invalid token")
                
                user_info = response.json()
                
                # Get specific data source configuration
                response = await client.get(
                    f"{self.django_api_url}/graphs/api/config/{source_id}/",
                    auth=(self.django_user, self.django_password),
                    headers={"X-User-ID": str(user_info['user_id'])}
                )
                if response.status_code != 200:
                    return None
                
                return response.json().get('data')
                
            except httpx.RequestError as e:
                raise HTTPException(status_code=503, detail=f"Django service unavailable: {str(e)}")

# Enhanced Adapter Registry
class AdapterRegistry:
    def __init__(self):
        self.adapters: Dict[str, DataSourceAdapter] = {}
        self.config_service = ConfigService()
        self._adapter_classes = {
            'wikidata': WikidataAdapter,
            'oxigraph': OxigraphAdapter,
            'ontop': OntopAdapter,
            'django_db': DjangoDBAdapter,
            'ols': OLSAdapter
        }
    
    async def initialize_adapters(self, user_token: str):
        """Initialize adapters from Django configurations"""
        try:
            configs = await self.config_service.get_data_source_configs(user_token)
            
            # Clear existing adapters
            self.adapters.clear()
            
            # Initialize adapters from configurations
            for config in configs:
                source_type = config.get('source_type')
                if source_type in self._adapter_classes:
                    adapter_class = self._adapter_classes[source_type]
                    adapter = adapter_class(config)
                    self.adapters[config['name']] = adapter
            
        except Exception as e:
            print(f"Failed to initialize adapters: {e}")
            # Fallback to default adapters
            self._initialize_default_adapters()
    
    def _initialize_default_adapters(self):
        """Fallback to default adapter initialization"""
        # Initialize Wikidata adapter with default config
        wikidata_config = {
            'name': 'wikidata',
            'api_url': 'https://www.wikidata.org/w/api.php',
        }
        self.adapters['wikidata'] = WikidataAdapter(wikidata_config)
        
        # Initialize OLS adapters with default configs
        try:
            from .adapters.ols_configs import OLS_CONFIGS
            
            for source_name, config in OLS_CONFIGS.items():
                adapter = OLSAdapter(config)
                self.adapters[source_name] = adapter
            print(f"Initialized {len(OLS_CONFIGS)} OLS adapters")
        except Exception as e:
            print(f"Failed to initialize OLS adapters: {e}")
        
        # Initialize Django DB adapters with default configs
        try:
            from .adapters.django_configs import DJANGO_DB_CONFIGS
            
            for source_name, config in DJANGO_DB_CONFIGS.items():
                adapter = DjangoDBAdapter(config)
                self.adapters[source_name] = adapter
        except Exception as e:
            print(f"Failed to initialize Django DB adapters: {e}")
        
        # Initialize Oxigraph adapter with default config
        try:
            oxigraph_config = {
                'name': 'oxigraph',
                'endpoint_url': 'http://localhost:7878/query',
                'graph_name': 'default'
            }
            self.adapters['oxigraph'] = OxigraphAdapter(oxigraph_config)
        except Exception as e:
            print(f"Failed to initialize Oxigraph adapter: {e}")

        # Initialize Ontop adapter with default config
        try:
            ontop_config = {
                'name': 'ontop',
                'endpoint_url': 'http://ontop:8080/sparql',
            }
            self.adapters['ontop'] = OntopAdapter(ontop_config)
        except Exception as e:
            print(f"Failed to initialize Ontop adapter: {e}")
    
    def get_adapter(self, source: str) -> DataSourceAdapter:
        """Get adapter by source name"""
        if source not in self.adapters:
            raise HTTPException(status_code=404, detail=f"Data source '{source}' not found")
        return self.adapters[source]
    
    def get_available_sources(self) -> List[str]:
        """Get list of available data sources"""
        return list(self.adapters.keys())
    
    async def search_with_config(self, query: str, source_name: str, user_token: str) -> List[Dict[str, Any]]:
        """Search using configuration-driven field mapping"""
        try:
            adapter = self.get_adapter(source_name)
            return await adapter.search_with_config(query)
        except Exception as e:
            print(f"Search with config error: {e}")
            return []
    
    async def get_graph_data(self, node_id: str, source_name: str, user_token: str) -> Dict[str, Any]:
        """Get graph data using configuration"""
        try:
            adapter = self.get_adapter(source_name)
            return await adapter.get_graph_data(node_id)
        except Exception as e:
            print(f"Graph data error: {e}")
            return {}

# Initialize global adapter registry
adapter_registry = AdapterRegistry()

# Configuration API endpoints
async def get_user_token(request) -> str:
    """Extract user token from request"""
    # This would depend on your authentication method
    # For now, assuming token is in Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    raise HTTPException(status_code=401, detail="No authentication token provided")

def add_config_endpoints(app: FastAPI):
    """Add configuration-related endpoints to FastAPI app"""
    
    # Also register domain-agnostic dataset/theme/branding endpoints
    from dataset_endpoints import add_dataset_endpoints
    add_dataset_endpoints(app)

    # Register GraphMap config CRUD + sharing endpoints
    from graphmap_endpoints import add_graphmap_endpoints
    add_graphmap_endpoints(app)
    
    @app.get("/api/config/sources")
    async def get_data_source_configs(token: str = Depends(get_user_token)):
        """Get all data source configurations"""
        try:
            configs = await adapter_registry.config_service.get_data_source_configs(token)
            return {"success": True, "data": configs}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/config/sources/{source_id}")
    async def get_data_source_config(source_id: int, token: str = Depends(get_user_token)):
        """Get specific data source configuration"""
        try:
            config = await adapter_registry.config_service.get_data_source_config(source_id, token)
            if config:
                return {"success": True, "data": config}
            else:
                raise HTTPException(status_code=404, detail="Data source not found")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/config/sources/{source_id}")
    async def update_data_source_config(
        source_id: int, 
        config_data: Dict[str, Any],
        token: str = Depends(get_user_token)
    ):
        """Update data source configuration"""
        try:
            async with httpx.AsyncClient() as client:
                # Validate token
                response = await client.post(
                    f"{adapter_registry.config_service.django_api_url}/api/internal/auth/validate/",
                    json={"token": token},
                    headers={"X-Internal-API-Key": adapter_registry.config_service.internal_api_key},
                )
                if response.status_code != 200:
                    raise HTTPException(status_code=401, detail="Invalid token")
                
                user_info = response.json()
                
                # Update configuration
                response = await client.post(
                    f"{adapter_registry.config_service.django_api_url}/graphs/api/config/{source_id}/",
                    auth=(adapter_registry.config_service.django_user, adapter_registry.config_service.django_password),
                    json=config_data,
                    headers={"X-User-ID": str(user_info['user_id'])}
                )
                
                if response.status_code == 200:
                    # Reinitialize adapters to pick up new configuration
                    await adapter_registry.initialize_adapters(token)
                    return {"success": True}
                else:
                    result = response.json()
                    raise HTTPException(
                        status_code=response.status_code, 
                        detail=result.get('error', 'Update failed')
                    )
                    
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/config/validate")
    async def validate_config(config_data: Dict[str, Any], token: str = Depends(get_user_token)):
        """Validate configuration data"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{adapter_registry.config_service.django_api_url}/graphs/api/config/validate/",
                    json=config_data,
                    auth=(adapter_registry.config_service.django_user, adapter_registry.config_service.django_password)
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    raise HTTPException(status_code=400, detail="Validation failed")
                    
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/config/source-types")
    async def get_source_types():
        """Get available data source types with default configurations"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{adapter_registry.config_service.django_api_url}/graphs/api/source-types/",
                    auth=(adapter_registry.config_service.django_user, adapter_registry.config_service.django_password)
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    raise HTTPException(status_code=500, detail="Failed to get source types")
                    
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/adapters/initialize")
    async def initialize_adapters(token: str = Depends(get_user_token)):
        """Initialize adapters from Django configurations"""
        try:
            await adapter_registry.initialize_adapters(token)
            return {"success": True, "message": "Adapters initialized successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # Enhanced search endpoint with configuration support
    @app.get("/api/search/configured")
    async def search_configured(
        query: str = Query(..., min_length=2),
        source: Optional[str] = Query(None),
        token: str = Depends(get_user_token)
    ):
        """Search using configuration-driven field mapping"""
        try:
            if not source:
                # Get available sources and search all
                sources = adapter_registry.get_available_sources()
                all_results = []
                for source_name in sources:
                    results = await adapter_registry.search_with_config(query, source_name, token)
                    all_results.extend(results)
                return {"success": True, "data": all_results}
            else:
                results = await adapter_registry.search_with_config(query, source, token)
                return {"success": True, "data": results}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # Enhanced graph endpoint with configuration support
    @app.get("/api/graph/configured/{node_id}")
    async def get_graph_configured(
        node_id: str,
        source: Optional[str] = Query(None),
        token: str = Depends(get_user_token)
    ):
        """Get graph data using configuration"""
        try:
            if not source:
                source = 'wikidata'  # Default source
            
            graph_data = await adapter_registry.get_graph_data(node_id, source, token)
            return {"success": True, "data": graph_data}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
