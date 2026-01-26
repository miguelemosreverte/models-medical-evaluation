#!/usr/bin/env python3
"""
Chapter 2: Bidirectional Consistency Testing
Handles all Chapter 2 dataset generation:
  2.0: Prediction experiments (description → code)
  2.1: Generate variant descriptions (code → descriptions at 11 detail levels)

Complete self-contained implementation.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from typing import Dict, Any, List

from db_manager import MedicalCodingDB
from typing import Callable
from collections import namedtuple


# =============================================================================
# UTILITY FUNCTIONS - Reusable building blocks (from experiments.py)
# =============================================================================

def call_claude(prompt: str, timeout: int = 30) -> Dict[str, Any]:
    """Call Claude CLI and return structured result."""
    start_time = time.time()

    try:
        result = subprocess.run(
            ['claude', '-p', prompt],
            capture_output=True,
            text=True,
            timeout=timeout
        )

        response_time = time.time() - start_time

        return {
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'response_time': response_time,
            'tokens_input': len(prompt.split()),
            'tokens_output': len(result.stdout.split())
        }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'stdout': '',
            'stderr': 'timeout',
            'response_time': timeout,
            'tokens_input': len(prompt.split()),
            'tokens_output': 0
        }
    except Exception as e:
        return {
            'success': False,
            'stdout': '',
            'stderr': str(e),
            'response_time': time.time() - start_time,
            'tokens_input': 0,
            'tokens_output': 0
        }


def call_codex(prompt: str, timeout: int = 30) -> Dict[str, Any]:
    """Call Codex CLI and return structured result."""
    start_time = time.time()

    try:
        result = subprocess.run(
            ['codex', 'exec', prompt],
            capture_output=True,
            text=True,
            timeout=timeout
        )

        response_time = time.time() - start_time

        return {
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'response_time': response_time,
            'tokens_input': len(prompt.split()),
            'tokens_output': len(result.stdout.split())
        }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'stdout': '',
            'stderr': 'timeout',
            'response_time': timeout,
            'tokens_input': len(prompt.split()),
            'tokens_output': 0
        }
    except Exception as e:
        return {
            'success': False,
            'stdout': '',
            'stderr': str(e),
            'response_time': time.time() - start_time,
            'tokens_input': 0,
            'tokens_output': 0
        }


def extract_icd10_codes(response: str) -> List[str]:
    """Extract ICD-10 codes from any model response."""
    # Look for JSON arrays first
    json_pattern = r'\[(?:\s*"[A-Z]\d{2}(?:\.\d{1,3})?"(?:\s*,\s*"[A-Z]\d{2}(?:\.\d{1,3})?")*)?\s*\]'
    match = re.search(json_pattern, response)
    if match:
        try:
            return json.loads(match.group())
        except:
            pass

    # Fallback: extract codes directly
    pattern = r'\b[A-Z]\d{2}(?:\.\d{1,3})?\b'
    matches = re.findall(pattern, response)
    return matches


def build_baseline_prompt(description: str) -> str:
    """Build baseline prompt for medical coding."""
    return f"Given this medical description: '{description}', provide only the relevant ICD-10 codes as a JSON array. No explanation, just the array."


def build_constrained_prompt(description: str) -> str:
    """Build constrained prompt with anti-hallucination instructions."""
    return f"""Given this medical description: '{description}', provide only the relevant ICD-10 codes as a JSON array.

IMPORTANT: Only return codes that are directly supported by the description. Do not add codes for:
- Assumed complications
- Inferred conditions
- Standard procedures
- Common comorbidities

