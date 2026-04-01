"""
Web crawler ingestion service
Supports static pages and dynamically rendered pages
"""

from typing import Dict, Any, Optional, List
import re
import logging
from urllib.parse import urljoin, urlparse

from .base import BaseIngestion, IngestionResult

logger = logging.getLogger(__name__)


class WebCrawler(BaseIngestion):
    """Web crawler"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)

        # Configuration
        self.timeout = self.config.get("timeout", 30)
        self.max_depth = self.config.get("max_depth", 2)
        self.max_pages = self.config.get("max_pages", 100)
        self.user_agent = self.config.get(
            "user_agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        self.follow_links = self.config.get("follow_links", False)
        self.allowed_domains = self.config.get("allowed_domains", [])

        # Visited URLs
        self._visited_urls: set = set()
    
    def ingest(self, source: str, **kwargs) -> IngestionResult:
        """
        Crawl web page content

        Args:
            source: URL
            **kwargs: Additional parameters (depth, follow_links)
        """
        url = source
        depth = kwargs.get("depth", 0)

        if not self._validate_url(url):
            return IngestionResult(
                source=url,
                content="",
                success=False,
                error="Invalid URL"
            )

        if url in self._visited_urls:
            return IngestionResult(
                source=url,
                content="",
                success=False,
                error="URL already visited"
            )

        self._visited_urls.add(url)
        
        try:
            import httpx
            
            headers = {"User-Agent": self.user_agent}
            
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                
                content_type = response.headers.get("content-type", "")
                
                if "text/html" in content_type:
                    content = self._extract_text(response.text)
                    metadata = {
                        "url": str(response.url),
                        "status_code": response.status_code,
                        "content_type": content_type,
                        "depth": depth
                    }
                    
                    # Extract links (optional)
                    if self.follow_links and depth < self.max_depth:
                        links = self._extract_links(response.text, url)
                        metadata["links"] = links[:20]  # Limit count

                    return IngestionResult(
                        source=url,
                        content=content,
                        metadata=metadata,
                        success=True
                    )
                else:
                    return IngestionResult(
                        source=url,
                        content="",
                        success=False,
                        error=f"Unsupported content type: {content_type}"
                    )

        except Exception as e:
            logger.error(f"Crawling failed: {url} - {e}")
            return IngestionResult(
                source=url,
                content="",
                success=False,
                error=str(e)
            )
    
    async def ingest_async(self, source: str, **kwargs) -> IngestionResult:
        """Async crawling"""
        import httpx
        
        url = source
        depth = kwargs.get("depth", 0)

        if not self._validate_url(url):
            return IngestionResult(
                source=url,
                content="",
                success=False,
                error="Invalid URL"
            )

        if url in self._visited_urls:
            return IngestionResult(
                source=url,
                content="",
                success=False,
                error="URL already visited"
            )

        self._visited_urls.add(url)
        
        try:
            headers = {"User-Agent": self.user_agent}
            
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                
                content_type = response.headers.get("content-type", "")
                
                if "text/html" in content_type:
                    content = self._extract_text(response.text)
                    metadata = {
                        "url": str(response.url),
                        "status_code": response.status_code,
                        "content_type": content_type,
                        "depth": depth
                    }
                    
                    return IngestionResult(
                        source=url,
                        content=content,
                        metadata=metadata,
                        success=True
                    )
                else:
                    return IngestionResult(
                        source=url,
                        content="",
                        success=False,
                        error=f"Unsupported content type: {content_type}"
                    )

        except Exception as e:
            logger.error(f"Async crawling failed: {url} - {e}")
            return IngestionResult(
                source=url,
                content="",
                success=False,
                error=str(e)
            )
    
    def crawl_site(
        self,
        start_url: str,
        max_pages: int = None
    ) -> List[IngestionResult]:
        """
        Crawl entire website

        Args:
            start_url: Starting URL
            max_pages: Maximum number of pages

        Returns:
            All page contents
        """
        max_pages = max_pages or self.max_pages
        results = []
        queue = [(start_url, 0)]
        
        while queue and len(results) < max_pages:
            url, depth = queue.pop(0)
            
            if depth > self.max_depth:
                continue
            
            result = self.ingest(url, depth=depth)
            results.append(result)
            
            if result.success and self.follow_links:
                links = result.metadata.get("links", [])
                for link in links:
                    if link not in self._visited_urls:
                        queue.append((link, depth + 1))
        
        return results
    
    def _validate_url(self, url: str) -> bool:
        """Validate URL"""
        try:
            parsed = urlparse(url)

            if not all([parsed.scheme, parsed.netloc]):
                return False

            if parsed.scheme not in ["http", "https"]:
                return False

            # Check domain restrictions
            if self.allowed_domains:
                domain = parsed.netloc
                if not any(domain.endswith(d) for d in self.allowed_domains):
                    return False
            
            return True
            
        except Exception:
            return False
    
    def _extract_text(self, html: str) -> str:
        """Extract text from HTML"""
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")

            # Remove scripts and styles
            for element in soup(["script", "style", "nav", "footer", "header"]):
                element.decompose()

            # Extract text
            text = soup.get_text(separator=" ", strip=True)

            return self.normalize_content(text)

        except ImportError:
            # No BeautifulSoup, use simple regex
            text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text)
            return text.strip()
    
    def _extract_links(self, html: str, base_url: str) -> List[str]:
        """Extract links from HTML"""
        links = []

        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")

            for a in soup.find_all("a", href=True):
                href = a["href"]
                full_url = urljoin(base_url, href)

                if self._validate_url(full_url):
                    links.append(full_url)

        except ImportError:
            # Use regex
            pattern = r'<a[^>]+href=["\']([^"\']+)["\']'
            for match in re.finditer(pattern, html):
                href = match.group(1)
                full_url = urljoin(base_url, href)
                if self._validate_url(full_url):
                    links.append(full_url)

        return list(set(links))

    def clear_cache(self):
        """Clear visited cache"""
        self._visited_urls.clear()


# Singleton
web_crawler = WebCrawler()
