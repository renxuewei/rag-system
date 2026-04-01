"""
RAG API routes
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Header, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging
import time
import uuid
import io
import json
import asyncio

from app.utils.auth import get_current_user, get_tenant_id, auth_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== Conversation Management Service Imports ====================
from app.services.conversation import conversation_service
from app.services.model_config_service import model_config_service


# ==================== Request/Response Models ====================

class QueryRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5


class QueryResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    cached: bool = False
    response_time: float = 0


class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_size: int
    file_type: str
    chunks_count: int
    status: str
    created_at: Optional[str] = None


class StatsResponse(BaseModel):
    doc_count: int
    query_count: int
    cache_hit_rate: float
    vector_count: int


class LoginRequest(BaseModel):
    username: str
    password: str
    tenant_id: Optional[str] = "default"


class LoginResponse(BaseModel):
    token: str
    username: str
    role: str
    tenant_id: str


# ==================== Category Management Models ====================

class CategoryCreate(BaseModel):
    name: str
    parent_id: Optional[str] = None
    description: Optional[str] = None
    tenant_id: Optional[str] = "default"


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class DocumentCategoryAssign(BaseModel):
    category_id: str


# ==================== Review Management Models ====================

class ReviewCreate(BaseModel):
    document_id: str
    reviewer_id: str
    comment: Optional[str] = None
    tenant_id: Optional[str] = "default"


class ReviewUpdate(BaseModel):
    status: str
    comment: Optional[str] = None


class ReviewTaskCreate(BaseModel):
    document_id: str
    assigned_to: str
    deadline: Optional[str] = None
    tenant_id: Optional[str] = "default"


class BatchReviewRequest(BaseModel):
    review_ids: List[str]
    status: str
    comment: Optional[str] = None
    tenant_id: Optional[str] = "default"


# ==================== Feedback Management Models ====================

class FeedbackCreate(BaseModel):
    query: str
    rating: int
    answer: Optional[str] = None
    comment: Optional[str] = None
    helpful: Optional[bool] = None
    tenant_id: Optional[str] = "default"


# ==================== Conversation Management Models ====================

class ConversationCreate(BaseModel):
    title: Optional[str] = None


class ConversationMessageCreate(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str


# ==================== Model Configuration Management Models ====================

class ModelConfigCreate(BaseModel):
    name: str
    provider: str
    model_id: str
    api_base: str
    api_key: str
    model_type: Optional[str] = "llm"
    max_tokens: Optional[int] = 4096
    is_default: Optional[bool] = False
    description: Optional[str] = None


class ModelConfigUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    model_id: Optional[str] = None
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    model_type: Optional[str] = None
    max_tokens: Optional[int] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    description: Optional[str] = None


# ==================== User Management Models ====================

class UserCreate(BaseModel):
    username: str
    password: str
    role: Optional[str] = "user"
    tenant_id: Optional[str] = "default"


class UserUpdate(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class PasswordResetResponse(BaseModel):
    temp_password: str


# ==================== Audit Log Models ====================

class AuditLogResponse(BaseModel):
    id: str
    action: str
    user_id: Optional[str] = None
    username: Optional[str] = None
    ip_address: Optional[str] = None
    details: Optional[str] = None
    tenant_id: Optional[str] = "default"
    created_at: Optional[str] = None


# ==================== Conversation Management Models ====================

class ConversationArchive(BaseModel):
    is_archived: bool


class ConversationTags(BaseModel):
    tags: List[str]


# ==================== Helper Functions ====================

def _reload_llm_services():
    """Reload LLM services from DB config"""
    try:
        from app.services.llm import llm_service
        from app.services.llm_router import llm_router
        from app.services.embeddings import embedding_service

        default_llm = model_config_service.get_default_config(model_type="llm")
        if default_llm:
            llm_service.reconfigure(
                model_name=default_llm["model_id"],
                api_key=default_llm["api_key"],
                base_url=default_llm["api_base"]
            )

        active_llm_configs = model_config_service.get_active_configs(model_type="llm")
        llm_router.reload_models(active_llm_configs)

        default_embedding = model_config_service.get_default_config(model_type="embedding")
        if default_embedding:
            embedding_service.reconfigure(
                model_name=default_embedding["model_id"],
                api_key=default_embedding["api_key"],
                base_url=default_embedding["api_base"]
            )
    except Exception as e:
        logger.error(f"Failed to reload LLM services: {e}")


# ==================== Authentication Interfaces ====================

# Demo user data (should use database in production)
DEMO_USERS = {
    "admin": {"password": "admin123", "role": "admin", "user_id": "u001"},
    "doc_admin": {"password": "docadmin123", "role": "doc_admin", "user_id": "u004"},
    "user": {"password": "user123", "role": "user", "user_id": "u002"},
    "demo": {"password": "demo123", "role": "user", "user_id": "u003"},
}


@router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """User login"""
    from app.utils.auth import auth_service
    from app.services import metadata_service
    import hashlib
    
    # First try to verify from database
    user = metadata_service.get_user_by_username(request.username, request.tenant_id or "default")
    
    if user:
        # Verify password
        password_hash = hashlib.sha256(request.password.encode()).hexdigest()
        if user["password_hash"] == password_hash:
            # Update last login time
            metadata_service.update_last_login(user["id"], request.tenant_id or "default")
            
            # Create Token
            token = auth_service.create_token(
                user_id=user["id"],
                username=request.username,
                role=user["role"],
                tenant_id=request.tenant_id or "default"
            )
            
            logger.info(f"User login successful: {request.username}, tenant={request.tenant_id}")
            
            return LoginResponse(
                token=token,
                username=request.username,
                role=user["role"],
                tenant_id=request.tenant_id or "default"
            )
    
    # Fallback to DEMO_USERS (for compatibility)
    demo_user = DEMO_USERS.get(request.username)
    
    if demo_user and demo_user["password"] == request.password:
        # Create Token
        token = auth_service.create_token(
            user_id=demo_user["user_id"],
            username=request.username,
            role=demo_user["role"],
            tenant_id=request.tenant_id or "default"
        )
        
        logger.info(f"User login successful (demo user): {request.username}, tenant={request.tenant_id}")
        
        return LoginResponse(
            token=token,
            username=request.username,
            role=demo_user["role"],
            tenant_id=request.tenant_id or "default"
        )
    
    raise HTTPException(status_code=401, detail="Incorrect username or password")


@router.get("/auth/verify")
async def verify_token(authorization: Optional[str] = Header(None)):
    """Verify Token validity"""
    from app.utils.auth import auth_service
    
    if not authorization:
        raise HTTPException(status_code=401, detail="No authentication information provided")
    
    # Parse Bearer token
    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0] != "Bearer":
        raise HTTPException(status_code=401, detail="Invalid authentication format")
    
    token = parts[1]
    payload = auth_service.verify_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return {"valid": True, "user": payload}


# ==================== User Management Interfaces ====================

@router.get("/users")
async def list_users(current_user: dict = Depends(get_current_user)):
    """List all users"""
    try:
        from app.services import metadata_service
        tenant_id = current_user.get("tenant_id", "default")
        result = metadata_service.list_users(tenant_id=tenant_id)
        return result
    except Exception as e:
        logger.error(f"Failed to list users: {e}")
        return []


@router.post("/users")
async def create_user(request: UserCreate, current_user: dict = Depends(auth_service.require_role("admin"))):
    """Create user"""
    from app.services import metadata_service
    import hashlib
    
    # Check for duplicate username
    existing = metadata_service.get_user_by_username(request.username, request.tenant_id)
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # Generate user ID and password hash
    user_id = str(uuid.uuid4())
    password_hash = hashlib.sha256(request.password.encode()).hexdigest()
    
    success = metadata_service.create_user(
        user_id=user_id,
        username=request.username,
        password_hash=password_hash,
        role=request.role,
        tenant_id=request.tenant_id
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create user")
    
    logger.info(f"Created user: {request.username} (tenant: {request.tenant_id})")
    
    return {
        "id": user_id,
        "username": request.username,
        "role": request.role,
        "tenant_id": request.tenant_id
    }


@router.get("/users/{user_id}")
async def get_user(user_id: str, current_user: dict = Depends(get_current_user)):
    """Get user information"""
    from app.services import metadata_service
    tenant_id = current_user.get("tenant_id", "default")
    
    user = metadata_service.get_user(user_id, tenant_id=tenant_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user


@router.put("/users/{user_id}")
async def update_user(user_id: str, request: UserUpdate, current_user: dict = Depends(auth_service.require_role("admin"))):
    """Update user information"""
    from app.services import metadata_service
    
    # Use exclude_unset to only update provided fields
    update_data = request.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    tenant_id = current_user.get("tenant_id", "default")
    success = metadata_service.update_user(
        user_id=user_id,
        tenant_id=tenant_id,
        **update_data
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="User not found or update failed")
    
    return {"message": "Update successful"}


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, current_user: dict = Depends(auth_service.require_role("admin"))):
    """Delete user (soft delete)"""
    from app.services import metadata_service
    
    tenant_id = current_user.get("tenant_id", "default")
    success = metadata_service.delete_user(user_id, tenant_id=tenant_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="User not found or delete failed")
    
    return {"message": "Delete successful"}


@router.post("/users/{user_id}/reset-password", response_model=PasswordResetResponse)
async def reset_user_password(user_id: str, current_user: dict = Depends(auth_service.require_role("admin"))):
    """Reset user password"""
    from app.services import metadata_service
    import secrets
    import string
    
    # Generate temporary password (12 random characters)
    temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
    
    tenant_id = current_user.get("tenant_id", "default")
    success = metadata_service.reset_user_password(user_id, temp_password, tenant_id=tenant_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="User not found or reset failed")
    
    logger.info(f"Reset user password: {user_id} (tenant: {tenant_id})")
    
    return PasswordResetResponse(temp_password=temp_password)


# ==================== Role Management Interfaces ====================

@router.get("/roles")
async def list_roles_endpoint(current_user: dict = Depends(get_current_user)):
    """List all available roles"""
    try:
        from app.services.metadata import metadata_service
        return metadata_service.list_roles()
    except Exception as e:
        logger.error(f"Failed to list roles: {e}")
        return []


# ==================== Audit Log Interfaces ====================

@router.get("/audit-logs")
async def list_audit_logs(
    page: int = 1,
    page_size: int = 20,
    user_id: str = None,
    action: str = None,
    current_user: dict = Depends(get_current_user)
):
    """List audit logs"""
    try:
        from app.utils.audit import audit_service
        tenant_id = current_user.get("tenant_id", "default")
        return audit_service.list_audit_logs(
            page=page,
            page_size=page_size,
            user_id=user_id,
            action=action,
            tenant_id=tenant_id
        )
    except Exception as e:
        logger.error(f"Failed to list audit logs: {e}")
        return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}


# ==================== Query Interfaces ====================

@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest, current_user: dict = Depends(get_current_user)):
    """RAG Q&A interface"""
    start_time = time.time()

    try:
        from app.services import cache_service, audit_service, llm_service
        from app.services.sensitive_filter import sensitive_filter

        # Sensitive word filtering
        filter_result = sensitive_filter.check_and_filter(request.query)
        if filter_result["has_sensitive"]:
            logger.warning(f"Query contains sensitive words: {filter_result['sensitive_words']}")
            # Use filtered query for search but log original
            request.query = filter_result["filtered_text"]

        # Check answer cache (high-quality answers from feedback weight ranking)
        try:
            from app.services.answer_cache import answer_cache_service
            answer_cached = answer_cache_service.search_cache(request.query)
            if answer_cached:
                audit_service.log_query(
                    user_id=current_user.get("user_id", "anonymous"),
                    query=request.query,
                    response_time=time.time() - start_time,
                    cached=True
                )
                return QueryResponse(
                    answer=answer_cached["answer"],
                    sources=[{"content": "", "source": "answer_cache"}],
                    cached=True,
                    response_time=time.time() - start_time
                )
        except Exception as e:
            logger.warning(f"Failed to query answer cache: {e}")

        # Check Redis cache
        cache_key = f"query:{request.query}"
        cached_result = cache_service.get(cache_key)
        if cached_result:
            audit_service.log_query(
                user_id=current_user.get("user_id", "anonymous"),
                query=request.query,
                response_time=time.time() - start_time,
                cached=True
            )
            return QueryResponse(
                answer=cached_result["answer"],
                sources=cached_result["sources"],
                cached=True,
                response_time=time.time() - start_time
            )

        # 1. Retrieve relevant documents (using hybrid retrieval)
        from app.services import milvus_service
        docs = milvus_service.search(request.query, top_k=request.top_k or 5)

        # 2. Build context and enrich source information
        if docs:
            context = "\n\n".join([doc["content"] for doc in docs[:3]])

            # Get document metadata from metadata service to enrich sources
            from app.services import metadata_service
            enriched_sources = []
            for doc in docs[:3]:
                doc_id = doc.get("doc_id", "")
                chunk_index = doc.get("chunk_index", 0)
                score = doc.get("score", 0.0)

                # Try to get document metadata
                document_info = None
                if doc_id:
                    document_info = metadata_service.get_document(doc_id, current_user.get("tenant_id", "default"))
                
                enriched_sources.append({
                    "document_id": doc_id,
                    "document_name": document_info.get("filename", "") if document_info else doc.get("source", ""),
                    "chunk_index": chunk_index,
                    "score": score,
                    "content": doc["content"][:200]
                })

            sources = enriched_sources
        else:
            context = ""
            sources = []

        # 3. Generate answer
        if context:
            prompt = f"""Please answer the following question based on the reference materials. If the materials are insufficient, please state that you cannot answer.

