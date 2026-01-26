#!/usr/bin/env python3
"""
Base class for stateless medical coding plugins.
Plugins are pure functions that process medical data and return structured JSON.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
import json
import time


class MedicalCodingPlugin(ABC):
    """Base class for medical coding plugins - stateless and database-agnostic."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the plugin name (e.g., 'claude', 'codex')."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Return the plugin version."""
        pass

    @abstractmethod
    def process_batch(self, items: List[Dict[str, Any]], batch_size: int = 1) -> List[Dict[str, Any]]:
        """
        Process a batch of medical items and return structured results.

        Args:
            items: List of items to process, each containing 'code' and 'description'
            batch_size: Number of items to process simultaneously

        Returns:
            List of results with structured data for each item:
            [
                {
                    "item_id": "A00.0",
                    "input": "Original description",
                    "predicted_codes": ["A00.0", "A00.1"],
                    "success": True,
                    "response_time": 1.23,
                    "tokens_input": 45,
                    "tokens_output": 12,
                    "error": None
                },
                ...
            ]
        """
        pass

    def process_single(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single item. Default implementation calls process_batch with batch_size=1.

        Args:
            item: Single item containing 'code' and 'description'

        Returns:
            Result dictionary with structured data
        """
        results = self.process_batch([item], batch_size=1)
        return results[0] if results else None