Return only codes explicitly indicated in the text. No explanation, just the array."""


# =============================================================================
# ADAPTIVE BATCH SIZE MANAGEMENT
# =============================================================================

class AdaptiveBatchManager:
    """Manages adaptive batch sizing based on success rate."""

    def __init__(self, initial_batch_size: int = 1, max_batch_size: int = 20):
        self.current_batch_size = initial_batch_size
        self.max_batch_size = max_batch_size
        self.consecutive_successes = 0
        self.consecutive_failures = 0

    def adjust(self, success_rate: float) -> int:
        """Adjust batch size based on success rate and return new size."""
        old_batch_size = self.current_batch_size

        # Very aggressive reduction on poor performance
        if success_rate < 0.5:
            self.current_batch_size = max(1, self.current_batch_size // 2)
            self.consecutive_failures = 0
            self.consecutive_successes = 0
        elif success_rate < 0.7:
            self.consecutive_failures += 1
            self.consecutive_successes = 0
            if self.consecutive_failures >= 1:
                self.current_batch_size = max(1, self.current_batch_size - 2)
                self.consecutive_failures = 0
        elif success_rate >= 0.9:
            self.consecutive_successes += 1
            self.consecutive_failures = 0
            if self.consecutive_successes >= 3:
                self.current_batch_size = min(self.max_batch_size, self.current_batch_size + 1)
                self.consecutive_successes = 0
        else:
            # 70-90% success: maintain current batch size
            self.consecutive_successes = 0
            self.consecutive_failures = 0

        return self.current_batch_size

    def get_size(self) -> int:
        """Get current batch size."""
        return self.current_batch_size


# =============================================================================
# EXPERIMENT RUNNER - Generic experiment execution
# =============================================================================

def run_experiment(
    experiment_name: str,
    model_caller: Callable[[str], Dict[str, Any]],
    prompt_builder: Callable[[str], str],
    db: MedicalCodingDB,
    initial_batch_size: int = 1,
    max_items: int = 100
) -> Dict[str, Any]:
    """Run a medical coding experiment with adaptive batch sizing."""
    print(f"\n{'='*60}")
    print(f"Running experiment: {experiment_name}")
    print(f"{'='*60}")

    batch_manager = AdaptiveBatchManager(initial_batch_size)
    start_time = datetime.now()
    items_processed = 0
    total_attempted = 0
    total_succeeded = 0
    response_times = []
    errors = []

    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT COUNT(DISTINCT code_id)
        FROM model_predictions
        WHERE model_name = ?
    """, (experiment_name,))
    result = cursor.fetchone()
    current_offset = result[0] if result else 0

    cursor.execute("SELECT COUNT(*) FROM icd10_codes")
    total_items = cursor.fetchone()[0]

    if current_offset > 0:
        print(f"[{experiment_name}] Resuming from item {current_offset} (already processed {current_offset}/{total_items})")

    print(f"[{experiment_name}] Starting with adaptive batch size: {batch_manager.get_size()}")
    print(f"[{experiment_name}] Max items to process this run: {max_items}")

    while items_processed < max_items and current_offset < total_items:
        batch_size = batch_manager.get_size()
        cursor.execute("""
            SELECT id, code, description
            FROM icd10_codes
            LIMIT ? OFFSET ?
        """, (batch_size, current_offset))

        batch = cursor.fetchall()
        if not batch:
            break

        batch_start = time.time()
        print(f"[{experiment_name}] Processing batch of {len(batch)} items (adaptive batch size: {batch_size})...")

        batch_id = db.start_batch(experiment_name, batch_size)
        batch_succeeded = 0
        batch_input_tokens = 0
        batch_output_tokens = 0

        for code_id, code, description in batch:
            prompt = prompt_builder(description)
            result = model_caller(prompt)
            predicted_codes = extract_icd10_codes(result['stdout']) if result['success'] else []
            success = code in predicted_codes
            if success:
                batch_succeeded += 1

            batch_input_tokens += result['tokens_input']
            batch_output_tokens += result['tokens_output']
            response_times.append(result['response_time'])

            if not result['success']:
                errors.append(result['stderr'])

            db.save_prediction_with_tokens(
                code_id=code_id,
                model=experiment_name,
                model_version="1.0.0",
                description=description,
                predicted_codes=predicted_codes,
                confidence=1.0 if success else 0.0,
                processing_time=result['response_time'],
                input_tokens=result['tokens_input'],
                output_tokens=result['tokens_output'],
                batch_id=batch_id,
                batch_size=batch_size
            )

            output_file = f"medical_coding_dataset.{experiment_name}.jsonl"
            with open(output_file, 'a') as f:
                entry = {
                    "text": description,
                    "golden_codes": [code],
                    "codes": predicted_codes
                }
                json.dump(entry, f)
                f.write('\n')

        db.update_batch_metrics(
            batch_id,
            batch_succeeded,
            len(batch) - batch_succeeded,
            batch_input_tokens,
            batch_output_tokens
        )

        total_attempted += len(batch)
        total_succeeded += batch_succeeded
        items_processed += len(batch)
        current_offset += len(batch)

        success_rate = batch_succeeded / len(batch) if len(batch) > 0 else 0
        new_batch_size = batch_manager.adjust(success_rate)
        db.record_time_series(experiment_name, 'batch_size', new_batch_size)

        batch_time = time.time() - batch_start
        throughput = len(batch) / batch_time if batch_time > 0 else 0

        print(f"[{experiment_name}]   Success: {batch_succeeded}/{len(batch)}")
        print(f"[{experiment_name}]   Throughput: {throughput:.2f} items/sec")
        print(f"[{experiment_name}]   Next batch size: {new_batch_size}")

    elapsed = (datetime.now() - start_time).total_seconds()

    print(f"\n[{experiment_name}] COMPLETED")
    print(f"  Total processed: {total_attempted}")
    print(f"  Success rate: {total_succeeded/total_attempted*100:.1f}%")
    print(f"  Throughput: {total_attempted/elapsed:.2f} items/sec")

    return {
        'experiment_name': experiment_name,
        'items_attempted': total_attempted,
        'items_succeeded': total_succeeded,
        'elapsed_seconds': elapsed,
        'throughput': total_attempted / elapsed if elapsed > 0 else 0,
        'response_times': response_times,
        'errors': errors
    }


