"""Report utilities package."""

from .report_styles import get_wsj_style
from .report_database import get_database_stats, get_chart_data, calculate_model_metrics
from .report_chapter_1 import generate_chapter_1_methodology
from .report_chapter_2_1 import generate_chapter_2_1_constrained_comparison
from .report_chapter_3 import generate_chapter_3_bidirectional_consistency
from .report_chapter_3_1 import generate_chapter_3_1
from .report_chapter_3_2 import generate_chapter_3_2
from .report_chapter_3_3 import generate_chapter_3_3
from .report_chapter_3_4 import generate_chapter_3_4
from .report_chapter_4 import generate_chapter_4
from .report_chapter_5 import generate_chapter_5
from .wsj_charts import get_chart_script

__all__ = [
    'get_wsj_style',
    'get_database_stats',
    'get_chart_data',
    'calculate_model_metrics',
    'generate_chapter_1_methodology',
    'generate_chapter_2_1_constrained_comparison',
    'generate_chapter_3_bidirectional_consistency',
    'generate_chapter_3_1',
    'generate_chapter_3_2',
    'generate_chapter_3_3',
    'generate_chapter_3_4',
    'generate_chapter_4',
    'generate_chapter_5',
    'get_chart_script',
]
