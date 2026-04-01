"""
Audit logging module
Uses PostgreSQL for persistence, supports multi-tenant
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session
import json
import uuid
import logging

logger = logging.getLogger(__name__)


class AuditService:
    """Audit logging service (database persistence)"""

    def get_db(self) -> Optional[Session]:
        from app.services.metadata import metadata_service
        if not metadata_service.SessionLocal:
            return None
        return metadata_service.SessionLocal()

    def _write_log(self, log_data: Dict[str, Any]):
        db = self.get_db()
        if not db:
            logger.warning("Audit log write failed: database unavailable")
            return

        try:
            from app.services.metadata import AuditLog

            extra_fields = {}
            reserved = {"action", "user_id", "username", "ip_address", "tenant_id", "details"}
            for k, v in log_data.items():
                if k not in reserved and k != "id" and k != "created_at":
                    extra_fields[k] = v

            row = AuditLog(
                id=log_data.get("id") or str(uuid.uuid4()),
                action=log_data.get("action", "unknown"),
                user_id=log_data.get("user_id"),
                username=log_data.get("username"),
                ip_address=log_data.get("ip_address"),
                tenant_id=log_data.get("tenant_id", "default"),
                details=log_data.get("details"),
                extra=json.dumps(extra_fields, ensure_ascii=False) if extra_fields else None,
                created_at=datetime.utcnow(),
            )
            db.add(row)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Audit log write failed: {e}")
        finally:
            db.close()

    def log_query(
        self,
        user_id: str,
        query: str,
        sources: List[Dict] = None,
        response_time: float = None,
        cached: bool = False,
        username: str = None,
        ip_address: str = None,
        tenant_id: str = "default",
    ):
        self._write_log({
            "action": "query",
            "user_id": user_id,
            "username": username,
            "ip_address": ip_address,
            "tenant_id": tenant_id,
            "details": query,
            "sources_count": len(sources) if sources else 0,
            "response_time": round(response_time, 3) if response_time else None,
            "cached": cached,
        })

    def log_document_upload(
        self,
        user_id: str,
        filename: str,
        file_size: int,
        chunks_count: int,
        success: bool = True,
        username: str = None,
        ip_address: str = None,
        tenant_id: str = "default",
    ):
        self._write_log({
            "action": "document_upload",
            "user_id": user_id,
            "username": username,
            "ip_address": ip_address,
            "tenant_id": tenant_id,
            "details": f"filename={filename}, size={file_size}, chunks={chunks_count}",
            "filename": filename,
            "file_size": file_size,
            "chunks_count": chunks_count,
            "success": success,
        })

    def log_document_delete(
        self,
        user_id: str,
        doc_id: str,
        success: bool = True,
        username: str = None,
        ip_address: str = None,
        tenant_id: str = "default",
    ):
        self._write_log({
            "action": "document_delete",
            "user_id": user_id,
            "username": username,
            "ip_address": ip_address,
            "tenant_id": tenant_id,
            "details": f"doc_id={doc_id}",
            "doc_id": doc_id,
            "success": success,
        })

    def log_user_login(
        self,
        user_id: str,
        username: str,
        ip_address: str = None,
        success: bool = True,
        tenant_id: str = "default",
    ):
        self._write_log({
            "action": "login",
            "user_id": user_id,
            "username": username,
            "ip_address": ip_address,
            "tenant_id": tenant_id,
            "details": f"login {'success' if success else 'failed'}",
            "success": success,
        })

    def log_error(
        self,
        user_id: str,
        error_type: str,
        error_message: str,
        details: Dict[str, Any] = None,
        username: str = None,
        ip_address: str = None,
        tenant_id: str = "default",
    ):
        self._write_log({
            "action": "error",
            "user_id": user_id,
            "username": username,
            "ip_address": ip_address,
            "tenant_id": tenant_id,
            "details": f"{error_type}: {error_message}",
            "error_type": error_type,
            "error_message": error_message,
        })

    def list_audit_logs(
        self,
        page: int = 1,
        page_size: int = 20,
        user_id: str = None,
        action: str = None,
        tenant_id: str = None
    ) -> Dict[str, Any]:
        db = self.get_db()
        if not db:
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}

        try:
            from app.services.metadata import AuditLog

            q = db.query(AuditLog)
            if tenant_id:
                q = q.filter(AuditLog.tenant_id == tenant_id)
            if user_id:
                q = q.filter(AuditLog.user_id == user_id)
            if action:
                q = q.filter(AuditLog.action == action)

            total = q.count()
            total_pages = (total + page_size - 1) // page_size if total > 0 else 0
            skip = (page - 1) * page_size

            rows = q.order_by(AuditLog.created_at.desc()).offset(skip).limit(page_size).all()

            items = []
            for row in rows:
                extra = {}
                if row.extra:
                    try:
                        extra = json.loads(row.extra)
                    except (json.JSONDecodeError, TypeError):
                        pass
                items.append({
                    "id": row.id,
                    "action": row.action,
                    "user_id": row.user_id,
                    "username": row.username,
                    "ip_address": row.ip_address,
                    "tenant_id": row.tenant_id,
                    "details": row.details,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    **extra,
                })

            return {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
            }
        except Exception as e:
            logger.error(f"Query audit logs failed: {e}")
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}
        finally:
            db.close()


audit_service = AuditService()
