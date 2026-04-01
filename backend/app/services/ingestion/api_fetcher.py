"""
API data ingestion service
Supports REST API data fetching
"""

from typing import Dict, Any, Optional, List
import json
import logging

from .base import BaseIngestion, IngestionResult

logger = logging.getLogger(__name__)


class APIFetcher(BaseIngestion):
    """API data fetcher"""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)

        self.timeout = self.config.get("timeout", 30)
        self.default_headers = self.config.get("headers", {})
        self.auth_config = self.config.get("auth", {})

        # API configuration cache
        self._api_configs: Dict[str, Dict[str, Any]] = {}

    def register_api(
        self,
        name: str,
        base_url: str,
        headers: Dict[str, str] = None,
        auth_type: str = None,
        auth_value: str = None,
        response_parser: str = None
    ):
        """
        Register API configuration

        Args:
            name: API name
            base_url: Base URL
            headers: Request headers
            auth_type: Authentication type (bearer, basic, api_key)
            auth_value: Authentication value
            response_parser: Response parser (json, text)
        """
        self._api_configs[name] = {
            "base_url": base_url,
            "headers": headers or {},
            "auth_type": auth_type,
            "auth_value": auth_value,
            "response_parser": response_parser or "json"
        }

        logger.info(f"Registered API: {name}")

    def ingest(
        self,
        source: str,
        method: str = "GET",
        params: Dict[str, Any] = None,
        data: Dict[str, Any] = None,
        headers: Dict[str, str] = None,
        **kwargs
    ) -> IngestionResult:
        """
        Fetch data from API

        Args:
            source: URL or API name + path
            method: HTTP method
            params: Query parameters
            data: Request body data
            headers: Additional headers
            **kwargs: Additional parameters
        """
        # Parse source
        url, api_headers, parser = self._resolve_source(source, headers)

        try:
            import httpx

            # Merge request headers
            final_headers = {**self.default_headers, **api_headers}
            if headers:
                final_headers.update(headers)

            # Add authentication
            self._add_auth(final_headers, source)

            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                if method.upper() == "GET":
                    response = client.get(url, params=params, headers=final_headers)
                elif method.upper() == "POST":
                    response = client.post(url, params=params, json=data, headers=final_headers)
                else:
                    response = client.request(method, url, params=params, json=data, headers=final_headers)

                response.raise_for_status()

                # Parse response
                content = self._parse_response(response, parser)
                
                metadata = {
                    "url": str(response.url),
                    "method": method,
                    "status_code": response.status_code,
                    "content_type": response.headers.get("content-type", "")
                }
                
                return IngestionResult(
                    source=source,
                    content=content,
                    metadata=metadata,
                    success=True
                )

        except Exception as e:
            logger.error(f"API request failed: {source} - {e}")
            return IngestionResult(
                source=source,
                content="",
                success=False,
                error=str(e)
            )
    
    async def ingest_async(
        self, 
        source: str,
        method: str = "GET",
        params: Dict[str, Any] = None,
        data: Dict[str, Any] = None,
        headers: Dict[str, str] = None,
        **kwargs
    ) -> IngestionResult:
        """Async API request"""
        import httpx

        url, api_headers, parser = self._resolve_source(source, headers)
        
        try:
            final_headers = {**self.default_headers, **api_headers}
            if headers:
                final_headers.update(headers)
            
            self._add_auth(final_headers, source)
            
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                if method.upper() == "GET":
                    response = await client.get(url, params=params, headers=final_headers)
                elif method.upper() == "POST":
                    response = await client.post(url, params=params, json=data, headers=final_headers)
                else:
                    response = await client.request(method, url, params=params, json=data, headers=final_headers)
                
                response.raise_for_status()
                
                content = self._parse_response(response, parser)
                
                metadata = {
                    "url": str(response.url),
                    "method": method,
                    "status_code": response.status_code,
                    "content_type": response.headers.get("content-type", "")
                }
                
                return IngestionResult(
                    source=source,
                    content=content,
                    metadata=metadata,
                    success=True
                )

        except Exception as e:
            logger.error(f"Async API request failed: {source} - {e}")
            return IngestionResult(
                source=source,
                content="",
                success=False,
                error=str(e)
            )
    
    def fetch_paginated(
        self,
        source: str,
        page_param: str = "page",
        size_param: str = "size",
        page_size: int = 20,
        max_pages: int = 10,
        **kwargs
    ) -> List[IngestionResult]:
        """
        Fetch paginated data

        Args:
            source: API endpoint
            page_param: Page parameter name
            size_param: Page size parameter name
            page_size: Items per page
            max_pages: Maximum pages
            **kwargs: Other parameters
        """
        results = []
        
        for page in range(1, max_pages + 1):
            params = kwargs.get("params", {})
            params[page_param] = page
            params[size_param] = page_size
            
            result = self.ingest(source, params=params, **kwargs)
            results.append(result)
            
            if not result.success:
                break

            # Check if there are more data
            try:
                data = json.loads(result.content)
                if isinstance(data, list) and len(data) < page_size:
                    break
                elif isinstance(data, dict):
                    items = data.get("items", data.get("data", []))
                    if len(items) < page_size:
                        break
            except:
                pass
        
        return results
    
    def _resolve_source(
        self,
        source: str,
        extra_headers: Dict[str, str] = None
    ) -> tuple:
        """Parse data source"""
        # Check if it's a registered API
        if ":" in source:
            api_name, path = source.split(":", 1)
            if api_name in self._api_configs:
                config = self._api_configs[api_name]
                url = config["base_url"].rstrip("/") + "/" + path.lstrip("/")
                headers = config.get("headers", {}).copy()
                parser = config.get("response_parser", "json")
                return url, headers, parser

        # Use URL directly
        return source, {}, "json"

    def _add_auth(self, headers: Dict[str, str], source: str):
        """Add authentication information"""
        # Check global authentication
        auth_type = self.auth_config.get("type")
        auth_value = self.auth_config.get("value")

        # Check API-specific authentication
        if ":" in source:
            api_name = source.split(":")[0]
            if api_name in self._api_configs:
                config = self._api_configs[api_name]
                auth_type = config.get("auth_type") or auth_type
                auth_value = config.get("auth_value") or auth_value
        
        if auth_type and auth_value:
            if auth_type == "bearer":
                headers["Authorization"] = f"Bearer {auth_value}"
            elif auth_type == "basic":
                headers["Authorization"] = f"Basic {auth_value}"
            elif auth_type == "api_key":
                headers["X-API-Key"] = auth_value

    def _parse_response(self, response, parser: str) -> str:
        """Parse response"""
        if parser == "json":
            try:
                data = response.json()
                return json.dumps(data, ensure_ascii=False, indent=2)
            except:
                return response.text
        else:
            return response.text


# Singleton
api_fetcher = APIFetcher()
