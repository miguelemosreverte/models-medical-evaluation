#!/usr/bin/env python3
"""
Continuous dataset generation script - runs all chapters in a loop.
Each chapter exposes a generate_dataset() function that knows:
  - What data it needs from the database
  - What rows to process next
  - Its internal DAG dependencies
"""

import argparse
import os
import signal
import sqlite3
import sys
from datetime import datetime
from typing import Dict

# Import chapter dataset generation functions
import chapter_2
import chapter_3

LOCK_FILE = ".generate_dataset.lock"
DB_PATH = "medical_coding.db"


def kill_existing_process():
    """Kill the process referenced in the lock file."""
    if not os.path.exists(LOCK_FILE):
        print("No lock file found - no process to kill")
        return

    with open(LOCK_FILE, 'r') as f:
        lines = f.read().strip().split('\n')
        if not lines:
            print("Lock file is empty")
            return

        try:
            pid = int(lines[0])
            print(f"Killing existing process (PID: {pid})...")
            os.kill(pid, signal.SIGTERM)
            print(f"Process {pid} terminated successfully")
        except ProcessLookupError:
            print(f"Process {pid} not found (already dead)")
        except ValueError:
            print(f"Invalid PID in lock file: {lines[0]}")
        except Exception as e:
            print(f"Error killing process: {e}")

    # Remove lock file
    os.remove(LOCK_FILE)
    print("Lock file removed")


def acquire_lock():
    """Acquire lock to prevent multiple instances."""
    if os.path.exists(LOCK_FILE):
        with open(LOCK_FILE, 'r') as f:
            pid = f.read().strip().split('\n')[0]
        print(f"ERROR: Another instance is already running (PID: {pid})")
        print(f"If you're sure no other instance is running, delete: {LOCK_FILE}")
        sys.exit(1)

    with open(LOCK_FILE, 'w') as f:
        f.write(f"{os.getpid()}\n{datetime.now().isoformat()}\n")


def release_lock():
    """Release the lock file."""
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)


