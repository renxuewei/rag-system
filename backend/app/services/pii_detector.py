"""
PII (Personally Identifiable Information) detection and masking service
Supports detection of sensitive information such as phone numbers, ID cards, email, bank cards, etc.
"""

from typing import List, Dict, Any, Optional, Tuple
import re
import logging

logger = logging.getLogger(__name__)


class PIIDetector:
    """PII detector"""
    
    def __init__(self):
        # PII pattern definitions
        self.patterns = {
            "phone": {
                # Chinese mobile number
                "pattern": r"(?:(?:\+|00)86)?1[3-9]\d{9}",
                "description": "Mobile phone number",
                "mask_type": "partial"  # partial: partial masking, full: complete masking
            },
            "id_card": {
                # Chinese ID card number
                "pattern": r"[1-9]\d{5}(?:18|19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]",
                "description": "ID card number",
                "mask_type": "partial"
            },
            "email": {
                # Email address
                "pattern": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                "description": "Email address",
                "mask_type": "partial"
            },
            "bank_card": {
                # Bank card number (16-19 digits)
                "pattern": r"\b\d{16,19}\b",
                "description": "Bank card number",
                "mask_type": "partial"
            },
            "passport": {
                # Passport number
                "pattern": r"[A-Za-z]\d{8}",
                "description": "Passport number",
                "mask_type": "partial"
            },
            "credit_card": {
                # Credit card number (with separator)
                "pattern": r"\b(?:\d{4}[-\s]){3}\d{4}\b",
                "description": "Credit card number",
                "mask_type": "partial"
            },
            "ip_address": {
                # IP address
                "pattern": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
                "description": "IP address",
                "mask_type": "partial"
            },
            "chinese_name": {
                # Chinese name (2-4 characters)
                "pattern": r"[\u4e00-\u9fa5]{2,4}",
                "description": "Chinese name",
                "mask_type": "full",
                "enabled": False  # Disabled by default, high false positive rate
            }
        }

        # Compile regex patterns
        self._compiled_patterns = {}
        for name, config in self.patterns.items():
            if config.get("enabled", True):
                self._compiled_patterns[name] = re.compile(config["pattern"])
    
    def detect(self, text: str) -> List[Dict[str, Any]]:
        """
        Detect PII in text

        Args:
            text: Text to detect

        Returns:
            List of PII with type, value, position
        """
        results = []

        for name, pattern in self._compiled_patterns.items():
            config = self.patterns[name]

            for match in pattern.finditer(text):
                value = match.group()
                results.append({
                    "type": name,
                    "description": config["description"],
                    "value": value,
                    "masked_value": self._mask_value(value, config["mask_type"]),
                    "start": match.start(),
                    "end": match.end(),
                    "mask_type": config["mask_type"]
                })

        # Sort by position
        results.sort(key=lambda x: x["start"])

        return results
    
    def _mask_value(self, value: str, mask_type: str) -> str:
        """
        Mask sensitive value

        Args:
            value: Original value
            mask_type: Mask type

        Returns:
            Masked value
        """
        if mask_type == "full":
            return "*" * len(value)

        # partial: retain some characters
        length = len(value)

        if length <= 4:
            return value[0] + "*" * (length - 1)
        elif length <= 8:
            return value[:2] + "*" * (length - 4) + value[-2:]
        else:
            return value[:3] + "*" * (length - 6) + value[-3:]
    
    def mask_text(self, text: str) -> str:
        """
        Mask PII in text

        Args:
            text: Original text

        Returns:
            Masked text
        """
        pii_list = self.detect(text)

        if not pii_list:
            return text

        # Replace from back to front to avoid position offset
        result = list(text)

        for pii in reversed(pii_list):
            masked = pii["masked_value"]
            result[pii["start"]:pii["end"]] = list(masked)

        return "".join(result)
    
    def check_and_mask(self, text: str) -> Dict[str, Any]:
        """
        Detect and mask PII

        Args:
            text: Original text

        Returns:
            {
                "has_pii": bool,
                "masked_text": str,
                "pii_count": int,
                "pii_details": List[Dict]
            }
        """
        pii_list = self.detect(text)

        return {
            "has_pii": len(pii_list) > 0,
            "masked_text": self.mask_text(text),
            "pii_count": len(pii_list),
            "pii_details": [
                {
                    "type": p["type"],
                    "description": p["description"],
                    "masked_value": p["masked_value"]
                }
                for p in pii_list
            ]
        }
    
    def add_pattern(
        self,
        name: str,
        pattern: str,
        description: str = "",
        mask_type: str = "partial"
    ):
        """
        Add custom PII pattern

        Args:
            name: Pattern name
            pattern: Regular expression
            description: Description
            mask_type: Mask type
        """
        self.patterns[name] = {
            "pattern": pattern,
            "description": description,
            "mask_type": mask_type,
            "enabled": True
        }
        self._compiled_patterns[name] = re.compile(pattern)
        logger.info(f"Added PII pattern: {name}")
    
    def enable_pattern(self, name: str):
        """Enable pattern"""
        if name in self.patterns:
            self.patterns[name]["enabled"] = True
            self._compiled_patterns[name] = re.compile(self.patterns[name]["pattern"])

    def disable_pattern(self, name: str):
        """Disable pattern"""
        if name in self.patterns:
            self.patterns[name]["enabled"] = False
            self._compiled_patterns.pop(name, None)


class DataMasker:
    """Data masking utility class"""
    
    @staticmethod
    def mask_phone(phone: str) -> str:
        """Mask phone number: 138****8888"""
        if len(phone) >= 7:
            return phone[:3] + "****" + phone[-4:]
        return "*" * len(phone)

    @staticmethod
    def mask_id_card(id_card: str) -> str:
        """Mask ID card: 110***********1234"""
        if len(id_card) >= 14:
            return id_card[:3] + "***********" + id_card[-4:]
        return "*" * len(id_card)

    @staticmethod
    def mask_email(email: str) -> str:
        """Mask email: a***@example.com"""
        if "@" in email:
            parts = email.split("@")
            name = parts[0]
            domain = parts[1]
            if len(name) > 1:
                return name[0] + "***" + "@" + domain
        return "*" * len(email)

    @staticmethod
    def mask_bank_card(card: str) -> str:
        """Mask bank card: 6222****1234"""
        if len(card) >= 8:
            return card[:4] + "****" + card[-4:]
        return "*" * len(card)

    @staticmethod
    def mask_name(name: str) -> str:
        """Mask name: Zhang*"""
        if len(name) > 0:
            return name[0] + "*" * (len(name) - 1)
        return "*"
    
    @staticmethod
    def mask_dict(
        data: Dict[str, Any],
        sensitive_keys: List[str]
    ) -> Dict[str, Any]:
        """
        Mask sensitive fields in dictionary

        Args:
            data: Original data
            sensitive_keys: List of sensitive field names

        Returns:
            Masked data
        """
        result = data.copy()

        for key in sensitive_keys:
            if key in result:
                value = str(result[key])
                if len(value) > 4:
                    result[key] = value[:2] + "****" + value[-2:]
                else:
                    result[key] = "****"

        return result


# Singleton
pii_detector = PIIDetector()
data_masker = DataMasker()
