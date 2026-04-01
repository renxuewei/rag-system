"""
Embedding service
Supports GLM Embedding API and BGE local models
"""

import os
from typing import List, Optional
import httpx
from langchain_openai import OpenAIEmbeddings

from app.config import config


class EmbeddingService:
    """Embedding service"""
    
    def __init__(
        self,
        model_name: str = None,
        api_key: str = None,
        base_url: str = None
    ):
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url

        # Try loading from DB first, fall back to env vars
        self._init_config()

        # Initialize Embedding model
        self.embeddings = OpenAIEmbeddings(
            model=self.model_name,
            openai_api_key=self.api_key,
            openai_api_base=self.base_url
        )

    def _init_config(self):
        """Initialize config from DB or env vars"""
        try:
            from app.services.model_config_service import model_config_service
            default_config = model_config_service.get_default_config(model_type="embedding")
            if default_config:
                if not self.model_name:
                    self.model_name = default_config["model_id"]
                if not self.api_key:
                    self.api_key = default_config["api_key"]
                if not self.base_url:
                    self.base_url = default_config["api_base"]
        except Exception:
            pass

        # Fall back to env vars
        if not self.model_name:
            self.model_name = config.EMBEDDING_MODEL_NAME
        if not self.api_key:
            self.api_key = config.OPENAI_API_KEY
        if not self.base_url:
            self.base_url = config.OPENAI_API_BASE

    def reconfigure(
        self,
        model_name: str = None,
        api_key: str = None,
        base_url: str = None
    ):
        """Reconfigure embedding service"""
        if model_name:
            self.model_name = model_name
        if api_key:
            self.api_key = api_key
        if base_url:
            self.base_url = base_url

        self.embeddings = OpenAIEmbeddings(
            model=self.model_name,
            openai_api_key=self.api_key,
            openai_api_base=self.base_url
        )
    
    def embed_query(self, query: str) -> List[float]:
        """Vectorize single query"""
        return self.embeddings.embed_query(query)
    
    def embed_documents(self, documents: List[str]) -> List[List[float]]:
        """Batch vectorize documents"""
        return self.embeddings.embed_documents(documents)
    
    async def aembed_query(self, query: str) -> List[float]:
        """Async vectorize single query"""
        return await self.embeddings.aembed_query(query)
    
    async def aembed_documents(self, documents: List[str]) -> List[List[float]]:
        """Async batch vectorize documents"""
        return await self.embeddings.aembed_documents(documents)


# Singleton
embedding_service = EmbeddingService()
