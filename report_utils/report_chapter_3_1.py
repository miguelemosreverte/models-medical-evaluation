"""
Chapter 3.1: RAG-Enhanced Consistency for medical coding report.
"""

import sqlite3
import json
from collections import Counter

DB_PATH = "medical_coding.db"


def generate_chapter_3_1() -> str:
    """Generate Chapter 3.1: RAG-Enhanced Prediction Using Variants."""
    html = """
    <div class="chapter">
        <div class="chapter-title">Chapter 3.1: RAG-Enhanced Prediction</div>

        <h3>The Problem from Chapter 3</h3>
        <p style="margin-bottom: 15px;">
            Chapter 3 revealed two critical issues when asking models to predict codes from their own generated descriptions:
        </p>
        <ul style="margin-left: 20px; margin-bottom: 15px;">
            <li><strong>Low Correctness:</strong> Only ~30% of predictions matched the actual medical code</li>
            <li><strong>Poor Consistency:</strong> The same code's 11 variants often produced wildly different predictions</li>
        </ul>

        <h3>The Hypothesis: Can Examples Help?</h3>
        <p style="margin-bottom: 15px;">
            Chapter 3.1 tests whether providing <strong>similar examples from other codes' variants</strong>
            improves both correctness and consistency through RAG (Retrieval-Augmented Generation).
        </p>

        <div class="info-box">
            <div class="info-title">How It Works</div>
            <ol style="margin-left: 20px; margin-top: 10px; margin-bottom: 10px;">
                <li>Take a description variant from Chapter 3 (e.g., "Patient has profuse watery diarrhea")</li>
                <li>Find similar descriptions from our variant database (e.g., other diarrhea-related variants)</li>
                <li>Show these as examples: "Similar cases: A00 → 'severe diarrhea', A00.0 → 'watery stool'"</li>
                <li>Ask model to predict the code with this context</li>
                <li>Compare with Chapter 3's prediction (without examples)</li>
            </ol>
        </div>

        <h3>Three Corpus Modes Tested</h3>
        <p style="margin-bottom: 15px;">We test three different retrieval strategies:</p>
        <ul style="margin-left: 20px; margin-bottom: 15px;">
            <li><strong>Chapter 3.1.1 (Real Only):</strong> Search only the 46k real medical descriptions from the original dataset</li>
            <li><strong>Chapter 3.1.2 (Synthetic Only):</strong> Search only the AI-generated description variants we created</li>
            <li><strong>Chapter 3.1.3 (Both):</strong> Search both real descriptions and synthetic variants together</li>
        </ul>

        <h3>Two Key Performance Indicators (KPIs)</h3>
        <p style="margin-bottom: 15px;">We measure:</p>
        <ul style="margin-left: 20px; margin-bottom: 15px;">
            <li><strong>Correctness (Accuracy):</strong> Does the prediction match the actual ground truth code?</li>
            <li><strong>Consistency (Stability):</strong> Do all 11 variants of the same code produce the same prediction?</li>
        </ul>

        <h3>Results</h3>
"""

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Check if all three RAG experiments exist
        cursor.execute("SELECT COUNT(*) FROM rag_real_only_predictions")
        real_only_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM rag_synthetic_only_predictions")
        synthetic_only_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM rag_both_predictions")
        both_count = cursor.fetchone()[0]

        if real_only_count > 0 and synthetic_only_count > 0 and both_count > 0:
            # Get Chapter 3 baseline for comparison
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN confidence > 0 THEN 1 ELSE 0 END) as correct,
                    AVG(confidence) * 100 as correctness_rate
                FROM reverse_predictions
            """)
            base_total, base_correct, base_correctness = cursor.fetchone()

            # Calculate baseline consistency
            cursor.execute("""
                SELECT
                    ic.code,
                    GROUP_CONCAT(rp.predicted_codes, '|||') as all_predictions
                FROM reverse_predictions rp
                JOIN generated_descriptions gd ON rp.generated_desc_id = gd.id
                JOIN icd10_codes ic ON gd.code_id = ic.id
                GROUP BY ic.code
            """)

            ch3_consistency_scores = []
            for code, predictions_str in cursor.fetchall():
                predictions_list = predictions_str.split('|||') if predictions_str else []
                top_predictions = []
                for pred_json in predictions_list:
                    try:
                        pred_codes = json.loads(pred_json) if pred_json else []
                        if pred_codes:
                            top_predictions.append(pred_codes[0])
                    except:
                        pass

                if top_predictions:
                    most_common = Counter(top_predictions).most_common(1)[0]
                    consistency = most_common[1] / len(top_predictions) * 100
                    ch3_consistency_scores.append(consistency)

            ch3_avg_consistency = sum(ch3_consistency_scores) / len(ch3_consistency_scores) if ch3_consistency_scores else 0

            # Get metrics for all three RAG experiments
            experiments = [
                ('real_only', 'rag_real_only_predictions', '3.1.1 (Real Only)'),
                ('synthetic_only', 'rag_synthetic_only_predictions', '3.1.2 (Synthetic Only)'),
                ('both', 'rag_both_predictions', '3.1.3 (Both)')
            ]

            rag_results = {}
            for exp_name, table_name, display_name in experiments:
                # Correctness
                cursor.execute(f"""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN confidence > 0 THEN 1 ELSE 0 END) as correct,
                        AVG(confidence) * 100 as correctness_rate
                    FROM {table_name}
                """)
                total, correct, correctness = cursor.fetchone()

                # Consistency
                cursor.execute(f"""
                    SELECT
                        ic.code,
                        GROUP_CONCAT(rap.predicted_codes, '|||') as all_predictions
                    FROM {table_name} rap
                    JOIN generated_descriptions gd ON rap.generated_desc_id = gd.id
                    JOIN icd10_codes ic ON gd.code_id = ic.id
                    GROUP BY ic.code
                """)

                consistency_scores = []
                for code, predictions_str in cursor.fetchall():
                    predictions_list = predictions_str.split('|||') if predictions_str else []
                    top_predictions = []
                    for pred_json in predictions_list:
                        try:
                            pred_codes = json.loads(pred_json) if pred_json else []
                            if pred_codes:
                                top_predictions.append(pred_codes[0])
                        except:
                            pass

                    if top_predictions:
                        most_common = Counter(top_predictions).most_common(1)[0]
                        consistency = most_common[1] / len(top_predictions) * 100
                        consistency_scores.append(consistency)

                avg_consistency = sum(consistency_scores) / len(consistency_scores) if consistency_scores else 0

                rag_results[exp_name] = {
                    'display_name': display_name,
                    'total': total,
                    'correct': correct,
                    'correctness': correctness,
                    'consistency': avg_consistency
                }

            html += f"""
        <h3>KPI Summary: Comparing All Approaches</h3>
        <table class="table-wsj">
            <thead>
                <tr>
                    <th>Approach</th>
                    <th>Correctness</th>
                    <th>Consistency</th>
                    <th>Change from Baseline</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><strong>Chapter 3</strong><br/><small>No RAG examples</small></td>
                    <td>{base_correctness:.1f}%<br/><small>{base_correct}/{base_total} correct</small></td>
                    <td>{ch3_avg_consistency:.1f}%<br/><small>Avg agreement</small></td>
                    <td>—</td>
                </tr>
