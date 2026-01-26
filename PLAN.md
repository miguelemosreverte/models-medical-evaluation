# Medical Coding Dataset Expansion Plan

## Phase 1: Data Acquisition
### 1.1 Research ICD-10 Sources
- [ ] WHO ICD-10 official API/downloads
- [ ] CMS (Centers for Medicare & Medicaid Services) ICD-10 data
- [ ] ICD10Data.com API or downloadable files
- [ ] Country-specific variants (ICD-10-CA for Canada, ICD-10-GM for Germany, etc.)

### 1.2 Download Raw Data
- [ ] Create `raw_data/` directory
- [ ] Download ICD-10 catalog files (XML, JSON, or CSV formats)
- [ ] Document each curl/wget command in README.md
- [ ] Store original files with timestamps

### 1.3 Parse Raw Data
- [ ] Create parser for each format (XML, JSON, CSV)
- [ ] Extract: code, description, category, subcategory
- [ ] Handle country-specific namespaces if available
- [ ] Generate unified `icd10_catalog.csv` with columns:
  - code
  - description
  - category
  - country (default: 'international')
  - source_file

## Phase 2: Database Setup
### 2.1 SQLite Schema Design
- [ ] Create `medical_coding.db` database
- [ ] Tables needed:
  ```sql
  -- Catalog of all ICD-10 codes
  icd10_codes (
    id INTEGER PRIMARY KEY,
    code TEXT UNIQUE,
    description TEXT,
    category TEXT,
    country TEXT,
    source_file TEXT,
    created_at TIMESTAMP
  )

  -- Processing status for each code
  processing_status (
    id INTEGER PRIMARY KEY,
    code_id INTEGER FOREIGN KEY,
    processed BOOLEAN,
    processed_at TIMESTAMP,
    error TEXT
  )

  -- Model predictions
  model_predictions (
    id INTEGER PRIMARY KEY,
    code_id INTEGER FOREIGN KEY,
    model_name TEXT,
    generated_description TEXT,
    predicted_codes TEXT,  -- JSON array
    confidence REAL,
    created_at TIMESTAMP
  )

  -- Training dataset entries
  dataset_entries (
    id INTEGER PRIMARY KEY,
    code_id INTEGER FOREIGN KEY,
    text TEXT,
    codes TEXT,  -- JSON array
    model_source TEXT,
    quality_score REAL,
    created_at TIMESTAMP
  )
  ```

### 2.2 Database Interface
- [ ] Create `db_manager.py` with functions:
  - `init_database()`
  - `import_catalog(csv_file)`
  - `get_unprocessed_codes(limit=100)`
  - `mark_processed(code_id)`
  - `save_prediction(code_id, model, description, codes)`
  - `get_statistics()`

## Phase 3: Processing Pipeline
### 3.1 Batch Processor
- [ ] Create `batch_processor.py`:
  - Load unprocessed codes from DB
  - Call code-to-description scripts for each model
  - Store results in database
  - Handle rate limiting and errors
  - Resume from last position

### 3.2 Quality Control
- [ ] Implement quality scoring:
  - Check if generated descriptions make sense
  - Verify predicted codes match input code
  - Flag suspicious entries for review

### 3.3 Dataset Generation
- [ ] Export high-quality entries to JSONL
- [ ] Maintain separate files:
  - `descriptions-to-codes.golden.jsonl` (1000+ best entries)
  - `descriptions-to-codes.all.jsonl` (all entries)
  - Per-model prediction files

## Phase 4: Monitoring & Reporting
### 4.1 Progress Tracking
- [ ] Create `status.py` script showing:
  - Total codes in catalog
  - Processed vs unprocessed
  - Success/error rates per model
  - Current processing speed
  - ETA for completion

### 4.2 Enhanced HTML Report
- [ ] Add statistics section:
  - Coverage by category
  - Coverage by country
  - Model performance by category
  - Processing timeline chart

## Phase 5: Orchestration
### 5.1 Master Controller
- [ ] Update `orchestrator.py` to:
  - Use SQLite for state management
  - Process in batches
  - Handle interruptions gracefully
  - Parallel processing for multiple models

### 5.2 Automation
- [ ] Create `run_pipeline.sh`:
  - Download latest ICD-10 data
  - Import to database
  - Process unprocessed codes
  - Generate reports
  - Can run as cron job

## Implementation Order
1. **First**: Download ICD-10 catalog from reliable source
2. **Second**: Create SQLite database and import catalog
3. **Third**: Modify existing scripts to use database
4. **Fourth**: Build batch processor
5. **Fifth**: Generate 1000+ row dataset
6. **Sixth**: Create monitoring tools

## Estimated Data Sources
- WHO ICD-10: ~14,000 codes
- ICD-10-CM (US Clinical Modification): ~72,000 codes
- Country variants: varies by country

## Technical Considerations
- Rate limiting for API calls (1-2 seconds between requests)
- Error handling for network issues
- Checkpoint/resume capability
- Data deduplication
- Quality filtering

## Success Metrics
- [ ] 1000+ high-quality training examples
- [ ] Coverage of major ICD-10 categories
- [ ] Both models successfully process >90% of codes
- [ ] Automated pipeline runs without intervention
- [ ] Clear documentation and reproducibility