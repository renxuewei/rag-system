"""
JWT authentication module
Supports multi-tenant context
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import jwt
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

from app.config import config

logger = logging.getLogger(__name__)

# Bearer Token authentication scheme
security = HTTPBearer(auto_error=False)


class AuthService:
    """Authentication service (supports multi-tenant)"""
    
    def __init__(
        self,
        secret_key: str = None,
        algorithm: str = None,
        expire_minutes: int = None
    ):
        self.secret_key = secret_key or config.JWT_SECRET_KEY
        self.algorithm = algorithm or config.JWT_ALGORITHM
        self.expire_minutes = expire_minutes or config.JWT_EXPIRE_MINUTES
    
    def create_token(
        self,
        user_id: str,
        username: str,
        role: str = "user",
        tenant_id: str = "default",
        extra_data: Dict[str, Any] = None
    ) -> str:
        """
        Create JWT Token (supports multi-tenant)
        Args:
            user_id: User ID
            username: Username
            role: Role
            tenant_id: Tenant ID
            extra_data: Extra data
        """
        # Build payload
        payload = {
            "user_id": user_id,
            "username": username,
            "role": role,
            "tenant_id": tenant_id,  # Add tenant ID
            "exp": datetime.utcnow() + timedelta(minutes=self.expire_minutes),
            "iat": datetime.utcnow()
        }
        
        # Add extra data
        if extra_data:
            payload.update(extra_data)
        
        # Generate Token
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        
        logger.info(f"Token created: user_id={user_id}, role={role}, tenant_id={tenant_id}")
        
        return token
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verify JWT Token
        Args:
            token: JWT Token
        Returns:
            Decoded payload
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")
    
    def check_permission(
        self,
        user: Dict[str, Any],
        required_role: str = "user"
    ) -> bool:
        """
        Check permission
        Args:
            user: User information
            required_role: Required role
        """
        user_role = user.get("role", "user")

        # Load role levels from database
        try:
            from app.services.metadata import metadata_service
            role_levels = metadata_service.get_role_levels()
        except Exception:
            role_levels = {"admin": 4, "doc_admin": 3, "user": 2, "guest": 1}

        user_level = role_levels.get(user_role, 0)
        required_level = role_levels.get(required_role, 0)

        return user_level >= required_level

    def require_role(self, required_role: str):
        """
        Role decorator (dependency injection)
        Args:
            required_role: Required role
        """
        async def role_checker(
            current_user: Dict[str, Any] = Depends(get_current_user)
        ):
            if not self.check_permission(current_user, required_role):
                raise HTTPException(
                    status_code=403,
                    detail=f"Insufficient permissions, requires {required_role} role"
                )
            return current_user

        return role_checker

    def require_tenant(self):
        """
        Tenant validation decorator (dependency injection)
        Ensure user belongs to specified tenant
        """
        async def tenant_checker(
            current_user: Dict[str, Any] = Depends(get_current_user)
        ):
            if not current_user.get("tenant_id"):
                raise HTTPException(
                    status_code=403,
                    detail="No tenant associated"
                )
            return current_user

        return tenant_checker


# ==================== Module-level dependency functions for FastAPI ====================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """
    Get current user (FastAPI dependency injection)
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="No authentication information provided")

    token = credentials.credentials
    payload = auth_service.verify_token(token)

    user_info = {
        "user_id": payload.get("user_id"),
        "username": payload.get("username"),
        "role": payload.get("role", "user"),
        "tenant_id": payload.get("tenant_id", "default")
    }

    # Set tenant context
    from app.services.tenant import set_tenant_id
    set_tenant_id(user_info["tenant_id"])

    return user_info


async def get_tenant_id(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> str:
    """
    Get current tenant ID (FastAPI dependency injection)
    """
    return current_user.get("tenant_id", "default")


# Utility function: get current tenant ID
def get_current_tenant_id() -> Optional[str]:
    """
    Get current request's tenant ID
    Priority: get from context, then from Token
    """
    from app.services.tenant import get_tenant_id
    return get_tenant_id()


# Singleton
auth_service = AuthService()
