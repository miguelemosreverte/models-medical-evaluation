#!/usr/bin/env python3
"""
Dataset Generation with Monitoring API

This unified script:
1. Orchestrates round-robin data generation for all chapters
2. Exposes REST API for monitoring progress
3. Can run as background daemon or one-time generation

Architecture:
- Flask API runs in a separate thread for monitoring
- Main thread runs round-robin generation loop
- Lock file prevents multiple instances
"""

import sqlite3
import subprocess
import time
import argparse
import threading
import os
from datetime import datetime
from typing import Dict, Tuple
from flask import Flask, jsonify, Response

DB_PATH = "medical_coding.db"
LOCK_FILE = ".dataset_generation.lock"

app = Flask(__name__)


# ============================================================================
# Database Status Functions
# ============================================================================

def get_generation_status() -> Dict[str, int]:
    """Get current status of data generation for all chapters."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM icd10_codes")
    total_codes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT code_id) FROM generated_descriptions")
    codes_with_variants = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM generated_descriptions")
    total_variants = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT generated_desc_id) FROM reverse_predictions")
    variants_with_predictions = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT generated_desc_id) FROM rag_real_only_predictions")
    rag_real_only = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT generated_desc_id) FROM rag_synthetic_only_predictions")
    rag_synthetic_only = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT generated_desc_id) FROM rag_both_predictions")
    rag_both = cursor.fetchone()[0]

    conn.close()

    return {
        'total_codes': total_codes,
        'codes_with_variants': codes_with_variants,
        'total_variants': total_variants,
        'variants_with_predictions': variants_with_predictions,
        'rag_real_only': rag_real_only,
        'rag_synthetic_only': rag_synthetic_only,
        'rag_both': rag_both
    }


def get_chapter_progress() -> Dict:
    """Get detailed progress for all chapters (for API)."""
    data = get_generation_status()
    total_codes = data['total_codes']
    total_variants = data['total_variants']
    variants_with_predictions = data['variants_with_predictions']

    # Expected targets
    VARIANTS_PER_CODE = 11  # detail levels 0-10
    expected_total_variants = total_codes * VARIANTS_PER_CODE

    # Chapter 2 progress: percentage of codes that have all 11 variants
    ch2_progress = (data['codes_with_variants'] / total_codes * 100) if total_codes > 0 else 0
    ch2_complete = data['codes_with_variants'] == total_codes

    # Chapter 3 depends on Chapter 2 - can only predict on variants that exist
    ch3_expected = total_variants  # Predict on all existing variants
    ch3_progress = (variants_with_predictions / ch3_expected * 100) if ch3_expected > 0 else 0
    ch3_complete = variants_with_predictions == ch3_expected and ch2_complete

    # Chapter 3.1.x depends on Chapter 3 - can only do RAG on variants with predictions
    ch31_expected = variants_with_predictions  # RAG on all variants that have Chapter 3 predictions

    return {
        'total_codes': total_codes,
        'expected_total_variants': expected_total_variants,
        'chapter_2': {
            'name': 'Description Variants Generation',
            'codes_with_variants': data['codes_with_variants'],
            'total_variants': total_variants,
            'expected_variants': expected_total_variants,
            'progress_pct': ch2_progress,
            'status': 'complete' if ch2_complete else 'in_progress'
        },
        'chapter_3': {
            'name': 'Reverse Predictions (Code from Description)',
            'variants_with_predictions': variants_with_predictions,
            'total_predictions': data['variants_with_predictions'],
            'expected_predictions': ch3_expected,
            'progress_pct': ch3_progress,
            'status': 'complete' if ch3_complete else 'in_progress'
        },
        'chapter_3_1': {
            'name': 'RAG-Enhanced Predictions',
            'experiments': {
                'real_only': {
                    'name': 'Chapter 3.1.1 (Real Descriptions Only)',
                    'predictions': data['rag_real_only'],
                    'expected': ch31_expected,
                    'progress_pct': (data['rag_real_only'] / ch31_expected * 100) if ch31_expected > 0 else 0,
                    'status': 'complete' if data['rag_real_only'] == ch31_expected and ch3_complete else 'in_progress'
                },
                'synthetic_only': {
                    'name': 'Chapter 3.1.2 (Synthetic Variants Only)',
                    'predictions': data['rag_synthetic_only'],
                    'expected': ch31_expected,
                    'progress_pct': (data['rag_synthetic_only'] / ch31_expected * 100) if ch31_expected > 0 else 0,
                    'status': 'complete' if data['rag_synthetic_only'] == ch31_expected and ch3_complete else 'in_progress'
                },
                'both': {
                    'name': 'Chapter 3.1.3 (Both Real & Synthetic)',
                    'predictions': data['rag_both'],
                    'expected': ch31_expected,
                    'progress_pct': (data['rag_both'] / ch31_expected * 100) if ch31_expected > 0 else 0,
                    'status': 'complete' if data['rag_both'] == ch31_expected and ch3_complete else 'in_progress'
                }
            }
        },
        'timestamp': datetime.now().isoformat()
    }


def format_progress_markdown() -> str:
    """Format progress as Markdown."""
    data = get_chapter_progress()

    md = f"""# Medical Coding Experiment Progress

**Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## Overall Status

- **Total ICD-10 Codes:** {data['total_codes']:,}

---

## Chapter 2: Description Variants Generation

**Purpose:** Generate 11 paraphrased variants for each medical code description

| Metric | Value |
|--------|-------|
| Codes with variants | {data['chapter_2']['codes_with_variants']:,} / {data['total_codes']:,} |
| Total variants generated | {data['chapter_2']['total_variants']:,} / {data['expected_total_variants']:,} |
| Progress | {data['chapter_2']['progress_pct']:.2f}% |
| Status | **{data['chapter_2']['status'].upper()}** |

---

## Chapter 3: Reverse Predictions

**Purpose:** Predict medical codes from generated descriptions (bidirectional consistency test)

**Dependency:** Requires Chapter 2 variants to exist

| Metric | Value |
|--------|-------|
| Variants with predictions | {data['chapter_3']['variants_with_predictions']:,} / {data['chapter_3']['expected_predictions']:,} |
| Total predictions | {data['chapter_3']['total_predictions']:,} |
| Progress | {data['chapter_3']['progress_pct']:.2f}% |
| Status | **{data['chapter_3']['status'].upper()}** |

---

## Chapter 3.1: RAG-Enhanced Predictions

**Purpose:** Test if providing similar examples improves prediction accuracy and consistency

**Dependency:** Requires Chapter 3 predictions to exist

### 3.1.1 - Real Descriptions Only (46k corpus)
- **Predictions:** {data['chapter_3_1']['experiments']['real_only']['predictions']:,} / {data['chapter_3_1']['experiments']['real_only']['expected']:,}
- **Progress:** {data['chapter_3_1']['experiments']['real_only']['progress_pct']:.2f}%
- **Status:** {data['chapter_3_1']['experiments']['real_only']['status'].upper()}

### 3.1.2 - Synthetic Variants Only (generated corpus)
- **Predictions:** {data['chapter_3_1']['experiments']['synthetic_only']['predictions']:,} / {data['chapter_3_1']['experiments']['synthetic_only']['expected']:,}
- **Progress:** {data['chapter_3_1']['experiments']['synthetic_only']['progress_pct']:.2f}%
- **Status:** {data['chapter_3_1']['experiments']['synthetic_only']['status'].upper()}

### 3.1.3 - Both Real & Synthetic (combined corpus)
- **Predictions:** {data['chapter_3_1']['experiments']['both']['predictions']:,} / {data['chapter_3_1']['experiments']['both']['expected']:,}
- **Progress:** {data['chapter_3_1']['experiments']['both']['progress_pct']:.2f}%
- **Status:** {data['chapter_3_1']['experiments']['both']['status'].upper()}

---

## Next Steps

