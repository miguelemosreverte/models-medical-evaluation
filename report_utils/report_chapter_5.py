"""
Chapter 5: Cost Analysis for medical coding report.
"""

import sqlite3


def generate_chapter_5(db_path: str, timestamp: str) -> str:
    """Generate Chapter 5: Cost Analysis."""
    html = """
        <!-- Chapter 5: Cost Analysis -->
        <div class="chapter">
            <div class="chapter-title">Chapter 5: Cost Analysis</div>

            <h3>Token Usage & Actual Costs</h3>"""

    # Get actual token usage and costs from database
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get token usage and calculate costs
        cursor.execute("""
            SELECT
                mp.model_name,
                COUNT(*) as predictions,
                SUM(mp.input_tokens) as total_input,
                SUM(mp.output_tokens) as total_output,
                mc.cost_per_1k_input_tokens,
                mc.cost_per_1k_output_tokens
            FROM model_predictions mp
            JOIN model_config mc ON mp.model_name = mc.model_name
            GROUP BY mp.model_name
        """)

        cost_data = {}
        for row in cursor.fetchall():
            model = row[0]
            predictions = row[1]
            input_tokens = row[2] or 0
            output_tokens = row[3] or 0
            cost_per_1k_input = row[4]
            cost_per_1k_output = row[5]

            actual_cost = (input_tokens / 1000.0 * cost_per_1k_input +
                          output_tokens / 1000.0 * cost_per_1k_output)

            # Calculate average tokens per prediction for projection
            avg_input = input_tokens / predictions if predictions > 0 else 0
            avg_output = output_tokens / predictions if predictions > 0 else 0

            cost_data[model] = {
                'predictions': predictions,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'actual_cost': actual_cost,
                'cost_per_1k_input': cost_per_1k_input,
                'cost_per_1k_output': cost_per_1k_output,
                'avg_input': avg_input,
                'avg_output': avg_output
            }

        conn.close()

        html += """
        <table class="table-wsj">
            <thead>
                <tr>
                    <th>Model</th>
                    <th>Predictions</th>
                    <th>Input Tokens</th>
                    <th>Output Tokens</th>
                    <th>Actual Cost</th>
                </tr>
            </thead>
            <tbody>"""

        for model_name in ['claude', 'codex', 'claude_constrained', 'codex_constrained']:
            if model_name in cost_data:
                data = cost_data[model_name]
                html += f"""
                <tr>
                    <td><strong>{model_name.upper().replace('_', ' ')}</strong></td>
                    <td>{data['predictions']:,}</td>
                    <td>{data['input_tokens']:,}</td>
                    <td>{data['output_tokens']:,}</td>
                    <td>${data['actual_cost']:.4f}</td>
                </tr>"""

        html += """
            </tbody>
        </table>

        <h3>Cost Rates</h3>
        <table class="table-wsj">
            <thead>
                <tr>
                    <th>Model</th>
                    <th>Cost per 1K Input</th>
                    <th>Cost per 1K Output</th>
                </tr>
            </thead>
            <tbody>"""

        for model_name in ['claude', 'codex', 'claude_constrained', 'codex_constrained']:
            if model_name in cost_data:
                data = cost_data[model_name]
                html += f"""
                <tr>
                    <td><strong>{model_name.upper().replace('_', ' ')}</strong></td>
                    <td>${data['cost_per_1k_input']:.3f}</td>
                    <td>${data['cost_per_1k_output']:.3f}</td>
                </tr>"""

        html += """
            </tbody>
        </table>"""

        # Calculate projections based on actual averages
        if cost_data:
            html += """
        <div class="highlight-box">
            <strong>Cost Projections (based on actual usage patterns):</strong><br>"""

            for model_name in ['claude', 'codex', 'claude_constrained', 'codex_constrained']:
                if model_name in cost_data:
                    data = cost_data[model_name]
                    # Project costs for different scales
                    cost_per_item = (data['avg_input'] / 1000.0 * data['cost_per_1k_input'] +
                                   data['avg_output'] / 1000.0 * data['cost_per_1k_output'])

                    cost_1k = cost_per_item * 1000
                    cost_10k = cost_per_item * 10000
                    cost_full = cost_per_item * 46237

                    html += f"""
            • <strong>{model_name.capitalize()}:</strong> 1K items: ${cost_1k:.2f} | 10K items: ${cost_10k:.2f} | Full dataset (46,237): ${cost_full:.2f}<br>"""

            html += """
        </div>"""

    except Exception as e:
        html += f"""
        <div class="info-box">
            <strong>Note:</strong> Cost data not available yet. Run predictions to see actual costs.
        </div>"""

    html += """
    </div>"""

    html += """
    <!-- Footer -->
    <div style="margin-top: 60px; padding-top: 30px; border-top: 1px solid #ddd;">
        <p style="text-align: center; color: #666; font-size: 12px;">
            Generated by Medical Coding System v1.0 • """ + timestamp + """
        </p>
    </div>
</div>
"""

    return html
