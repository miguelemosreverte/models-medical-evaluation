#!/usr/bin/env python3

import json
import sqlite3
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime

def load_predictions(model_name):
    """Load predictions for a specific model."""
    file_path = Path(f"medical_coding_dataset.{model_name}.jsonl")
    if not file_path.exists():
        return None

    predictions = []
    with open(file_path, 'r') as f:
        for line in f:
            predictions.append(json.loads(line))
    return predictions

def get_code_descriptions():
    """Get ICD-10 code descriptions from database."""
    descriptions = {}
    try:
        conn = sqlite3.connect('medical_coding.db')
        cursor = conn.cursor()
        cursor.execute("SELECT code, description FROM icd10_codes")
        for code, desc in cursor.fetchall():
            descriptions[code] = desc
        conn.close()
    except:
        pass
    return descriptions

def classify_mismatch(predicted_code, golden_code):
    """Classify the type of mismatch between codes."""
    # Check if codes are in same family (first 3 chars)
    if predicted_code[:3] == golden_code[:3]:
        # Same family, different specificity
        if len(predicted_code) < len(golden_code):
            return "less_specific"  # e.g., R05 vs R05.9
        else:
            return "wrong_subtype"  # e.g., R05.1 vs R05.9
    return "different_family"  # Completely different codes

def calculate_metrics(predictions):
    """Calculate precision, recall, F1 for each prediction and overall."""
    metrics = []
    all_true_positives = 0
    all_false_positives = 0
    all_false_negatives = 0

    # Get code descriptions
    code_descriptions = get_code_descriptions()

    code_stats = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})

    for pred in predictions:
        golden = set(pred.get("golden_codes", []))
        predicted = set(pred.get("codes", []))

        true_positives = golden & predicted
        false_positives = predicted - golden
        false_negatives = golden - predicted

        # Classify mismatches for better understanding
        fp_classifications = {}
        for fp_code in false_positives:
            # Find if this is a family match with any golden code
            for golden_code in golden:
                if fp_code[:3] == golden_code[:3]:
                    fp_classifications[fp_code] = classify_mismatch(fp_code, golden_code)
                    break
            else:
                fp_classifications[fp_code] = "different_family"

        fn_classifications = {}
        for fn_code in false_negatives:
            # Find if this is a family match with any predicted code
            for pred_code in predicted:
                if fn_code[:3] == pred_code[:3]:
                    fn_classifications[fn_code] = classify_mismatch(pred_code, fn_code)
                    break
            else:
                fn_classifications[fn_code] = "different_family"

        # Update per-code statistics
        for code in true_positives:
            code_stats[code]["tp"] += 1
        for code in false_positives:
            code_stats[code]["fp"] += 1
        for code in false_negatives:
            code_stats[code]["fn"] += 1

        # Calculate metrics for this prediction
        tp = len(true_positives)
        fp = len(false_positives)
        fn = len(false_negatives)

        all_true_positives += tp
        all_false_positives += fp
        all_false_negatives += fn

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

        metrics.append({
            "text": pred["text"],
            "golden": sorted(list(golden)),  # Sort for consistent display
            "predicted": sorted(list(predicted)),  # Sort for consistent display
            "true_positives": sorted(list(true_positives)),
            "false_positives": sorted(list(false_positives)),
            "false_negatives": sorted(list(false_negatives)),
            "fp_classifications": fp_classifications,
            "fn_classifications": fn_classifications,
            "code_descriptions": code_descriptions,
            "precision": precision,
            "recall": recall,
            "f1": f1
        })

    # Calculate overall metrics
    overall_precision = all_true_positives / (all_true_positives + all_false_positives) if (all_true_positives + all_false_positives) > 0 else 0
    overall_recall = all_true_positives / (all_true_positives + all_false_negatives) if (all_true_positives + all_false_negatives) > 0 else 0
    overall_f1 = 2 * (overall_precision * overall_recall) / (overall_precision + overall_recall) if (overall_precision + overall_recall) > 0 else 0

    return {
        "predictions": metrics,
        "overall": {
            "true_positives": all_true_positives,
            "false_positives": all_false_positives,
            "false_negatives": all_false_negatives,
            "precision": overall_precision,
            "recall": overall_recall,
            "f1": overall_f1
        },
        "code_stats": dict(code_stats)
    }

