# Medical Coding Dataset Generator - Scientific Research Edition

## Overview

A comprehensive, reproducible system for generating medical coding datasets using Large Language Models (LLMs) with adaptive batch processing, token tracking, and cost analysis.

## Features

### 🔬 Scientific Reproducibility
- **Deterministic data fetching** from official CMS sources
- **SHA256 checksums** for data integrity
- **Complete processing history** in SQLite database
- **Time series tracking** of all metrics

### 📊 Adaptive Batch Processing
- **Dynamic batch sizing** that adapts to model performance
- **Automatic rate limiting** to respect API constraints
- **Token usage tracking** for cost optimization
- **Throughput optimization** with real-time adjustments

### 💰 Cost Analysis
- **Per-model token tracking** (input/output)
- **Real-time cost calculation** based on current API pricing
- **Cost projections** for larger datasets
- **Cost per entry** metrics

### 📈 Performance Metrics
- **Throughput monitoring** (items/second)
- **Latency tracking** (ms per request)
- **Success/failure rates** per model
- **Time series visualization** in HTML reports

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd models-medical-evaluation

# Install Python dependencies (standard library only!)
# No external dependencies required - uses only Python standard library

# Verify required tools
which python3 curl
```

## Quick Start

### One-Command Pipeline

```bash
# Generate 1000 dataset entries with full pipeline
python3 run_pipeline.py --target-size 1000

# Use specific model only
python3 run_pipeline.py --target-size 500 --model claude

# Skip data fetching if already downloaded
python3 run_pipeline.py --target-size 2000 --skip-fetch
```

## Architecture

### Data Flow

```
1. Data Fetching (fetch_icd10_cms.py)
   ↓
2. Database Import (db_manager_v2.py)
   ↓
3. Adaptive Processing (adaptive_batch_processor.py)
   ↓
4. Quality Scoring & Dataset Generation
   ↓
5. Report Generation (generate_report.py)
```

### Database Schema

```sql
-- Core Tables
icd10_codes           -- All ICD-10 codes from CMS
model_predictions     -- Model outputs with token tracking
batch_metrics        -- Batch processing performance
batch_size_history   -- Adaptive sizing history
time_series_metrics  -- Time series data for charts
model_config         -- Model costs and limits
dataset_entries      -- Generated training data
```

## File Structure

```
models-medical-evaluation/
├── run_pipeline.py              # Main orchestration script
├── fetch_icd10_cms.py          # Reproducible data fetcher
├── db_manager_v2.py            # Enhanced database with metrics
├── adaptive_batch_processor.py # Smart batch processing
├── generate_report.py          # HTML report with charts
│
├── raw_data/                   # Downloaded source data
│   ├── 2024-ICD-10-CM.zip
│   └── icd10cm_tabular_2024.xml
│
├── data/                       # Processed data
│   └── icd10_cms_catalog.csv
│
├── medical_coding.db          # SQLite database
│
├── descriptions-to-codes.golden.jsonl  # High-quality dataset
├── descriptions-to-codes.all.jsonl     # Complete dataset
└── index.html                          # Interactive report
```

## Adaptive Batch Processing Algorithm

The system automatically adjusts batch sizes per model:

1. **Start** with default batch size (10)
2. **On Success**: After 3 consecutive successes, increase by 1
3. **On Failure**: After 2 failures or timeout, decrease by 1
4. **Bounds**: Min=1, Max=50
5. **Track** optimal size in database

## Token & Cost Tracking

### Token Estimation
- Input: ~4 characters per token or 0.75 words
- Output: Actual response length

### Cost Calculation
```python
cost = (input_tokens/1000 * cost_per_1k_input) +
       (output_tokens/1000 * cost_per_1k_output)
```

### Default Pricing (USD)
- **Claude**: $0.015/1K input, $0.075/1K output
- **Codex**: $0.010/1K input, $0.030/1K output
- **Gemini**: $0.0035/1K input, $0.0105/1K output

## Metrics Tracked

### Per Request
- Input/output tokens
- Processing time
- Batch size
- Success/failure
- Quality score

### Time Series (for charts)
- Throughput (items/second)
- Batch size evolution
- Token usage over time
- Cost accumulation

### Aggregate
- Average/peak/min throughput
- Optimal batch sizes
- Total costs per model
- Category coverage

## Quality Scoring

Each generated entry receives a quality score (0-1):

- **1.0**: Original code perfectly matched
- **0.7-0.9**: Code in prediction list
- **0.5-0.7**: Partial match
- **<0.5**: Poor match (excluded from golden dataset)

## Output Files

### Datasets
- `descriptions-to-codes.golden.jsonl`: High-quality entries (quality ≥ 0.7)
- `descriptions-to-codes.all.jsonl`: All generated entries

### Format
```json
{
  "text": "Acute myocardial infarction",
  "codes": ["I21.9"],
  "quality": 0.95,
  "source_code": "I21.9"
}
```

### Report
- `index.html`: Interactive report with charts
  - Cost analysis
  - Throughput time series
  - Batch size evolution
  - Quality distribution
  - Category coverage

## Monitoring Progress

The system provides real-time feedback:

```
📈 Increasing claude batch size: 10 → 11
✓ Success: 11/11
📉 Decreasing codex batch size: 15 → 14
Progress: 250/1000
claude: 2.45 items/sec, batch size: 11
codex: 1.89 items/sec, batch size: 14
```

## Database Queries

```python
from db_manager_v2 import MedicalCodingDB

db = MedicalCodingDB()

# Get statistics
stats = db.get_statistics()

# Get time series data
throughput_data = db.get_time_series_data(
    metric_type='throughput',
    hours=24
)

# Get cost summary
costs = db.get_cost_summary()

# Get batch performance
perf = db.get_batch_performance_stats()
```

## Reproducibility Checklist

✅ Data source: CMS official 2024 ICD-10-CM
✅ Version tracking: SHA256 of downloaded files
✅ Random seed: Not applicable (deterministic)
✅ Model versions: Stored in database
✅ Processing history: Complete audit trail
✅ Metrics: Time-stamped in database
✅ Scripts: All included in repository

## Troubleshooting

### Rate Limiting
- Adjust delay in `adaptive_batch_processor.py`
- Reduce batch size limits

### Memory Issues
- Process in smaller chunks
- Use `--target-size` parameter

### API Errors
- Check model availability
- Verify API credentials
- Review batch size limits

## Scientific Citation

```bibtex
@software{medical_coding_dataset_2024,
  title={Adaptive Batch Processing for Medical Coding Dataset Generation},
  author={Your Name},
  year={2024},
  url={repository-url},
  note={Reproducible pipeline with token tracking and cost analysis}
}
```

## License

This project is for scientific research purposes.

## Support

For issues or questions, please open a GitHub issue with:
1. Full error message
2. Database statistics (`python3 -c "from db_manager_v2 import ..."`)
3. Log files from `logs/` directory