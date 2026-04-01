"""
Hybrid retrieval service
Supports BM25 + vector retrieval + RRF fusion ranking
"""

from typing import List, Dict, Any, Optional
import math
from rank_bm25 import BM25Okapi
import jieba

from app.services.vector_store import milvus_service


class RetrieverService:
    """Hybrid retrieval service"""

    def __init__(self, rrf_k: int = 60):
        """
        Args:
            rrf_k: RRF fusion parameter (default 60)
        """
        self.rrf_k = rrf_k

        # BM25 index (in memory)
        self.bm25_corpus = []  # Document content list
        self.bm25_metadata = []  # Document metadata
        self.bm25_index = None

    def tokenize(self, text: str) -> List[str]:
        """Chinese word segmentation"""
        return list(jieba.cut(text))

    def build_bm25_index(self, documents: List[Dict[str, Any]]):
        """Build BM25 index"""
        self.bm25_corpus = []
        self.bm25_metadata = []

        for doc in documents:
            self.bm25_corpus.append(doc["content"])
            self.bm25_metadata.append({
                "doc_id": doc.get("doc_id"),
                "source": doc.get("source"),
                "chunk_index": doc.get("chunk_index")
            })

        # Tokenize and build index
        tokenized_corpus = [self.tokenize(doc) for doc in self.bm25_corpus]
        self.bm25_index = BM25Okapi(tokenized_corpus)

        print(f"✅ BM25 index built, total {len(self.bm25_corpus)} documents")
    
    def bm25_search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """BM25 retrieval"""
        if not self.bm25_index:
            return []

        tokenized_query = self.tokenize(query)
        scores = self.bm25_index.get_scores(tokenized_query)

        # Sort and take top_k
        results = []
        for i, score in enumerate(scores):
            if score > 0:
                results.append({
                    "score": float(score),
                    "content": self.bm25_corpus[i],
                    "rank": 0,  # Fill later
                    **self.bm25_metadata[i]
                })

        # Sort by score
        results.sort(key=lambda x: x["score"], reverse=True)

        # Fill ranks
        for i, result in enumerate(results[:top_k]):
            result["rank"] = i + 1

        return results[:top_k]
    
    def vector_search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """Vector retrieval"""
        results = milvus_service.search(query, top_k=top_k)

        # Fill ranks
        for i, result in enumerate(results):
            result["rank"] = i + 1

        return results

    async def async_vector_search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """Async vector retrieval"""
        results = await milvus_service.search_async(query, top_k=top_k)

        # Fill ranks
        for i, result in enumerate(results):
            result["rank"] = i + 1

        return results
    
    async def async_hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        bm25_weight: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Async hybrid retrieval
        Parallel execution of BM25 and vector retrieval for improved performance

        Args:
            query: Query text
            top_k: Return count
            bm25_weight: BM25 weight
        """
        import asyncio

        # Parallel execution of two retrievals
        bm25_task = asyncio.create_task(
            asyncio.to_thread(self.bm25_search, query, top_k * 2)
        )
        vector_task = asyncio.create_task(
            self.async_vector_search(query, top_k * 2)
        )

        # Wait for both tasks to complete
        bm25_results, vector_results = await asyncio.gather(
            bm25_task, vector_task
        )

        # RRF fusion
        fused_results = self.rrf_fusion(bm25_results, vector_results, top_k=top_k)

        return fused_results
    
    def rrf_fusion(
        self,
        bm25_results: List[Dict[str, Any]],
        vector_results: List[Dict[str, Any]],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        RRF fusion ranking
        Formula: RRF Score = Σ 1 / (k + rank_i)
        """
        # Dedup and merge by content
        doc_scores = {}

        # BM25 results
        for result in bm25_results:
            content = result.get("content", "")
            if content not in doc_scores:
                doc_scores[content] = {
                    "content": content,
                    "bm25_rank": result.get("rank", 0),
                    "vector_rank": 0,
                    "bm25_score": result.get("score", 0),
                    "vector_score": 0,
                    "source": result.get("source", ""),
                    "doc_id": result.get("doc_id", ""),
                    "chunk_index": result.get("chunk_index", 0)
                }
            else:
                doc_scores[content]["bm25_rank"] = result.get("rank", 0)
                doc_scores[content]["bm25_score"] = result.get("score", 0)

        # Vector retrieval results
        for result in vector_results:
            content = result.get("content", "")
            if content not in doc_scores:
                doc_scores[content] = {
                    "content": content,
                    "bm25_rank": 0,
                    "vector_rank": result.get("rank", 0),
                    "bm25_score": 0,
                    "vector_score": result.get("score", 0),
                    "source": result.get("source", ""),
                    "doc_id": result.get("doc_id", ""),
                    "chunk_index": result.get("chunk_index", 0)
                }
            else:
                doc_scores[content]["vector_rank"] = result.get("rank", 0)
                doc_scores[content]["vector_score"] = result.get("score", 0)

        # Calculate RRF scores
        for doc in doc_scores.values():
            rrf_score = 0
            if doc["bm25_rank"] > 0:
                rrf_score += 1 / (self.rrf_k + doc["bm25_rank"])
            if doc["vector_rank"] > 0:
                rrf_score += 1 / (self.rrf_k + doc["vector_rank"])
            doc["rrf_score"] = rrf_score

        # Sort by RRF score
        sorted_results = sorted(
            doc_scores.values(),
            key=lambda x: x["rrf_score"],
            reverse=True
        )

        return sorted_results[:top_k]
    
    def hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        bm25_weight: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Hybrid retrieval
        Args:
            query: Query text
            top_k: Return count
            bm25_weight: BM25 weight (vector retrieval weight is 1 - bm25_weight)
        """
        # Parallel execution of two retrievals
        bm25_results = self.bm25_search(query, top_k=top_k * 2)
        vector_results = self.vector_search(query, top_k=top_k * 2)

        # RRF fusion
        fused_results = self.rrf_fusion(bm25_results, vector_results, top_k=top_k)

        return fused_results


# Singleton
retriever_service = RetrieverService()
