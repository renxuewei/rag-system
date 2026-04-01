"""
Conversation history service
Supports conversation creation, message saving, history queries
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean, func, ForeignKey
from sqlalchemy.orm import Session, relationship
import logging
import uuid
import json

from app.services.metadata import Base, metadata_service

logger = logging.getLogger(__name__)


# ==================== Data Models ====================
# Note: Conversation and ChatMessage models are defined in metadata.py


# ==================== Conversation Service ====================

class ConversationService:
    """Conversation history service (multi-tenant support)"""

    def __init__(self):
        """Initialize conversation service, reuse database connection from metadata service"""
        self.engine = metadata_service.engine
        self.SessionLocal = metadata_service.SessionLocal

    def get_db(self) -> Optional[Session]:
        """Get database session"""
        if not self.SessionLocal:
            return None
        return self.SessionLocal()

    def _get_tenant_id(self, tenant_id: str = None) -> str:
        """Get tenant ID, prefer passed parameter, then use context"""
        if tenant_id:
            return tenant_id

        # Try to get from context
        from app.services.tenant import get_tenant_id
        ctx_tenant_id = get_tenant_id()
        if ctx_tenant_id:
            return ctx_tenant_id

        # Default tenant
        return "default"

    def create_conversation(
        self,
        tenant_id: str,
        user_id: str,
        title: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create conversation (multi-tenant support)

        Args:
            tenant_id: Tenant ID
            user_id: User ID
            title: Conversation title, if None will auto-generate after first message

        Returns:
            Conversation info dict
        """
        db = self.get_db()
        if not db:
            return None

        try:
            from app.services.metadata import Conversation

            # If no title provided, use default title
            if title is None:
                title = "New conversation"

            conversation = Conversation(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                user_id=user_id,
                title=title
            )
            db.add(conversation)
            db.commit()

            logger.info(f"Conversation created: {conversation.id} (tenant: {tenant_id}, user: {user_id})")

            return {
                "id": conversation.id,
                "tenant_id": conversation.tenant_id,
                "user_id": conversation.user_id,
                "title": conversation.title,
                "is_archived": conversation.is_archived,
                "tags": json.loads(conversation.tags) if conversation.tags else [],
                "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
                "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None
            }
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create conversation: {e}")
            return None
        finally:
            db.close()

    def update_conversation_title(
        self,
        conv_id: str,
        title: str,
        tenant_id: str = None
    ) -> bool:
        """
        Update conversation title

        Args:
            conv_id: Conversation ID
            title: New title
            tenant_id: Tenant ID

        Returns:
            Success status
        """
        db = self.get_db()
        if not db:
            return False

        tenant_id = self._get_tenant_id(tenant_id)

        try:
            from app.services.metadata import Conversation

            conversation = db.query(Conversation).filter(
                Conversation.id == conv_id,
                Conversation.tenant_id == tenant_id
            ).first()

            if conversation:
                conversation.title = title
                conversation.updated_at = datetime.utcnow()
                db.commit()
                logger.info(f"Conversation title updated: {conv_id} -> {title}")
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update conversation title: {e}")
            return False
        finally:
            db.close()

    def list_conversations(
        self,
        tenant_id: str,
        user_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List user conversations (multi-tenant support)

        Args:
            tenant_id: Tenant ID
            user_id: User ID
            limit: Result count limit

        Returns:
            List of conversations
        """
        db = self.get_db()
        if not db:
            return []

        try:
            from app.services.metadata import Conversation

            conversations = db.query(Conversation).filter(
                Conversation.tenant_id == tenant_id,
                Conversation.user_id == user_id
            ).order_by(
                Conversation.updated_at.desc()
            ).limit(limit).all()

            return [
                {
                    "id": conv.id,
                    "tenant_id": conv.tenant_id,
                    "user_id": conv.user_id,
                    "title": conv.title,
                    "is_archived": conv.is_archived,
                    "tags": json.loads(conv.tags) if conv.tags else [],
                    "created_at": conv.created_at.isoformat() if conv.created_at else None,
                    "updated_at": conv.updated_at.isoformat() if conv.updated_at else None
                }
                for conv in conversations
            ]
        except Exception as e:
            logger.error(f"Failed to list conversations: {e}")
            return []
        finally:
            db.close()

    def get_conversation(
        self,
        conv_id: str,
        tenant_id: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get conversation info (multi-tenant support)

        Args:
            conv_id: Conversation ID
            tenant_id: Tenant ID

        Returns:
            Conversation info
        """
        db = self.get_db()
        if not db:
            return None

        tenant_id = self._get_tenant_id(tenant_id)

        try:
            from app.services.metadata import Conversation

            conversation = db.query(Conversation).filter(
                Conversation.id == conv_id,
                Conversation.tenant_id == tenant_id
            ).first()

            if conversation:
                return {
                    "id": conversation.id,
                    "tenant_id": conversation.tenant_id,
                    "user_id": conversation.user_id,
                    "title": conversation.title,
                    "is_archived": conversation.is_archived,
                    "tags": json.loads(conversation.tags) if conversation.tags else [],
                    "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
                    "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None
                }
            return None
        finally:
            db.close()

    def add_message(
        self,
        conv_id: str,
        role: str,
        content: str,
        tenant_id: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Add message to conversation (multi-tenant support)

        Args:
            conv_id: Conversation ID
            role: Role ('user' or 'assistant')
            content: Message content
            tenant_id: Tenant ID

        Returns:
            Message info
        """
        db = self.get_db()
        if not db:
            return None

        tenant_id = self._get_tenant_id(tenant_id)

        try:
            from app.services.metadata import ChatMessage, Conversation

            # Verify conversation exists and belongs to tenant
            conversation = db.query(Conversation).filter(
                Conversation.id == conv_id,
                Conversation.tenant_id == tenant_id
            ).first()

            if not conversation:
                logger.error(f"Conversation not found or does not belong to tenant: {conv_id}")
                return None

            message = ChatMessage(
                id=str(uuid.uuid4()),
                conversation_id=conv_id,
                role=role,
                content=content
            )
            db.add(message)

            # Update conversation's updated_at
            conversation.updated_at = datetime.utcnow()

            db.commit()

            logger.info(f"Message added: {message.id} (conversation: {conv_id}, role: {role})")

            # If this is first user message and title is "New conversation", auto-update title
            if role == 'user' and conversation.title == "New conversation":
                messages_count = db.query(ChatMessage).filter(
                    ChatMessage.conversation_id == conv_id
                ).count()
                if messages_count == 1:
                    # Use first 20 characters of user message as title
                    auto_title = content[:20] + "..." if len(content) > 20 else content
                    conversation.title = auto_title
                    db.commit()
                    logger.info(f"Auto-updated conversation title: {conv_id} -> {auto_title}")

            return {
                "id": message.id,
                "conversation_id": message.conversation_id,
                "role": message.role,
                "content": message.content,
                "created_at": message.created_at.isoformat() if message.created_at else None
            }
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to add message: {e}")
            return None
        finally:
            db.close()

    def get_messages(
        self,
        conv_id: str,
        tenant_id: str = None
    ) -> List[Dict[str, Any]]:
        """
        Get all messages of a conversation (multi-tenant support)

        Args:
            conv_id: Conversation ID
            tenant_id: Tenant ID

        Returns:
            List of messages
        """
        db = self.get_db()
        if not db:
            return []

        tenant_id = self._get_tenant_id(tenant_id)

        try:
            from app.services.metadata import ChatMessage, Conversation

            # Verify conversation exists and belongs to tenant
            conversation = db.query(Conversation).filter(
                Conversation.id == conv_id,
                Conversation.tenant_id == tenant_id
            ).first()

            if not conversation:
                logger.error(f"Conversation not found or does not belong to tenant: {conv_id}")
                return []

            messages = db.query(ChatMessage).filter(
                ChatMessage.conversation_id == conv_id
            ).order_by(
                ChatMessage.created_at.asc()
            ).all()

            return [
                {
                    "id": msg.id,
                    "conversation_id": msg.conversation_id,
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat() if msg.created_at else None
                }
                for msg in messages
            ]
        except Exception as e:
            logger.error(f"Failed to get messages: {e}")
            return []
        finally:
            db.close()

    def delete_conversation(
        self,
        conv_id: str,
        tenant_id: str = None
    ) -> bool:
        """
        Delete conversation and all its messages (multi-tenant support)

        Args:
            conv_id: Conversation ID
            tenant_id: Tenant ID

        Returns:
            Success status
        """
        db = self.get_db()
        if not db:
            return False

        tenant_id = self._get_tenant_id(tenant_id)

        try:
            from app.services.metadata import Conversation, ChatMessage

            # Verify conversation exists and belongs to tenant
            conversation = db.query(Conversation).filter(
                Conversation.id == conv_id,
                Conversation.tenant_id == tenant_id
            ).first()

            if not conversation:
                logger.error(f"Conversation not found or does not belong to tenant: {conv_id}")
                return False

            # Delete all messages
            db.query(ChatMessage).filter(
                ChatMessage.conversation_id == conv_id
            ).delete()

            # Delete conversation
            db.delete(conversation)
            db.commit()

            logger.info(f"Conversation deleted: {conv_id} (tenant: {tenant_id})")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to delete conversation: {e}")
            return False
        finally:
            db.close()

    def update_conversation_archive(
        self,
        conv_id: str,
        is_archived: bool,
        tenant_id: str = None
    ) -> bool:
        """
        Update conversation archive status

        Args:
            conv_id: Conversation ID
            is_archived: Whether archived
            tenant_id: Tenant ID

        Returns:
            Success status
        """
        db = self.get_db()
        if not db:
            return False

        tenant_id = self._get_tenant_id(tenant_id)

        try:
            from app.services.metadata import Conversation

            conversation = db.query(Conversation).filter(
                Conversation.id == conv_id,
                Conversation.tenant_id == tenant_id
            ).first()

            if conversation:
                conversation.is_archived = is_archived
                conversation.updated_at = datetime.utcnow()
                db.commit()
                logger.info(f"Conversation archive status updated: {conv_id} -> {is_archived}")
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update conversation archive status: {e}")
            return False
        finally:
            db.close()

    def update_conversation_tags(
        self,
        conv_id: str,
        tags: List[str],
        tenant_id: str = None
    ) -> bool:
        """
        Update conversation tags

        Args:
            conv_id: Conversation ID
            tags: Tag list
            tenant_id: Tenant ID

        Returns:
            Success status
        """
        db = self.get_db()
        if not db:
            return False

        tenant_id = self._get_tenant_id(tenant_id)

        try:
            from app.services.metadata import Conversation
            import json

            conversation = db.query(Conversation).filter(
                Conversation.id == conv_id,
                Conversation.tenant_id == tenant_id
            ).first()

            if conversation:
                conversation.tags = json.dumps(tags)
                conversation.updated_at = datetime.utcnow()
                db.commit()
                logger.info(f"Conversation tags updated: {conv_id} -> {tags}")
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update conversation tags: {e}")
            return False
        finally:
            db.close()


# Singleton
conversation_service = ConversationService()