# =============================================================================
# SPECIFIC EXPERIMENT FUNCTIONS
# =============================================================================

def run_baseline_claude(db: MedicalCodingDB, batch_size: int = 1, max_items: int = 100):
    """Run baseline Claude experiment."""
    return run_experiment(
        experiment_name="claude",
        model_caller=call_claude,
        prompt_builder=build_baseline_prompt,
        db=db,
        initial_batch_size=batch_size,
        max_items=max_items
    )


def run_baseline_codex(db: MedicalCodingDB, batch_size: int = 1, max_items: int = 100):
    """Run baseline Codex experiment."""
    return run_experiment(
        experiment_name="codex",
        model_caller=call_codex,
        prompt_builder=build_baseline_prompt,
        db=db,
        initial_batch_size=batch_size,
        max_items=max_items
    )


def run_constrained_claude(db: MedicalCodingDB, batch_size: int = 1, max_items: int = 100):
    """Run constrained Claude experiment with anti-hallucination prompts."""
    return run_experiment(
        experiment_name="claude_constrained",
        model_caller=call_claude,
        prompt_builder=build_constrained_prompt,
        db=db,
        initial_batch_size=batch_size,
        max_items=max_items
    )


def run_constrained_codex(db: MedicalCodingDB, batch_size: int = 1, max_items: int = 100):
    """Run constrained Codex experiment with anti-hallucination prompts."""
    return run_experiment(
        experiment_name="codex_constrained",
        model_caller=call_codex,
        prompt_builder=build_constrained_prompt,
        db=db,
        initial_batch_size=batch_size,
        max_items=max_items
    )


# =============================================================================
# CHAPTER 2.0: PREDICTION EXPERIMENTS
# =============================================================================

# Configuration
ENABLED_EXPERIMENTS = [
    "claude_constrained",
    "codex_constrained"
]


