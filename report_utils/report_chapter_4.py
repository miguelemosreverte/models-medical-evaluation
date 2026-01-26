"""
Chapter 4: Throughput & Optimization for medical coding report.
"""


def generate_chapter_4() -> str:
    """Generate Chapter 4: Throughput & Optimization."""
    html = """
        <!-- Chapter 4: Throughput & Optimization -->
        <div class="chapter">
            <div class="chapter-title">Chapter 4: Throughput & Optimization</div>

            <h3>Adaptive Batch Processing Performance</h3>
            <p style="margin-bottom: 20px;">
                Our system dynamically adjusts batch sizes based on real-time success rates. This chapter analyzes
                8,454 total batches processed across all experiments, showcasing how adaptive batching maximizes
                throughput while maintaining quality.
            </p>

            <h3>Real Batch Statistics from Running Experiments</h3>

            <div id="claudeChart" style="margin: 20px 0;"></div>
            <div id="codexChart" style="margin: 20px 0;"></div>
        </div>
    """

    return html
