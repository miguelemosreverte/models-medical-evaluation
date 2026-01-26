"""
Chapter 1: Methodology & Dataset for medical coding report.
"""

from typing import Dict


def generate_chapter_1_methodology(stats: Dict) -> str:
    """Generate Chapter 1: Methodology & Dataset."""
    return f"""
        <!-- Chapter 1: Methodology & Reproducibility -->
        <div class="chapter">
            <div class="chapter-title">Chapter 1: Methodology & Dataset</div>

            <h3>Dataset Statistics</h3>
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-label">Total ICD-10 Codes</div>
                    <div class="metric-value">{stats['total_codes']:,}</div>
                    <div class="metric-detail">From CMS 2024 dataset</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Codes Processed</div>
                    <div class="metric-value">{stats['processed_codes']:,}</div>
                    <div class="metric-detail">{(stats['processed_codes']/stats['total_codes']*100) if stats['total_codes'] > 0 else 0:.1f}% complete</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Quality Score</div>
                    <div class="metric-value">≥0.9</div>
                    <div class="metric-detail">High confidence threshold</div>
                </div>
            </div>

            <h3>Research Methodology</h3>
            <p style="margin-bottom: 15px;">
                This evaluation uses a standardized benchmark of ICD-10 codes from the Centers for Medicare & Medicaid Services (CMS)
                2024 dataset. Each code includes an official medical description, which serves as input to the language models.
                We measure precision, recall, and F1 scores to evaluate model performance in medical coding tasks.
            </p>

            <h3>Experimental Setup</h3>
            <div class="info-box">
                <div class="info-title">Model Configuration</div>
                <p style="margin-bottom: 10px;"><strong>Primary Models:</strong></p>
                <ul style="margin-left: 20px; margin-bottom: 10px;">
                    <li><strong>Claude (Anthropic)</strong>: claude-3-5-sonnet-20241022</li>
                    <li><strong>Codex (OpenAI)</strong>: gpt-4o-2024-11-20</li>
                </ul>
                <p style="margin-bottom: 10px;"><strong>Constrained Versions:</strong></p>
                <ul style="margin-left: 20px;">
                    <li>Both models tested with anti-hallucination instructions</li>
                    <li>Explicit constraints against over-specification</li>
                </ul>
            </div>

            <h3>Evaluation Metrics</h3>
            <table class="table-wsj">
                <thead>
                    <tr>
                        <th>Metric</th>
                        <th>Definition</th>
                        <th>Purpose</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>Precision</strong></td>
                        <td>TP / (TP + FP)</td>
                        <td>Measures accuracy of positive predictions</td>
                    </tr>
                    <tr>
                        <td><strong>Recall</strong></td>
                        <td>TP / (TP + FN)</td>
                        <td>Measures completeness of predictions</td>
                    </tr>
                    <tr>
                        <td><strong>F1 Score</strong></td>
                        <td>2 × (Precision × Recall) / (Precision + Recall)</td>
                        <td>Harmonic mean balancing precision and recall</td>
                    </tr>
                </tbody>
            </table>

            <h3>Technical Infrastructure</h3>
            <table class="table-wsj">
                <thead>
                    <tr>
                        <th>Component</th>
                        <th>Technology</th>
                        <th>Purpose</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>API Integration</td>
                        <td>Anthropic & OpenAI SDKs</td>
                        <td>Model inference</td>
                    </tr>
                    <tr>
                        <td>Async Processing</td>
                        <td>Python asyncio</td>
                        <td>Parallel batch processing</td>
                    </tr>
                    <tr>
                        <td>Database</td>
                        <td>SQLite3</td>
                        <td>State management and metrics</td>
                    </tr>
                </tbody>
            </table>
        </div>
"""
