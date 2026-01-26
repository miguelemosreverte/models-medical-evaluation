#!/usr/bin/env python3
"""
Adapter to bridge stateless plugins with the experiment framework.
"""

import time
from datetime import datetime
from typing import List, Dict, Any
from collections import namedtuple

# Simple metrics object
BatchMetrics = namedtuple('BatchMetrics', ['items_attempted', 'items_succeeded', 'throughput'])


class PluginAdapter:
    """Adapts stateless plugins to work with the experiment framework."""

    def __init__(self, plugin_instance, db):
        """Initialize the adapter with a stateless plugin and database."""
        self.plugin = plugin_instance
        self.db = db
        self.name = self.plugin.name
        self.version = self.plugin.version

        # State for batch processing
        self.current_batch_size = 1  # Start conservatively at 1
        self.items_processed = 0
        self.max_items = 100  # Default to 100 items
        self.start_time = None

        # Metrics tracking
        self.total_attempted = 0
        self.total_succeeded = 0
        self.response_times = []
        self.errors = []

        # Adaptive batch sizing
        self.consecutive_successes = 0
        self.consecutive_failures = 0
        self.max_batch_size = 20  # Cap maximum batch size

        # Current batch management - resume from where we left off
        self.current_offset = self._get_processed_count()

    def is_complete(self) -> bool:
        """Check if we've processed all items or hit the limit."""
        return self.items_processed >= self.max_items or self.current_offset >= self._get_total_items()

    def get_adaptive_batch_size(self) -> int:
        """Return the current adaptive batch size."""
        return self.current_batch_size

    def get_next_batch(self, batch_size: int) -> List[Dict[str, Any]]:
        """Get the next batch of items from the database."""
        cursor = self.db.conn.cursor()

        # Get items with offset
        cursor.execute("""
            SELECT code, description
            FROM icd10_codes
            LIMIT ? OFFSET ?
        """, (batch_size, self.current_offset))

        items = []
        for row in cursor.fetchall():
            items.append({
                'code': row[0],
                'description': row[1]
            })

        self.current_offset += len(items)
        return items

    def process_batch(self, batch: List[Dict[str, Any]]) -> BatchMetrics:
        """Process a batch using the stateless plugin and track metrics."""
        if not batch:
            return BatchMetrics(0, 0, 0.0)

        batch_start = time.time()

        # Start batch tracking in database
        batch_id = self.db.start_batch(self.name, self.current_batch_size)

        # Call the stateless plugin
        results = self.plugin.process_batch(batch, self.current_batch_size)

        # Track metrics
        items_attempted = len(batch)
        items_succeeded = sum(1 for r in results if r.get('success', False))

        # Calculate token totals for this batch
        total_input_tokens = sum(r.get('tokens_input', 0) for r in results)
        total_output_tokens = sum(r.get('tokens_output', 0) for r in results)

        self.total_attempted += items_attempted
        self.total_succeeded += items_succeeded
        self.items_processed += items_attempted

        # Store response times
        for result in results:
            if 'response_time' in result:
                self.response_times.append(result['response_time'])
            if result.get('error'):
                self.errors.append(result['error'])

        # Save results to database and JSONL
        self._save_results(results, batch_id)

        # Update batch metrics in database
        self.db.update_batch_metrics(
            batch_id,
            items_succeeded,
            items_attempted - items_succeeded,  # failures
            total_input_tokens,
            total_output_tokens
        )

        # Adjust batch size based on success rate
        success_rate = items_succeeded / items_attempted if items_attempted > 0 else 0
        self._adjust_batch_size(success_rate)

        batch_time = time.time() - batch_start
        throughput = items_attempted / batch_time if batch_time > 0 else 0

        return BatchMetrics(items_attempted, items_succeeded, throughput)

    def get_comprehensive_metrics(self) -> Dict[str, Any]:
        """Get comprehensive metrics for the experiment."""
        if not self.start_time:
            return {}

        elapsed = (datetime.now() - self.start_time).total_seconds()

        return {
            'experiment': {
                'name': self.name,
                'version': self.version,
                'total_elapsed_seconds': elapsed,
                'active_time_seconds': elapsed,  # Simplified for now
                'availability_percentage': 100.0  # Simplified for now
            },
            'throughput': {
                'effective_items_per_second': self.total_attempted / elapsed if elapsed > 0 else 0,
                'peak_throughput': max(self.response_times) if self.response_times else 0,
                'sustained_throughput': self.total_attempted / elapsed if elapsed > 0 else 0
            },
            'latency': {
                'p50': self._percentile(self.response_times, 50),
                'p90': self._percentile(self.response_times, 90),
                'p99': self._percentile(self.response_times, 99)
            },
            'errors': {
                'total_errors': len(self.errors),
                'error_rate': len(self.errors) / self.total_attempted if self.total_attempted > 0 else 0
            },
            'throttling': {
                'throttle_events': 0,  # Simplified
                'rate_limit_errors': sum(1 for e in self.errors if 'rate' in str(e).lower())
            }
        }

    def _get_total_items(self) -> int:
        """Get total number of items in database."""
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM icd10_codes")
        return cursor.fetchone()[0]

    def _get_processed_count(self) -> int:
        """Get the number of items already processed by this model."""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT COUNT(DISTINCT code_id)
                FROM model_predictions
                WHERE model_name = ?
            """, (self.name,))
            result = cursor.fetchone()
            return result[0] if result else 0
        except Exception as e:
            # Table doesn't exist yet, starting fresh
            print(f"[{self.name}] Warning: Could not get processed count: {e}")
            return 0

    def _save_results(self, results: List[Dict[str, Any]], batch_id: str):
        """Save results to both database and JSONL files."""
        import json

        # Save to JSONL files in the format expected by evaluate_models.py
        output_file = f"medical_coding_dataset.{self.name}.jsonl"
        with open(output_file, 'a') as f:
            for result in results:
                # Transform to expected format for JSONL
                entry = {
                    "text": result.get("input", ""),
                    "golden_codes": [result.get("item_id", "")],  # item_id is the original code
                    "codes": result.get("predicted_codes", [])
                }
                json.dump(entry, f)
                f.write('\n')

        # Save to database
        cursor = self.db.conn.cursor()
        for result in results:
            # Get code_id from the icd10_codes table
            code = result.get("item_id", "")
            cursor.execute("SELECT id FROM icd10_codes WHERE code = ?", (code,))
            row = cursor.fetchone()

            if row:
                code_id = row[0]

                # Save prediction to database
                self.db.save_prediction_with_tokens(
                    code_id=code_id,
                    model=self.name,
                    model_version=self.version,
                    description=result.get("input", ""),
                    predicted_codes=result.get("predicted_codes", []),
                    confidence=1.0 if result.get("success", False) else 0.0,
                    processing_time=result.get("response_time", 0.0),
                    input_tokens=result.get("tokens_input", 0),
                    output_tokens=result.get("tokens_output", 0),
                    batch_id=batch_id,
                    batch_size=self.current_batch_size
                )

    def _adjust_batch_size(self, success_rate: float):
        """Adjust batch size based on success rate with aggressive failure response."""
        old_batch_size = self.current_batch_size

        # Very aggressive reduction on poor performance
        if success_rate < 0.5:
            # Immediate halving on terrible success rate
            self.current_batch_size = max(1, self.current_batch_size // 2)
            self.consecutive_failures = 0
            self.consecutive_successes = 0
        elif success_rate < 0.7:
            # Quick reduction on mediocre performance
            self.consecutive_failures += 1
            self.consecutive_successes = 0
            if self.consecutive_failures >= 1:  # React after just 1 failure
                self.current_batch_size = max(1, self.current_batch_size - 2)
                self.consecutive_failures = 0
        elif success_rate >= 0.9:
            # Conservative increase only with very high success
            self.consecutive_successes += 1
            self.consecutive_failures = 0
            if self.consecutive_successes >= 3:  # Need 3 consecutive wins
                self.current_batch_size = min(self.max_batch_size, self.current_batch_size + 1)
                self.consecutive_successes = 0
        else:
            # 70-90% success: maintain current batch size
            self.consecutive_successes = 0
            self.consecutive_failures = 0

        # Record batch size change in time series
        if self.current_batch_size != old_batch_size:
            self.db.record_time_series(self.name, 'batch_size', self.current_batch_size)

    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of data."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]