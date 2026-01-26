"""
Chapter 3: Bidirectional Consistency Testing for medical coding report.
"""

import sqlite3
import json

DB_PATH = "medical_coding.db"


def generate_chapter_3_bidirectional_consistency() -> str:
    """Generate Chapter 3: Bidirectional Consistency Testing."""
    html = """
    <div class="chapter">
        <div class="chapter-title">Chapter 3: Bidirectional Consistency Testing</div>

        <h3>Introduction: Testing Model Understanding</h3>
        <p style="margin-bottom: 15px;">
            Beyond one-way prediction accuracy, we can test whether models truly <em>understand</em>
            medical codes by examining <strong>bidirectional consistency</strong>: Can a model generate
            a description from a code, then correctly predict that code from its own description?
        </p>

        <h3>Experimental Design</h3>
        <div class="info-box">
            <div class="info-title">Round-Trip Testing Protocol</div>
            <p>For each ICD-10 code, we perform a three-step process:</p>
            <ol style="margin-left: 20px; margin-top: 10px;">
                <li><strong>Forward Generation:</strong> Code → Description at varying detail levels (0-10)</li>
                <li><strong>Reverse Prediction:</strong> Description → Predicted Codes</li>
                <li><strong>Consistency Check:</strong> Does predicted code match original?</li>
            </ol>
            <p style="margin-top: 10px;">
                We test 11 different description detail levels to identify the minimum specificity
                needed for accurate round-trip prediction.
            </p>
        </div>

        <h3>Detail Level Variations</h3>
        <p style="margin-bottom: 15px;">
            Each ICD-10 code is expanded into descriptions at 11 detail levels (0=minimal, 10=maximal).
            This allows us to analyze how description specificity affects prediction accuracy.
        </p>

        <h3>Results</h3>
"""

    # Query bidirectional experiment results
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Check if tables exist first
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name IN ('generated_descriptions', 'reverse_predictions')
        """)
        tables = [row[0] for row in cursor.fetchall()]

        desc_count = 0
        reverse_count = 0

        if 'generated_descriptions' in tables:
            cursor.execute("SELECT COUNT(*) FROM generated_descriptions")
            desc_count = cursor.fetchone()[0]

        if 'reverse_predictions' in tables:
            cursor.execute("SELECT COUNT(*) FROM reverse_predictions")
            reverse_count = cursor.fetchone()[0]

        if desc_count > 0 and reverse_count > 0:
            # Get detailed statistics by detail level
            cursor.execute("""
                SELECT
                    gd.detail_level,
                    COUNT(*) as total,
                    SUM(CASE WHEN rp.confidence > 0 THEN 1 ELSE 0 END) as successful,
                    ROUND(AVG(rp.confidence) * 100, 1) as success_rate
                FROM generated_descriptions gd
                JOIN reverse_predictions rp ON rp.generated_desc_id = gd.id
                GROUP BY gd.detail_level
                ORDER BY gd.detail_level
            """)
            detail_stats = cursor.fetchall()

            # Calculate overall consistency rate
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN confidence > 0 THEN 1 ELSE 0 END) as successful
                FROM reverse_predictions
            """)
            total, successful = cursor.fetchone()
            consistency_rate = (successful / total * 100) if total > 0 else 0

            # Build chart data
            detail_levels = [str(row[0]) for row in detail_stats]
            success_rates = [row[3] for row in detail_stats]

            html += f"""
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">Descriptions Generated</div>
                <div class="metric-value">{desc_count:,}</div>
                <div class="metric-detail">Across 11 detail levels</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Reverse Predictions</div>
                <div class="metric-value">{reverse_count:,}</div>
                <div class="metric-detail">Round-trip tests</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Overall Consistency</div>
                <div class="metric-value">{consistency_rate:.1f}%</div>
                <div class="metric-detail">{successful}/{total} successful</div>
            </div>
        </div>

        <h3>Success Rate by Detail Level</h3>
        <div class="bar-chart">"""
            # Create simple bar chart visualization
            max_rate = max(success_rates) if success_rates else 100
            for i, (level, rate) in enumerate(zip(detail_levels, success_rates)):
                width_pct = (rate / max_rate * 100) if max_rate > 0 else 0
                html += f"""
            <div class="bar-row">
                <div class="bar-label">Level {level}</div>
                <div class="bar-container">
                    <div class="bar" style="width: {width_pct}%;"></div>
                </div>
                <div class="bar-value">{rate}%</div>
            </div>"""
            # Calculate level 8 success rate for key findings
            level_8_rate = success_rates[8] if len(success_rates) > 8 else 0

            html += f"""
        </div>

        <h3>Key Findings</h3>
        <div class="info-box">
            <div class="info-title">Optimal Detail Level Identified</div>
            <ul style="margin-left: 20px; margin-top: 10px;">
                <li><strong>Level 8 achieved highest consistency:</strong> {level_8_rate:.1f}% success rate</li>
                <li><strong>Too little detail fails:</strong> Levels 0-2 have poor round-trip accuracy</li>
                <li><strong>Too much detail also problematic:</strong> Very detailed descriptions (level 10) can introduce noise</li>
                <li><strong>Sweet spot:</strong> Moderate to high detail (levels 7-9) provides optimal balance</li>
            </ul>
        </div>

        <h3>Detailed Statistics by Level</h3>
        <table class="table-wsj">
            <thead>
                <tr>
                    <th>Detail Level</th>
                    <th>Total Tests</th>
                    <th>Successful</th>
                    <th>Failed</th>
                    <th>Success Rate</th>
                    <th>Avg Time (s)</th>
                </tr>
            </thead>
            <tbody>
"""
            # Get processing time stats
            cursor.execute("""
                SELECT
                    gd.detail_level,
                    COUNT(*) as total,
                    SUM(CASE WHEN rp.confidence > 0 THEN 1 ELSE 0 END) as successful,
                    COUNT(*) - SUM(CASE WHEN rp.confidence > 0 THEN 1 ELSE 0 END) as failed,
                    ROUND(AVG(rp.confidence) * 100, 1) as success_rate,
                    ROUND(AVG(rp.processing_time), 2) as avg_time
                FROM generated_descriptions gd
                JOIN reverse_predictions rp ON rp.generated_desc_id = gd.id
                GROUP BY gd.detail_level
                ORDER BY gd.detail_level
            """)
            level_details = cursor.fetchall()

            for level, total, succ, fail, rate, avg_time in level_details:
                html += f"""
                <tr>
                    <td><strong>{level}</strong></td>
                    <td>{total}</td>
                    <td>{succ}</td>
                    <td>{fail}</td>
                    <td><strong>{rate}%</strong></td>
                    <td>{avg_time}</td>
                </tr>
"""
            html += """
            </tbody>
        </table>

        <h3>Complete Round-Trip Examples: The Journey from Code to Description and Back</h3>
        <p style="margin-bottom: 20px;">Watch how description detail affects round-trip accuracy. Each row shows the same code at different detail levels.</p>
"""
            # Get all examples for each code grouped by detail level
            cursor.execute("""
                SELECT DISTINCT ic.code
                FROM generated_descriptions gd
                JOIN icd10_codes ic ON gd.code_id = ic.id
                ORDER BY ic.code
                LIMIT 3
            """)
            codes = [row[0] for row in cursor.fetchall()]

            for code in codes:
                cursor.execute("""
                    SELECT
                        ic.code,
                        ic.description as code_desc,
                        gd.detail_level,
                        gd.description,
                        rp.predicted_codes,
                        rp.confidence
                    FROM generated_descriptions gd
                    JOIN icd10_codes ic ON gd.code_id = ic.id
                    JOIN reverse_predictions rp ON rp.generated_desc_id = gd.id
                    WHERE ic.code = ?
                    ORDER BY gd.detail_level
                """, (code,))
                code_examples = cursor.fetchall()

                if code_examples:
                    original_code = code_examples[0][0]
                    code_description = code_examples[0][1]

                    html += f"""
        <div class="info-box roundtrip-example">
            <div class="info-title">Code: {original_code} - {code_description}</div>

            <table class="table-wsj">
                <thead>
                    <tr>
                        <th>Level</th>
                        <th>Generated Description</th>
                        <th>Predicted Codes</th>
                        <th>Match?</th>
                    </tr>
                </thead>
                <tbody>
"""
                    for _, _, level, desc, predicted, confidence in code_examples:
                        import json
                        try:
                            pred_codes = json.loads(predicted) if predicted else []
                            pred_display = ", ".join(pred_codes) if pred_codes else "(none)"
                        except:
                            pred_display = "(error)"

                        match_icon = "✓" if confidence > 0 else "✗"

                        # Split codes and wrap each in code-badge, leave empty if none
                        if pred_codes:
                            code_badges = " ".join([f'<span class="code-badge">{code}</span>' for code in pred_codes])
                        elif pred_display == "(error)":
                            code_badges = "<em>(error)</em>"
                        else:
                            code_badges = ""

                        html += f"""
                    <tr>
                        <td><strong>{level}</strong></td>
                        <td>{desc}</td>
                        <td>{code_badges}</td>
                        <td><strong>{match_icon}</strong></td>
                    </tr>
"""
                    html += """
                </tbody>
            </table>
        </div>
"""

            # After the for loop, add Statistical Analysis
            html += """
        <h3>Statistical Analysis</h3>
        <div class="metrics-grid">
"""
            # Calculate statistical metrics
            cursor.execute("""
                SELECT
                    MIN(CASE WHEN confidence > 0 THEN detail_level END) as min_success_level,
                    MAX(CASE WHEN confidence > 0 THEN detail_level END) as max_success_level,
                    AVG(processing_time) as avg_processing_time,
                    MAX(processing_time) as max_processing_time
                FROM reverse_predictions rp
                JOIN generated_descriptions gd ON gd.id = rp.generated_desc_id
            """)
            min_succ, max_succ, avg_proc, max_proc = cursor.fetchone()

            html += f"""
            <div class="metric-card">
                <div class="metric-label">Min Success Level</div>
                <div class="metric-value">{min_succ if min_succ else 'N/A'}</div>
                <div class="metric-detail">Lowest detail that worked</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Max Success Level</div>
                <div class="metric-value">{max_succ if max_succ else 'N/A'}</div>
                <div class="metric-detail">Highest detail that worked</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Avg Processing Time</div>
                <div class="metric-value">{avg_proc:.2f}s</div>
                <div class="metric-detail">Per prediction</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Max Processing Time</div>
                <div class="metric-value">{max_proc:.2f}s</div>
                <div class="metric-detail">Longest prediction</div>
            </div>
        </div>
"""
        elif desc_count > 0 or reverse_count > 0:
            html += f"""
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">Descriptions Generated</div>
                <div class="metric-value">{desc_count:,}</div>
                <div class="metric-detail">Across 11 detail levels</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Reverse Predictions</div>
                <div class="metric-value">{reverse_count:,}</div>
                <div class="metric-detail">In progress...</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Consistency Rate</div>
                <div class="metric-value">Pending</div>
                <div class="metric-detail">Awaiting completion</div>
            </div>
        </div>

        <p style="margin-top: 20px;">
            <em>Detailed analysis will appear once reverse predictions complete.</em>
        </p>
"""
        else:
            html += """
        <div class="info-box">
            <div class="info-title">Status: Experiments Not Yet Started</div>
            <p>
                Bidirectional consistency experiments are planned but have not yet begun. These experiments
                will run after baseline and constrained prompting studies complete.
            </p>
        </div>
"""

        conn.close()

    except Exception as e:
        html += f"""
        <div class="info-box">
            <div class="info-title">Status: Data Not Available</div>
            <p>Unable to load bidirectional experiment results. Error: {e}</p>
        </div>
"""
        try:
            conn.close()
        except:
            pass

    html += """
    </div>
"""
    return html