class MedicalCodingSystem:
    """Main system orchestrator for Chapter 2.0 prediction experiments."""

    def __init__(self):
        self.db = MedicalCodingDB()
        self._ensure_data_loaded()
        self.experiments = self._get_experiment_functions()

    def _ensure_data_loaded(self):
        """Ensure ICD-10 codes are loaded into the database."""
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM icd10_codes")
        count = cursor.fetchone()[0]

        if count == 0:
            print("No ICD-10 codes found in database. Fetching from CMS...")
            # Run the fetch script to get fresh data from CMS
            try:
                subprocess.run(['python3', 'fetch_icd10_cms.py'], check=True)

                # Import the catalog into database
                csv_path = 'data/icd10_cms_catalog.csv'
                if os.path.exists(csv_path):
                    print(f"Importing {csv_path} into database...")
                    self.db.import_catalog(csv_path)
                    cursor.execute("SELECT COUNT(*) FROM icd10_codes")
                    count = cursor.fetchone()[0]
                    print(f"Database initialized with {count:,} ICD-10 codes")
                else:
                    print(f"ERROR: Expected catalog file not found: {csv_path}")
                    sys.exit(1)
            except Exception as e:
                print(f"ERROR: Failed to fetch ICD-10 codes: {e}")
                sys.exit(1)
        else:
            print(f"Database initialized with {count:,} ICD-10 codes")

    def _get_experiment_functions(self) -> Dict:
        """Map experiment names to their functions."""
        return {
            "claude": run_baseline_claude,
            "codex": run_baseline_codex,
            "claude_constrained": run_constrained_claude,
            "codex_constrained": run_constrained_codex
        }

    def _run_single_experiment(self, experiment_name: str, experiment_func, initial_batch_size: int, max_items: int):
        """Run a single experiment in a thread."""
        # Each thread needs its own database connection
        thread_db = MedicalCodingDB()

        # Run the experiment
        experiment_func(thread_db, initial_batch_size, max_items)

    def _report_generator_loop(self, stop_event):
        """Background thread that generates reports every 10 seconds."""
        while not stop_event.is_set():
            try:
                print("\n[REPORT] Generating updated reports...")
                self.generate_report()
                print("[REPORT] Reports updated successfully")
            except Exception as e:
                print(f"[REPORT] Error generating reports: {e}")

            # Wait 10 seconds or until stop signal
            stop_event.wait(10)

    def run_experiment(self, experiment_name: str = None, initial_batch_size: int = 10, max_items: int = 100, generate_reports: bool = True):
        """Run experiments for configured experiments or a specific experiment (in parallel)."""
        # Use specified experiment or all configured experiments
        if experiment_name:
            if experiment_name not in self.experiments:
                print(f"ERROR: Unknown experiment '{experiment_name}'")
                print(f"Available experiments: {', '.join(self.experiments.keys())}")
                return
            experiments_to_run = [(experiment_name, self.experiments[experiment_name])]
        else:
            # Run only enabled experiments
            experiments_to_run = [(name, self.experiments[name]) for name in ENABLED_EXPERIMENTS if name in self.experiments]

        print(f"Running experiments: {', '.join([name for name, _ in experiments_to_run])}")

        # Start background report generation thread
        stop_report_thread = threading.Event()
        report_thread = None
        if generate_reports:
            report_thread = threading.Thread(
                target=self._report_generator_loop,
                args=(stop_report_thread,),
                daemon=True
            )
            report_thread.start()

        # Run experiments in parallel using threads
        threads = []
        for exp_name, exp_func in experiments_to_run:
            thread = threading.Thread(
                target=self._run_single_experiment,
                args=(exp_name, exp_func, initial_batch_size, max_items)
            )
            thread.start()
            threads.append(thread)

        try:
            # Wait for all threads to complete
            for thread in threads:
                thread.join()

            print("\n" + "="*60)
            print("ALL EXPERIMENTS COMPLETED")
            print("="*60)

        finally:
            # Stop report generation thread
            if report_thread:
                stop_report_thread.set()
                report_thread.join(timeout=2)

            # Generate final report
            if generate_reports:
                print("\n[REPORT] Generating final reports...")
                self.generate_report()
                print("[REPORT] Final reports generated")

    def generate_report(self):
        """Generate the comprehensive HTML report."""
        try:
            # Import and run the report generators directly (don't use subprocess)
            import evaluate_models
            import generate_book_report

            # Run evaluation and generate index.html
            evaluate_models.main()

            # Generate book report
            generate_book_report.main()

        except Exception as e:
            print(f"Error generating reports: {e}")

    def status(self):
        """Show current system status."""
        print("\n" + "="*50)
        print("SYSTEM STATUS")
        print("="*50)

        # Database stats
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM icd10_codes")
        total_codes = cursor.fetchone()[0]
        print(f"\nDatabase: {total_codes:,} ICD-10 codes loaded")

        # Check existing results
        print("\nPredictions in database:")
        cursor.execute("""
            SELECT model_name, COUNT(DISTINCT code_id)
            FROM model_predictions
            GROUP BY model_name
            ORDER BY model_name
        """)
        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[1]:,} predictions")

        # Experiment status
        print(f"\nAvailable experiments: {', '.join(self.experiments.keys())}")
        print(f"Enabled experiments: {', '.join(ENABLED_EXPERIMENTS)}")


# =============================================================================
# CHAPTER 2.1: GENERATE VARIANT DESCRIPTIONS
# =============================================================================

