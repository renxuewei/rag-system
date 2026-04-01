"""
Data ingestion layer
Supports multiple data sources: crawler, API, database sync
"""

from .base import BaseIngestion
from .crawler import WebCrawler
from .api_fetcher import APIFetcher
from .db_sync import DatabaseSync

__all__ = [
    "BaseIngestion",
    "WebCrawler", 
    "APIFetcher",
    "DatabaseSync"
]
