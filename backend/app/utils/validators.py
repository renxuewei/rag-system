"""
Input validation and security module
Validates user input and prevents common security threats
"""

import re
import html
import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, validator, constr, conint
from enum import Enum

logger = logging.getLogger(__name__)


class SecurityLevel(str, Enum):
    """Security level"""
    STRICT = "strict"      # Strict mode, minimum allowed input
    MODERATE = "moderate"  # Moderate mode, balance between security and usability
    LENIENT = "lenient"    # Lenient mode, allows more input


class InputValidator:
    """
    Input validator
    Provides common input validation and security checks
    """

    # Allowed file extensions
    ALLOWED_FILE_EXTENSIONS = [
        '.pdf', '.docx', '.doc', '.txt', '.md',
        '.pptx', '.ppt', '.xlsx', '.xls',
        '.json', '.xml', '.csv'
    ]

    # Dangerous SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r"(?i)\b(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|EXEC|UNION)\b",
        r"(?i)\b(OR|AND)\s+\d+\s*=\s*\d+",
        r"(?i)(;|\-\-|\/\*|\*\/)",
        r"(?i)(xp_|sp_)\w+",
    ]

    # XSS patterns
    XSS_PATTERNS = [
        r"<script.*?>.*?</script>",
        r"javascript:",
        r"on\w+\s*=",
        r"fromCharCode",
        r"eval\s*\(",
    ]

    # Dangerous command injection patterns
    COMMAND_INJECTION_PATTERNS = [
        r"[;&|`$(){}\[\]<>]",
        r"\|\|",
        r"&&",
        r"`.*`",
    ]

    @classmethod
    def validate_filename(cls, filename: str, max_length: int = 255) -> bool:
        """
        Validate if filename is safe

        Args:
            filename: Filename
            max_length: Maximum length

        Returns:
            Whether safe
        """
        if not filename or len(filename) > max_length:
            return False

        # Check path traversal
        if ".." in filename or "/" in filename or "\\" in filename:
            return False

        # Check file extension
        if not any(filename.lower().endswith(ext) for ext in cls.ALLOWED_FILE_EXTENSIONS):
            return False

        return True

    @classmethod
    def validate_query(cls, query: str, max_length: int = 1000) -> bool:
        """
        Validate if query string is safe

        Args:
            query: Query string
            max_length: Maximum length

        Returns:
            Whether safe
        """
        if not query or len(query) > max_length:
            return False

        # Check SQL injection
        for pattern in cls.SQL_INJECTION_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                logger.warning(f"Detected SQL injection pattern: {pattern}")
                return False

        # Check XSS
        for pattern in cls.XSS_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                logger.warning(f"Detected XSS pattern: {pattern}")
                return False

        return True

    @classmethod
    def validate_email(cls, email: str) -> bool:
        """
        Validate email address format

        Args:
            email: Email address

        Returns:
            Whether valid
        """
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    @classmethod
    def sanitize_html(cls, html_content: str) -> str:
        """
        Sanitize HTML content to prevent XSS attacks

        Args:
            html_content: HTML content

        Returns:
            Sanitized HTML
        """
        # Escape HTML special characters
        sanitized = html.escape(html_content)

        # Remove dangerous tags
        dangerous_tags = ['<script', '</script', '<iframe', '</iframe', '<object', '</object']
        for tag in dangerous_tags:
            sanitized = re.sub(re.escape(tag), '', sanitized, flags=re.IGNORECASE)

        return sanitized

    @classmethod
    def validate_json(cls, json_str: str) -> bool:
        """
        Validate if JSON string is valid

        Args:
            json_str: JSON string

        Returns:
            Whether valid
        """
        import json
        try:
            json.loads(json_str)
            return True
        except (json.JSONDecodeError, ValueError):
            return False

    @classmethod
    def validate_top_k(cls, top_k: int) -> bool:
        """
        Validate top_k parameter

        Args:
            top_k: Number of documents to return

        Returns:
            Whether valid
        """
        return 1 <= top_k <= 100

    @classmethod
    def validate_chunk_size(cls, chunk_size: int) -> bool:
        """
        Validate chunk size

        Args:
            chunk_size: Chunk size

        Returns:
            Whether valid
        """
        return 100 <= chunk_size <= 2000

    @classmethod
    def validate_password(cls, password: str, min_length: int = 8) -> tuple[bool, Optional[str]]:
        """
        Validate password strength

        Args:
            password: Password
            min_length: Minimum length

        Returns:
            (Whether valid, Error message)
        """
        if len(password) < min_length:
            return False, f"Password must be at least {min_length} characters long"

        # Check if contains digit
        if not re.search(r"\d", password):
            return False, "Password must contain at least one digit"

        # Check if contains uppercase letter
        if not re.search(r"[A-Z]", password):
            return False, "Password must contain at least one uppercase letter"

        # Check if contains lowercase letter
        if not re.search(r"[a-z]", password):
            return False, "Password must contain at least one lowercase letter"

        # Check if contains special character
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            return False, "Password must contain at least one special character"

        return True, None