"""

    # Determine what to work on next
    if data['chapter_2']['status'] != 'complete':
        md += f"- 🔄 **Continue generating variants** ({data['total_codes'] - data['chapter_2']['codes_with_variants']:,} codes remaining)\n"
    elif data['chapter_3']['variants_with_predictions'] < data['chapter_2']['total_variants']:
        md += f"- 🔄 **Continue reverse predictions** ({data['chapter_2']['total_variants'] - data['chapter_3']['variants_with_predictions']:,} variants remaining)\n"
    elif data['chapter_3_1']['experiments']['real_only']['predictions'] < data['chapter_3']['variants_with_predictions']:
        md += "- 🔄 **Continue RAG experiments** (real_only, synthetic_only, both)\n"
    else:
        md += "- ✅ **All experiments complete!** Ready for analysis.\n"

    return md


# ============================================================================
# Chapter Execution Functions
# ============================================================================

def run_chapter_2(batch_size: int = 5, max_items: int = 100) -> Tuple[bool, str]:
    """Generate description variants (Chapter 2)."""
    print(f"\n{'='*60}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Running Chapter 2: Generating variants")
    print(f"{'='*60}")

    try:
        result = subprocess.run(
            ['python3', 'chapter_2_generate_variants.py', 'run',
             '--max-items', str(max_items),
             '--batch-size', str(batch_size)],
            capture_output=True,
            text=True,
            timeout=1800
        )

        if result.returncode == 0:
            print(f"✓ Chapter 2 completed")
            return True, result.stdout
        else:
            print(f"✗ Chapter 2 failed: {result.stderr}")
            return False, result.stderr
    except subprocess.TimeoutExpired:
        print(f"✗ Chapter 2 timeout")
        return False, "Timeout after 30 minutes"
    except Exception as e:
        print(f"✗ Chapter 2 error: {e}")
        return False, str(e)


def run_chapter_3(max_items: int = 100) -> Tuple[bool, str]:
    """Generate reverse predictions (Chapter 3)."""
    print(f"\n{'='*60}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Running Chapter 3: Reverse predictions")
    print(f"{'='*60}")

    try:
        result = subprocess.run(
            ['python3', 'chapter_3.py',
             '--max-items', str(max_items)],
            capture_output=True,
            text=True,
            timeout=1800
        )

        if result.returncode == 0:
            print(f"✓ Chapter 3 completed")
            return True, result.stdout
        else:
            print(f"✗ Chapter 3 failed: {result.stderr}")
            return False, result.stderr
    except subprocess.TimeoutExpired:
        print(f"✗ Chapter 3 timeout")
        return False, "Timeout"
    except Exception as e:
        print(f"✗ Chapter 3 error: {e}")
        return False, str(e)


def run_chapter_3_1(corpus_mode: str, max_items: int = 33, top_k: int = 5) -> Tuple[bool, str]:
    """Generate RAG-enhanced predictions (Chapter 3.1.x)."""
    print(f"\n{'='*60}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Running Chapter 3.1 ({corpus_mode})")
    print(f"{'='*60}")

    try:
        result = subprocess.run(
            ['python3', 'chapter_3_1_rag.py',
             '--max-items', str(max_items),
             '--top-k', str(top_k),
             '--corpus-mode', corpus_mode],
            capture_output=True,
            text=True,
            timeout=1800
        )

        if result.returncode == 0:
            print(f"✓ Chapter 3.1 ({corpus_mode}) completed")
            return True, result.stdout
        else:
            print(f"✗ Chapter 3.1 ({corpus_mode}) failed: {result.stderr}")
            return False, result.stderr
    except subprocess.TimeoutExpired:
        print(f"✗ Chapter 3.1 ({corpus_mode}) timeout")
        return False, "Timeout"
    except Exception as e:
        print(f"✗ Chapter 3.1 ({corpus_mode}) error: {e}")
        return False, str(e)


def regenerate_report() -> Tuple[bool, str]:
    """Regenerate the book report."""
    print(f"\n{'='*60}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Regenerating book report")
    print(f"{'='*60}")

    try:
        result = subprocess.run(
            ['python3', 'generate_book_report.py'],
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode == 0:
            print(f"✓ Report generated")
            return True, result.stdout
        else:
            print(f"✗ Report generation failed: {result.stderr}")
            return False, result.stderr
    except Exception as e:
        print(f"✗ Report error: {e}")
        return False, str(e)


# ============================================================================
# Flask API Endpoints
# ============================================================================

@app.route('/api/progress', methods=['GET'])
def api_progress():
    """JSON endpoint for progress data."""
    try:
        data = get_chapter_progress()
        return jsonify(data), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/progress/markdown', methods=['GET'])
def api_progress_markdown():
    """Markdown endpoint for progress data."""
    try:
        md = format_progress_markdown()
        return Response(md, mimetype='text/markdown'), 200
    except Exception as e:
        return Response(f"Error: {str(e)}", mimetype='text/plain'), 500


@app.route('/api/chapters', methods=['GET'])
def api_chapters():
    """List all chapters and their status."""
    try:
        data = get_chapter_progress()

        chapters = [
            {
                'id': 'chapter_2',
                'name': data['chapter_2']['name'],
                'progress_pct': data['chapter_2']['progress_pct'],
                'status': data['chapter_2']['status']
            },
            {
                'id': 'chapter_3',
                'name': data['chapter_3']['name'],
                'progress_pct': data['chapter_3']['progress_pct'],
                'status': data['chapter_3']['status']
            },
            {
                'id': 'chapter_3_1_1',
                'name': data['chapter_3_1']['experiments']['real_only']['name'],
                'progress_pct': data['chapter_3_1']['experiments']['real_only']['progress_pct'],
                'status': data['chapter_3_1']['experiments']['real_only']['status']
            },
            {
                'id': 'chapter_3_1_2',
                'name': data['chapter_3_1']['experiments']['synthetic_only']['name'],
                'progress_pct': data['chapter_3_1']['experiments']['synthetic_only']['progress_pct'],
                'status': data['chapter_3_1']['experiments']['synthetic_only']['status']
            },
            {
                'id': 'chapter_3_1_3',
                'name': data['chapter_3_1']['experiments']['both']['name'],
                'progress_pct': data['chapter_3_1']['experiments']['both']['progress_pct'],
                'status': data['chapter_3_1']['experiments']['both']['status']
            }
        ]

        return jsonify({'chapters': chapters}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'lock_file_exists': os.path.exists(LOCK_FILE)
    }), 200


@app.route('/', methods=['GET'])
def index():
    """Root endpoint."""
    return """
    <html>
    <head><title>Medical Coding Dataset Generation</title></head>
    <body>
        <h1>Medical Coding Dataset Generation & Monitoring</h1>
        <h2>API Endpoints:</h2>
        <ul>
            <li><a href="/api/progress">/api/progress</a> - JSON progress data</li>
            <li><a href="/api/progress/markdown">/api/progress/markdown</a> - Markdown progress report</li>
            <li><a href="/api/chapters">/api/chapters</a> - List all chapters</li>
            <li><a href="/health">/health</a> - Health check</li>
        </ul>
    </body>
    </html>
    """


def start_api_server(port: int = 5001):
    """Start Flask API server in separate thread."""
    print(f"🚀 Starting Monitoring API on port {port}...")
    print(f"📊 Endpoints:")
    print(f"   - http://localhost:{port}/api/progress (JSON)")
    print(f"   - http://localhost:{port}/api/progress/markdown (Markdown)")
    print(f"   - http://localhost:{port}/api/chapters (Chapters list)")
    print(f"   - http://localhost:{port}/health (Health check)")
    print("")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)


# ============================================================================
# Main Generation Loop
# ============================================================================

def continuous_generation_loop(
    batch_size: int = 5,
    variants_per_round: int = 100,
    predictions_per_round: int = 100,
    report_interval: int = 10,
    sleep_between_rounds: int = 60
):
    """Main continuous generation loop."""
    round_number = 0

    print(f"""
{'='*60}
Continuous Round-Robin Data Generation
{'='*60}
Configuration:
- Batch size: {batch_size}
- Variants per round: {variants_per_round}
- Predictions per round: {predictions_per_round}
- Report regeneration: every {report_interval} rounds
- Sleep between rounds: {sleep_between_rounds}s
{'='*60}
Press Ctrl+C to stop
{'='*60}
""")

    try:
        while True:
            round_number += 1
            print(f"\n{'#'*60}")
            print(f"# ROUND {round_number} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'#'*60}")

            status = get_generation_status()
            print(f"\nCurrent Status:")
            print(f"  Total ICD-10 codes: {status['total_codes']:,}")
            print(f"  Codes with variants: {status['codes_with_variants']:,}")
            print(f"  Total variants: {status['total_variants']:,}")
            print(f"  Variants with predictions: {status['variants_with_predictions']:,}")
            print(f"  RAG predictions (real_only): {status['rag_real_only']}")
            print(f"  RAG predictions (synthetic_only): {status['rag_synthetic_only']}")
            print(f"  RAG predictions (both): {status['rag_both']}")

            # Step 1: Generate variants
            if status['codes_with_variants'] < status['total_codes']:
                run_chapter_2(batch_size, variants_per_round)
                status = get_generation_status()
            else:
                print(f"\n✓ All codes have variants, skipping Chapter 2")

            # Step 2: Generate reverse predictions
            if status['variants_with_predictions'] < status['total_variants']:
                run_chapter_3(predictions_per_round)
                status = get_generation_status()
            else:
                print(f"\n✓ All variants have predictions, skipping Chapter 3")

            # Step 3: Run RAG experiments
            if status['variants_with_predictions'] > 0:
                if status['rag_real_only'] < status['variants_with_predictions']:
                    run_chapter_3_1('real_only', max_items=min(33, status['variants_with_predictions']))

                if status['rag_synthetic_only'] < status['variants_with_predictions']:
                    run_chapter_3_1('synthetic_only', max_items=min(33, status['variants_with_predictions']))

                if status['rag_both'] < status['variants_with_predictions']:
                    run_chapter_3_1('both', max_items=min(33, status['variants_with_predictions']))

            # Step 4: Regenerate report periodically
            if round_number % report_interval == 0:
                regenerate_report()

            # Sleep or finish
            if status['codes_with_variants'] < status['total_codes']:
                print(f"\nSleeping {sleep_between_rounds}s before next round...")
                time.sleep(sleep_between_rounds)
            else:
                print(f"\n✓ All data generated! Entering monitoring mode (checking every 5 minutes)...")
                time.sleep(300)

    except KeyboardInterrupt:
        print(f"\n\n{'='*60}")
        print(f"Dataset generation stopped by user")
        print(f"Total rounds completed: {round_number}")
        print(f"{'='*60}")


def create_lock_file():
    """Create lock file to prevent multiple instances."""
    if os.path.exists(LOCK_FILE):
        return False
    with open(LOCK_FILE, 'w') as f:
        f.write(f"{os.getpid()}\n{datetime.now().isoformat()}\n")
    return True


def remove_lock_file():
    """Remove lock file."""
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)


def is_generation_running() -> bool:
    """Check if dataset generation is currently running."""
    return os.path.exists(LOCK_FILE)


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Dataset Generation with Monitoring API"
    )
    parser.add_argument(
        '--api-only',
        action='store_true',
        help='Run only the monitoring API (no data generation)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=5,
        help='Batch size for variant generation (default: 5)'
    )
    parser.add_argument(
        '--variants-per-round',
        type=int,
        default=100,
        help='Max variants to generate per round (default: 100)'
    )
    parser.add_argument(
        '--predictions-per-round',
        type=int,
        default=100,
        help='Max predictions per round (default: 100)'
    )
    parser.add_argument(
        '--report-interval',
        type=int,
        default=10,
        help='Regenerate report every N rounds (default: 10)'
    )
    parser.add_argument(
        '--sleep',
        type=int,
        default=60,
        help='Seconds to sleep between rounds (default: 60)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5001,
        help='API server port (default: 5001)'
    )

    args = parser.parse_args()

    if args.api_only:
        # Run only API server
        start_api_server(port=args.port)
    else:
        # Check lock file
        if not create_lock_file():
            print("❌ Dataset generation is already running!")
            print("   Check lock file: .dataset_generation.lock")
            print("   Or run with --api-only to just start the monitoring API")
            exit(1)

        try:
            # Start API in separate thread
            api_thread = threading.Thread(
                target=start_api_server,
                args=(args.port,),
                daemon=True
            )
            api_thread.start()

            # Give API time to start
            time.sleep(2)

            # Run generation loop
            continuous_generation_loop(
                batch_size=args.batch_size,
                variants_per_round=args.variants_per_round,
                predictions_per_round=args.predictions_per_round,
                report_interval=args.report_interval,
                sleep_between_rounds=args.sleep
            )
        finally:
            remove_lock_file()
