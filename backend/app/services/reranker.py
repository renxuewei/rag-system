"""
Reranking service
Uses BGE-Reranker to perform precise ranking of retrieval results
"""

from typing import List, Dict, Any, Optional
import httpx
import os

from app.config import config


class RerankerService:
    """Reranking service"""

    def __init__(self, model_name: str = "BAAI/bge-reranker-base"):
        """
        Args:
            model_name: Reranker model name
        """
        self.model_name = model_name
        # Temporarily use GLM API to simulate reranking (local model available in production)
        self.api_key = config.OPENAI_API_KEY
        self.base_url = config.OPENAI_API_BASE

    async def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Rerank
        Args:
            query: Query text
            documents: Document list to rerank
            top_k: Return count
        """
        if not documents:
            return []

        # Simulate reranking: use LLM to score
        # Production environment recommends using BGE-Reranker local model

        scored_docs = []

        for doc in documents:
            score = await self._score_relevance(query, doc.get("content", ""))
            doc["rerank_score"] = score
            scored_docs.append(doc)

        # Sort by score
        scored_docs.sort(key=lambda x: x["rerank_score"], reverse=True)

        return scored_docs[:top_k]

    async def _score_relevance(self, query: str, content: str) -> float:
        """
        Use LLM to evaluate relevance (0-1 score)
        Production environment should replace with BGE-Reranker
        """
        # Truncate content to avoid too long
        content = content[:500]

        # Simplified here, return fixed high score
        # Should actually call LLM or local model
        # TODO: Integrate BGE-Reranker local model

        return 0.8
    
    def rerank_sync(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Synchronous reranking (simplified, return original results directly)"""
        if not documents:
            return []

        # Add rerank score to each document
        for i, doc in enumerate(documents):
            doc["rerank_score"] = 1.0 - (i * 0.1)  # Simplified: decreasing by order

        return documents[:top_k]


# Singleton
reranker_service = RerankerService()