Reference materials:
{context}

Question: {request.query}

Answer:"""
        else:
            prompt = f"""Please answer the following question.

Question: {request.query}

Answer:"""

        answer = llm_service.generate(prompt=prompt)

        # PII redaction
        from app.services.pii_detector import pii_detector
        pii_result = pii_detector.check_and_mask(answer)
        if pii_result["has_pii"]:
            logger.info(f"PII detected in answer, redacted: {pii_result['pii_count']} instances")
            answer = pii_result["masked_text"]

        # Save to Redis cache
        cache_service.set(
            key=cache_key,
            value={"answer": answer, "sources": sources},
            ttl=3600
        )

        # Write to answer cache (for feedback weight ranking)
        try:
            from app.services.answer_cache import answer_cache_service
            answer_cache_service.upsert_cache(request.query, answer)
        except Exception as e:
            logger.warning(f"Failed to write answer cache: {e}")

        # Log audit log
        audit_service.log_query(
            user_id=current_user.get("user_id", "anonymous"),
            query=request.query,
            sources=sources,
            response_time=time.time() - start_time,
            cached=False
        )
        
        return QueryResponse(
            answer=answer,
            sources=sources,
            cached=False,
            response_time=time.time() - start_time
        )

    except Exception as e:
        logger.error(f"Query failed: {e}")
        return QueryResponse(
            answer=f"System processing, please try again later. Error: {str(e)[:100]}",
            sources=[],
            cached=False,
            response_time=time.time() - start_time
        )


class StreamQueryRequest(BaseModel):
    """Stream query request"""
    query: str
    top_k: Optional[int] = 5
    tenant_id: Optional[str] = "default"
    conversation_id: Optional[str] = None


@router.post("/query/stream")
async def query_stream(request: StreamQueryRequest, current_user: dict = Depends(get_current_user)):
    """RAG streaming Q&A interface (SSE)"""
    from app.services import stream_service

    tenant_id = current_user.get("tenant_id", "default")
    user_id = current_user.get("user_id")
    conv_id = request.conversation_id

    async def event_generator():
        nonlocal conv_id

        try:
            if conv_id:
                await asyncio.to_thread(
                    conversation_service.add_message,
                    conv_id,
                    "user",
                    request.query,
                    tenant_id
                )
            else:
                if not user_id:
                    raise ValueError("user_id is required for creating conversation")
                conv_result = await asyncio.to_thread(
                    conversation_service.create_conversation,
                    tenant_id,
                    user_id,
                    request.query[:20] + "..." if len(request.query) > 20 else request.query
                )
                if conv_result:
                    conv_id = conv_result["id"]
                    await asyncio.to_thread(
                        conversation_service.add_message,
                        conv_id,
                        "user",
                        request.query,
                        tenant_id
                    )

            full_response = ""
            try:
                async for chunk in stream_service.rag_stream(
                    query=request.query,
                    top_k=request.top_k or 5
                ):
                    if chunk.startswith("event: content"):
                        content_start = chunk.find("data: ") + 6
                        content_end = chunk.find("\n\n", content_start)
                        if content_end != -1:
                            full_response += chunk[content_start:content_end]
                    elif chunk.startswith("event: done"):
                        done_data_start = chunk.find("data: ") + 6
                        done_data_end = chunk.find("\n\n", done_data_start)
                        if done_data_end != -1:
                            done_json = json.loads(chunk[done_data_start:done_data_end])
                            done_json["conversation_id"] = conv_id
                            chunk = chunk[:done_data_start] + json.dumps(done_json, ensure_ascii=False) + chunk[done_data_end:]

                    yield chunk
            except Exception as e:
                logger.error(f"Streaming query failed: {e}")
                error_data = json.dumps({"error": str(e)}, ensure_ascii=False)
                yield f"event: error\ndata: {error_data}\n\n"
            finally:
                if conv_id and full_response:
                    try:
                        await asyncio.to_thread(
                            conversation_service.add_message,
                            conv_id,
                            "assistant",
                            full_response,
                            tenant_id
                        )
                    except Exception as save_error:
                        logger.error(f"Failed to save assistant message: {save_error}")
        except Exception as e:
            logger.error(f"Failed to save user message: {e}")
            error_data = json.dumps({"error": str(e)}, ensure_ascii=False)
            yield f"event: error\ndata: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# ==================== Document Interfaces ====================

@router.post("/documents")
async def upload_document(file: UploadFile = File(...), current_user: dict = Depends(auth_service.require_role("doc_admin"))):
    """Upload document"""
    import hashlib
    from http.client import IncompleteRead

    try:
        from app.services import metadata_service, storage_service, document_processor, embedding_service

        # Generate document ID
        doc_id = str(uuid.uuid4())

        # Read file content
        content = await file.read()

        # File integrity verification
        file_size = len(content)
        file_hash = hashlib.md5(content).hexdigest()

        if file_size == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        logger.info(f"File upload started: {file.filename}, size: {file_size} bytes, MD5: {file_hash[:16]}")

        # Deduplication check
        from app.services.deduplication import deduplication_service
        content_text = content.decode('utf-8', errors='ignore')
        dup_result = deduplication_service.check_duplicate(content_text[:10000], tenant_id=current_user.get("tenant_id", "default"))
        if dup_result.get("is_duplicate"):
            existing_id = dup_result.get("existing_doc_id")
            logger.warning(f"Duplicate document, skipping upload: hash={dup_result.get('content_hash', '')[:16]}, existing_doc={existing_id}")
            return DocumentResponse(
                id=existing_id or doc_id,
                filename=file.filename,
                file_size=file_size,
                file_type=file.filename.split(".")[-1] if "." in file.filename else "unknown",
                chunks_count=0,
                status="duplicate"
            )

        # Save to MinIO
        storage_path = f"documents/{doc_id}_{file.filename}"
        storage_service.upload_file(
            object_name=storage_path,
            file_data=io.BytesIO(content),
            file_size=file_size,
            content_type=file.content_type or "application/octet-stream"
        )

        # Create metadata (initial status is processing)
        metadata_service.create_document(
            doc_id=doc_id,
            filename=file.filename,
            file_path=storage_path,
            file_size=file_size,
            file_type=file.filename.split(".")[-1] if "." in file.filename else "unknown",
            content_hash=file_hash
        )

        # Process document asynchronously (with retry mechanism)
        tmp_path = None
        chunks_count = 0
        status = "processing"

        try:
            import tempfile
            import os

            # Save temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            logger.info(f"Starting document processing: {doc_id}, temp file: {tmp_path}")

            # Retry mechanism (maximum 3 attempts)
            max_retries = 3
            last_error = None

            for attempt in range(max_retries):
                try:
                    # Process document
                    chunks = document_processor.process_file(tmp_path)

                    if not chunks:
                        raise ValueError("Document processing failed: no chunks generated")

                    logger.info(f"Document chunking completed: {doc_id}, chunk count: {len(chunks)}")

                    # Store in vector database
                    from app.services import milvus_service
                    for i, chunk in enumerate(chunks):
                        embeddings = embedding_service.embed_documents([chunk.page_content])
                        milvus_service.insert(
                            doc_id=doc_id,
                            chunks=[{
                                "chunk_index": i,
                                "content": chunk.page_content,
                                "source": file.filename
                            }],
                            embeddings=embeddings
                        )

                    # Update status to success
                    chunks_count = len(chunks)
                    status = "completed"
                    metadata_service.update_document_status(doc_id, "completed", chunks_count)
                    logger.info(f"✅ Document processing successful: {doc_id}, chunk count: {chunks_count}")
                    break

                except (IncompleteRead, ValueError) as e:
                    last_error = e
                    logger.warning(f"Document processing failed (attempt {attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff
                    else:
                        raise
                except Exception as e:
                    last_error = e
                    logger.error(f"Document processing exception (attempt {attempt + 1}/{max_retries}): {type(e).__name__}: {e}")
                    raise

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.error(f"❌ Document processing ultimately failed: {doc_id}, error: {error_msg}")
            chunks_count = 0
            status = "failed"
            metadata_service.update_document_status(doc_id, "failed", 0)
        finally:
            # Ensure cleanup of temporary files
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                    logger.debug(f"Cleaned up temporary file: {tmp_path}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary file: {e}")
        
        return DocumentResponse(
            id=doc_id,
            filename=file.filename,
            file_size=file_size,
            file_type=file.filename.split(".")[-1] if "." in file.filename else "unknown",
            chunks_count=chunks_count,
            status=status
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents")
async def list_documents(current_user: dict = Depends(get_current_user)):
    """List documents"""
    try:
        from app.services import metadata_service

        tenant_id = current_user.get("tenant_id", "default")
        result = metadata_service.list_documents(tenant_id=tenant_id)

        # Get database session to query document categories
        db = metadata_service.get_db()
        if not db:
            return result.get("items", [])

        try:
            from app.services.metadata import DocumentCategory, Category

            # Add tags and source information to each document
            enriched_items = []
            for doc in result.get("items", []):
                doc_id = doc["id"]

                # Query document categories
                category_ids = db.query(DocumentCategory.category_id).filter(
                    DocumentCategory.document_id == doc_id
                ).all()

                # Get category names as tags
                tags = []
                for (cat_id,) in category_ids:
                    cat = db.query(Category).filter(Category.id == cat_id).first()
                    if cat:
                        tags.append(cat.name)

                # Determine source type (based on file path)
                source = "minio"  # Default stored in MinIO
                file_path = doc.get("file_path", "")
                if file_path.startswith("/local/"):
                    source = "local"
                elif file_path.startswith("http") or file_path.startswith("https"):
                    source = "url"

                # Add new fields to document information
                enriched_doc = {
                    **doc,
                    "tags": tags,
                    "source": source
                }
                enriched_items.append(enriched_doc)

            return enriched_items
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        return []


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, current_user: dict = Depends(auth_service.require_role("doc_admin"))):
    """Delete document"""
    from app.services import metadata_service, milvus_service

    try:
        milvus_service.delete_by_doc_id(doc_id)
    except Exception as e:
        logger.warning(f"Failed to delete from vector database: {e}")

    metadata_service.delete_document(doc_id)
    return {"message": "Delete successful"}


# ==================== Model Configuration Management Interfaces ====================

@router.get("/model-configs")
async def list_model_configs(
    model_type: str = None,
    current_user: dict = Depends(get_current_user)
):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return model_config_service.list_model_configs(model_type=model_type)


@router.post("/model-configs")
async def create_model_config(
    request: ModelConfigCreate,
    current_user: dict = Depends(get_current_user)
):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    config_id = str(uuid.uuid4())
    result = model_config_service.create_model_config(
        id=config_id,
        name=request.name,
        provider=request.provider,
        model_id=request.model_id,
        api_base=request.api_base,
        api_key=request.api_key,
        model_type=request.model_type,
        max_tokens=request.max_tokens,
        is_default=request.is_default,
        description=request.description
    )
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create model configuration")
    return result


@router.get("/model-configs/{config_id}")
async def get_model_config(
    config_id: str,
    current_user: dict = Depends(get_current_user)
):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    config = model_config_service.get_model_config(config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Model configuration does not exist")
    return config


@router.put("/model-configs/{config_id}")
async def update_model_config(
    config_id: str,
    request: ModelConfigUpdate,
    current_user: dict = Depends(get_current_user)
):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    update_data = request.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    success = model_config_service.update_model_config(config_id, **update_data)
    if not success:
        raise HTTPException(status_code=404, detail="Model configuration does not exist or update failed")

    # Reload LLM services after config change
    _reload_llm_services()

    return {"message": "Update successful"}


@router.delete("/model-configs/{config_id}")
async def delete_model_config(
    config_id: str,
    current_user: dict = Depends(get_current_user)
):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    success = model_config_service.delete_model_config(config_id)
    if not success:
        raise HTTPException(status_code=404, detail="Model configuration does not exist or deletion failed")
    return {"message": "Delete successful"}


@router.post("/model-configs/{config_id}/test")
async def test_model_connection(
    config_id: str,
    current_user: dict = Depends(get_current_user)
):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    result = model_config_service.test_connection(config_id)
    return result



# ==================== Statistics Interfaces ====================

@router.get("/stats", response_model=StatsResponse)
async def get_stats(current_user: dict = Depends(get_current_user)):
    """Get statistics"""
    try:
        from app.services import metadata_service, audit_service, milvus_service

        result = metadata_service.list_documents(status="completed")
        docs = result.get("items", [])
        stats = audit_service.get_stats(days=7)

        try:
            vector_count = milvus_service.count()
        except:
            vector_count = 0

        return StatsResponse(
            doc_count=len(docs),
            query_count=stats.get("total_queries", 0),
            cache_hit_rate=stats.get("cache_hit_rate", 0),
            vector_count=vector_count
        )
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        return StatsResponse(
            doc_count=0,
            query_count=0,
            cache_hit_rate=0,
            vector_count=0
        )


# ==================== Health Check ====================

@router.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "timestamp": time.time()
    }


# ==================== Category Management Interfaces ====================

@router.post("/categories")
async def create_category(request: CategoryCreate, current_user: dict = Depends(get_current_user)):
    """Create category"""
    from app.services import metadata_service

    category_id = str(uuid.uuid4())
    success = metadata_service.create_category(
        category_id=category_id,
        name=request.name,
        tenant_id=request.tenant_id,
        parent_id=request.parent_id,
        description=request.description
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to create category")

    # Return complete category object
    category = metadata_service.get_category(category_id, tenant_id=request.tenant_id)
    if not category:
        raise HTTPException(status_code=500, detail="Failed to create category")

    return category


@router.get("/categories")
async def list_categories(tenant_id: str = "default", parent_id: str = None, current_user: dict = Depends(get_current_user)):
    """List categories"""
    from app.services import metadata_service
    return metadata_service.list_categories(tenant_id=tenant_id, parent_id=parent_id)


@router.get("/categories/{category_id}")
async def get_category(category_id: str, tenant_id: str = "default", current_user: dict = Depends(get_current_user)):
    """Get category details"""
    from app.services import metadata_service

    category = metadata_service.get_category(category_id, tenant_id=tenant_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category does not exist")
    return category


@router.put("/categories/{category_id}")
async def update_category(category_id: str, request: CategoryUpdate, tenant_id: str = "default", current_user: dict = Depends(get_current_user)):
    """Update category"""
    from app.services import metadata_service

    success = metadata_service.update_category(
        category_id=category_id,
        tenant_id=tenant_id,
        name=request.name,
        description=request.description
    )
    if not success:
        raise HTTPException(status_code=404, detail="Category does not exist or update failed")
    return {"message": "Update successful"}


@router.delete("/categories/{category_id}")
async def delete_category(category_id: str, tenant_id: str = "default", current_user: dict = Depends(get_current_user)):
    """Delete category"""
    from app.services import metadata_service

    success = metadata_service.delete_category(category_id, tenant_id=tenant_id)
    if not success:
        raise HTTPException(status_code=404, detail="Category does not exist or deletion failed")
    return {"message": "Delete successful"}


@router.post("/documents/{doc_id}/categories")
async def assign_document_category(doc_id: str, request: DocumentCategoryAssign, current_user: dict = Depends(auth_service.require_role("doc_admin"))):
    """Associate document with category"""
    from app.services import metadata_service

    success = metadata_service.assign_document_category(doc_id, request.category_id)
    if not success:
        raise HTTPException(status_code=500, detail="Association failed")
    return {"message": "Association successful"}


@router.delete("/documents/{doc_id}/categories/{category_id}")
async def remove_document_category(doc_id: str, category_id: str, current_user: dict = Depends(auth_service.require_role("doc_admin"))):
    """Remove document-category association"""
    from app.services import metadata_service

    success = metadata_service.remove_document_category(doc_id, category_id)
    if not success:
        raise HTTPException(status_code=404, detail="Association does not exist")
    return {"message": "Removal successful"}


@router.get("/categories/{category_id}/documents")
async def list_documents_by_category(category_id: str, tenant_id: str = "default", page: int = 1, page_size: int = 20, current_user: dict = Depends(get_current_user)):
    """List documents by category"""
    from app.services import metadata_service
    return metadata_service.list_documents_by_category(
        category_id=category_id,
        tenant_id=tenant_id,
        page=page,
        page_size=page_size
    )


# ==================== Review Process Interfaces ====================

@router.post("/reviews")
async def create_review(request: ReviewCreate, current_user: dict = Depends(get_current_user)):
    """Submit review"""
    from app.services import review_service

    review_id = str(uuid.uuid4())
    success = review_service.create_review(
        review_id=review_id,
        document_id=request.document_id,
        reviewer_id=request.reviewer_id,
        tenant_id=request.tenant_id,
        comment=request.comment
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create review")

    # Return complete review object
    review = review_service.get_review(review_id, tenant_id=request.tenant_id)
    if not review:
        raise HTTPException(status_code=500, detail="Failed to create review")

    return review


@router.get("/reviews")
async def list_reviews(
    document_id: str = None,
    status: str = None,
    tenant_id: str = "default",
    page: int = 1,
    page_size: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """List review records"""
    from app.services import review_service
    return review_service.list_reviews(
        document_id=document_id,
        status=status,
        tenant_id=tenant_id,
        page=page,
        page_size=page_size
    )


@router.put("/reviews/{review_id}")
async def update_review(review_id: str, request: ReviewUpdate, tenant_id: str = "default", current_user: dict = Depends(get_current_user)):
    """Approve/reject review"""
    from app.services import review_service

    if request.status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="Status must be approved or rejected")

    success = review_service.update_review(
        review_id=review_id,
        status=request.status,
        comment=request.comment,
        tenant_id=tenant_id
    )
    if not success:
        raise HTTPException(status_code=404, detail="Review record does not exist or update failed")
    return {"message": "Review completed"}


@router.post("/reviews/batch")
async def batch_review(request: BatchReviewRequest, current_user: dict = Depends(get_current_user)):
    """Batch review"""
    from app.services import review_service

    if request.status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="Status must be approved or rejected")

    result = review_service.batch_review(
        review_ids=request.review_ids,
        status=request.status,
        comment=request.comment,
        tenant_id=request.tenant_id
    )
    return result


@router.post("/review-tasks")
async def create_review_task(request: ReviewTaskCreate, current_user: dict = Depends(get_current_user)):
    """Create review task"""
    from app.services import review_service
    from datetime import datetime as dt

    task_id = str(uuid.uuid4())
    deadline = None
    if request.deadline:
        try:
            deadline = dt.fromisoformat(request.deadline)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")

    success = review_service.create_review_task(
        task_id=task_id,
        document_id=request.document_id,
        assigned_to=request.assigned_to,
        tenant_id=request.tenant_id,
        deadline=deadline
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create review task")
    return {"task_id": task_id, "status": "pending"}


@router.get("/review-tasks")
async def list_review_tasks(
    status: str = None,
    assigned_to: str = None,
    tenant_id: str = "default",
    page: int = 1,
    page_size: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """List review tasks"""
    from app.services import review_service
    return review_service.list_review_tasks(
        status=status,
        assigned_to=assigned_to,
        tenant_id=tenant_id,
        page=page,
        page_size=page_size
    )


# ==================== User Satisfaction Interfaces ====================

class FeedbackStatsRequest(BaseModel):
    tenant_id: Optional[str] = "default"
    days: Optional[int] = 7


@router.post("/feedback")
async def create_feedback(request: FeedbackCreate, current_user: dict = Depends(get_current_user)):
    """Submit satisfaction feedback"""
    from app.services import feedback_service
    if not feedback_service:
        raise HTTPException(status_code=503, detail="Feedback service unavailable")

    feedback_id = str(uuid.uuid4())
    success = feedback_service.create_feedback(
        feedback_id=feedback_id,
        query=request.query,
        rating=request.rating,
        tenant_id=request.tenant_id,
        answer=request.answer,
        user_id=current_user.get("user_id"),
        comment=request.comment,
        helpful=request.helpful
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create feedback")

    if request.helpful is not None and request.answer:
        try:
            from app.services.answer_cache import answer_cache_service
            answer_cache_service.update_feedback_weight(
                query=request.query,
                answer=request.answer,
                helpful=request.helpful,
                tenant_id=request.tenant_id
            )
        except Exception as e:
            logger.warning(f"Failed to update answer cache weight: {e}")

    # Return complete feedback object
    feedback = feedback_service.get_feedback(feedback_id, tenant_id=request.tenant_id)
    if not feedback:
        raise HTTPException(status_code=500, detail="Failed to create feedback")

    return feedback


@router.get("/feedback/stats")
async def get_feedback_stats(tenant_id: str = "default", days: int = 7, current_user: dict = Depends(get_current_user)):
    """Get satisfaction statistics"""
    from app.services import feedback_service
    if not feedback_service:
        raise HTTPException(status_code=503, detail="Feedback service unavailable")
    return feedback_service.get_feedback_stats(tenant_id=tenant_id, days=days)


@router.get("/feedback/low-rating")
async def get_low_rating_feedback(tenant_id: str = "default", max_rating: int = 2, page: int = 1, page_size: int = 20, current_user: dict = Depends(get_current_user)):
    """Get low-rating feedback list"""
    from app.services import feedback_service
    if not feedback_service:
        raise HTTPException(status_code=503, detail="Feedback service unavailable")
    return feedback_service.get_low_rating_feedback(tenant_id=tenant_id, max_rating=max_rating, page=page, page_size=page_size)


@router.get("/feedback/trend")
async def get_feedback_trend(tenant_id: str = "default", days: int = 30, current_user: dict = Depends(get_current_user)):
    """Get satisfaction trend"""
    from app.services import feedback_service
    if not feedback_service:
        raise HTTPException(status_code=503, detail="Feedback service unavailable")
    return feedback_service.get_feedback_trend(tenant_id=tenant_id, days=days)


# ==================== Conversation Management Interfaces ====================

@router.post("/conversations")
async def create_conversation(request: ConversationCreate, current_user: dict = Depends(get_current_user)):
    """Create new conversation"""
    if not conversation_service:
        raise HTTPException(status_code=503, detail="Conversation service unavailable")

    tenant_id = current_user.get("tenant_id", "default")
    user_id = current_user.get("user_id")

    result = conversation_service.create_conversation(
        tenant_id=tenant_id,
        user_id=user_id,
        title=request.title
    )

    if not result:
        raise HTTPException(status_code=500, detail="Failed to create conversation")

    return result


@router.get("/conversations")
async def list_conversations(current_user: dict = Depends(get_current_user)):
    """List all user conversations"""
    if not conversation_service:
        raise HTTPException(status_code=503, detail="Conversation service unavailable")

    tenant_id = current_user.get("tenant_id", "default")
    user_id = current_user.get("user_id")

    result = conversation_service.list_conversations(
        tenant_id=tenant_id,
        user_id=user_id,
        limit=50
    )

    return result


@router.get("/conversations/{conv_id}")
async def get_conversation(conv_id: str, current_user: dict = Depends(get_current_user)):
    """Get conversation details"""
    if not conversation_service:
        raise HTTPException(status_code=503, detail="Conversation service unavailable")

    tenant_id = current_user.get("tenant_id", "default")

    result = conversation_service.get_conversation(
        conv_id=conv_id,
        tenant_id=tenant_id
    )

    if not result:
        raise HTTPException(status_code=404, detail="Conversation does not exist")

    return result


@router.get("/conversations/{conv_id}/messages")
async def get_conversation_messages(conv_id: str, current_user: dict = Depends(get_current_user)):
    """Get all messages in a conversation"""
    if not conversation_service:
        raise HTTPException(status_code=503, detail="Conversation service unavailable")

    tenant_id = current_user.get("tenant_id", "default")

    result = conversation_service.get_messages(
        conv_id=conv_id,
        tenant_id=tenant_id
    )

    return result


@router.post("/conversations/{conv_id}/messages")
async def add_conversation_message(conv_id: str, request: ConversationMessageCreate, current_user: dict = Depends(get_current_user)):
    """Add message to conversation"""
    if not conversation_service:
        raise HTTPException(status_code=503, detail="Conversation service unavailable")

    tenant_id = current_user.get("tenant_id", "default")

    if request.role not in ("user", "assistant"):
        raise HTTPException(status_code=400, detail="Role must be user or assistant")

    result = conversation_service.add_message(
        conv_id=conv_id,
        role=request.role,
        content=request.content,
        tenant_id=tenant_id
    )

    if not result:
        raise HTTPException(status_code=404, detail="Conversation does not exist or failed to add message")

    return result


@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str, current_user: dict = Depends(get_current_user)):
    """Delete conversation"""
    if not conversation_service:
        raise HTTPException(status_code=503, detail="Conversation service unavailable")

    tenant_id = current_user.get("tenant_id", "default")

    success = conversation_service.delete_conversation(
        conv_id=conv_id,
        tenant_id=tenant_id
    )

    if not success:
        raise HTTPException(status_code=404, detail="Conversation does not exist or deletion failed")

    return {"message": "Deletion successful"}


@router.put("/conversations/{conv_id}/archive")
async def archive_conversation(conv_id: str, request: ConversationArchive, current_user: dict = Depends(get_current_user)):
    """Set conversation archive status"""
    if not conversation_service:
        raise HTTPException(status_code=503, detail="Conversation service unavailable")

    tenant_id = current_user.get("tenant_id", "default")

    success = conversation_service.update_conversation_archive(
        conv_id=conv_id,
        is_archived=request.is_archived,
        tenant_id=tenant_id
    )

    if not success:
        raise HTTPException(status_code=404, detail="Conversation does not exist or update failed")

    return {"message": "Update successful"}


@router.put("/conversations/{conv_id}/tags")
async def update_conversation_tags(conv_id: str, request: ConversationTags, current_user: dict = Depends(get_current_user)):
    """Update conversation tags"""
    if not conversation_service:
        raise HTTPException(status_code=503, detail="Conversation service unavailable")

    tenant_id = current_user.get("tenant_id", "default")

    success = conversation_service.update_conversation_tags(
        conv_id=conv_id,
        tags=request.tags,
        tenant_id=tenant_id
    )

    if not success:
        raise HTTPException(status_code=404, detail="Conversation does not exist or update failed")

    return {"message": "Update successful"}

