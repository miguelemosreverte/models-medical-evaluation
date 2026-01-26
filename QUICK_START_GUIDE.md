# Quick Start Guide - Medical Coding Experiments

## Current Status

### Running Experiments ✅
- **Claude (baseline):** 50+/1000 predictions (in progress)
- **Codex (baseline):** 131+/1000 predictions (in progress)
- **Monitoring:** Real-time API running on port 5001

### System Improvements Applied ✅
1. WAL mode enabled for concurrent database writes
2. Adaptive batch sizing (starts at 1, grows conservatively)
3. Fixed progress tracking to resume correctly
4. Hallucination throttle removed

---

## Available Plugins

### Chapter 1: Intrinsic Knowledge Assessment

#### 1.1 Baseline Plugins (Currently Running)
- `claude.py` - Direct prediction without constraints
- `codex.py` - Direct prediction without constraints

#### 1.2 Constrained Plugins (Ready to Run)
- `claude_constrained.py` ✅ - Tests hallucination-aware prompting
- `codex_constrained.py` - (TODO: create based on claude_constrained.py)

### Chapter 2: Bidirectional Consistency (To Be Implemented)

#### 2.1 Description Generation
- `generate_descriptions_claude.py` - (TODO)
- `generate_descriptions_codex.py` - (TODO)

#### 2.2 Reverse Prediction
- `reverse_predict_claude.py` - (TODO)
- `reverse_predict_codex.py` - (TODO)

---

## How to Run Experiments

### Enable/Disable Plugins

Edit `main.py` line 8:
```python
ENABLED_PLUGINS = ["claude", "codex"]  # Current baseline
```

Options:
```python
# Run baseline only
ENABLED_PLUGINS = ["claude", "codex"]

# Add constrained experiments
ENABLED_PLUGINS = ["claude", "codex", "claude_constrained", "codex_constrained"]

# Run only constrained (after baseline completes)
ENABLED_PLUGINS = ["claude_constrained", "codex_constrained"]
```

### Run Command
```bash
# Run for 1000 items (resumes from where it left off)
python3 main.py run --max-items 1000

# Run with custom batch size (not recommended - uses adaptive sizing now)
python3 main.py run --max-items 1000 --batch-size 1

# Check status without running
python3 main.py status

# Generate reports only
python3 main.py report
```

### Test a Plugin Before Running
```bash
# Test with sample data
python3 plugins/claude_constrained.py --test

# Output shows if prompting strategy works correctly
```

---

## Monitoring Progress

### Real-Time Monitoring API
```bash
# Start monitoring API (if not already running)
python3 monitoring_api.py

# Check status
curl http://localhost:5001/api/status

# See recent batches
curl http://localhost:5001/api/batches/recent

# Get throughput metrics
curl http://localhost:5001/api/throughput

# Live status (what's happening now)
curl http://localhost:5001/api/live
```

### Monitor Script (Auto-updating every 30s)
```bash
# Already running in background
# Shows progress toward 1000 items for both models
# Displays throughput and estimated completion time
```

### Check Database Directly
```bash
sqlite3 medical_coding.db "SELECT model_name, COUNT(*) FROM model_predictions GROUP BY model_name"
```

---

## Implementation Workflow

### For New Plugins (e.g., claude_constrained)

1. **Create the plugin file** ✅
   ```bash
   # Copy template from existing plugin
   cp plugins/claude.py plugins/claude_constrained.py
   ```

2. **Modify the prompt/logic** ✅
   - Update `name` property
   - Update `version` property
   - Modify `_process_single_item()` with new prompt

3. **Test standalone** ✅
   ```bash
   python3 plugins/claude_constrained.py --test
   ```

4. **Add to ENABLED_PLUGINS** in `main.py`
   ```python
   ENABLED_PLUGINS = ["claude", "codex", "claude_constrained"]
   ```

5. **Run experiment**
   ```bash
   python3 main.py run --max-items 1000
   ```

6. **Monitor progress**
   - Check API: `curl http://localhost:5001/api/status`
   - Watch JSONL files: `wc -l medical_coding_dataset.*.jsonl`
   - Database: `sqlite3 medical_coding.db "SELECT model_name, COUNT(*) FROM model_predictions GROUP BY model_name"`

7. **Generate report**
   ```bash
   python3 main.py report
   # Opens index.html and book_report.html
   ```

---

## Report Generation

### Automatic
- Reports regenerate every 10 seconds while experiments run
- Access at:
  - `index.html` - Summary dashboard
  - `book_report.html` - Detailed narrative report with chapters

