"""
Sensitive word filtering service
Uses DFA algorithm for efficient sensitive word matching
"""

from typing import List, Dict, Any, Optional, Set
import logging
import re

logger = logging.getLogger(__name__)


class SensitiveWordFilter:
    """Sensitive word filter (DFA algorithm)"""
    
    def __init__(self):
        # DFA tree
        self._word_tree: Dict[str, Any] = {}

        # Default sensitive word library
        self._default_words = [
            # Political sensitive
            "Falun Gong", "June 4", "Tiananmen",
            # Pornography
            "pornography", "yellow", "nudity",
            # Violence
            "violence", "murder", "terrorist attack",
            # Gambling
            "gambling", "betting", "lottery",
            # Drugs
            "drugs", "drug use", "drug trafficking",
            # Fraud
            "fraud", "scammer", "pyramid scheme",
        ]

        # Custom sensitive words
        self._custom_words: Set[str] = set()

        # Replacement character
        self.replacement = "*"

        # Initialize
        self._build_tree(self._default_words)
    
    def _build_tree(self, words: List[str]):
        """
        Build DFA tree

        Args:
            words: List of sensitive words
        """
        for word in words:
            word = word.strip()
            if not word:
                continue

            node = self._word_tree
            for char in word:
                if char not in node:
                    node[char] = {}
                node = node[char]

            # Mark word end
            node["__is_end__"] = True
    
    def add_words(self, words: List[str]):
        """
        Add sensitive words

        Args:
            words: List of sensitive words
        """
        for word in words:
            word = word.strip()
            if word and word not in self._custom_words:
                self._custom_words.add(word)

        self._build_tree(words)
        logger.info(f"Added {len(words)} sensitive words")
    
    def remove_words(self, words: List[str]):
        """
        Remove sensitive words (only from custom word library)

        Args:
            words: List of sensitive words
        """
        for word in words:
            self._custom_words.discard(word)
        logger.info(f"Removed {len(words)} sensitive words")
    
    def contains_sensitive(self, text: str) -> bool:
        """
        Check if text contains sensitive words

        Args:
            text: Text to check

        Returns:
            Whether contains sensitive words
        """
        for i in range(len(text)):
            node = self._word_tree
            j = i

            while j < len(text) and text[j] in node:
                node = node[text[j]]
                j += 1

                if node.get("__is_end__"):
                    return True

        return False
    
    def find_sensitive_words(self, text: str) -> List[Dict[str, Any]]:
        """
        Find sensitive words in text

        Args:
            text: Text to check

        Returns:
            List of sensitive words with position information
        """
        results = []

        for i in range(len(text)):
            node = self._word_tree
            j = i
            matched_word = ""

            while j < len(text) and text[j] in node:
                node = node[text[j]]
                matched_word += text[j]
                j += 1

                if node.get("__is_end__"):
                    results.append({
                        "word": matched_word,
                        "start": i,
                        "end": j
                    })

        return results
    
    def filter_text(self, text: str, replacement: str = None) -> str:
        """
        Filter sensitive words in text

        Args:
            text: Original text
            replacement: Replacement character (default uses self.replacement)

        Returns:
            Filtered text
        """
        replacement = replacement or self.replacement
        result = list(text)

        sensitive_words = self.find_sensitive_words(text)

        for item in sensitive_words:
            for i in range(item["start"], item["end"]):
                result[i] = replacement

        return "".join(result)
    
    def check_and_filter(self, text: str) -> Dict[str, Any]:
        """
        Check and filter sensitive words

        Args:
            text: Original text

        Returns:
            {
                "has_sensitive": bool,
                "filtered_text": str,
                "sensitive_words": List[str],
                "count": int
            }
        """
        sensitive_words = self.find_sensitive_words(text)
        unique_words = list(set(item["word"] for item in sensitive_words))

        return {
            "has_sensitive": len(sensitive_words) > 0,
            "filtered_text": self.filter_text(text),
            "sensitive_words": unique_words,
            "count": len(sensitive_words)
        }
    
    def get_all_words(self) -> List[str]:
        """Get all sensitive words"""
        return list(set(self._default_words) | self._custom_words)
    
    def load_from_file(self, file_path: str):
        """
        Load sensitive words from file (one word per line)

        Args:
            file_path: File path
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                words = [line.strip() for line in f if line.strip()]
            self.add_words(words)
            logger.info(f"Loaded {len(words)} sensitive words from file: {file_path}")
        except Exception as e:
            logger.error(f"Failed to load sensitive words file: {e}")
    
    def save_to_file(self, file_path: str):
        """
        Save sensitive words to file

        Args:
            file_path: File path
        """
        try:
            words = self.get_all_words()
            with open(file_path, "w", encoding="utf-8") as f:
                for word in words:
                    f.write(word + "\n")
            logger.info(f"Saved {len(words)} sensitive words to: {file_path}")
        except Exception as e:
            logger.error(f"Failed to save sensitive words file: {e}")


# Singleton
sensitive_filter = SensitiveWordFilter()