def generate_html_report(results):
    """Generate an HTML report with WSJ-style design and model comparison."""

    # Collect all models data
    models_data = {}
    for model in ["claude", "codex"]:
        predictions = load_predictions(model)
        if predictions:
            models_data[model] = calculate_metrics(predictions)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Medical Coding Model Evaluation</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: Georgia, 'Times New Roman', serif;
            line-height: 1.5;
            color: #000;
            background: #fff;
            padding: 40px 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        h1 {{
            font-size: 36px;
            font-weight: normal;
            margin-bottom: 8px;
            border-bottom: 1px solid #000;
            padding-bottom: 12px;
        }}
        h2 {{
            font-size: 24px;
            font-weight: normal;
            margin: 40px 0 20px 0;
            padding-top: 20px;
            border-top: 1px solid #ddd;
        }}
        h3 {{
            font-size: 14px;
            font-weight: bold;
            margin: 30px 0 16px 0;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        }}
        .timestamp {{
            color: #666;
            font-size: 13px;
            margin-bottom: 40px;
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        }}
        .executive-summary {{
            background: #f9f9f9;
            border-left: 3px solid #0066cc;
            padding: 20px;
            margin: 30px 0;
            font-size: 16px;
        }}
        .comparison-section {{
            margin: 40px 0;
        }}
        .comparison-grid {{
            display: grid;
            grid-template-columns: 150px repeat(2, 1fr);
            gap: 1px;
            background: #000;
            border: 1px solid #000;
            margin: 20px 0;
        }}
        .comparison-header {{
            background: #000;
            color: #fff;
            padding: 12px;
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 1px;
            text-align: center;
        }}
        .comparison-metric {{
            background: #f5f5f5;
            padding: 12px;
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            font-size: 12px;
            font-weight: bold;
            text-transform: uppercase;
        }}
        .comparison-value {{
            background: white;
            padding: 12px;
            text-align: center;
            font-size: 20px;
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        }}
        .comparison-value.winner {{
            background: #e8f4fd;
            font-weight: bold;
        }}
        .performance-chart {{
            margin: 40px 0;
        }}
        .bar-chart {{
            margin: 20px 0;
        }}
        .bar-row {{
            display: grid;
            grid-template-columns: 120px 1fr 60px;
            align-items: center;
            margin: 8px 0;
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            font-size: 13px;
        }}
        .bar-label {{
            text-align: right;
            padding-right: 12px;
            font-weight: bold;
        }}
        .bar-container {{
            background: #f0f0f0;
            height: 24px;
            position: relative;
        }}
        .bar {{
            height: 100%;
            background: #0066cc;
            position: relative;
        }}
        .bar-value {{
            padding-left: 8px;
            font-weight: bold;
        }}
        .model-section {{
            margin: 60px 0;
            padding-top: 40px;
            border-top: 2px solid #000;
        }}
        .model-name {{
            font-size: 20px;
            font-weight: bold;
            margin-bottom: 24px;
            letter-spacing: 0.5px;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 1px;
            background: #ddd;
            border: 1px solid #ddd;
            margin-bottom: 40px;
        }}
        .metric-card {{
            background: white;
            padding: 20px;
            text-align: center;
        }}
        .metric-label {{
            font-size: 11px;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        }}
        .metric-value {{
            font-size: 32px;
            font-weight: normal;
            color: #000;
        }}
        .code-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        }}
        .code-table th, .code-table td {{
            padding: 12px 8px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        .code-table th {{
            background: #000;
            color: white;
            font-weight: normal;
            text-transform: uppercase;
            font-size: 11px;
            letter-spacing: 0.5px;
        }}
        .code-table tr:hover {{
            background: #f8f8f8;
        }}
        .code-badge {{
            display: inline-block;
            padding: 2px 6px;
            font-size: 11px;
            font-family: 'Courier New', monospace;
            background: #f0f0f0;
            border: 1px solid #ddd;
            margin: 2px;
        }}
        .tp-badge {{
            background: #fff;
            border: 1px solid #000;
            font-weight: bold;
        }}
        .fp-badge {{
            background: #f0f0f0;
            border: 1px solid #999;
        }}
        .fn-badge {{
            background: #fff;
            border: 1px dashed #666;
            opacity: 0.7;
        }}
        .prediction-card {{
            background: white;
            border-top: 1px solid #ddd;
            border-bottom: 1px solid #ddd;
            padding: 20px 0;
            margin-bottom: 20px;
        }}
        .prediction-text {{
            font-style: italic;
            color: #333;
            margin-bottom: 12px;
            font-size: 14px;
        }}
        .codes-row {{
            margin: 20px 0;
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            font-size: 13px;
        }}
        .codes-label {{
            font-size: 11px;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #666;
            margin-bottom: 6px;
        }}
        .no-predictions {{
            text-align: center;
            padding: 60px;
            color: #666;
            font-style: italic;
            border: 1px dashed #ddd;
        }}
        .insight-box {{
            background: #fff;
            border: 1px solid #000;
            padding: 20px;
            margin: 20px 0;
        }}
        .insight-title {{
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            font-size: 12px;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Medical Coding Model Evaluation Report</h1>
        <div class="timestamp">Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</div>
"""

    # Executive Summary
    if models_data:
        html += """
        <div class="executive-summary">
            <strong>Executive Summary:</strong> Performance evaluation of medical coding models from the Anthropic (Claude)
            and OpenAI (Codex) families on ICD-10 code prediction tasks. The analysis measures precision, recall,
            and F1 scores across diverse medical descriptions.
        </div>
"""

    # Model Comparison Section
    if len(models_data) >= 2:
        html += """
        <h2>Model Performance Comparison</h2>

        <div class="comparison-section">
            <div class="comparison-grid">
                <div class="comparison-header">Metric</div>
                <div class="comparison-header">Anthropic (Claude)</div>
                <div class="comparison-header">OpenAI (Codex)</div>
"""

        claude_metrics = models_data.get("claude", {}).get("overall", {})
        codex_metrics = models_data.get("codex", {}).get("overall", {})

        metrics = [
            ("Precision", "precision"),
            ("Recall", "recall"),
            ("F1 Score", "f1"),
            ("True Positives", "true_positives"),
            ("False Positives", "false_positives"),
            ("False Negatives", "false_negatives")
        ]

        for label, key in metrics:
            claude_val = claude_metrics.get(key, 0)
            codex_val = codex_metrics.get(key, 0)

            if key in ["precision", "recall", "f1"]:
                claude_str = f"{claude_val:.1%}"
                codex_str = f"{codex_val:.1%}"
                winner = "claude" if claude_val > codex_val else "codex" if codex_val > claude_val else None
            else:
                claude_str = str(claude_val)
                codex_str = str(codex_val)
                if key == "true_positives":
                    winner = "claude" if claude_val > codex_val else "codex" if codex_val > claude_val else None
                else:  # false positives/negatives - lower is better
                    winner = "claude" if claude_val < codex_val else "codex" if codex_val < claude_val else None

            html += f"""
                <div class="comparison-metric">{label}</div>
                <div class="comparison-value {'winner' if winner == 'claude' else ''}">{claude_str}</div>
                <div class="comparison-value {'winner' if winner == 'codex' else ''}">{codex_str}</div>
"""

        html += """
            </div>
        </div>

        <div class="performance-chart">
            <h3>F1 Score Comparison</h3>
            <div class="bar-chart">
"""

        # Bar chart for F1 scores
        for model_name, display_name in [("claude", "Anthropic (Claude)"), ("codex", "OpenAI (Codex)")]:
            if model_name in models_data:
                f1 = models_data[model_name]["overall"]["f1"]
                html += f"""
                <div class="bar-row">
                    <div class="bar-label">{display_name}</div>
                    <div class="bar-container">
                        <div class="bar" style="width: {f1*100}%"></div>
                    </div>
                    <div class="bar-value">{f1:.1%}</div>
                </div>
"""

        html += """
            </div>
        </div>
"""

        # Key Insights
        if claude_metrics and codex_metrics:
            claude_f1 = claude_metrics.get("f1", 0)
            codex_f1 = codex_metrics.get("f1", 0)

            winner = "Anthropic (Claude)" if claude_f1 > codex_f1 else "OpenAI (Codex)"
            margin = abs(claude_f1 - codex_f1) * 100

            html += f"""
        <div class="insight-box">
            <div class="insight-title">Key Findings</div>
            <ul style="margin-left: 20px;">
                <li>{winner} demonstrates superior overall performance with a {margin:.1f} percentage point lead in F1 score.</li>
                <li>Both models show strong capability in medical code prediction, with F1 scores above {min(claude_f1, codex_f1)*100:.0f}%.</li>
                <li>Error patterns suggest opportunities for ensemble approaches to improve accuracy.</li>
            </ul>
        </div>
"""

    # Individual Model Details
    for model, display_name in [("claude", "ANTHROPIC (CLAUDE)"), ("codex", "OPENAI (CODEX)")]:
        if model not in models_data:
            html += f"""
        <div class="model-section">
            <div class="model-name">{display_name}</div>
            <div class="no-predictions">No predictions found. Run: python3 generate_predictions.py {model}</div>
        </div>
"""
            continue

        metrics = models_data[model]
        overall = metrics["overall"]

        html += f"""
        <div class="model-section">
            <div class="model-name">{display_name}</div>

            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-label">Precision</div>
                    <div class="metric-value">{overall['precision']:.1%}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Recall</div>
                    <div class="metric-value">{overall['recall']:.1%}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">F1 Score</div>
                    <div class="metric-value">{overall['f1']:.1%}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">True Positives</div>
                    <div class="metric-value">{overall['true_positives']}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">False Positives</div>
                    <div class="metric-value">{overall['false_positives']}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">False Negatives</div>
                    <div class="metric-value">{overall['false_negatives']}</div>
                </div>
            </div>

            <h3>Most Problematic Codes</h3>
            <table class="code-table">
                <thead>
                    <tr>
                        <th>ICD-10 Code</th>
                        <th>True Positives</th>
                        <th>False Positives</th>
                        <th>False Negatives</th>
                        <th>F1 Score</th>
                    </tr>
                </thead>
                <tbody>
"""

        # Calculate F1 for each code and sort by error rate
        code_metrics = []
        for code, stats in metrics["code_stats"].items():
            tp = stats["tp"]
            fp = stats["fp"]
            fn = stats["fn"]
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
            error_score = fp + fn
            code_metrics.append((code, tp, fp, fn, f1, error_score))

        # Sort by error score (descending) to show most problematic first
        code_metrics.sort(key=lambda x: x[5], reverse=True)

        # Show top 10 most problematic codes
        for code, tp, fp, fn, f1, _ in code_metrics[:10]:
            html += f"""
                    <tr>
                        <td><span class="code-badge">{code}</span></td>
                        <td>{tp}</td>
                        <td>{fp}</td>
                        <td>{fn}</td>
                        <td>{f1:.1%}</td>
                    </tr>
"""

        html += """
                </tbody>
            </table>

            <h3>Sample Predictions</h3>
"""

        # Show detailed predictions
        for pred in metrics["predictions"][:3]:  # Show first 3
            # Build code descriptions for display
            code_desc = pred.get('code_descriptions', {})

            # Format expected codes with nomenclature
            expected_display = []
            for code in sorted(pred['golden']):
                desc = code_desc.get(code, 'Not found in dataset')
                expected_display.append(f'<div style="margin: 4px 0;"><span class="code-badge">{code}</span> <span style="font-size: 12px; color: #666; margin-left: 8px;">{desc}</span></div>')

            # Format predicted codes with nomenclature
            predicted_display = []
            for code in sorted(pred['predicted']):
                desc = code_desc.get(code, 'Not found in dataset')
                predicted_display.append(f'<div style="margin: 4px 0;"><span class="code-badge">{code}</span> <span style="font-size: 12px; color: #666; margin-left: 8px;">{desc}</span></div>')

            # Build analysis table with all unique codes
            all_codes = set(pred['golden']) | set(pred['predicted'])

            # Build table rows for analysis
            table_rows = []
            for code in sorted(all_codes):
                is_expected = code in pred['golden']
                is_predicted = code in pred['predicted']
                desc = code_desc.get(code, 'Not found in dataset')

                # Determine the match status and explanation
                if is_expected and is_predicted:
                    status = "Match"
                    explanation = "Correctly predicted"
                elif is_expected and not is_predicted:
                    status = "Missed"
                    # Check if there's a related predicted code
                    related = None
                    for p_code in pred['predicted']:
                        if p_code[:3] == code[:3]:
                            related = p_code
                            break
                    if related:
                        explanation = f"Model predicted {related} instead (less specific)" if len(related) < len(code) else f"Model predicted {related} instead (different subtype)"
                    else:
                        explanation = "Not predicted by model"
                elif not is_expected and is_predicted:
                    status = "Extra"
                    # Check if this relates to an expected code
                    related = None
                    for e_code in pred['golden']:
                        if code[:3] == e_code[:3]:
                            related = e_code
                            break
                    if related:
                        if len(code) < len(related):
                            explanation = f"Less specific than expected {related}"
                        else:
                            explanation = f"Wrong subtype (expected {related})"
                    else:
                        explanation = "Not in golden truth"

                table_rows.append({
                    'code': code,
                    'is_expected': is_expected,
                    'is_predicted': is_predicted,
                    'description': desc,
                    'status': status,
                    'explanation': explanation
                })

            html += f"""
            <div class="prediction-card">
                <div class="prediction-text">"{pred['text']}"</div>
                <div style="margin-top: 20px;">
                    <div class="codes-label">Analysis</div>
                    <table style="width: 100%; border-collapse: collapse; margin-top: 12px; font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 13px;">
                        <thead>
                            <tr style="background: #f5f5f5;">
                                <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">Code</th>
                                <th style="padding: 10px; text-align: center; border-bottom: 2px solid #ddd;">Expected</th>
                                <th style="padding: 10px; text-align: center; border-bottom: 2px solid #ddd;">Predicted</th>
                                <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">Description</th>
                                <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">Note</th>
                            </tr>
                        </thead>
                        <tbody>
"""

            for row in table_rows:
                expected_mark = '<span class="code-badge" style="background: #fff; border: 1px solid #000;">✓</span>' if row['is_expected'] else ''
                predicted_mark = '<span class="code-badge" style="background: #fff; border: 1px solid #000;">✓</span>' if row['is_predicted'] else ''

                html += f"""
                            <tr>
                                <td style="padding: 8px; border-bottom: 1px solid #eee;">
                                    <span class="code-badge">{row['code']}</span>
                                </td>
                                <td style="padding: 8px; text-align: center; border-bottom: 1px solid #eee;">
                                    {expected_mark}
                                </td>
                                <td style="padding: 8px; text-align: center; border-bottom: 1px solid #eee;">
                                    {predicted_mark}
                                </td>
                                <td style="padding: 8px; border-bottom: 1px solid #eee; font-size: 12px; color: #666;">
                                    {row['description']}
                                </td>
                                <td style="padding: 8px; border-bottom: 1px solid #eee; font-size: 12px; color: #666;">
                                    {row['explanation']}
                                </td>
                            </tr>
"""

            html += """
                        </tbody>
                    </table>
                </div>
            </div>
"""

        html += """
        </div>
"""

    html += """
    </div>
</body>
</html>
"""

    # Write the HTML file
    with open("index.html", "w") as f:
        f.write(html)

    print("HTML report generated: index.html")

def main():
    print("Evaluating model predictions...")
    results = {}

    for model in ["claude", "codex"]:
        predictions = load_predictions(model)
        if predictions:
            results[model] = calculate_metrics(predictions)
            print(f"\n{model.upper()} Results:")
            print(f"  Precision: {results[model]['overall']['precision']:.1%}")
            print(f"  Recall: {results[model]['overall']['recall']:.1%}")
            print(f"  F1 Score: {results[model]['overall']['f1']:.1%}")

    generate_html_report(results)

if __name__ == "__main__":
    main()