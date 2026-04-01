"""
Document deduplication service
Performs deduplication based on content hash and vector similarity
"""

from typing import List, Dict, Any, Optional, Tuple
import hashlib
import logging

from app.services.embeddings import embedding_service
from app.services.vector_store import milvus_service

logger = logging.getLogger(__name__)


class DeduplicationService:
    """Document deduplication service"""

    def __init__(
        self,
        similarity_threshold: float = 0.98,
        min_content_length: int = 50
    ):
        """
        Args:
            similarity_threshold: Vector similarity threshold (above this value considered duplicate)
            min_content_length: Minimum content length (short text skip vector dedup)
        """
        self.similarity_threshold = similarity_threshold
        self.min_content_length = min_content_length

    def compute_content_hash(self, content: str) -> str:
        """
        Compute content hash (SHA256)

        Args:
            content: Document content

        Returns:
            Hash string
        """
        # Normalize: remove whitespace, convert to lowercase
        normalized = "".join(content.split()).lower()
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

    def check_duplicate_by_hash(
        self,
        content: str,
        tenant_id: str = None
    ) -> Optional[str]:
        """
        Check if exists by hash

        Args:
            content: Document content
            tenant_id: Tenant ID

        Returns:
            Existing document ID, None if not found
        """
        content_hash = self.compute_content_hash(content)

        # Check vector store
        existing_doc_id = milvus_service.check_duplicate_by_hash(
            content_hash=content_hash,
            tenant_id=tenant_id
        )

        if existing_doc_id:
            logger.info(f"Hash dedup hit: {content_hash[:16]}... -> doc_id={existing_doc_id}")

        return existing_doc_id
    
    def check_duplicate_by_similarity(
        self,
        content: str,
        tenant_id: str = None,
        top_k: int = 5
    ) -> Optional[Tuple[str, float]]:
        """
        Check if exists by vector similarity

        Args:
            content: Document content
            tenant_id: Tenant ID
            top_k: Retrieval count

        Returns:
            (Existing document ID, similarity score), None if not found
        """
        # Short text, skip vector dedup
        if len(content) < self.min_content_length:
            return None

        # Vectorize query
        query_embedding = embedding_service.embed_query(content[:1000])  # Take only first 1000 chars

        # Search for similar documents in vector store
        results = milvus_service.search(
            query=content[:500],
            top_k=top_k,
            tenant_id=tenant_id
        )

        if results:
            # Check highest score
            best_match = results[0]
            if best_match["score"] >= self.similarity_threshold:
                logger.info(
                    f"Similarity dedup hit: score={best_match['score']:.4f} -> "
                    f"doc_id={best_match['doc_id']}"
                )
                return (best_match["doc_id"], best_match["score"])

        return None
    
    def check_duplicate(
        self,
        content: str,
        tenant_id: str = None,
        use_similarity: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Comprehensive dedup check (hash + similarity)

        Args:
            content: Document content
            tenant_id: Tenant ID
            use_similarity: Whether to use similarity dedup

        Returns:
            Dedup result containing is_duplicate and existing_doc_id
        """
        # 1. Hash dedup (fast)
        existing_doc_id = self.check_duplicate_by_hash(content, tenant_id)
        if existing_doc_id:
            return {
                "is_duplicate": True,
                "method": "hash",
                "existing_doc_id": existing_doc_id,
                "content_hash": self.compute_content_hash(content)
            }

        # 2. Similarity dedup (slower but more accurate)
        if use_similarity:
            similarity_result = self.check_duplicate_by_similarity(content, tenant_id)
            if similarity_result:
                doc_id, score = similarity_result
                return {
                    "is_duplicate": True,
                    "method": "similarity",
                    "existing_doc_id": doc_id,
                    "similarity_score": score
                }

        return {
            "is_duplicate": False,
            "content_hash": self.compute_content_hash(content)
        }
    
    def deduplicate_chunks(
        self,
        chunks: List[Dict[str, Any]],
        tenant_id: str = None,
        use_similarity: bool = False
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Deduplicate chunk list

        Args:
            chunks: Chunk list
            tenant_id: Tenant ID
            use_similarity: Whether to use similarity dedup (slower)

        Returns:
            (Unique chunks, Duplicate chunks)
        """
        unique_chunks = []
        duplicate_chunks = []
        seen_hashes = set()

        for chunk in chunks:
            content = chunk.get("content", "")
            content_hash = self.compute_content_hash(content)
            chunk["content_hash"] = content_hash

            # Hash dedup
            if content_hash in seen_hashes:
                duplicate_chunks.append(chunk)
                logger.debug(f"Chunk hash duplicate: {content_hash[:16]}...")
                continue

            # Similarity dedup (optional)
            if use_similarity:
                dup_result = self.check_duplicate_by_similarity(content, tenant_id)
                if dup_result:
                    duplicate_chunks.append(chunk)
                    continue

            seen_hashes.add(content_hash)
            unique_chunks.append(chunk)

        logger.info(
            f"Chunk dedup completed: original {len(chunks)}, "
            f"unique {len(unique_chunks)}, "
            f"duplicate {len(duplicate_chunks)}"
        )

        return unique_chunks, duplicate_chunks


# Singleton
deduplication_service = DeduplicationService()
