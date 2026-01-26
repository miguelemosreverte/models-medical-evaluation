# Dataset Generation Architecture

## Overview

Clean, standardized chapter-based architecture. Each chapter is a single self-contained file that exposes `generate_dataset()`.

## Files

```
chapter_2.py          # Chapter 2 (2.0 + 2.1) - 18KB
chapter_3.py          # Chapter 3 (3.0 + 3.1) - 19KB
generate_dataset.py   # Orchestrator - 88 lines
```

## Chapter Interface

Every chapter **must** expose:
```python
def generate_dataset() -> Dict[str, Any]:
    """
    No arguments. Uses MedicalCodingDB() to query what needs processing.
    Processes batch (typically 100 items). Returns stats dict.
    """
```

## Chapter 2: `chapter_2.py`

**Bidirectional Consistency Testing**

**Internal workflow:**
```
2.0: Prediction Experiments (description → code)
     ↓ (independent)
2.1: Variant Descriptions (code → 11 detail levels)
```

**Contains:**
- Complete MedicalCodingSystem class
- Parallel experiment execution
- Description generation (11 detail levels: 0-10)
- Report generation
- CLI with `status`, `run`, `report`, `clean` commands

**Dependencies:**
- `db_manager.MedicalCodingDB`
- `experiments.py` (run_baseline_claude, run_constrained_claude, etc.)

## Chapter 3: `chapter_3.py`

**Reverse Predictions and RAG Experiments**

**Internal workflow:**
```
3.0: Reverse Predictions (description → code)
     ↓
3.1: RAG Experiments (3 corpus modes: real_only, synthetic_only, both)
     ↓
3.2: Dense Variant Generation (20 variants per code: 10 short + 10 long)
     ↓
3.3: Dense RAG with Negative Examples (positive + negative context)
```

**Contains:**
- Claude/Codex CLI wrappers
- ICD-10 code extraction
- Complete reverse prediction implementation
- RAG similarity search
- Context-aware predictions
- 3 corpus experiments (3.1)
- Dense variant generation (3.2)
- Negative example learning (3.3)
- CLI with options for `--reverse-only`, `--rag-only`, `--dense-variants-only`, `--dense-rag-only`

**Dependencies:**
- `db_manager.MedicalCodingDB`
- `rag_engine.MedicalCodingRAG`

## Orchestrator: `generate_dataset.py`

**Ultra-simple design:**
```python
import chapter_2
import chapter_3

while True:
    chapter_2.generate_dataset()
    chapter_3.generate_dataset()
```

**Features:**
- Lock file (`.generate_dataset.lock`) prevents concurrent runs
- Continuous infinite loop
- Sequential execution
- Error handling with traceback
- No configuration needed

## Database Tables

| Table | Created By | Used By |
|-------|-----------|---------|
| `icd10_codes` | Initial load | All |
| `model_predictions` | Chapter 2.0 | Reports |
| `generated_descriptions` | Chapter 2.1 | Chapter 3.0 |
| `reverse_predictions` | Chapter 3.0 | Chapter 3.1 |
| `rag_real_only_predictions` | Chapter 3.1 | Reports |
| `rag_synthetic_only_predictions` | Chapter 3.1 | Reports |
| `rag_both_predictions` | Chapter 3.1 | Reports |
| `dense_variants` | Chapter 3.2 | Chapter 3.3 |
| `dense_rag_predictions` | Chapter 3.3 | Reports |

## Workflow DAG

```
┌─────────────────────────────────────────────┐
│ Chapter 2                                   │
│                                             │
│  2.0: Prediction Experiments                │
│       (ICD-10 description → code)           │
│       • claude_constrained                  │
│       • codex_constrained                   │
│                                             │
│  2.1: Generate Variant Descriptions         │
│       (ICD-10 code → 11 detail levels)      │
│       • Level 0: Ultra-minimal (3-5 words)  │
│       • Level 10: Hyper-detailed clinical   │
└─────────────────┬───────────────────────────┘
                  │
                  │ generated_descriptions
                  ▼
┌─────────────────────────────────────────────┐
│ Chapter 3                                   │
│                                             │
│  3.0: Reverse Predictions                   │
│       (variant description → code)          │
│       • claude                              │
│         │                                   │
│         │ reverse_predictions               │
│         ▼                                   │
│  3.1: RAG Experiments                       │
│       • real_only (official corpus)         │
│       • synthetic_only (generated corpus)   │
│       • both (combined corpus)              │
│         │                                   │
│         ▼                                   │
│  3.2: Dense Variant Generation              │
│       (20 variants per code)                │
│       • 10 short (5-15 words)               │
│       • 10 long (20-40 words)               │
│         │                                   │
│         │ dense_variants                    │
│         ▼                                   │
│  3.3: Dense RAG with Negative Examples      │
│       • Positive examples (same code)       │
│       • Negative examples (different codes) │
│       • 100% accuracy in initial tests!     │
└─────────────────────────────────────────────┘
```

## Usage

### Start Continuous Generation
```bash
python3 -u generate_dataset.py > /tmp/generation.log 2>&1 &
```

### Monitor Progress
```bash
tail -f /tmp/generation.log
```

### Run Individual Chapters (CLI)
```bash
# Chapter 2
python3 chapter_2.py status
python3 chapter_2.py run --max-items 100

# Chapter 3
python3 chapter_3.py --max-items 100
python3 chapter_3.py --reverse-only --max-items 100
python3 chapter_3.py --rag-only --corpus-mode real_only
```

### Stop Generation
```bash
# Ctrl+C or kill process
# Safe to stop anytime - chapters commit atomically
```

## Adding New Chapters

1. Create `chapter_N.py` with:
   ```python
   def generate_dataset() -> Dict[str, Any]:
       db = MedicalCodingDB()
       # Query DB for unprocessed rows
       # Process batch
       # Return stats
   ```

2. Update `generate_dataset.py`:
   ```python
   import chapter_N

   chapters = [
       ("Chapter 2", chapter_2.generate_dataset),
       ("Chapter 3", chapter_3.generate_dataset),
       ("Chapter N", chapter_N.generate_dataset),
   ]
   ```

Done!
