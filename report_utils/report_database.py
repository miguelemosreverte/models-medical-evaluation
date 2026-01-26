"""
Database utility functions for medical coding report generation.
"""

import sqlite3
import json
from typing import Dict

DB_PATH = "medical_coding.db"


def get_database_stats() -> Dict:
    """Get statistics from the database."""
    stats = {
        'total_codes': 0,
        'processed_codes': 0,
        'total_cost': 0,
        'models': {}
    }

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Get total codes
        cursor.execute("SELECT COUNT(*) FROM icd10_codes")
        result = cursor.fetchone()
        stats['total_codes'] = result[0] if result else 0

        # Get processed codes
        cursor.execute("SELECT COUNT(DISTINCT code_id) FROM model_predictions")
        result = cursor.fetchone()
        stats['processed_codes'] = result[0] if result else 0

        # Get model stats
        cursor.execute("""
            SELECT model_name,
                   COUNT(*) as predictions,
                   AVG(confidence) as avg_confidence,
                   AVG(processing_time) as avg_time
            FROM model_predictions
            GROUP BY model_name
        """)

        for row in cursor.fetchall():
            stats['models'][row[0]] = {
                'predictions': row[1],
                'avg_confidence': row[2] or 0,
                'avg_time': row[3] or 0
            }

        conn.close()
    except:
        pass

    return stats


def get_chart_data() -> Dict:
    chart_data = {
        'claude': {'times': [], 'throughput': [], 'batch_size': []},
        'codex': {'times': [], 'throughput': [], 'batch_size': []},
        'claude_constrained': {'times': [], 'throughput': [], 'batch_size': []},
        'codex_constrained': {'times': [], 'throughput': [], 'batch_size': []}
    }

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Get combined data from batch_metrics (which has everything we need)
        for model in ['claude', 'codex', 'claude_constrained', 'codex_constrained']:
            cursor.execute("""
                SELECT
                    end_time,
                    (success_count + failure_count) as total_items,
                    CAST((julianday(end_time) - julianday(start_time)) * 24 * 60 AS REAL) as duration_minutes,
                    batch_size
                FROM batch_metrics
                WHERE model_name = ? AND end_time IS NOT NULL AND start_time IS NOT NULL
                ORDER BY end_time
            """, (model,))

            from datetime import datetime, timezone
            for row in cursor.fetchall():
                # Convert timestamp to JavaScript milliseconds
                # SQLite stores timestamps in UTC, so we need to parse them as UTC
                timestamp_str = row[0]
                dt = datetime.fromisoformat(timestamp_str)
                # Assume the datetime is in UTC since SQLite CURRENT_TIMESTAMP is UTC
                dt_utc = dt.replace(tzinfo=timezone.utc)
                # Convert to Unix timestamp (seconds since epoch), then to milliseconds
                js_timestamp = int(dt_utc.timestamp() * 1000)

                chart_data[model]['times'].append(js_timestamp)
                # Calculate throughput as items per minute
                total_items = row[1] or 0
                duration_minutes = row[2] or 1
                throughput_per_min = total_items / duration_minutes if duration_minutes > 0 else 0
                chart_data[model]['throughput'].append(throughput_per_min)
                chart_data[model]['batch_size'].append(int(row[3]) if row[3] else 10)

        conn.close()
    except Exception as e:
        # If no data, return empty arrays
        print(f"Warning: Could not load chart data: {e}")
        pass

    return chart_data


def calculate_model_metrics(model_name: str) -> dict:
    """Reusable helper method for metrics calculation.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Get predictions and ground truth
        cursor.execute("""
            SELECT mp.predicted_codes, ic.code
            FROM model_predictions mp
            JOIN icd10_codes ic ON mp.code_id = ic.id
            WHERE mp.model_name = ?
        """, (model_name,))

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return None

        # Calculate TP, FP, FN
        total_tp = 0
        total_fp = 0
        total_fn = 0

        for row in rows:
            predicted_codes_json = row[0]
            golden_code = row[1]

            # Parse predicted codes
            try:
                predicted_codes = json.loads(predicted_codes_json) if predicted_codes_json else []
            except:
                predicted_codes = []

            # Convert to sets for comparison
            predicted_set = set(predicted_codes)
            golden_set = {golden_code}

            # Calculate for this prediction
            tp = len(golden_set & predicted_set)
            fp = len(predicted_set - golden_set)
            fn = len(golden_set - predicted_set)

            total_tp += tp
            total_fp += fp
            total_fn += fn

        # Calculate metrics
        precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
        recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

        return {
            'precision': precision * 100,
            'recall': recall * 100,
            'f1': f1 * 100,
            'tp': total_tp,
            'fp': total_fp,
            'fn': total_fn,
            'total': len(rows)
        }

    except Exception as e:
        print(f"Error calculating metrics for {model_name}: {e}")
        return None