class DocumentUploadValidator(BaseModel):
    """Document upload validation"""

    filename: constr(min_length=1, max_length=255)
    file_size: conint(ge=1, le=10 * 1024 * 1024)  # Maximum 10MB

    @validator('filename')
    def validate_filename(cls, v):
        """Validate filename"""
        if not InputValidator.validate_filename(v):
            raise ValueError("Invalid filename format or unsupported file type")
        return v


class QueryValidator(BaseModel):
    """Query validation"""

    query: constr(min_length=1, max_length=1000)
    top_k: conint(ge=1, le=100) = 5
    filters: Dict[str, Any] = {}

    @validator('query')
    def validate_query(cls, v):
        """Validate query string"""
        if not InputValidator.validate_query(v):
            raise ValueError("Query string contains unsafe content")
        return v

    @validator('top_k')
    def validate_top_k(cls, v):
        """Validate top_k"""
        if not InputValidator.validate_top_k(v):
            raise ValueError("top_k must be between 1 and 100")
        return v

    @validator('filters')
    def validate_filters(cls, v):
        """Validate filters"""
        if not isinstance(v, dict):
            raise ValueError("filters must be a dictionary")

        # Check if filter keys are safe
        for key in v.keys():
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', key):
                raise ValueError(f"Filter key '{key}' has invalid format")

        return v


class LoginValidator(BaseModel):
    """Login validation"""

    username: constr(min_length=3, max_length=50)
    password: constr(min_length=8, max_length=100)

    @validator('username')
    def validate_username(cls, v):
        """Validate username"""
        # Only allow letters, numbers, underscores
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError("Username can only contain letters, numbers, and underscores")
        return v

    @validator('password')
    def validate_password(cls, v):
        """Validate password"""
        is_valid, error_msg = InputValidator.validate_password(v)
        if not is_valid:
            raise ValueError(error_msg)
        return v


class SecurityHeaders:
    """
    Security response headers
    """

    @staticmethod
    def get_headers() -> Dict[str, str]:
        """
        Get security response headers

        Returns:
            Response headers dictionary
        """
        return {
            # Prevent clickjacking
            "X-Frame-Options": "DENY",

            # Prevent MIME type sniffing
            "X-Content-Type-Options": "nosniff",

            # Enable browser XSS protection
            "X-XSS-Protection": "1; mode=block",

            # Content security policy
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self'; "
                "connect-src 'self';"
            ),

            # Strict transport security (HTTPS only)
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",

            # Referrer policy
            "Referrer-Policy": "strict-origin-when-cross-origin",

            # Permissions policy
            "Permissions-Policy": (
                "geolocation=(), microphone=(), camera=(), "
                "payment=(), usb=(), magnetometer=(), gyroscope=()"
            ),
        }


def mask_sensitive_data(data: Dict[str, Any], sensitive_keys: List[str]) -> Dict[str, Any]:
    """
    Mask sensitive data

    Args:
        data: Original data
        sensitive_keys: List of sensitive field names

    Returns:
        Masked data
    """
    masked_data = data.copy()

    for key in sensitive_keys:
        if key in masked_data:
            value = str(masked_data[key])
            # Keep first 4 characters, replace rest with *
            if len(value) > 4:
                masked_data[key] = value[:4] + "*" * (len(value) - 4)
            else:
                masked_data[key] = "*" * len(value)

    return masked_data


def log_security_event(event_type: str, details: Dict[str, Any], request_ip: Optional[str] = None):
    """
    Log security event

    Args:
        event_type: Event type
        details: Event details
        request_ip: Request IP
    """
    log_data = {
        "event_type": event_type,
        "timestamp": str(__import__('datetime').datetime.utcnow()),
        "details": details,
        "request_ip": request_ip
    }

    logger.warning(f"Security Event: {event_type}", extra={"security_event": log_data})
