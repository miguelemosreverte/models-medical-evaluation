# Medical Coding Experiments

Comprehensive experiments exploring AI model performance on medical coding tasks using ICD-10 codes.

**Live Report:** https://miguelemosreverte.github.io/models-medical-evaluation/

## Reproduce the Report

This repository includes all data needed to reproduce the report. No API keys required.

```bash
git clone https://github.com/miguelemosreverte/models-medical-evaluation
cd models-medical-evaluation
python3 generate_book_report.py
open book_report.html
```

**Included data files:**
- `medical_coding.db` - SQLite database with experiment results (14 MB)
- `medical_coding_dataset.*.jsonl` - Model prediction datasets for Claude and Codex

The generated report will be identical to the live version (except for timestamps and minor row ordering differences due to SQL query ordering).

## Running New Experiments (Reproduce Data from Scratch)

To regenerate the experimental data from scratch, you'll need CLI access to both AI models.

### Prerequisites

1. **Claude CLI** - Anthropic's Claude Code CLI
   ```bash
   # Install Claude Code CLI
   npm install -g @anthropic-ai/claude-code

   # Authenticate (requires Anthropic API key)
   claude auth
   ```

2. **Codex CLI** - OpenAI's CLI tool
   ```bash
   # Install OpenAI CLI
   pip install openai

   # Set API key
   export OPENAI_API_KEY="your-api-key"
   ```

3. **Python dependencies**
   ```bash
   pip install flask requests anthropic
   ```

### Generate Fresh Data

```bash
# Remove existing data to start fresh
rm medical_coding.db
rm medical_coding_dataset.*.jsonl

# Run data generation (this will take several hours)
python3 dataset_generation.py
```

The generation process:
1. **Chapter 2**: Generates 11 description variants per ICD-10 code using both models
2. **Chapter 3**: Tests reverse predictions (description → code)
3. **Chapter 3.1**: Runs RAG-enhanced predictions with different corpus modes

### Monitor Progress

View live progress in your browser:

```bash
curl http://localhost:5001/api/progress/markdown
```

Or open: http://localhost:5001

### Cost Considerations

Running the full experiment involves thousands of API calls to both Claude and OpenAI. Estimated costs depend on current API pricing. The included dataset represents the results of these experiments so you can analyze the results without incurring API costs.

## 📁 Project Structure

### Core Files

| File | Purpose |
|------|---------|
| **dataset_generation.py** | Unified orchestrator + monitoring API |
| **generate_book_report.py** | Smart report generator (auto-starts dataset generation) |
| **chapter_2_generate_variants.py** | Chapter 2: Generate 11 description variants per code |
| **chapter_3.py** | Chapter 3: Reverse predictions (code from description) |
| **chapter_3_1_rag.py** | Chapter 3.1: RAG-enhanced predictions (3 corpus modes) |

### Report Modules

| File | Purpose |
|------|---------|
| `report_chapter_1.py` | Methodology chapter |
| `report_chapter_2_1.py` | Constrained vs unconstrained comparison |
| `report_chapter_3.py` | Bidirectional consistency |
| `report_chapter_3_1.py` | RAG-enhanced predictions comparison |
| `report_chapters_4_5.py` | Additional analysis chapters |

## 🏗️ Architecture

### Data Flow

```
┌─────────────────────────────────────────────────────────┐
│               dataset_generation.py                     │
│        (Orchestrator + Monitoring API)                  │
│                                                         │
│  • Round-robin data generation                          │
│  • REST API on port 5001                                │
│  • Lock file prevents multiple instances                │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ├─→ Chapter 2: chapter_2_generate_variants.py
                   │   └─→ Stores in: generated_descriptions
                   │
                   ├─→ Chapter 3: chapter_3.py
                   │   └─→ Stores in: reverse_predictions
                   │
                   └─→ Chapter 3.1: chapter_3_1_rag.py
                       └─→ Stores in: rag_*_predictions (3 tables)
```

### Report Generation

```
generate_book_report.py
  1. Check if dataset_generation.py is running
  2. If not running & no data: start it automatically
  3. Generate report from current database state
  4. Output: book_report.html
```

## 📊 Monitoring API

Built-in REST API for monitoring progress.

### Endpoints

#### Markdown Progress
```bash
curl http://localhost:5001/api/progress/markdown
```

#### JSON Progress
```bash
curl http://localhost:5001/api/progress
```

#### Chapters List
```bash
curl http://localhost:5001/api/chapters
```

## 🔬 Experimental Chapters

### Chapter 2: Description Variant Generation
Generate 11 paraphrased variants for each ICD-10 code

### Chapter 3: Bidirectional Consistency
Test if models can predict the original code from their own generated descriptions

### Chapter 3.1: RAG-Enhanced Predictions
Test if providing similar examples improves prediction accuracy

Three corpus modes:
- **3.1.1 (Real Only):** Search 46k real medical descriptions
- **3.1.2 (Synthetic Only):** Search AI-generated variants
- **3.1.3 (Both):** Search combined corpus

## 🛠️ Usage

### Manual Dataset Generation

```bash
python3 dataset_generation.py
```

Options:
- `--api-only` - Run only monitoring API
- `--batch-size N` - Batch size (default: 5)
- `--variants-per-round N` - Max variants per round (default: 100)
- `--port N` - API port (default: 5001)

### Run Specific Chapter

```bash
# Chapter 2: Generate variants
python3 chapter_2_generate_variants.py run --max-items 100 --batch-size 10

# Chapter 3: Reverse predictions
python3 chapter_3.py --max-items 100

# Chapter 3.1: RAG experiments
python3 chapter_3_1_rag.py --max-items 33 --corpus-mode synthetic_only
```

## 🚨 Troubleshooting

### Dataset generation not starting
```bash
# Check if already running
ls .dataset_generation.lock

# If stale, remove it
rm .dataset_generation.lock
```

### API not responding
```bash
# Check if port in use
lsof -i :5001

# Kill existing process
pkill -f dataset_generation
```