def _generate_descriptions_for_code(
    db: MedicalCodingDB,
    code_id: int,
    code: str,
    description: str,
    model_name: str,
    detail_levels: List[int]
) -> Dict[str, Any]:
    """Generate descriptions for a single ICD-10 code."""
    start_time = time.time()

    try:
        prompt = f"""You are a medical documentation expert. Generate {len(detail_levels)} clinical descriptions for this ICD-10 code, ranging from Level 0 (most concise, conversational) to Level 10 (most detailed, clinical).

ICD-10 Code: {code}
Official Description: {description}

IMPORTANT GUIDELINES:
- Level 0: Ultra-minimal, broad, natural language (3-5 words). NOT verbatim from ICD-10. Use conversational, general terms.
  Example: "Severe bacterial diarrhea" or "Acute diarrheal infection"

- Level 1-3: Minimal to brief clinical mentions (1-2 short sentences)
  Example: "Patient has severe watery diarrhea" to "Acute onset severe diarrhea with dehydration"

- Level 4-6: Essential to moderate clinical detail (2-4 sentences with key symptoms)
  Example: "Patient presents with rice-water stools, severe dehydration, muscle cramps"

- Level 7-9: Standard to comprehensive clinical presentations (full paragraph with clinical context)
  Example: Full symptom description with clinical signs

- Level 10: Hyper-detailed clinical presentation (comprehensive with lab findings, vital signs, specific diagnostic criteria)
  Example: Complete clinical picture with all diagnostic details

CRITICAL: Ensure Level 0 is truly minimal and conversational - NOT the exact ICD-10 description.

Generate ONLY a valid JSON array with this exact format:
[
  {{"level": 0, "description": "..."}},
  {{"level": 1, "description": "..."}},
  {{"level": 2, "description": "..."}},
  {{"level": 3, "description": "..."}},
  {{"level": 4, "description": "..."}},
  {{"level": 5, "description": "..."}},
  {{"level": 6, "description": "..."}},
  {{"level": 7, "description": "..."}},
  {{"level": 8, "description": "..."}},
  {{"level": 9, "description": "..."}},
  {{"level": 10, "description": "..."}}
]

Return ONLY the JSON array, no other text."""

        # Determine which CLI to use
        cli_cmd = 'claude' if 'claude' in model_name else 'codex'

        result = subprocess.run(
            [cli_cmd, '-p', prompt],
            capture_output=True,
            text=True,
            timeout=60
        )

        response_time = time.time() - start_time

        if result.returncode == 0:
            descriptions = _extract_descriptions(result.stdout)

            if descriptions and len(descriptions) == len(detail_levels):
                _save_descriptions(db, code_id, model_name, descriptions)
                return {
                    "success": True,
                    "response_time": response_time,
                    "error": None
                }
            else:
                return {
                    "success": False,
                    "response_time": response_time,
                    "error": f"Expected {len(detail_levels)} descriptions, got {len(descriptions) if descriptions else 0}"
                }
        else:
            return {
                "success": False,
                "response_time": response_time,
                "error": result.stderr[:100]
            }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "response_time": 60.0,
            "error": "timeout"
        }
    except Exception as e:
        return {
            "success": False,
            "response_time": time.time() - start_time,
            "error": str(e)[:100]
        }


def _extract_descriptions(response: str) -> List[Dict[str, Any]]:
    """Extract JSON array of descriptions from model response."""
    try:
        json_pattern = r'\[\s*\{.*?\}\s*(?:,\s*\{.*?\}\s*)*\]'
        match = re.search(json_pattern, response, re.DOTALL)

        if match:
            json_str = match.group()
            descriptions = json.loads(json_str)

            if isinstance(descriptions, list) and all(
                isinstance(d, dict) and 'level' in d and 'description' in d
                for d in descriptions
            ):
                descriptions.sort(key=lambda x: x['level'])
                return descriptions

    except (json.JSONDecodeError, Exception) as e:
        print(f"      Error extracting descriptions: {e}")

    return []


