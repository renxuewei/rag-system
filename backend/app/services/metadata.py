"""
Metadata management service
Uses PostgreSQL to store document and user metadata
Supports multi-tenant isolation
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import logging

from app.config import config

logger = logging.getLogger(__name__)

Base = declarative_base()


# ==================== Data Models ====================

class Tenant(Base):
    """Tenant table"""
    __tablename__ = "tenants"
    
    id = Column(String(100), primary_key=True)
    name = Column(String(200), nullable=False)
    is_active = Column(Boolean, default=True)
    config = Column(Text)  # JSON format tenant configuration
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Document(Base):
    """Document table (supports multi-tenancy)"""
    __tablename__ = "documents"
    
    id = Column(String(100), primary_key=True)
    tenant_id = Column(String(100), nullable=False, index=True)  # Tenant ID
    filename = Column(String(500), nullable=False)
    file_path = Column(String(1000))
    file_size = Column(Integer)
    file_type = Column(String(50))
    chunks_count = Column(Integer, default=0)
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    content_hash = Column(String(64), index=True)  # Document content hash, used for deduplication
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(100))
    
    # Composite index: tenant + status
    __table_args__ = (
        Index('ix_documents_tenant_status', 'tenant_id', 'status'),
    )


class User(Base):
    """User table (supports multi-tenancy)"""
    __tablename__ = "users"
    
    id = Column(String(100), primary_key=True)
    tenant_id = Column(String(100), nullable=False, index=True)  # Tenant ID
    username = Column(String(100), nullable=False)
    password_hash = Column(String(200))
    role = Column(String(50), default="user")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)
    
    # Composite unique index: unique username within tenant
    __table_args__ = (
        Index('ix_users_tenant_username', 'tenant_id', 'username', unique=True),
    )


class KnowledgeBase(Base):
    """Knowledge base table (supports multi-tenancy)"""
    __tablename__ = "knowledge_bases"
    
    id = Column(String(100), primary_key=True)
    tenant_id = Column(String(100), nullable=False, index=True)  # Tenant ID
    name = Column(String(200), nullable=False)
    description = Column(Text)
    document_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(100))
    
    # Composite index
    __table_args__ = (
        Index('ix_kb_tenant_name', 'tenant_id', 'name'),
    )


class Category(Base):
    """Category table (supports multi-tenancy)"""
    __tablename__ = "categories"
    
    id = Column(String(100), primary_key=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    parent_id = Column(String(100), nullable=True)  # Parent category ID, NULL = top-level category
    name = Column(String(200), nullable=False)
    description = Column(Text)
    document_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(100))
    
    # Composite index
    __table_args__ = (
        Index('ix_categories_tenant_parent', 'tenant_id', 'parent_id'),
    )


class DocumentCategory(Base):
    """Document-category association table"""
    __tablename__ = "document_categories"

    document_id = Column(String(100), primary_key=True)
    category_id = Column(String(100), primary_key=True)


class Conversation(Base):
    """Conversation table (supports multi-tenancy)"""
    __tablename__ = "conversations"

    id = Column(String(100), primary_key=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    user_id = Column(String(100), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    is_archived = Column(Boolean, default=False)
    tags = Column(Text)  # JSON format tag list storage
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Composite index
    __table_args__ = (
        Index('ix_conversations_tenant_user', 'tenant_id', 'user_id'),
    )


class ChatMessage(Base):
    """Chat message table"""
    __tablename__ = "chat_messages"

    id = Column(String(100), primary_key=True)
    conversation_id = Column(String(100), nullable=False, index=True)
    role = Column(String(50), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Composite index
    __table_args__ = (
        Index('ix_chat_messages_conv_created', 'conversation_id', 'created_at'),
    )


class ModelConfig(Base):
    """Model configuration table"""
    __tablename__ = "model_configs"

    id = Column(String(100), primary_key=True)
    name = Column(String(200), nullable=False)
    provider = Column(String(50), nullable=False)
    model_id = Column(String(200), nullable=False)
    api_base = Column(String(500), nullable=False)
    api_key = Column(String(500), nullable=False)
    model_type = Column(String(50), default="llm")
    max_tokens = Column(Integer, default=4096)
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Role(Base):
    """Role table"""
    __tablename__ = "roles"

    name = Column(String(50), primary_key=True)
    display_name = Column(String(100), nullable=False)
    level = Column(Integer, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    """Audit log table (supports multi-tenancy)"""
    __tablename__ = "audit_logs"

    id = Column(String(100), primary_key=True)
    action = Column(String(100), nullable=False, index=True)
    user_id = Column(String(100))
    username = Column(String(100))
    ip_address = Column(String(100))
    tenant_id = Column(String(100), default="default", index=True)
    details = Column(Text)
    extra = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('ix_audit_logs_tenant_action', 'tenant_id', 'action'),
        Index('ix_audit_logs_created_at', 'created_at'),
    )


# ==================== Metadata Service ====================

class MetadataService:
    """Metadata management service (supports multi-tenancy)"""
    
    def __init__(self, database_url: str = None):
        self.database_url = database_url or config.get_db_url()
        self.engine = None
        self.SessionLocal = None
        self._init_db()
    
    def _init_db(self):
        """Initialize database connection"""
        try:
            self.engine = create_engine(self.database_url)
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            
            Base.metadata.create_all(bind=self.engine)
            self.seed_default_roles()

            logger.info("✅ Database connection successful")
        except Exception as e:
            logger.warning(f"⚠️ Database connection failed: {e}")
            self.engine = None
            self.SessionLocal = None

    def _ensure_tables(self):
        """Ensure all model tables are created"""
        try:
            import importlib
            import app.services.feedback as _FeedbackModel
            import app.services.answer_cache as _AnswerCacheModel
        except Exception as e:
            logger.warning(f"Model import failed: {e}")
        if self.engine:
            Base.metadata.create_all(bind=self.engine)

    def get_db(self) -> Optional[Session]:
        """Get database session"""
        if not self.SessionLocal:
            return None
        return self.SessionLocal()
    
    def _get_tenant_id(self, tenant_id: str = None) -> str:
        """Get tenant ID, prioritize parameter, fall back to context"""
        if tenant_id:
            return tenant_id
        
        # Try to get from context
        from app.services.tenant import get_tenant_id
        ctx_tenant_id = get_tenant_id()
        if ctx_tenant_id:
            return ctx_tenant_id
        
        # Default tenant
        return "default"
    
    # ==================== Document Operations ====================
    
    def create_document(
        self,
        doc_id: str,
        filename: str,
        file_path: str = None,
        file_size: int = 0,
        file_type: str = None,
        created_by: str = None,
        tenant_id: str = None,
        content_hash: str = None
    ) -> bool:
        """Create document record (supports multi-tenancy)"""
        db = self.get_db()
        if not db:
            return False
        
        # Get tenant ID
        tenant_id = self._get_tenant_id(tenant_id)
        
        try:
            doc = Document(
                id=doc_id,
                tenant_id=tenant_id,
                filename=filename,
                file_path=file_path,
                file_size=file_size,
                file_type=file_type,
                created_by=created_by,
                content_hash=content_hash
            )
            db.add(doc)
            db.commit()
            logger.info(f"Created document record: {doc_id} (tenant: {tenant_id})")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create document record: {e}")
            return False
        finally:
            db.close()
    
    def check_document_exists_by_hash(
        self,
        content_hash: str,
        tenant_id: str = None
    ) -> Optional[str]:
        """
        Check if document exists by content hash
        Used for document deduplication

        Returns:
            ID of existing document, None if not found
        """
        db = self.get_db()
        if not db:
            return None
        
        tenant_id = self._get_tenant_id(tenant_id)
        
        try:
            doc = db.query(Document).filter(
                Document.tenant_id == tenant_id,
                Document.content_hash == content_hash
            ).first()
            
            return doc.id if doc else None
        finally:
            db.close()
    
    def update_document_status(
        self,
        doc_id: str,
        status: str,
        chunks_count: int = None,
        tenant_id: str = None
    ) -> bool:
        """Update document status (supports multi-tenancy)"""
        db = self.get_db()
        if not db:
            return False
        
        tenant_id = self._get_tenant_id(tenant_id)
        
        try:
            doc = db.query(Document).filter(
                Document.id == doc_id,
                Document.tenant_id == tenant_id
            ).first()
            if doc:
                doc.status = status
                if chunks_count is not None:
                    doc.chunks_count = chunks_count
                doc.updated_at = datetime.utcnow()
                db.commit()
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update document status: {e}")
            return False
        finally:
            db.close()
    
    def get_document(self, doc_id: str, tenant_id: str = None) -> Optional[Dict[str, Any]]:
        """Get document information (supports multi-tenancy)"""
        db = self.get_db()
        if not db:
            return None
        
        tenant_id = self._get_tenant_id(tenant_id)
        
        try:
            doc = db.query(Document).filter(
                Document.id == doc_id,
                Document.tenant_id == tenant_id
            ).first()
            if doc:
                return {
                    "id": doc.id,
                    "tenant_id": doc.tenant_id,
                    "filename": doc.filename,
                    "file_path": doc.file_path,
                    "file_size": doc.file_size,
                    "file_type": doc.file_type,
                    "chunks_count": doc.chunks_count,
                    "status": doc.status,
                    "content_hash": doc.content_hash,
                    "created_at": doc.created_at.isoformat() if doc.created_at else None,
                    "created_by": doc.created_by
                }
            return None
        finally:
            db.close()
    
    def list_documents(
        self,
        status: str = None,
        tenant_id: str = None,
        page: int = 1,
        page_size: int = 20,
        offset: int = None
    ) -> Dict[str, Any]:
        """
        List documents (supports multi-tenancy and pagination)

        Args:
            status: Status filter
            tenant_id: Tenant ID
            page: Page number (starting from 1)
            page_size: Number of items per page
            offset: Offset (takes precedence over page)

        Returns:
            {
                "items": [...],
                "total": total count,
                "page": current page,
                "page_size": items per page,
                "total_pages": total pages
            }
        """
        db = self.get_db()
        if not db:
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}
        
        tenant_id = self._get_tenant_id(tenant_id)
        
        try:
            query = db.query(Document).filter(Document.tenant_id == tenant_id)
            if status:
                query = query.filter(Document.status == status)
            
            # Get total count
            total = query.count()
            
            # Calculate pagination
            if offset is not None:
                skip = offset
            else:
                skip = (page - 1) * page_size
            
            # Query
            docs = query.order_by(Document.created_at.desc()).offset(skip).limit(page_size).all()
            
            total_pages = (total + page_size - 1) // page_size if total > 0 else 0
            
            return {
                "items": [
                    {
                        "id": doc.id,
                        "filename": doc.filename,
                        "file_size": doc.file_size,
                        "file_type": doc.file_type,
                        "chunks_count": doc.chunks_count,
                        "status": doc.status,
                        "created_at": doc.created_at.isoformat() if doc.created_at else None
                    }
                    for doc in docs
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages
            }
        finally:
            db.close()
    
    def delete_document(self, doc_id: str, tenant_id: str = None) -> bool:
        """Delete document record (supports multi-tenancy)"""
        db = self.get_db()
        if not db:
            return False
        
        tenant_id = self._get_tenant_id(tenant_id)
        
        try:
            doc = db.query(Document).filter(
                Document.id == doc_id,
                Document.tenant_id == tenant_id
            ).first()
            if doc:
                db.delete(doc)
                db.commit()
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to delete document record: {e}")
            return False
        finally:
            db.close()
    
    def count_documents(self, tenant_id: str = None, status: str = None) -> int:
        """Count documents (supports multi-tenancy)"""
        db = self.get_db()
        if not db:
            return 0
        
        tenant_id = self._get_tenant_id(tenant_id)
        
        try:
            query = db.query(Document).filter(Document.tenant_id == tenant_id)
            if status:
                query = query.filter(Document.status == status)
            return query.count()
        finally:
            db.close()
    
    # ==================== User Operations ====================
    
    def create_user(
        self,
        user_id: str,
        username: str,
        password_hash: str,
        role: str = "user",
        tenant_id: str = None
    ) -> bool:
        """Create user (supports multi-tenancy)"""
        db = self.get_db()
        if not db:
            return False
        
        tenant_id = self._get_tenant_id(tenant_id)
        
        try:
            user = User(
                id=user_id,
                tenant_id=tenant_id,
                username=username,
                password_hash=password_hash,
                role=role
            )
            db.add(user)
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create user: {e}")
            return False
        finally:
            db.close()
    
    def get_user_by_username(self, username: str, tenant_id: str = None) -> Optional[Dict[str, Any]]:
        """Get user by username (supports multi-tenancy)"""
        db = self.get_db()
        if not db:
            return None
        
        tenant_id = self._get_tenant_id(tenant_id)
        
        try:
            user = db.query(User).filter(
                User.tenant_id == tenant_id,
                User.username == username
            ).first()
            if user:
                return {
                    "id": user.id,
                    "tenant_id": user.tenant_id,
                    "username": user.username,
                    "password_hash": user.password_hash,
                    "role": user.role,
                    "is_active": user.is_active
                }
            return None
        finally:
            db.close()
    
    def update_last_login(self, user_id: str, tenant_id: str = None) -> bool:
        """Update last login time (supports multi-tenancy)"""
        db = self.get_db()
        if not db:
            return False
        
        tenant_id = self._get_tenant_id(tenant_id)
        
        try:
            user = db.query(User).filter(
                User.id == user_id,
                User.tenant_id == tenant_id
            ).first()
            if user:
                user.last_login = datetime.utcnow()
                db.commit()
                return True
            return False
        finally:
            db.close()
    
    def list_users(self, tenant_id: str = None) -> List[Dict[str, Any]]:
        """List all users (supports multi-tenancy)"""
        db = self.get_db()
        if not db:
            return []
        
        tenant_id = self._get_tenant_id(tenant_id)
        
        try:
            users = db.query(User).filter(User.tenant_id == tenant_id).order_by(User.created_at.desc()).all()
            return [
                {
                    "id": user.id,
                    "tenant_id": user.tenant_id,
                    "username": user.username,
                    "role": user.role,
                    "is_active": user.is_active,
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                    "last_login": user.last_login.isoformat() if user.last_login else None
                }
                for user in users
            ]
        finally:
            db.close()
    
    def get_user(self, user_id: str, tenant_id: str = None) -> Optional[Dict[str, Any]]:
        """Get user information (supports multi-tenancy)"""
        db = self.get_db()
        if not db:
            return None
        
        tenant_id = self._get_tenant_id(tenant_id)
        
        try:
            user = db.query(User).filter(
                User.id == user_id,
                User.tenant_id == tenant_id
            ).first()
            if user:
                return {
                    "id": user.id,
                    "tenant_id": user.tenant_id,
                    "username": user.username,
                    "role": user.role,
                    "is_active": user.is_active,
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                    "last_login": user.last_login.isoformat() if user.last_login else None
                }
            return None
        finally:
            db.close()
    
    def update_user(
        self,
        user_id: str,
        username: str = None,
        role: str = None,
        is_active: bool = None,
        tenant_id: str = None
    ) -> bool:
        """Update user information (supports multi-tenancy)"""
        db = self.get_db()
        if not db:
            return False
        
        tenant_id = self._get_tenant_id(tenant_id)
        
        try:
            user = db.query(User).filter(
                User.id == user_id,
                User.tenant_id == tenant_id
            ).first()
            if user:
                if username is not None:
                    user.username = username
                if role is not None:
                    user.role = role
                if is_active is not None:
                    user.is_active = is_active
                db.commit()
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update user: {e}")
            return False
        finally:
            db.close()
    
    def delete_user(self, user_id: str, tenant_id: str = None) -> bool:
        """Delete user (soft delete: set is_active=False)"""
        return self.update_user(user_id, is_active=False, tenant_id=tenant_id)
    
    def reset_user_password(
        self,
        user_id: str,
        new_password: str,
        tenant_id: str = None
    ) -> bool:
        """Reset user password"""
        import hashlib
        
        db = self.get_db()
        if not db:
            return False
        
        tenant_id = self._get_tenant_id(tenant_id)
        
        try:
            user = db.query(User).filter(
                User.id == user_id,
                User.tenant_id == tenant_id
            ).first()
            if user:
                user.password_hash = hashlib.sha256(new_password.encode()).hexdigest()
                db.commit()
                logger.info(f"Reset user password: {user_id} (tenant: {tenant_id})")
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to reset user password: {e}")
            return False
        finally:
            db.close()
    
    # ==================== Tenant Operations ====================
    
    def create_tenant(
        self,
        tenant_id: str,
        name: str,
        config_json: str = None
    ) -> bool:
        """Create tenant"""
        db = self.get_db()
        if not db:
            return False
        
        try:
            tenant = Tenant(
                id=tenant_id,
                name=name,
                config=config_json
            )
            db.add(tenant)
            db.commit()
            logger.info(f"Created tenant: {tenant_id}")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create tenant: {e}")
            return False
        finally:
            db.close()
    
    def get_tenant(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get tenant information"""
        db = self.get_db()
        if not db:
            return None
        
        try:
            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            if tenant:
                return {
                    "id": tenant.id,
                    "name": tenant.name,
                    "is_active": tenant.is_active,
                    "config": tenant.config,
                    "created_at": tenant.created_at.isoformat() if tenant.created_at else None
                }
            return None
        finally:
            db.close()
    
    # ==================== Category Operations ====================
    
    def create_category(
        self,
        category_id: str,
        name: str,
        tenant_id: str = None,
        parent_id: str = None,
        description: str = None,
        created_by: str = None
    ) -> bool:
        """Create category (supports multi-tenancy)"""
        db = self.get_db()
        if not db:
            return False
        
        tenant_id = self._get_tenant_id(tenant_id)
        
        try:
            category = Category(
                id=category_id,
                tenant_id=tenant_id,
                parent_id=parent_id,
                name=name,
                description=description,
                created_by=created_by
            )
            db.add(category)
            db.commit()
            logger.info(f"Created category: {category_id} (tenant: {tenant_id})")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create category: {e}")
            return False
        finally:
            db.close()
    
    def get_category(self, category_id: str, tenant_id: str = None) -> Optional[Dict[str, Any]]:
        """Get category information"""
        db = self.get_db()
        if not db:
            return None
        
        tenant_id = self._get_tenant_id(tenant_id)
        
        try:
            category = db.query(Category).filter(
                Category.id == category_id,
                Category.tenant_id == tenant_id
            ).first()
            if category:
                return {
                    "id": category.id,
                    "tenant_id": category.tenant_id,
                    "parent_id": category.parent_id,
                    "name": category.name,
                    "description": category.description,
                    "document_count": category.document_count,
                    "created_at": category.created_at.isoformat() if category.created_at else None,
                    "created_by": category.created_by
                }
            return None
        finally:
            db.close()
    
    def list_categories(
        self,
        tenant_id: str = None,
        parent_id: str = None
    ) -> List[Dict[str, Any]]:
        """List categories (supports filtering by parent category)"""
        db = self.get_db()
        if not db:
            return []
        
        tenant_id = self._get_tenant_id(tenant_id)
        
        try:
            query = db.query(Category).filter(Category.tenant_id == tenant_id)
            if parent_id is not None:
                query = query.filter(Category.parent_id == parent_id)
            
            categories = query.order_by(Category.created_at.asc()).all()
            return [
                {
                    "id": cat.id,
                    "tenant_id": cat.tenant_id,
                    "parent_id": cat.parent_id,
                    "name": cat.name,
                    "description": cat.description,
                    "document_count": cat.document_count,
                    "created_at": cat.created_at.isoformat() if cat.created_at else None,
                    "created_by": cat.created_by
                }
                for cat in categories
            ]
        finally:
            db.close()
    
    def update_category(
        self,
        category_id: str,
        tenant_id: str = None,
        name: str = None,
        description: str = None
    ) -> bool:
        """Update category"""
        db = self.get_db()
        if not db:
            return False
        
        tenant_id = self._get_tenant_id(tenant_id)
        
        try:
            category = db.query(Category).filter(
                Category.id == category_id,
                Category.tenant_id == tenant_id
            ).first()
            if category:
                if name is not None:
                    category.name = name
                if description is not None:
                    category.description = description
                db.commit()
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update category: {e}")
            return False
        finally:
            db.close()
    
    def delete_category(self, category_id: str, tenant_id: str = None) -> bool:
        """Delete category (also deletes document-category associations)"""
        db = self.get_db()
        if not db:
            return False
        
        tenant_id = self._get_tenant_id(tenant_id)
        
        try:
            # Delete associations
            db.query(DocumentCategory).filter(
                DocumentCategory.category_id == category_id
            ).delete()
            
            # Delete category
            category = db.query(Category).filter(
                Category.id == category_id,
                Category.tenant_id == tenant_id
            ).first()
            if category:
                db.delete(category)
                db.commit()
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to delete category: {e}")
            return False
        finally:
            db.close()

    # ==================== Role Operations ====================

    def seed_default_roles(self):
        """Initialize default roles (only executed when roles table is empty)"""
        db = self.get_db()
        if not db:
            return

        try:
            existing_count = db.query(Role).count()
            if existing_count > 0:
                return

            default_roles = [
                Role(name="admin", display_name="System Admin", level=4,
                     description="Full system access including user management and role configuration"),
                Role(name="doc_admin", display_name="Document Admin", level=3,
                     description="Can upload, delete, and manage documents and categories"),
                Role(name="user", display_name="Standard User", level=2,
                     description="Can query documents and manage own conversations"),
                Role(name="guest", display_name="Guest", level=1,
                     description="Read-only access with limited functionality"),
            ]
            db.add_all(default_roles)
            db.commit()
            logger.info("Default roles initialized: admin, doc_admin, user, guest")
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to initialize default roles: {e}")
        finally:
            db.close()

    def list_roles(self) -> List[Dict[str, Any]]:
        """List all roles"""
        db = self.get_db()
        if not db:
            return [
                {"name": "admin", "display_name": "System Admin", "level": 4, "description": ""},
                {"name": "doc_admin", "display_name": "Document Admin", "level": 3, "description": ""},
                {"name": "user", "display_name": "Standard User", "level": 2, "description": ""},
                {"name": "guest", "display_name": "Guest", "level": 1, "description": ""},
            ]

        try:
            roles = db.query(Role).order_by(Role.level.desc()).all()
            return [
                {
                    "name": role.name,
                    "display_name": role.display_name,
                    "level": role.level,
                    "description": role.description,
                }
                for role in roles
            ]
        finally:
            db.close()

    def get_role_levels(self) -> Dict[str, int]:
        """Get role level mapping (used for permission checking)"""
        db = self.get_db()
        if not db:
            return {"admin": 4, "doc_admin": 3, "user": 2, "guest": 1}

        try:
            roles = db.query(Role).all()
            return {role.name: role.level for role in roles}
        finally:
            db.close()

    def assign_document_category(self, document_id: str, category_id: str) -> bool:
        """Associate document with category"""
        db = self.get_db()
        if not db:
            return False
        
        try:
            existing = db.query(DocumentCategory).filter(
                DocumentCategory.document_id == document_id,
                DocumentCategory.category_id == category_id
            ).first()
            if existing:
                return True
            
            assoc = DocumentCategory(
                document_id=document_id,
                category_id=category_id
            )
            db.add(assoc)
            
                # Update category document count
            category = db.query(Category).filter(Category.id == category_id).first()
            if category:
                category.document_count = (category.document_count or 0) + 1
            
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to associate document with category: {e}")
            return False
        finally:
            db.close()
    
    def remove_document_category(self, document_id: str, category_id: str) -> bool:
        """Remove document-category association"""
        db = self.get_db()
        if not db:
            return False
        
        try:
            assoc = db.query(DocumentCategory).filter(
                DocumentCategory.document_id == document_id,
                DocumentCategory.category_id == category_id
            ).first()
            if assoc:
                db.delete(assoc)
                
            # Update category document count
                category = db.query(Category).filter(Category.id == category_id).first()
                if category and category.document_count and category.document_count > 0:
                    category.document_count -= 1
                
                db.commit()
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to remove document-category association: {e}")
            return False
        finally:
            db.close()
    
    def list_documents_by_category(
        self,
        category_id: str,
        tenant_id: str = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """List documents by category (paginated)"""
        db = self.get_db()
        if not db:
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}
        
        tenant_id = self._get_tenant_id(tenant_id)
        
        try:
            # Get document IDs under this category
            doc_ids_query = db.query(DocumentCategory.document_id).filter(
                DocumentCategory.category_id == category_id
            ).subquery()
            
            query = db.query(Document).filter(
                Document.tenant_id == tenant_id,
                Document.id.in_(db.query(doc_ids_query.c.document_id))
            )
            
            total = query.count()
            skip = (page - 1) * page_size
            docs = query.order_by(Document.created_at.desc()).offset(skip).limit(page_size).all()
            total_pages = (total + page_size - 1) // page_size if total > 0 else 0
            
            return {
                "items": [
                    {
                        "id": doc.id,
                        "filename": doc.filename,
                        "file_size": doc.file_size,
                        "file_type": doc.file_type,
                        "chunks_count": doc.chunks_count,
                        "status": doc.status,
                        "created_at": doc.created_at.isoformat() if doc.created_at else None
                    }
                    for doc in docs
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages
            }
        finally:
            db.close()


# Singleton
metadata_service = MetadataService()