### Manual
```bash
python3 main.py report
```

### Report Structure
```
Chapter 1: Intrinsic Knowledge Assessment
├── 1.1 Direct Prediction (claude, codex)
│   ├── Accuracy metrics
│   ├── Throughput analysis
│   └── Error patterns
└── 1.2 Hallucination-Aware Prediction (claude_constrained, codex_constrained)
    ├── Constraint impact
    ├── Precision vs Recall
    └── False positive analysis

Chapter 2: Bidirectional Consistency (future)
├── 2.1 Description Generation
├── 2.2 Round-Trip Accuracy
└── 2.3 Cross-Model Consistency
```

---

## Key Features

### Idempotency ✅
- Safe to restart anytime
- Never re-processes the same item for the same model
- Resumes exactly where it left off

### Parallel Execution ✅
- Multiple models run in parallel threads
- WAL mode prevents database conflicts
- Independent progress tracking per model

### Adaptive Batch Sizing ✅
- Starts conservatively (batch_size=1)
- Grows based on success rate:
  - ≥90% success → increase by 1 (after 3 good batches)
  - <70% success → decrease by 2
  - <50% success → halve immediately
- Max cap: 20 items per batch

### Real-Time Monitoring ✅
- REST API with detailed metrics
- Live batch tracking
- Throughput visualization
- Progress estimation

---

## Next Steps

### Phase 1: Complete Baseline (In Progress)
- [ ] Wait for claude.py and codex.py to reach 1000 items each
- [ ] Generate baseline report (Chapter 1.1)

### Phase 2: Hallucination Constraints (Ready to Start)
- [x] Create claude_constrained.py ✅
- [ ] Create codex_constrained.py
- [ ] Add to ENABLED_PLUGINS
- [ ] Run to 1000 items
- [ ] Generate comparative analysis (Chapter 1.2)

### Phase 3: Description Generation (Design Phase)
- [ ] Design 10-level detail taxonomy
- [ ] Create generation prompts
- [ ] Implement description generator plugins
- [ ] Add database tables for generated descriptions
- [ ] Test on small subset (100 codes)
- [ ] Run full generation

### Phase 4: Reverse Prediction (Depends on Phase 3)
- [ ] Create reverse prediction plugins
- [ ] Implement round-trip pipeline
- [ ] Calculate bidirectional metrics
- [ ] Generate consistency analysis

---

## Troubleshooting

### Process Not Running
```bash
# Check lock file
ls -la main.lock

# Check process
ps aux | grep "python.*main.py"

# Remove stale lock if needed
rm main.lock
```

### Database Locked
```bash
# Check if WAL mode is enabled
sqlite3 medical_coding.db "PRAGMA journal_mode"
# Should return: wal

# Enable if not
sqlite3 medical_coding.db "PRAGMA journal_mode=WAL"
```

### Slow Throughput
- Claude: ~3-10 items/min expected (depends on API latency + adaptive batching)
- Codex: ~15-30 items/min expected
- Adaptive batch sizing will optimize over time

### Reports Not Updating
```bash
# Manually regenerate
python3 main.py report

# Check if report generator is running
ps aux | grep generate_book_report
```

---

## File Locations

### Configuration
- `main.py` - Main orchestrator, ENABLED_PLUGINS configuration
- `plugin_adapter.py` - Adaptive batch sizing logic
- `db_manager.py` - Database operations (WAL mode)

### Plugins
- `plugins/claude.py` - Claude baseline
- `plugins/codex.py` - Codex baseline
- `plugins/claude_constrained.py` - Claude with constraints ✅
- `plugins/codex_constrained.py` - (TODO)

### Data
- `medical_coding.db` - SQLite database (WAL mode)
- `medical_coding_dataset.{model}.jsonl` - JSONL output files

### Reports
- `index.html` - Dashboard
- `book_report.html` - Narrative report
- `evaluate_models.py` - Report generator
- `generate_book_report.py` - Book-style report generator

### Monitoring
- `monitoring_api.py` - REST API (port 5001)
- `monitor_progress.sh` - Auto-updating console monitor

---

## Tips

1. **Always test plugins standalone first** with `--test` flag
2. **Monitor progress** via API rather than tailing logs
3. **Let adaptive batching work** - don't override batch sizes
4. **Reports regenerate automatically** - just open HTML files
5. **System is idempotent** - restart anytime without losing progress
6. **Parallel by default** - multiple models run concurrently
7. **Iterate quickly** - test prompts on small batches before full runs