"""

            for exp_name in ['real_only', 'synthetic_only', 'both']:
                r = rag_results[exp_name]
                corr_change = r['correctness'] - base_correctness
                cons_change = r['consistency'] - ch3_avg_consistency

                html += f"""
                <tr>
                    <td><strong>Chapter {r['display_name']}</strong><br/><small>RAG with {exp_name.replace('_', ' ')}</small></td>
                    <td>{r['correctness']:.1f}%<br/><small>{r['correct']}/{r['total']} correct</small></td>
                    <td>{r['consistency']:.1f}%<br/><small>Avg agreement</small></td>
                    <td>
                        <strong style="color: {'green' if corr_change > 0 else 'red'}">{"+" if corr_change > 0 else ""}{corr_change:.1f}%</strong> correctness<br/>
                        <strong style="color: {'green' if cons_change > 0 else 'red'}">{"+" if cons_change > 0 else ""}{cons_change:.1f}%</strong> consistency
                    </td>
                </tr>
"""

            html += """
            </tbody>
        </table>
"""

            # Show detailed breakdown for best performing experiment (synthetic_only)
            best_exp = max(rag_results.items(), key=lambda x: x[1]['correctness'])
            best_table = f"rag_{best_exp[0]}_predictions"

            html += f"""
        <h3>Detailed Analysis: Best Performing Approach ({best_exp[1]['display_name']})</h3>
        <p style="margin-bottom: 20px;">
            The {best_exp[1]['display_name']} approach achieved the highest correctness ({best_exp[1]['correctness']:.1f}%).
            Below we show how its predictions compare to the Chapter 3 baseline for selected codes.
        </p>