def get_progress_state() -> Dict[str, int]:
    """Get current counts from all tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    state = {}

    # Chapter 2.1: Generated Descriptions
    cursor.execute("SELECT COUNT(*) FROM generated_descriptions")
    state['generated_descriptions_total'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT code_id) FROM generated_descriptions")
    state['generated_descriptions_codes'] = cursor.fetchone()[0]

    # Chapter 3.0: Reverse Predictions
    cursor.execute("SELECT COUNT(*) FROM reverse_predictions")
    state['reverse_predictions'] = cursor.fetchone()[0]

    # Chapter 3.1: RAG predictions
    cursor.execute("SELECT COUNT(*) FROM rag_real_only_predictions")
    state['rag_real_only'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM rag_synthetic_only_predictions")
    state['rag_synthetic_only'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM rag_both_predictions")
    state['rag_both'] = cursor.fetchone()[0]

    # Chapter 3.2: Dense Variants
    cursor.execute("SELECT COUNT(*) FROM dense_variants")
    state['dense_variants_total'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT code_id) FROM dense_variants")
    state['dense_variants_codes'] = cursor.fetchone()[0]

    # Chapter 3.3: Dense RAG Predictions
    cursor.execute("SELECT COUNT(*) FROM dense_rag_predictions")
    state['dense_rag_predictions'] = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(CASE WHEN confidence = 1.0 THEN 1 ELSE 0 END) FROM dense_rag_predictions")
    state['dense_rag_correct'] = cursor.fetchone()[0] or 0

    # Chapter 2.0: Model Predictions
    cursor.execute("SELECT COUNT(*) FROM model_predictions WHERE model_name = 'claude_constrained'")
    state['claude_constrained'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM model_predictions WHERE model_name = 'codex_constrained'")
    state['codex_constrained'] = cursor.fetchone()[0]

    conn.close()
    return state


def get_last_progress_state() -> Dict[str, int]:
    """Get the last saved state snapshot."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Ensure table exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS progress_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            value INTEGER NOT NULL
        )
    """)

    # Get the last timestamp
    cursor.execute("SELECT MAX(timestamp) FROM progress_snapshots")
    last_timestamp = cursor.fetchone()[0]

    if not last_timestamp:
        conn.close()
        return {}

    # Get all metrics from that timestamp
    cursor.execute("""
        SELECT metric_name, value
        FROM progress_snapshots
        WHERE timestamp = ?
    """, (last_timestamp,))

    result = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return result


def save_progress_state(state: Dict[str, int]):
    """Save current state as a snapshot."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Ensure table exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS progress_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            value INTEGER NOT NULL
        )
    """)

    timestamp = datetime.now().isoformat()

    for metric_name, value in state.items():
        cursor.execute("""
            INSERT INTO progress_snapshots (timestamp, metric_name, value)
            VALUES (?, ?, ?)
        """, (timestamp, metric_name, value))

    conn.commit()
    conn.close()


def show_progress():
    """Show progress report in markdown format."""
    current = get_progress_state()
    last = get_last_progress_state()

    # Build markdown report
    lines = [
        "# Dataset Generation Progress Report",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        ""
    ]

    if not last:
        dense_rag_accuracy = (current['dense_rag_correct'] / current['dense_rag_predictions'] * 100) if current['dense_rag_predictions'] > 0 else 0
        lines.extend([
            "## Current State (First Query)",
            "",
            "### Chapter 2.1 - Variant Descriptions",
            f"- **{current['generated_descriptions_total']:,}** total descriptions",
            f"- **{current['generated_descriptions_codes']:,}** unique codes (11 levels each)",
            "",
            "### Chapter 3.0 - Reverse Predictions",
            f"- **{current['reverse_predictions']:,}** predictions",
            "",
            "### Chapter 3.1 - RAG Experiments",
            f"- **RAG real_only**: {current['rag_real_only']:,} predictions",
            f"- **RAG synthetic_only**: {current['rag_synthetic_only']:,} predictions",
            f"- **RAG both**: {current['rag_both']:,} predictions",
            f"- **Total**: {current['rag_real_only'] + current['rag_synthetic_only'] + current['rag_both']:,} RAG predictions",
            "",
            "### Chapter 3.2 - Dense Variants (20 per code)",
            f"- **{current['dense_variants_total']:,}** total dense variants",
            f"- **{current['dense_variants_codes']:,}** unique codes with dense variants",
            "",
            "### Chapter 3.3 - Dense RAG with Negative Examples",
            f"- **{current['dense_rag_predictions']:,}** predictions",
            f"- **{current['dense_rag_correct']:,}** correct ({dense_rag_accuracy:.1f}% accuracy)",
            "",
            "### Chapter 2.0 - Model Predictions",
            f"- **claude_constrained**: {current['claude_constrained']:,} predictions",
            f"- **codex_constrained**: {current['codex_constrained']:,} predictions",
        ])
    else:
        # Calculate deltas
        def delta(key: str) -> int:
            return current.get(key, 0) - last.get(key, 0)

        def format_delta(val: int) -> str:
            if val > 0:
                return f"+{val:,}"
            elif val < 0:
                return f"{val:,}"
            else:
                return "no change"

        dense_rag_accuracy = (current['dense_rag_correct'] / current['dense_rag_predictions'] * 100) if current['dense_rag_predictions'] > 0 else 0

        lines.extend([
            "## Changes Since Last Query",
            "",
            "### Chapter 2.1 - Variant Descriptions",
            f"- **{current['generated_descriptions_total']:,}** total descriptions ({format_delta(delta('generated_descriptions_total'))})",
            f"- **{current['generated_descriptions_codes']:,}** unique codes ({format_delta(delta('generated_descriptions_codes'))})",
            "",
            "### Chapter 3.0 - Reverse Predictions",
            f"- **{current['reverse_predictions']:,}** predictions ({format_delta(delta('reverse_predictions'))})",
            "",
            "### Chapter 3.1 - RAG Experiments",
            f"- **RAG real_only**: {current['rag_real_only']:,} predictions ({format_delta(delta('rag_real_only'))})",
            f"- **RAG synthetic_only**: {current['rag_synthetic_only']:,} predictions ({format_delta(delta('rag_synthetic_only'))})",
            f"- **RAG both**: {current['rag_both']:,} predictions ({format_delta(delta('rag_both'))})",
            "",
            "### Chapter 3.2 - Dense Variants (20 per code)",
            f"- **{current['dense_variants_total']:,}** total dense variants ({format_delta(delta('dense_variants_total'))})",
            f"- **{current['dense_variants_codes']:,}** unique codes ({format_delta(delta('dense_variants_codes'))})",
            "",
            "### Chapter 3.3 - Dense RAG with Negative Examples",
            f"- **{current['dense_rag_predictions']:,}** predictions ({format_delta(delta('dense_rag_predictions'))})",
            f"- **{current['dense_rag_correct']:,}** correct ({dense_rag_accuracy:.1f}% accuracy)",
            "",
            "### Chapter 2.0 - Model Predictions",
            f"- **claude_constrained**: {current['claude_constrained']:,} predictions ({format_delta(delta('claude_constrained'))})",
            f"- **codex_constrained**: {current['codex_constrained']:,} predictions ({format_delta(delta('codex_constrained'))})",
            "",
            "---",
            "",
            "## Summary",
            f"- **New variant descriptions (11 levels)**: {format_delta(delta('generated_descriptions_total'))}",
            f"- **New dense variants (20 per code)**: {format_delta(delta('dense_variants_total'))}",
            f"- **New reverse predictions**: {format_delta(delta('reverse_predictions'))}",
            f"- **New RAG predictions (3 modes)**: {format_delta(delta('rag_real_only') + delta('rag_synthetic_only') + delta('rag_both'))}",
            f"- **New dense RAG predictions (w/ negatives)**: {format_delta(delta('dense_rag_predictions'))} ({current['dense_rag_correct']}/{current['dense_rag_predictions']} correct = {dense_rag_accuracy:.1f}%)",
            f"- **New model predictions**: {format_delta(delta('claude_constrained') + delta('codex_constrained'))}",
        ])

    # Save current state for next comparison
    save_progress_state(current)

    print("\n".join(lines))


def run_all_chapters():
    """
    Run all chapters in round-robin fashion.
    Each chapter determines what needs processing from the database.
    """
    chapters = [
        ("Chapter 2", chapter_2.generate_dataset),
        ("Chapter 3", chapter_3.generate_dataset),
    ]

    for chapter_name, generate_func in chapters:
        print("="*60)
        print(f"{chapter_name}")
        print("="*60)

        try:
            stats = generate_func()
            print(f"  ✓ {chapter_name} complete: {stats}")
        except Exception as e:
            print(f"  ✗ {chapter_name} failed: {e}")
            import traceback
            traceback.print_exc()


def main():
    """Main loop - continuously process all chapters with 1 item per round for pipeline efficiency."""
    parser = argparse.ArgumentParser(description='Dataset generation - continuous processing')
    parser.add_argument('--restart', action='store_true',
                       help='Kill existing process and restart')
    parser.add_argument('--progress', action='store_true',
                       help='Show progress report (markdown format)')
    args = parser.parse_args()

    # Handle progress flag
    if args.progress:
        show_progress()
        return

    # Handle restart flag
    if args.restart:
        kill_existing_process()
        print("\nStarting fresh...\n")

    acquire_lock()

    try:
        round_num = 1
        while True:
            # Process 1 item per chapter per round for maximum pipeline efficiency
            # This ensures Chapter 3 can pick up work as soon as Chapter 2.1 generates it
            print(f"\n{'#'*60}")
            print(f"# ROUND {round_num} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'#'*60}\n")

            run_all_chapters()

            print(f"\n✓ Round {round_num} complete.\n")
            round_num += 1

    except KeyboardInterrupt:
        print("\n\nStopping generation...")
    finally:
        release_lock()


if __name__ == '__main__':
    main()
