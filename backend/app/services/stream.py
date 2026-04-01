"""
Streaming output service
Supports SSE (Server-Sent Events) streaming response
"""

from typing import AsyncIterator, List, Dict, Any
import asyncio
import json
import logging

from app.services.llm import llm_service
from app.services.retriever import retriever_service
from app.services.reranker import reranker_service

logger = logging.getLogger(__name__)


class StreamService:
    """Streaming output service"""

    _SKIP_RETRIEVAL_INPUTS = frozenset({
        "hi", "hello", "hey", "ok", "thanks", "thx",
        "nihao", "hai", "haode", "xiexie", "ganxie", "en", "o",
    })

    def _needs_retrieval(self, query: str) -> bool:
        stripped = query.strip()
        if len(stripped) < 3:
            return False
        if stripped.lower() in self._SKIP_RETRIEVAL_INPUTS:
            return False
        return True

    async def _direct_stream(
        self,
        query: str,
        history: List[Dict[str, str]] = None,
    ) -> AsyncIterator[str]:
        yield self._format_sse("status", "Generating answer...")

        full_response = ""
        full_thinking = ""
        async for item in llm_service.chat_stream(query, "", history):
            text = item.get("content", "")
            if not text:
                continue
            if item["type"] == "thinking":
                full_thinking += text
                yield self._format_sse("thinking", text)
            else:
                full_response += text
                yield self._format_sse("content", text)

        yield self._format_sse("done", json.dumps({
            "full_response": full_response,
            "thinking": full_thinking,
        }, ensure_ascii=False))

    async def rag_stream(
        self,
        query: str,
        history: List[Dict[str, str]] = None,
        top_k: int = 5
    ) -> AsyncIterator[str]:
        """
        RAG streaming Q&A
        Args:
            query: User question
            history: Conversation history
            top_k: Retrieval count
        """
        if not self._needs_retrieval(query):
            async for event in self._direct_stream(query, history):
                yield event
            return

        # 1. Check answer cache (feedback-weighted high-quality answers)
        yield self._format_sse("status", "Checking answer cache...")
        try:
            from app.services.answer_cache import answer_cache_service
            cached = await asyncio.to_thread(
                answer_cache_service.search_cache, query, None, 3, 1, 0.92
            )
            if cached:
                logger.info(f"Answer cache hit: similarity={cached['similarity']:.4f}, weight={cached['weight']}")
                yield self._format_sse("status", "Retrieved answer from cache")
                yield self._format_sse("content", cached["answer"])
                yield self._format_sse("cache_hit", json.dumps({
                    "similarity": round(cached["similarity"], 4),
                    "weight": cached["weight"],
                    "cache_id": cached["id"]
                }, ensure_ascii=False))
                yield self._format_sse("done", json.dumps({"full_response": cached["answer"]}, ensure_ascii=False))
                return
        except Exception as e:
            logger.warning(f"Answer cache query failed, continuing normal flow: {e}")

        # 2. Send start event
        yield self._format_sse("status", "Starting retrieval...")
        
        # 3. Retrieve relevant documents (if BM25 index is empty, use pure vector retrieval)
        try:
            documents = await asyncio.to_thread(retriever_service.hybrid_search, query, top_k)
        except Exception as e:
            logger.warning(f"Hybrid retrieval failed, using pure vector retrieval: {e}")
            try:
                documents = await asyncio.to_thread(retriever_service.vector_search, query, top_k)
            except Exception as ve:
                logger.error(f"Vector retrieval also failed: {ve}")
                yield self._format_sse("error", json.dumps({"error": f"Retrieval service error: {ve}"}, ensure_ascii=False))
                yield self._format_sse("done", "")
                return
        
        if not documents:
            yield self._format_sse("status", "No relevant content found in knowledge base")
            yield self._format_sse("content", "Sorry, no content related to your question was found in the knowledge base.")
            yield self._format_sse("done", "")
            return
        
        # 4. Send retrieval results
        yield self._format_sse("status", f"Found {len(documents)} relevant documents")
        yield self._format_sse("sources", json.dumps(documents, ensure_ascii=False))
        
        # 5. Rerank (optional)
        reranked_docs = await asyncio.to_thread(reranker_service.rerank_sync, query, documents, 3)
        
        # 6. Build context
        context = "\n\n".join([
            f"[Source: {doc.get('source', 'Unknown')}]\n{doc.get('content', '')}"
            for doc in reranked_docs
        ])
        
        # 7. Stream answer generation
        yield self._format_sse("status", "Generating answer...")
        
        full_response = ""
        full_thinking = ""
        async for item in llm_service.chat_stream(query, context, history):
            text = item.get("content", "")
            if not text:
                continue
            if item["type"] == "thinking":
                full_thinking += text
                yield self._format_sse("thinking", text)
            else:
                full_response += text
                yield self._format_sse("content", text)
        
        # 8. Write to answer cache (background async, does not block response)
        try:
            from app.services.answer_cache import answer_cache_service as _cache_svc
            await asyncio.to_thread(_cache_svc.upsert_cache, query, full_response)
        except Exception as e:
            logger.warning(f"Failed to write to answer cache: {e}")

        # 9. Send completion event
        yield self._format_sse("done", json.dumps({"full_response": full_response}, ensure_ascii=False))
    
    def _format_sse(self, event: str, data: str) -> str:
        """
        Format SSE message
        Args:
            event: Event type
            data: Data content
        """
        return f"event: {event}\ndata: {data}\n\n"


# Singleton
stream_service = StreamService()