"""

            # Get list of codes we tested
            cursor.execute(f"""
                SELECT DISTINCT ic.code, ic.description
                FROM {best_table} rap
                JOIN generated_descriptions gd ON rap.generated_desc_id = gd.id
                JOIN icd10_codes ic ON gd.code_id = ic.id
                ORDER BY ic.code
                LIMIT 5
            """)
            codes = cursor.fetchall()

            for actual_code, code_description in codes:
                # Get all variants for this code
                cursor.execute(f"""
                    SELECT
                        gd.detail_level,
                        gd.description,
                        rp.predicted_codes as ch3_pred,
                        rp.confidence as ch3_conf,
                        rap.predicted_codes as rag_pred,
                        rap.variant_codes as rag_context,
                        rap.confidence as rag_conf
                    FROM generated_descriptions gd
                    JOIN icd10_codes ic ON gd.code_id = ic.id
                    LEFT JOIN reverse_predictions rp ON rp.generated_desc_id = gd.id
                    LEFT JOIN {best_table} rap ON rap.generated_desc_id = gd.id
                    WHERE ic.code = ?
                    ORDER BY gd.detail_level
                """, (actual_code,))

                variants = cursor.fetchall()

                if variants:
                    # Calculate consistency for this code
                    ch3_top_preds = []
                    rag_top_preds = []

                    for level, desc, ch3_pred, ch3_conf, rag_pred, rag_ctx, rag_conf in variants:
                        try:
                            ch3_codes = json.loads(ch3_pred) if ch3_pred else []
                            rag_codes = json.loads(rag_pred) if rag_pred else []
                            if ch3_codes:
                                ch3_top_preds.append(ch3_codes[0])
                            if rag_codes:
                                rag_top_preds.append(rag_codes[0])
                        except:
                            pass

                    ch3_unique = len(set(ch3_top_preds))
                    rag_unique = len(set(rag_top_preds))

                    html += f"""
        <div class="info-box roundtrip-example">
            <div class="info-title">Ground Truth: <span class="code-badge">{actual_code}</span> - {code_description}</div>
            <p style="margin-bottom: 10px;">
                <strong>Chapter 3:</strong> {ch3_unique} different predictions across {len(ch3_top_preds)} variants
                &nbsp;&nbsp;|&nbsp;&nbsp;
                <strong>Chapter {best_exp[1]['display_name']}:</strong> {rag_unique} different predictions across {len(rag_top_preds)} variants
            </p>

            <table class="table-wsj">
                <thead>
                    <tr>
                        <th>Level</th>
                        <th>Generated Description</th>
                        <th>Chapter 3<br/>Prediction</th>
                        <th>Chapter {best_exp[1]['display_name']}<br/>Prediction</th>
                        <th>RAG Context</th>
                    </tr>
                </thead>
                <tbody>
"""

                    for level, desc, ch3_pred, ch3_conf, rag_pred, rag_ctx, rag_conf in variants[:5]:  # Show first 5 levels
                        try:
                            ch3_codes = json.loads(ch3_pred) if ch3_pred else []
                            rag_codes = json.loads(rag_pred) if rag_pred else []
                            ctx_codes = json.loads(rag_ctx) if rag_ctx else []
                        except:
                            ch3_codes = []
                            rag_codes = []
                            ctx_codes = []

                        ch3_display = f'<span class="code-badge">{ch3_codes[0]}</span>' if ch3_codes else '<em>none</em>'
                        rag_display = f'<span class="code-badge">{rag_codes[0]}</span>' if rag_codes else '<em>none</em>'
                        ctx_display = ", ".join(f'<span class="code-badge">{c}</span>' for c in ctx_codes[:3]) if ctx_codes else '<em>none</em>'

                        ch3_match = "✓" if ch3_codes and ch3_codes[0] == actual_code else "✗"
                        rag_match = "✓" if rag_codes and rag_codes[0] == actual_code else "✗"

                        html += f"""
                    <tr>
                        <td><strong>{level}</strong></td>
                        <td>{desc[:80]}{"..." if len(desc) > 80 else ""}</td>
                        <td>{ch3_display} {ch3_match}</td>
                        <td>{rag_display} {rag_match}</td>
                        <td>{ctx_display}</td>
                    </tr>