def _save_descriptions(
    db: MedicalCodingDB,
    code_id: int,
    model_name: str,
    descriptions: List[Dict[str, Any]]
):
    """Save generated descriptions to database."""
    try:
        cursor = db.conn.cursor()

        for desc_obj in descriptions:
            level = desc_obj['level']
            description = desc_obj['description']

            cursor.execute("""
                INSERT OR REPLACE INTO generated_descriptions
                (code_id, generator_model, detail_level, description, created_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (code_id, model_name, level, description))

        db.conn.commit()

    except Exception as e:
        print(f"      Error saving descriptions: {e}")
        db.conn.rollback()


def _generate_variant_descriptions(
    db: MedicalCodingDB,
    model: str = "claude",
    max_items: int = 100
) -> Dict[str, Any]:
    """
    Generate variant clinical descriptions at 11 detail levels (0-10).

    Args:
        db: Database connection
        model: Model to use ("claude" or "codex")
        max_items: Maximum number of codes to process

    Returns:
        Dictionary with generation statistics
    """
    detail_levels = list(range(11))  # Levels 0-10
    model_name = f"generate_descriptions_{model}"

    # Get codes that don't have all detail levels generated yet
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT ic.id, ic.code, ic.description
        FROM icd10_codes ic
        WHERE (
            SELECT COUNT(DISTINCT detail_level)
            FROM generated_descriptions gd
            WHERE gd.code_id = ic.id
            AND gd.generator_model = ?
        ) < ?
        LIMIT ?
    """, (model_name, len(detail_levels), max_items))

    codes_to_process = cursor.fetchall()

    if not codes_to_process:
        print(f"    No codes need description generation for {model}")
        return {"processed": 0, "success": 0, "error": 0}

    print(f"    Generating descriptions for {len(codes_to_process)} codes using {model}")

    stats = {"processed": 0, "success": 0, "error": 0}

    for code_id, code, description in codes_to_process:
        result = _generate_descriptions_for_code(
            db, code_id, code, description, model_name, detail_levels
        )

        stats["processed"] += 1
        if result["success"]:
            stats["success"] += 1
        else:
            stats["error"] += 1

        if stats["processed"] % 10 == 0:
            print(f"      Progress: {stats['processed']}/{len(codes_to_process)} "
                  f"(success: {stats['success']}, errors: {stats['error']})")

    print(f"    Description generation complete: {stats}")
    return stats


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def generate_dataset() -> Dict[str, Any]:
    """
    Main entry point for Chapter 2 dataset generation.
    Handles internal workflow:
      2.0: Run prediction experiments
      2.1: Generate variant descriptions

    Returns:
        Dictionary with generation statistics
    """
    stats = {
        "chapter_2_0": {},
        "chapter_2_1": {}
    }

    # Chapter 2.0: Prediction Experiments (1 item per round for pipeline efficiency)
    print("  [2.0] Running prediction experiments...")
    db = MedicalCodingDB()
    system = MedicalCodingSystem()
    system.run_experiment(
        experiment_name=None,
        initial_batch_size=10,
        max_items=1,  # Process 1 item per round
        generate_reports=False
    )
    stats["chapter_2_0"] = {"status": "completed"}

    # Chapter 2.1: Generate Variant Descriptions (1 code = 11 variants)
    print("  [2.1] Generating variant descriptions...")
    stats["chapter_2_1"] = _generate_variant_descriptions(db, model="claude", max_items=1)  # 1 code per round

    return stats


def main():
    """Main entry point for CLI usage."""
    parser = argparse.ArgumentParser(
        description="Medical Coding Evaluation System - Chapter 2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python chapter_2.py status              # Show system status
  python chapter_2.py run                 # Run all experiments
  python chapter_2.py run -e claude       # Run Claude experiment only
  python chapter_2.py report              # Generate HTML reports
  python chapter_2.py clean               # Clean up old files
        """
    )

    parser.add_argument('command', choices=['status', 'run', 'report', 'clean'],
                       help='Command to execute')
    parser.add_argument('-e', '--experiment', help='Specific experiment to run')
    parser.add_argument('-b', '--batch-size', type=int, default=10,
                       help='Batch size for processing (default: 10)')
    parser.add_argument('-n', '--max-items', type=int, default=1000,
                       help='Maximum number of items to process per run (default: 1000)')

    args = parser.parse_args()

    # Prevent concurrent runs with lock file
    lock_file = 'chapter_2.lock'
    if args.command == 'run':
        if os.path.exists(lock_file):
            print("ERROR: Another instance is already running!")
            print(f"If you're sure no other instance is running, delete: {lock_file}")
            sys.exit(1)

        # Create lock file
        with open(lock_file, 'w') as f:
            f.write(str(os.getpid()))

        try:
            system = MedicalCodingSystem()
            system.run_experiment(args.experiment, args.batch_size, args.max_items)
        finally:
            # Always remove lock file on exit
            if os.path.exists(lock_file):
                os.remove(lock_file)
    else:
        system = MedicalCodingSystem()

        if args.command == 'status':
            system.status()
        elif args.command == 'report':
            system.generate_report()
        elif args.command == 'clean':
            # Clean up old files
            print("Cleaning up old files...")
            os.system("rm -rf old_files/*.py")
            print("Cleanup complete")


if __name__ == "__main__":
    main()
