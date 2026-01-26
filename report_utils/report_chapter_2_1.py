"""
Chapter 2.1: Constrained Prompting Comparison for medical coding report.
"""

import sqlite3
from .report_database import calculate_model_metrics

DB_PATH = "medical_coding.db"


def generate_chapter_2_1_constrained_comparison() -> str:
    """Generate Chapter 2.1: Constrained Prompting Comparison."""
    html = """
    <div class="chapter">
        <div class="chapter-title">Chapter 2.1: Constrained Prompting Analysis</div>

        <h3>Introduction: The Hallucination Problem</h3>
        <p style="margin-bottom: 15px;">
            In baseline experiments (Chapter 2), we observed that models sometimes generate ICD-10 codes
            with higher specificity than warranted by the input description. For example, given a general
            description like "Cholera", a model might predict specific subtypes (e.g., A00.1) rather than
            the general code (A00). This phenomenon—known as <strong>hallucination</strong> or
            <strong>over-specification</strong>—can lead to reduced precision.
        </p>

        <h3>Hypothesis</h3>
        <div class="info-box">
            <div class="info-title">Anti-Hallucination Instructions</div>
            <p>We hypothesize that adding explicit anti-hallucination instructions to the system prompt
            will improve precision by reducing false positives from over-specification. Specifically, we
            instruct models to:</p>
            <ul style="margin-left: 20px; margin-top: 10px;">
                <li>Provide ONLY codes that can be DEFINITIVELY inferred from the description</li>
                <li>NOT add specificity beyond what is explicitly stated</li>
                <li>Prefer general codes over specific subtypes when details are absent</li>
                <li>Avoid false positives by not hallucinating details</li>
            </ul>
        </div>

        <h3>Experimental Setup</h3>
        <p style="margin-bottom: 15px;">
            We created constrained versions of both Claude and Codex models with modified system prompts
            that include the anti-hallucination instructions above. All other parameters (temperature,
            dataset, evaluation metrics) remain identical to baseline experiments.
        </p>

        <h3>Results: Baseline vs. Constrained</h3>
"""

    # Calculate metrics for all four models using our reusable helper
    try:
        metrics_data = {}
        for model in ['claude', 'codex', 'claude_constrained', 'codex_constrained']:
            metrics = calculate_model_metrics(model)
            if metrics:
                metrics_data[model] = metrics

        # Generate comparison table
        if len(metrics_data) >= 2:
            html += """
        <table class="table-wsj">
            <thead>
                <tr>
                    <th>Model</th>
                    <th>Type</th>
                    <th>Precision</th>
                    <th>Recall</th>
                    <th>F1 Score</th>
                    <th>TP / FP / FN</th>
                    <th>Predictions</th>
                </tr>
            </thead>
            <tbody>
"""

            # Claude baseline
            if 'claude' in metrics_data:
                m = metrics_data['claude']
                html += f"""
                <tr>
                    <td><strong>CLAUDE</strong></td>
                    <td>Baseline</td>
                    <td>{m['precision']:.1f}%</td>
                    <td>{m['recall']:.1f}%</td>
                    <td>{m['f1']:.1f}%</td>
                    <td>{m['tp']} / {m['fp']} / {m['fn']}</td>
                    <td>{m['total']:,}</td>
                </tr>
"""

            # Claude constrained
            if 'claude_constrained' in metrics_data:
                m = metrics_data['claude_constrained']
                html += f"""
                <tr style="background-color: #f8f9fa;">
                    <td><strong>CLAUDE CONSTRAINED</strong></td>
                    <td>Anti-hallucination</td>
                    <td>{m['precision']:.1f}%</td>
                    <td>{m['recall']:.1f}%</td>
                    <td>{m['f1']:.1f}%</td>
                    <td>{m['tp']} / {m['fp']} / {m['fn']}</td>
                    <td>{m['total']:,}</td>
                </tr>
"""

            # Codex baseline
            if 'codex' in metrics_data:
                m = metrics_data['codex']
                html += f"""
                <tr>
                    <td><strong>CODEX</strong></td>
                    <td>Baseline</td>
                    <td>{m['precision']:.1f}%</td>
                    <td>{m['recall']:.1f}%</td>
                    <td>{m['f1']:.1f}%</td>
                    <td>{m['tp']} / {m['fp']} / {m['fn']}</td>
                    <td>{m['total']:,}</td>
                </tr>
"""

            # Codex constrained
            if 'codex_constrained' in metrics_data:
                m = metrics_data['codex_constrained']
                html += f"""
                <tr style="background-color: #f8f9fa;">
                    <td><strong>CODEX CONSTRAINED</strong></td>
                    <td>Anti-hallucination</td>
                    <td>{m['precision']:.1f}%</td>
                    <td>{m['recall']:.1f}%</td>
                    <td>{m['f1']:.1f}%</td>
                    <td>{m['tp']} / {m['fp']} / {m['fn']}</td>
                    <td>{m['total']:,}</td>
                </tr>
"""

            html += """
            </tbody>
        </table>

        <h3>Analysis</h3>
        <p style="margin-bottom: 15px;">
"""

            # Generate dynamic analysis based on results
            if 'claude' in metrics_data and 'claude_constrained' in metrics_data:
                claude_precision_diff = metrics_data['claude_constrained']['precision'] - metrics_data['claude']['precision']
                claude_recall_diff = metrics_data['claude_constrained']['recall'] - metrics_data['claude']['recall']

                html += f"""
            <strong>Claude:</strong> The constrained version shows a precision change of
            {claude_precision_diff:+.1f}% and recall change of {claude_recall_diff:+.1f}% compared to baseline.
"""

            if 'codex' in metrics_data and 'codex_constrained' in metrics_data:
                codex_precision_diff = metrics_data['codex_constrained']['precision'] - metrics_data['codex']['precision']
                codex_recall_diff = metrics_data['codex_constrained']['recall'] - metrics_data['codex']['recall']

                html += f"""
            <strong>Codex:</strong> The constrained version shows a precision change of
            {codex_precision_diff:+.1f}% and recall change of {codex_recall_diff:+.1f}% compared to baseline.
"""

            html += """
        </p>

        <div class="info-box">
            <div class="info-title">Key Findings</div>
            <p>Anti-hallucination instructions impact model behavior by explicitly constraining
            the specificity of predictions. The trade-off between precision and recall reveals
            whether models benefit from explicit guidance on avoiding over-specification.</p>
        </div>
"""
        else:
            html += """
        <div class="info-box">
            <div class="info-title">Status: Experiments In Progress</div>
            <p>Constrained prompting experiments are currently running. Results will appear here
            as data becomes available.</p>
        </div>
"""

    except Exception as e:
        html += f"""
        <div class="info-box">
            <div class="info-title">Status: Data Not Available</div>
            <p>Unable to load constrained experiment results. Error: {e}</p>
        </div>
"""

    html += """
    </div>
"""
    return html