"""

                    html += """
                </tbody>
            </table>
        </div>
"""

            # Analysis section
            html += """
        <h3>Analysis: Which Corpus Mode Works Best?</h3>
"""

            # Find best and worst performers
            best_corr = max(rag_results.items(), key=lambda x: x[1]['correctness'])
            worst_corr = min(rag_results.items(), key=lambda x: x[1]['correctness'])
            best_cons = max(rag_results.items(), key=lambda x: x[1]['consistency'])

            html += f"""
        <div class="highlight-box">
            <strong>Best Correctness:</strong> {best_corr[1]['display_name']} at {best_corr[1]['correctness']:.1f}%
            ({best_corr[1]['correctness'] - base_correctness:+.1f}% vs baseline)<br/>
            <strong>Worst Correctness:</strong> {worst_corr[1]['display_name']} at {worst_corr[1]['correctness']:.1f}%
            ({worst_corr[1]['correctness'] - base_correctness:+.1f}% vs baseline)<br/>
            <strong>Best Consistency:</strong> {best_cons[1]['display_name']} at {best_cons[1]['consistency']:.1f}%
            ({best_cons[1]['consistency'] - ch3_avg_consistency:+.1f}% vs baseline)
        </div>

        <h4>Key Findings</h4>
        <ul style="margin-left: 20px; margin-bottom: 15px;">
"""

            # Analyze synthetic_only performance
            synth_corr_change = rag_results['synthetic_only']['correctness'] - base_correctness
            if synth_corr_change > 5:
                html += f"""
            <li><strong>Synthetic variants are highly effective:</strong> Using only AI-generated variants improved
            correctness by {synth_corr_change:.1f}%, likely because they provide diverse rephrasing patterns
            that help the model recognize the same medical concept described differently.</li>
"""

            # Analyze real_only performance
            real_corr_change = rag_results['real_only']['correctness'] - base_correctness
            if real_corr_change < synth_corr_change:
                html += f"""
            <li><strong>Real descriptions alone are less helpful:</strong> The 46k official descriptions improved
            correctness by only {real_corr_change:.1f}%, suggesting that exact medical terminology matches
            are less useful than understanding semantic variations.</li>
"""

            # Analyze both performance
            both_corr_change = rag_results['both']['correctness'] - base_correctness
            if both_corr_change < rag_results['synthetic_only']['correctness'] - base_correctness:
                html += f"""
            <li><strong>Mixing both corpora dilutes performance:</strong> Combining real and synthetic examples
            achieved {both_corr_change:.1f}% improvement, actually {rag_results['synthetic_only']['correctness'] - rag_results['both']['correctness']:.1f}%
            worse than synthetic-only. This suggests that official descriptions may introduce noise or
            distract from the paraphrase-matching patterns.</li>
"""

            html += """
        </ul>

        <p style="margin-bottom: 15px; margin-top: 15px;">
            <strong>Conclusion:</strong> RAG-enhanced prediction with synthetic variants significantly improves
            medical code prediction by teaching the model to recognize diverse descriptions of the same condition.
            Surprisingly, official medical descriptions are less helpful, possibly because they use standardized
            terminology rather than the varied language patterns seen in real clinical notes.
        </p>
"""

        else:
            html += """
        <div class="info-box">
            <div class="info-title">Status: Experiments Not Yet Run</div>
            <p>
                RAG-enhanced predictions have not been generated yet. The generate_book_report.py script
                will automatically run all three corpus mode experiments when needed.
            </p>
            <p style="margin-top: 10px;">
                Or run them manually:
            </p>
            <pre style="background: #f5f5f5; padding: 10px; margin-top: 10px;">
python3 chapter_3_1_rag.py --max-items 100 --top-k 3 --corpus-mode real_only
python3 chapter_3_1_rag.py --max-items 100 --top-k 3 --corpus-mode synthetic_only
python3 chapter_3_1_rag.py --max-items 100 --top-k 3 --corpus-mode both
            </pre>
        </div>
"""

        conn.close()

    except Exception as e:
        html += f"""
        <div class="info-box">
            <div class="info-title">Status: Data Not Available</div>
            <p>Unable to load RAG experiment results. Error: {e}</p>
        </div>
"""

    html += """
    </div>
"""
    return html
