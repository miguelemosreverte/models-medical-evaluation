#!/usr/bin/env python3
"""
Enhanced database manager with token tracking, batch metrics, and time series data.
"""

import sqlite3
import json
import csv
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import time

class MedicalCodingDB:
    def __init__(self, db_path="medical_coding.db"):
        self.db_path = db_path
        self.conn = None
        self.init_database()

    def init_database(self):
        """Initialize database with enhanced schema."""
        self.conn = sqlite3.connect(self.db_path, timeout=30.0)
        self.conn.row_factory = sqlite3.Row  # Enable column access by name

        # Enable WAL mode for concurrent read/write access
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.conn.execute('PRAGMA busy_timeout=30000')  # 30 second timeout

        cursor = self.conn.cursor()

        # Create tables with enhanced schema
        cursor.executescript("""
            -- Catalog of all ICD-10 codes
            CREATE TABLE IF NOT EXISTS icd10_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                description TEXT NOT NULL,
                category TEXT,
                country TEXT DEFAULT 'international',
                source_file TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Processing status for each code
            CREATE TABLE IF NOT EXISTS processing_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code_id INTEGER NOT NULL,
                processed BOOLEAN DEFAULT 0,
                processed_at TIMESTAMP,
                error TEXT,
                FOREIGN KEY (code_id) REFERENCES icd10_codes(id)
            );

            -- Enhanced model predictions with token tracking
            CREATE TABLE IF NOT EXISTS model_predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code_id INTEGER NOT NULL,
                model_name TEXT NOT NULL,
                model_version TEXT,  -- e.g., 'claude-3-opus', 'gpt-4'
                generated_description TEXT,
                predicted_codes TEXT,  -- JSON array
                confidence REAL,
                processing_time REAL,  -- seconds
                input_tokens INTEGER,
                output_tokens INTEGER,
                batch_size INTEGER DEFAULT 1,
                batch_id TEXT,  -- Groups items processed in same batch
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (code_id) REFERENCES icd10_codes(id),
                UNIQUE(code_id, model_name)
            );

            -- Training dataset entries
            CREATE TABLE IF NOT EXISTS dataset_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code_id INTEGER,
                text TEXT NOT NULL,
                codes TEXT NOT NULL,  -- JSON array
                model_source TEXT,
                quality_score REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (code_id) REFERENCES icd10_codes(id)
            );

            -- Batch processing metrics
            CREATE TABLE IF NOT EXISTS batch_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT UNIQUE NOT NULL,
                model_name TEXT NOT NULL,
                batch_size INTEGER NOT NULL,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                total_input_tokens INTEGER DEFAULT 0,
                total_output_tokens INTEGER DEFAULT 0,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                throughput_per_second REAL,  -- items/second
                avg_latency_ms REAL,  -- milliseconds
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Adaptive batch sizing history
            CREATE TABLE IF NOT EXISTS batch_size_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT NOT NULL,
                batch_size INTEGER NOT NULL,
                success BOOLEAN,
                reason TEXT,  -- 'success', 'timeout', 'rate_limit', 'token_limit', etc.
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Time series metrics (for charts)
            CREATE TABLE IF NOT EXISTS time_series_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT NOT NULL,
                metric_type TEXT NOT NULL,  -- 'throughput', 'batch_size', 'tokens', 'latency'
                value REAL NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Model configuration and costs
            CREATE TABLE IF NOT EXISTS model_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT UNIQUE NOT NULL,
                model_version TEXT,
                optimal_batch_size INTEGER DEFAULT 10,
                max_batch_size INTEGER DEFAULT 50,
                min_batch_size INTEGER DEFAULT 1,
                cost_per_1k_input_tokens REAL,  -- in USD
                cost_per_1k_output_tokens REAL,  -- in USD
                max_tokens_per_request INTEGER,
                rate_limit_per_minute INTEGER,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Create indexes for faster queries
            CREATE INDEX IF NOT EXISTS idx_processing_status ON processing_status(processed);
            CREATE INDEX IF NOT EXISTS idx_model_predictions ON model_predictions(model_name, code_id);
            CREATE INDEX IF NOT EXISTS idx_dataset_quality ON dataset_entries(quality_score DESC);
            CREATE INDEX IF NOT EXISTS idx_batch_metrics ON batch_metrics(model_name, created_at);
            CREATE INDEX IF NOT EXISTS idx_time_series ON time_series_metrics(model_name, metric_type, timestamp);
            CREATE INDEX IF NOT EXISTS idx_batch_history ON batch_size_history(model_name, timestamp);

            -- Insert default model configurations
            INSERT OR IGNORE INTO model_config (model_name, model_version, cost_per_1k_input_tokens, cost_per_1k_output_tokens, max_tokens_per_request, rate_limit_per_minute)
            VALUES
                ('claude', 'claude-3-opus-20240229', 0.015, 0.075, 200000, 10),
                ('codex', 'gpt-4-turbo', 0.010, 0.030, 128000, 30),
                ('gemini', 'gemini-1.5-pro', 0.0035, 0.0105, 1000000, 60);
        """)

        self.conn.commit()

        # Run migrations to ensure schema is up to date
        self._run_migrations()

    def _run_migrations(self):
        """Run database migrations to ensure schema is up to date."""
        cursor = self.conn.cursor()

        # Check if model_version column exists in model_predictions
        cursor.execute("PRAGMA table_info(model_predictions)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'model_version' not in columns:
            print("Adding model_version column to model_predictions table...")
            cursor.execute("""
                ALTER TABLE model_predictions
                ADD COLUMN model_version TEXT
            """)
            self.conn.commit()
            print("Migration complete: added model_version column")

    def import_catalog(self, csv_file: str):
        """Import ICD-10 codes from CSV file."""
        cursor = self.conn.cursor()
        imported = 0
        skipped = 0

        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    cursor.execute("""
                        INSERT INTO icd10_codes (code, description, category, country, source_file)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        row['code'],
                        row['description'],
                        row.get('category', ''),
                        row.get('country', 'international'),
                        csv_file
                    ))
                    imported += 1

                    # Also create processing status entry
                    code_id = cursor.lastrowid
                    cursor.execute("""
                        INSERT INTO processing_status (code_id, processed)
                        VALUES (?, 0)
                    """, (code_id,))

                except sqlite3.IntegrityError:
                    # Code already exists
                    skipped += 1

        self.conn.commit()
        print(f"Imported {imported} codes, skipped {skipped} duplicates")
        return imported, skipped

    def get_optimal_batch_size(self, model: str) -> int:
        """Get the current optimal batch size for a model."""
        cursor = self.conn.cursor()

        # Get from config
        cursor.execute("""
            SELECT optimal_batch_size
            FROM model_config
            WHERE model_name = ?
        """, (model,))
        result = cursor.fetchone()

        return result[0] if result else 10

    def update_optimal_batch_size(self, model: str, new_size: int):
        """Update optimal batch size based on performance."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE model_config
            SET optimal_batch_size = ?, updated_at = CURRENT_TIMESTAMP
            WHERE model_name = ?
        """, (new_size, model))
        self.conn.commit()

    def record_batch_size_attempt(self, model: str, batch_size: int, success: bool, reason: str):
        """Record a batch size attempt for adaptive sizing."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO batch_size_history (model_name, batch_size, success, reason)
            VALUES (?, ?, ?, ?)
        """, (model, batch_size, success, reason))

        # Record in time series
        self.record_time_series(model, 'batch_size', batch_size)
        self.conn.commit()

    def start_batch(self, model: str, batch_size: int) -> str:
        """Start a new batch and return batch_id."""
        import uuid
        batch_id = f"{model}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO batch_metrics (batch_id, model_name, batch_size, start_time)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """, (batch_id, model, batch_size))
        self.conn.commit()

        return batch_id

    def update_batch_metrics(self, batch_id: str, success_count: int, failure_count: int,
                           input_tokens: int, output_tokens: int):
        """Update batch metrics after processing."""
        cursor = self.conn.cursor()

        # Get start time
        cursor.execute("SELECT start_time FROM batch_metrics WHERE batch_id = ?", (batch_id,))
        result = cursor.fetchone()
        if not result:
            return

        start_time = datetime.fromisoformat(result[0])
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        total_items = success_count + failure_count
        throughput = total_items / duration if duration > 0 else 0
        avg_latency = (duration * 1000) / total_items if total_items > 0 else 0

        cursor.execute("""
            UPDATE batch_metrics
            SET success_count = ?, failure_count = ?,
                total_input_tokens = ?, total_output_tokens = ?,
                end_time = CURRENT_TIMESTAMP,
                throughput_per_second = ?,
                avg_latency_ms = ?
            WHERE batch_id = ?
        """, (success_count, failure_count, input_tokens, output_tokens,
              throughput, avg_latency, batch_id))

        self.conn.commit()

        # Record throughput in time series
        cursor.execute("SELECT model_name FROM batch_metrics WHERE batch_id = ?", (batch_id,))
        model = cursor.fetchone()[0]
        self.record_time_series(model, 'throughput', throughput)

    def record_time_series(self, model: str, metric_type: str, value: float):
        """Record a time series data point."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO time_series_metrics (model_name, metric_type, value)
            VALUES (?, ?, ?)
        """, (model, metric_type, value))
        self.conn.commit()

    def save_prediction_with_tokens(self, code_id: int, model: str, model_version: str,
                                   description: str, predicted_codes: List[str],
                                   confidence: float, processing_time: float,
                                   input_tokens: int, output_tokens: int,
                                   batch_id: str = None, batch_size: int = 1):
        """Save prediction with token tracking."""
        cursor = self.conn.cursor()
        codes_json = json.dumps(predicted_codes)

        cursor.execute("""
            INSERT OR REPLACE INTO model_predictions
            (code_id, model_name, model_version, generated_description, predicted_codes,
             confidence, processing_time, input_tokens, output_tokens, batch_id, batch_size)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (code_id, model, model_version, description, codes_json, confidence,
              processing_time, input_tokens, output_tokens, batch_id, batch_size))

        self.conn.commit()

    def get_unprocessed_codes(self, limit: int = 100, model: str = None) -> List[Dict]:
        """Get codes that haven't been processed yet."""
        cursor = self.conn.cursor()

        if model:
            # Get codes not processed by specific model
            query = """
                SELECT c.id, c.code, c.description, c.category
                FROM icd10_codes c
                LEFT JOIN model_predictions mp ON c.id = mp.code_id AND mp.model_name = ?
                WHERE mp.id IS NULL
                LIMIT ?
            """
            cursor.execute(query, (model, limit))
        else:
            # Get completely unprocessed codes
            query = """
                SELECT c.id, c.code, c.description, c.category
                FROM icd10_codes c
                JOIN processing_status ps ON c.id = ps.code_id
                WHERE ps.processed = 0
                LIMIT ?
            """
            cursor.execute(query, (limit,))

        return [dict(row) for row in cursor.fetchall()]

    def get_time_series_data(self, model: str = None, metric_type: str = None,
                            hours: int = 24) -> List[Dict]:
        """Get time series data for visualization."""
        cursor = self.conn.cursor()

        query = """
            SELECT model_name, metric_type, value, timestamp
            FROM time_series_metrics
            WHERE timestamp > datetime('now', '-{} hours')
        """.format(hours)

        params = []
        if model:
            query += " AND model_name = ?"
            params.append(model)
        if metric_type:
            query += " AND metric_type = ?"
            params.append(metric_type)

        query += " ORDER BY timestamp"

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_cost_summary(self) -> Dict:
        """Calculate total costs per model."""
        cursor = self.conn.cursor()

        query = """
            SELECT
                mp.model_name,
                mc.model_version,
                COUNT(*) as total_requests,
                SUM(mp.input_tokens) as total_input_tokens,
                SUM(mp.output_tokens) as total_output_tokens,
                mc.cost_per_1k_input_tokens,
                mc.cost_per_1k_output_tokens,
                (SUM(mp.input_tokens) / 1000.0 * mc.cost_per_1k_input_tokens +
                 SUM(mp.output_tokens) / 1000.0 * mc.cost_per_1k_output_tokens) as total_cost
            FROM model_predictions mp
            JOIN model_config mc ON mp.model_name = mc.model_name
            GROUP BY mp.model_name
        """

        cursor.execute(query)
        results = {}
        for row in cursor.fetchall():
            results[row['model_name']] = dict(row)

        return results

    def get_batch_performance_stats(self) -> Dict:
        """Get batch processing performance statistics."""
        cursor = self.conn.cursor()

        query = """
            SELECT
                model_name,
                AVG(batch_size) as avg_batch_size,
                MAX(batch_size) as max_batch_size,
                MIN(batch_size) as min_batch_size,
                AVG(throughput_per_second) as avg_throughput,
                MAX(throughput_per_second) as peak_throughput,
                MIN(throughput_per_second) as min_throughput,
                AVG(avg_latency_ms) as avg_latency,
                SUM(success_count) as total_success,
                SUM(failure_count) as total_failures,
                COUNT(*) as total_batches
            FROM batch_metrics
            WHERE end_time IS NOT NULL
            GROUP BY model_name
        """

        cursor.execute(query)
        results = {}
        for row in cursor.fetchall():
            results[row['model_name']] = dict(row)

        return results

    def get_statistics(self) -> Dict:
        """Get comprehensive processing statistics."""
        cursor = self.conn.cursor()
        stats = {}

        # Basic counts
        cursor.execute("SELECT COUNT(*) FROM icd10_codes")
        stats['total_codes'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM processing_status WHERE processed = 1")
        stats['processed_codes'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM processing_status WHERE error IS NOT NULL")
        stats['error_codes'] = cursor.fetchone()[0]

        # Predictions per model with tokens
        cursor.execute("""
            SELECT
                model_name,
                COUNT(*) as count,
                SUM(input_tokens) as total_input_tokens,
                SUM(output_tokens) as total_output_tokens
            FROM model_predictions
            GROUP BY model_name
        """)
        stats['predictions_by_model'] = {}
        for row in cursor.fetchall():
            stats['predictions_by_model'][row[0]] = {
                'count': row[1],
                'input_tokens': row[2] or 0,
                'output_tokens': row[3] or 0
            }

        # Dataset entries
        cursor.execute("SELECT COUNT(*) FROM dataset_entries")
        stats['dataset_entries'] = cursor.fetchone()[0]

        # Quality distribution
        cursor.execute("""
            SELECT
                COUNT(CASE WHEN quality_score >= 0.9 THEN 1 END) as high_quality,
                COUNT(CASE WHEN quality_score >= 0.7 AND quality_score < 0.9 THEN 1 END) as medium_quality,
                COUNT(CASE WHEN quality_score < 0.7 THEN 1 END) as low_quality
            FROM dataset_entries
            WHERE quality_score IS NOT NULL
        """)
        quality = cursor.fetchone()
        stats['quality_distribution'] = {
            'high': quality[0],
            'medium': quality[1],
            'low': quality[2]
        }

        # Add batch performance stats
        stats['batch_performance'] = self.get_batch_performance_stats()

        # Add cost summary
        stats['costs'] = self.get_cost_summary()

        # Category coverage
        cursor.execute("""
            SELECT c.category, COUNT(DISTINCT c.id) as total,
                   COUNT(DISTINCT mp.code_id) as processed
            FROM icd10_codes c
            LEFT JOIN model_predictions mp ON c.id = mp.code_id
            GROUP BY c.category
        """)
        stats['category_coverage'] = [dict(row) for row in cursor.fetchall()]

        return stats

    def export_dataset(self, output_file: str = "descriptions-to-codes.golden.jsonl",
                      min_quality: float = 0.7, limit: int = 1000):
        """Export high-quality dataset entries to JSONL."""
        cursor = self.conn.cursor()

        query = """
            SELECT de.text, de.codes, de.quality_score, c.code
            FROM dataset_entries de
            LEFT JOIN icd10_codes c ON de.code_id = c.id
            WHERE de.quality_score >= ? OR de.quality_score IS NULL
            ORDER BY de.quality_score DESC NULLS LAST
            LIMIT ?
        """
        cursor.execute(query, (min_quality, limit))

        exported = 0
        with open(output_file, 'w', encoding='utf-8') as f:
            for row in cursor.fetchall():
                entry = {
                    "text": row[0],
                    "codes": json.loads(row[1])
                }
                if row[2]:  # quality_score
                    entry["quality"] = row[2]
                if row[3]:  # original code
                    entry["source_code"] = row[3]

                f.write(json.dumps(entry) + '\n')
                exported += 1

        print(f"Exported {exported} entries to {output_file}")
        return exported

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

def main():
    """Test the enhanced database manager."""
    db = MedicalCodingDB()

    # Get statistics
    print("\n=== Enhanced Database Statistics ===")
    stats = db.get_statistics()

    print(f"\nCodes: {stats['total_codes']}")
    print(f"Processed: {stats['processed_codes']}")

    if stats.get('costs'):
        print("\n=== Cost Analysis ===")
        for model, cost_data in stats['costs'].items():
            print(f"\n{model}:")
            print(f"  Total requests: {cost_data['total_requests']}")
            print(f"  Input tokens: {cost_data['total_input_tokens']:,}")
            print(f"  Output tokens: {cost_data['total_output_tokens']:,}")
            print(f"  Total cost: ${cost_data['total_cost']:.4f}")

    if stats.get('batch_performance'):
        print("\n=== Batch Performance ===")
        for model, perf in stats['batch_performance'].items():
            print(f"\n{model}:")
            print(f"  Avg batch size: {perf['avg_batch_size']:.1f}")
            print(f"  Throughput: {perf['avg_throughput']:.2f} items/sec (peak: {perf['peak_throughput']:.2f})")
            print(f"  Avg latency: {perf['avg_latency']:.0f}ms")

    db.close()

if __name__ == "__main__":
    main()