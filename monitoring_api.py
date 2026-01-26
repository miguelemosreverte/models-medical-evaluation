#!/usr/bin/env python3
"""
Real-time monitoring API for the Medical Coding System.
Provides detailed metrics and status information via HTTP endpoints.
"""

from flask import Flask, jsonify
from flask_cors import CORS
import sqlite3
from datetime import datetime, timedelta
import os
import sys

app = Flask(__name__)
CORS(app)  # Enable CORS for browser access

DB_PATH = "medical_coding.db"


def get_db():
    """Get database connection."""
    return sqlite3.connect(DB_PATH)


@app.route('/api/status', methods=['GET'])
def status():
    """Get overall system status."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Get total codes
        cursor.execute("SELECT COUNT(*) FROM icd10_codes")
        total_codes = cursor.fetchone()[0]

        # Get predictions by model
        cursor.execute("""
            SELECT model_name, COUNT(*) as count
            FROM model_predictions
            GROUP BY model_name
        """)
        predictions = {row[0]: row[1] for row in cursor.fetchall()}

        # Check if system is running (lock file exists)
        is_running = os.path.exists('main.lock')

        conn.close()

        return jsonify({
            'status': 'running' if is_running else 'idle',
            'total_codes': total_codes,
            'predictions': predictions,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/throughput', methods=['GET'])
def throughput():
    """Get real-time throughput metrics for the last minute."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Get recent batch metrics (last 5 minutes)
        cutoff = (datetime.now() - timedelta(minutes=5)).isoformat()

        cursor.execute("""
            SELECT
                model_name,
                end_time,
                (success_count + failure_count) as total_items,
                CAST((julianday(end_time) - julianday(start_time)) * 24 * 60 * 60 AS REAL) as duration_seconds,
                batch_size
            FROM batch_metrics
            WHERE end_time > ? AND start_time IS NOT NULL
            ORDER BY end_time DESC
        """, (cutoff,))

        results = {}
        for row in cursor.fetchall():
            model = row[0]
            if model not in results:
                results[model] = {
                    'batches': [],
                    'total_items': 0,
                    'total_duration': 0
                }

            items = row[2] or 0
            duration = row[3] or 0
            throughput_per_sec = items / duration if duration > 0 else 0

            results[model]['batches'].append({
                'end_time': row[1],
                'items': items,
                'duration_seconds': duration,
                'throughput_per_sec': throughput_per_sec,
                'throughput_per_min': throughput_per_sec * 60,
                'batch_size': row[4]
            })
            results[model]['total_items'] += items
            results[model]['total_duration'] += duration

        # Calculate aggregates
        for model in results:
            if results[model]['total_duration'] > 0:
                results[model]['avg_throughput_per_sec'] = results[model]['total_items'] / results[model]['total_duration']
                results[model]['avg_throughput_per_min'] = results[model]['avg_throughput_per_sec'] * 60
            else:
                results[model]['avg_throughput_per_sec'] = 0
                results[model]['avg_throughput_per_min'] = 0

        conn.close()

        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'window': '5_minutes',
            'models': results
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/batches/recent', methods=['GET'])
def recent_batches():
    """Get the most recent batches with detailed timing."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                model_name,
                batch_id,
                batch_size,
                start_time,
                end_time,
                success_count,
                failure_count,
                CAST((julianday(end_time) - julianday(start_time)) * 24 * 60 * 60 AS REAL) as duration_seconds
            FROM batch_metrics
            WHERE end_time IS NOT NULL
            ORDER BY end_time DESC
            LIMIT 20
        """)

        batches = []
        for row in cursor.fetchall():
            duration = row[7] or 0
            total_items = (row[5] or 0) + (row[6] or 0)
            batches.append({
                'model': row[0],
                'batch_id': row[1],
                'batch_size': row[2],
                'start_time': row[3],
                'end_time': row[4],
                'success_count': row[5],
                'failure_count': row[6],
                'duration_seconds': duration,
                'items_per_second': total_items / duration if duration > 0 else 0
            })

        conn.close()

        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'batches': batches
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/predictions/recent', methods=['GET'])
def recent_predictions():
    """Get the most recent predictions."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                mp.model_name,
                ic.code,
                ic.description,
                mp.predicted_codes,
                mp.confidence,
                mp.processing_time,
                mp.created_at
            FROM model_predictions mp
            JOIN icd10_codes ic ON mp.code_id = ic.id
            ORDER BY mp.created_at DESC
            LIMIT 20
        """)

        predictions = []
        for row in cursor.fetchall():
            predictions.append({
                'model': row[0],
                'code': row[1],
                'description': row[2],
                'predicted_codes': row[3],
                'confidence': row[4],
                'processing_time_ms': row[5],
                'timestamp': row[6]
            })

        conn.close()

        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'predictions': predictions
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/performance', methods=['GET'])
def performance():
    """Get performance metrics by model."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                model_name,
                COUNT(*) as total_predictions,
                AVG(confidence) as avg_confidence,
                AVG(processing_time) as avg_processing_time_ms,
                MIN(processing_time) as min_processing_time_ms,
                MAX(processing_time) as max_processing_time_ms,
                SUM(input_tokens) as total_input_tokens,
                SUM(output_tokens) as total_output_tokens
            FROM model_predictions
            GROUP BY model_name
        """)

        models = {}
        for row in cursor.fetchall():
            models[row[0]] = {
                'total_predictions': row[1],
                'avg_confidence': row[2],
                'avg_processing_time_ms': row[3],
                'min_processing_time_ms': row[4],
                'max_processing_time_ms': row[5],
                'total_input_tokens': row[6],
                'total_output_tokens': row[7]
            }

        conn.close()

        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'models': models
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/live', methods=['GET'])
def live():
    """Get live processing status - what's happening right now."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Get batches that started in the last 2 minutes
        cutoff = (datetime.now() - timedelta(minutes=2)).isoformat()

        cursor.execute("""
            SELECT
                model_name,
                batch_id,
                batch_size,
                start_time,
                end_time,
                success_count,
                failure_count
            FROM batch_metrics
            WHERE start_time > ?
            ORDER BY start_time DESC
        """, (cutoff,))

        active_batches = []
        completed_batches = []

        for row in cursor.fetchall():
            batch_info = {
                'model': row[0],
                'batch_id': row[1],
                'batch_size': row[2],
                'start_time': row[3],
                'end_time': row[4],
                'success_count': row[5] or 0,
                'failure_count': row[6] or 0
            }

            if row[4] is None:  # No end_time = still processing
                # Calculate elapsed time
                start = datetime.fromisoformat(row[3])
                elapsed = (datetime.now() - start).total_seconds()
                batch_info['elapsed_seconds'] = elapsed
                active_batches.append(batch_info)
            else:
                start = datetime.fromisoformat(row[3])
                end = datetime.fromisoformat(row[4])
                batch_info['duration_seconds'] = (end - start).total_seconds()
                completed_batches.append(batch_info)

        # Get most recent prediction for each model
        cursor.execute("""
            SELECT model_name, MAX(created_at) as last_prediction
            FROM model_predictions
            GROUP BY model_name
        """)

        last_predictions = {row[0]: row[1] for row in cursor.fetchall()}

        conn.close()

        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'is_running': os.path.exists('main.lock'),
            'active_batches': active_batches,
            'recent_completed_batches': completed_batches,
            'last_prediction_by_model': last_predictions
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/', methods=['GET'])
def index():
    """API documentation."""
    return jsonify({
        'name': 'Medical Coding System Monitoring API',
        'version': '1.0.0',
        'endpoints': {
            '/api/status': 'Overall system status',
            '/api/throughput': 'Real-time throughput metrics (last 5 minutes)',
            '/api/batches/recent': 'Most recent 20 batches',
            '/api/predictions/recent': 'Most recent 20 predictions',
            '/api/performance': 'Performance metrics by model',
            '/api/live': 'Live processing status (what\'s happening now)'
        }
    })


if __name__ == '__main__':
    port = 5001
    print(f"Starting Medical Coding System Monitoring API on http://localhost:{port}")
    print("Available endpoints:")
    print("  GET / - API documentation")
    print("  GET /api/status - Overall status")
    print("  GET /api/throughput - Throughput metrics")
    print("  GET /api/batches/recent - Recent batches")
    print("  GET /api/predictions/recent - Recent predictions")
    print("  GET /api/performance - Performance metrics")
    print("  GET /api/live - Live processing status")
    print("\nPress Ctrl+C to stop")

    app.run(host='0.0.0.0', port=port, debug=False)