#!/usr/bin/env python3
"""
Generate comprehensive book-like HTML report with WSJ aesthetic.

Smart Behavior:
- Checks if dataset generation is running
- If not running and no data exists, starts dataset generation for 1 hour
- Generates report with whatever data is available
- Can be run anytime to get current progress
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
import subprocess
import os
import time
from report_utils import (
    get_wsj_style,
    get_database_stats,
    get_chart_data,
    calculate_model_metrics,
    generate_chapter_1_methodology,
    generate_chapter_2_1_constrained_comparison,
    generate_chapter_3_bidirectional_consistency,
    generate_chapter_3_1,
    generate_chapter_3_2,
    generate_chapter_3_3,
    generate_chapter_3_4,
    generate_chapter_4,
    generate_chapter_5,
    get_chart_script,
)


LOCK_FILE = ".dataset_generation.lock"


def is_generation_running() -> bool:
    """Check if dataset generation is currently running."""
    return os.path.exists(LOCK_FILE)


def check_if_data_exists() -> bool:
    """Check if any experimental data exists."""
    try:
        conn = sqlite3.connect("medical_coding.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM generated_descriptions")
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except:
        return False


def start_dataset_generation_if_needed():
    """Smart startup: Start dataset generation if needed."""

    if is_generation_running():
        print("✓ Dataset generation is already running")
        return

    if check_if_data_exists():
        print("✓ Dataset exists, skipping generation startup")
        return

    # No data and not running - start it!
    print("\n" + "="*70)
    print("📊 NO DATASET FOUND - Starting background data generation...")
    print("="*70)
    print("")
    print("This will:")
    print("  1. Start dataset_generation.py in the background")
    print("  2. Run for initial data generation (~1 hour)")
    print("  3. Continue running to completion")
    print("")
    print("You can monitor progress at: http://localhost:5001/api/progress/markdown")
    print("")
    print("="*70)

    # Start dataset generation in background
    subprocess.Popen(
        ['python3', 'dataset_generation.py',
         '--batch-size', '10',
         '--variants-per-round', '500',
         '--predictions-per-round', '500',
         '--port', '5001'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True  # Detach from parent
    )

    print("\n⏳ Waiting 60 seconds for initial data generation...")
    print("   (Report will show progress even with partial data)")
    time.sleep(60)
    print("\n✓ Proceeding with report generation...\n")


class BookReportGenerator:
    def __init__(self):
        self.db_path = "medical_coding.db"
        self.timestamp = datetime.now().strftime('%B %d, %Y at %I:%M %p')

    def setup_experiment_tables(self):
        """Setup all experiment tables."""
        print("Setting up experiment tables...")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create three tables for the three corpus modes
        for corpus_mode in ['real_only', 'synthetic_only', 'both']:
            table_name = f"rag_{corpus_mode}_predictions"

            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    generated_desc_id INTEGER NOT NULL,
                    model_name TEXT NOT NULL,
                    predicted_codes TEXT NOT NULL,
                    num_variants_used INTEGER NOT NULL,
                    variant_codes TEXT,
                    confidence REAL,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    processing_time REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (generated_desc_id) REFERENCES generated_descriptions(id)
                )
            """)

            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{corpus_mode}_desc
                ON {table_name}(generated_desc_id)
            """)

            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{corpus_mode}_model
                ON {table_name}(model_name)
            """)

        # Legacy table for backwards compatibility
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rag_enhanced_predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                generated_desc_id INTEGER NOT NULL,
                model_name TEXT NOT NULL,
                predicted_codes TEXT NOT NULL,
                num_variants_used INTEGER NOT NULL,
                variant_codes TEXT,
                confidence REAL,
                input_tokens INTEGER,
                output_tokens INTEGER,
                processing_time REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (generated_desc_id) REFERENCES generated_descriptions(id)
            )
        """)

        conn.commit()
        conn.close()
        print("✓ Experiment tables ready")

    def run_experiments(self):
        """Run all experiments if data is missing."""
        # Always setup tables first
        self.setup_experiment_tables()

        print("Checking for missing experiment data...")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check all three RAG experiments
        experiments_to_run = []
        for corpus_mode in ['real_only', 'synthetic_only', 'both']:
            table_name = f"rag_{corpus_mode}_predictions"
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            if count == 0:
                experiments_to_run.append(corpus_mode)

        conn.close()

        # Run missing experiments
        for corpus_mode in experiments_to_run:
            print(f"\nRunning Chapter 3.1.{['real_only', 'synthetic_only', 'both'].index(corpus_mode) + 1} ({corpus_mode}) experiment...")
            result = subprocess.run(
                ['python3', 'chapter_3_1_rag.py',
                 '--max-items', '33',
                 '--top-k', '5',
                 '--corpus-mode', corpus_mode],
                capture_output=True,
                text=True,
                timeout=600
            )
            if result.returncode == 0:
                print(f"✓ Chapter 3.1 ({corpus_mode}) completed")
            else:
                print(f"⚠ Chapter 3.1 ({corpus_mode}) had issues: {result.stderr[:200]}")

    def get_evaluation_section(self) -> str:
        """Import the evaluation section from evaluate_models.py if available."""
        try:
            # Try to run evaluate_models.py and capture its HTML output
            result = subprocess.run(['python3', 'evaluate_models.py'],
                                  capture_output=True, text=True)

            # Parse the generated HTML to extract the full comparison and model sections
            if Path('index.html').exists():
                with open('index.html', 'r') as f:
                    html = f.read()
                    # Extract from comparison through all model sections
                    start = html.find('<h2>Model Performance Comparison</h2>')
                    # Find the closing container div (just before closing body)
                    end = html.find('</div>\n</body>')
                    if start != -1 and end != -1:
                        # Get everything from Model Performance Comparison to the end
                        content = html[start:end]
                        # Remove any duplicate closing divs
                        content = content.replace('</div>\n\n    </div>', '</div>')
                        return content
        except:
            pass

        # Generate evaluation section from database experiment data
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get experiment statistics from model_predictions table
            cursor.execute("""
                SELECT
                    model_name,
                    COUNT(*) as total_processed,
                    SUM(CASE WHEN confidence > 0.5 THEN 1 ELSE 0 END) as successes,
                    AVG(processing_time) as avg_time,
                    AVG(input_tokens) as avg_tokens_input,
                    AVG(output_tokens) as avg_tokens_output
                FROM model_predictions
                GROUP BY model_name
            """)

            results = cursor.fetchall()

            if not results:
                return """
                <h2>Model Performance Comparison</h2>
                <div class="info-box">
                    <div class="info-title">No Data Available</div>
                    Experiment data is still being collected. Please wait for processing to complete.
                </div>
                """

            # Get sample results for demonstration
            cursor.execute("""
                SELECT
                    i.code,
                    i.description,
                    mp.predicted_codes,
                    CASE WHEN mp.confidence > 0.5 THEN 1 ELSE 0 END as success,
                    mp.model_name
                FROM model_predictions mp
                JOIN icd10_codes i ON mp.code_id = i.id
                WHERE mp.predicted_codes IS NOT NULL
                ORDER BY mp.id DESC
                LIMIT 10
            """)

            samples = cursor.fetchall()

            html = "<h2>Model Performance Comparison</h2>"

            # Performance metrics table
            html += """
            <h3>Performance Metrics</h3>
            <table class="comparison-table">
                <thead>
                    <tr>
                        <th>Model</th>
                        <th>Processed</th>
                        <th>Success Rate</th>
                        <th>Avg Response Time</th>
                        <th>Avg Tokens (In/Out)</th>
                    </tr>
                </thead>
                <tbody>
            """

            for model_name, total, successes, avg_time, avg_in, avg_out in results:
                success_rate = (successes / total * 100) if total > 0 else 0
                model_display = "Claude" if "claude" in model_name.lower() else "Codex"
                html += f"""
                    <tr>
                        <td><strong>{model_display}</strong></td>
                        <td>{total:,}</td>
                        <td>{success_rate:.1f}%</td>
                        <td>{avg_time:.1f}s</td>
                        <td>{int(avg_in or 0)}/{int(avg_out or 0)}</td>
                    </tr>
                """

            html += "</tbody></table>"

            # Sample results
            if samples:
                html += """
                <h3>Sample Results</h3>
                <table class="samples-table">
                    <thead>
                        <tr>
                            <th>Original Code</th>
                            <th>Description</th>
                            <th>Predicted</th>
                            <th>Match</th>
                            <th>Model</th>
                        </tr>
                    </thead>
                    <tbody>
                """

                for code, desc, predicted, success, model_name in samples:
                    model_display = "Claude" if "claude" in model_name.lower() else "Codex"
                    match_icon = "✓" if success else "✗"
                    match_class = "success" if success else "failure"

                    # Truncate description if too long
                    display_desc = desc[:50] + "..." if len(desc) > 50 else desc

                    html += f"""
                        <tr>
                            <td><code class="code-badge">{code}</code></td>
                            <td>{display_desc}</td>
                            <td><code class="code-badge">{predicted or 'None'}</code></td>
                            <td><span class="{match_class}">{match_icon}</span></td>
                            <td>{model_display}</td>
                        </tr>
                    """

                html += "</tbody></table>"

            conn.close()
            return html

        except Exception as e:
            return f"""
            <h2>Model Performance Comparison</h2>
            <div class="info-box">
                <div class="info-title">Error</div>
                Unable to generate comparison data: {str(e)}
            </div>
            """

    def generate_report(self) -> str:
        """Generate the complete book-like HTML report."""
        self.run_experiments()
        stats = get_database_stats()
        chart_data = get_chart_data()
        evaluation_section = self.get_evaluation_section()

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Medical Coding System - Comprehensive Report</title>
    <!-- No external chart libraries needed - using custom SVG implementation -->
    <style>
        {get_wsj_style()}
    </style>
</head>
<body>
    <div class="container">
        <h1>Medical Coding System</h1>
        <div class="timestamp">Comprehensive Report • Generated: {self.timestamp}</div>

        <div class="executive-summary">
            <strong>Executive Summary:</strong> This comprehensive report documents the medical coding system's
            performance, comparing AI models from Anthropic (Claude) and OpenAI (Codex) on ICD-10 code prediction tasks.
            The system processes {stats['total_codes']:,} medical codes with adaptive batch optimization,
            real-time performance tracking, and detailed cost analysis.
        </div>

        <!-- Table of Contents -->
        <div class="toc">
            <div class="toc-title">Table of Contents</div>
            <div class="toc-item">Chapter 1: Methodology & Dataset</div>
            <div class="toc-item">Chapter 2: Model Performance Comparison</div>
            <div class="toc-item">Chapter 2.1: Constrained Prompting Analysis</div>
            <div class="toc-item">Chapter 3: Bidirectional Consistency Testing</div>
            <div class="toc-item">Chapter 4: Throughput & Optimization</div>
            <div class="toc-item">Chapter 5: Cost Analysis</div>
        </div>

        {generate_chapter_1_methodology(stats)}

        <!-- Chapter 2: Model Performance Comparison (THE CROWN JEWEL) -->
        <div class="chapter">
            <div class="chapter-title">Chapter 2: Model Performance Comparison</div>
            {evaluation_section}
        </div>

        <!-- Chapter 2.1: Constrained Prompting Analysis -->
        {generate_chapter_2_1_constrained_comparison()}

        <!-- Chapter 3.0: Bidirectional Consistency Testing -->
        {generate_chapter_3_bidirectional_consistency()}

        <!-- Chapter 3.1: RAG-Enhanced Prediction -->
        {generate_chapter_3_1()}

        <!-- Chapter 3.2: Billable Code Filtering -->
        {generate_chapter_3_2()}

        <!-- Chapter 3.3: Dense Variant Generation -->
        {generate_chapter_3_3()}

        <!-- Chapter 3.4: Dense RAG with Negative Examples -->
        {generate_chapter_3_4()}

        {generate_chapter_4()}

        {generate_chapter_5(self.db_path, self.timestamp)}

    <!-- Custom SVG chart implementation -->
    <script>
        // Get data from database
        const claudeData = """ + json.dumps(chart_data['claude']) + """;
        const codexData = """ + json.dumps(chart_data['codex']) + """;
        const claudeConstrainedData = """ + json.dumps(chart_data['claude_constrained']) + """;
        const codexConstrainedData = """ + json.dumps(chart_data['codex_constrained']) + """;

        """ + get_chart_script() + """
    </script>
</body>
</html>"""

        return html

    def save_report(self, filename="book_report.html"):
        """Generate and save the report."""
        html = self.generate_report()
        with open(filename, 'w') as f:
            f.write(html)
        print(f"Book-like report generated: {filename}")
        return filename

def main():
    # Smart startup: Check and start dataset generation if needed
    start_dataset_generation_if_needed()

    # Generate report
    generator = BookReportGenerator()
    filename = generator.save_report()

    # Don't automatically open in browser - let user open manually
    # if os.path.exists(filename):
    #     subprocess.run(['open', filename])

if __name__ == "__main__":
    main()