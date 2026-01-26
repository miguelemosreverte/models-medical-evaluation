# Implementation Plan - Chapter 2: Bidirectional Consistency

## Key Design Decisions

### Detail Levels (0-10, not 1-10)
- **Level 0**: Most concise, broad definition in typical human language (NOT verbatim from ICD-10)
  - Example: "Severe bacterial diarrhea" instead of exact ICD-10 description
  - Natural, conversational language
  - Minimal detail, maximum ambiguity
- **Level 10**: Hyper-detailed clinical presentation
  - Full symptoms, signs, lab findings, diagnostic criteria
  - Maximum specificity

**Rationale:** Chapter 1 already tests exact verbatim (one-to-one mapping). Chapter 2 tests free-text understanding across a spectrum of human-written descriptions.

### Round-Robin Execution Strategy
Since both models (Claude & Codex) use the same centralized resources:
- Run description generation for **all codes** with Claude first
- Then run description generation for **all codes** with Codex
- This prevents resource conflicts and ensures clean round-robin processing
- Same for reverse prediction phase

### Throughput Tracking
- All experiments use the same `batch_metrics` and `time_series_metrics` tables
- Throughput charts automatically include all plugins
- No special configuration needed - it's already built into the system

---

## Implementation Steps

### Phase 1: Design & Test Description Generation Plugin

#### Step 1.1: Create `generate_descriptions.py` plugin
**Goal:** Generate 11 descriptions (Level 0-10) per ICD-10 code

**Detail Level Taxonomy:**
```
Level 0:  Ultra-minimal, broad, conversational (3-5 words)
          "Severe bacterial diarrhea"

Level 1:  Minimal clinical (one short sentence)
          "Patient has severe watery diarrhea"

Level 2:  Terse symptom mention
          "Profuse watery diarrhea with dehydration"

Level 3:  Brief clinical features
          "Acute onset of severe watery diarrhea, vomiting, rapid dehydration"

Level 4:  Abbreviated clinical description
          "Patient presents with rice-water stools, severe dehydration, muscle cramps"

Level 5:  Minimal clinical context
          "Acute cholera with profuse watery diarrhea, vomiting, electrolyte imbalance"

Level 6:  Essential clinical features
          "Cholera infection causing severe diarrhea with rice-water appearance,
           significant fluid loss, hypotension"

Level 7:  Moderate detail with key symptoms
          "Patient diagnosed with cholera presenting with severe watery diarrhea
           (rice-water stools), profuse vomiting, rapid dehydration, muscle cramps,
           and signs of hypovolemic shock"

Level 8:  Standard clinical presentation
          "Cholera infection due to Vibrio cholerae with characteristic symptoms:
           profuse watery diarrhea with rice-water appearance, severe vomiting,
           rapid onset of dehydration, muscle cramps, hypotension, tachycardia"

Level 9:  Comprehensive clinical narrative
          "Patient presents with acute onset of profuse watery diarrhea (rice-water
           stools), severe vomiting, rapid dehydration with sunken eyes, decreased
           skin turgor, muscle cramps, hypotension, tachycardia. Stool examination
           shows Vibrio cholerae organisms"

Level 10: Hyper-detailed clinical presentation
          "Patient presents with severe acute watery diarrhea with characteristic
           rice-water appearance (fluid loss >1L/hour), profuse vomiting, rapid
           dehydration with clinical signs including sunken eyes, decreased skin
           turgor, dry mucous membranes, muscle cramps (particularly in legs),
           hypotension (BP 80/50), tachycardia (HR 120), oliguria. Stool microscopy
           shows comma-shaped gram-negative bacilli. Culture confirms Vibrio cholerae
           O1, classical biotype, serotype Ogawa. Rapid diagnostic test positive."
```

**Prompt Template:**
```python
prompt = f"""You are a medical documentation expert. Generate 11 clinical descriptions
for this ICD-10 code, ranging from Level 0 (most concise, conversational) to Level 10
(most detailed, clinical).

ICD-10 Code: {code}
Official Description: {description}

IMPORTANT GUIDELINES:
- Level 0: Ultra-minimal, broad, natural language (3-5 words). NOT verbatim from ICD-10.
- Level 1-3: Minimal to brief clinical mentions
- Level 4-7: Essential to moderate clinical detail
- Level 8-10: Standard to hyper-detailed clinical presentations

Generate as JSON array:
[
  {{"level": 0, "description": "..."}},
  {{"level": 1, "description": "..."}},
  ...
  {{"level": 10, "description": "..."}}
]

Ensure medical accuracy while varying specificity naturally."""
```

#### Step 1.2: Test Plugin in Isolation
```bash
# Create test script with 5-10 diverse codes
python3 plugins/generate_descriptions.py --test --codes A00.0,A01,I10,J44.0,E11
```

#### Step 1.3: Document Sample Outputs
- Capture generated descriptions for review
- Verify:
  - Level 0 is truly minimal and conversational
  - Level 10 is appropriately detailed
  - Smooth progression across levels
  - Medical plausibility at all levels

#### Step 1.4: Iterate on Prompts if Needed
- Adjust prompts based on test outputs
- Re-test until satisfied with quality

---

### Phase 2: Create Description Generation Plugins for Both Models

#### Step 2.1: Create `generate_descriptions_claude.py`
- Inherits from description generation base
- Uses Claude API via subprocess
- Stores in `generated_descriptions` table with `generator_model='claude'`

#### Step 2.2: Create `generate_descriptions_codex.py`
- Same structure as Claude version
- Uses Codex API
- Stores with `generator_model='codex'`

#### Step 2.3: Add Database Schema
```sql
CREATE TABLE IF NOT EXISTS generated_descriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code_id INTEGER NOT NULL,
    generator_model TEXT NOT NULL,  -- 'claude' or 'codex'
    detail_level INTEGER NOT NULL,  -- 0-10
    description TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (code_id) REFERENCES icd10_codes(id),
    UNIQUE(code_id, generator_model, detail_level)  -- Prevent duplicates
);

CREATE INDEX IF NOT EXISTS idx_gen_desc_code ON generated_descriptions(code_id);
CREATE INDEX IF NOT EXISTS idx_gen_desc_model ON generated_descriptions(generator_model);
```

---

### Phase 3: Test Description Generation with Arguments

#### Step 3.1: Enable Plugins with Limited Scope
```python
# In main.py
ENABLED_PLUGINS = ["generate_descriptions_claude", "generate_descriptions_codex"]
```

#### Step 3.2: Test with Small Dataset
```bash
# Generate descriptions for first 100 codes only
python3 main.py run --max-items 100

# Check outputs
sqlite3 medical_coding.db "
  SELECT generator_model, detail_level, COUNT(*)
  FROM generated_descriptions
  GROUP BY generator_model, detail_level
"
```

#### Step 3.3: Review Sample Descriptions
```bash
# Export samples to review
python3 -c "
import sqlite3
conn = sqlite3.connect('medical_coding.db')
cursor = conn.cursor()

cursor.execute('''
  SELECT ic.code, gd.generator_model, gd.detail_level, gd.description
  FROM generated_descriptions gd
  JOIN icd10_codes ic ON gd.code_id = ic.id
  WHERE ic.code IN ('A00', 'A00.0', 'A01', 'I10')
  ORDER BY ic.code, gd.generator_model, gd.detail_level
''')

for row in cursor:
    print(f'{row[0]} | {row[1]} | Level {row[2]}: {row[3][:80]}...')
"
```

#### Step 3.4: Document in README
Add to README section "Sample Outputs":
```markdown
### Description Generation Examples

#### Code: A00 (Cholera)
**Claude:**
- Level 0: "Severe bacterial diarrhea"
- Level 5: "Acute cholera with profuse watery diarrhea..."
- Level 10: "Patient presents with severe acute watery diarrhea..."

**Codex:**
- Level 0: "Acute diarrheal infection"
- Level 5: "Cholera infection causing severe diarrhea..."
- Level 10: "Patient with confirmed cholera presenting with..."
```

---

### Phase 4: Create Reverse Prediction Plugins

#### Step 4.1: Create `reverse_predict_claude.py`
**Input:** Generated descriptions from database (all models, all levels)
**Output:** Predicted ICD-10 codes for each description

```python
def process_batch(self, items):
    """
    items = [
      {
        'generated_desc_id': 123,
        'description': 'Severe bacterial diarrhea',
        'original_code': 'A00',
        'detail_level': 0,
        'generator_model': 'claude'
      },
      ...
    ]
    """
    results = []
    for item in items:
        predicted_codes = self._predict_from_description(item['description'])
        results.append({
            'generated_desc_id': item['generated_desc_id'],
            'predicted_codes': predicted_codes,
            'original_code': item['original_code'],
            'detail_level': item['detail_level']
        })
    return results
```

#### Step 4.2: Create `reverse_predict_codex.py`
- Same structure
- Uses Codex API

#### Step 4.3: Add Database Schema
```sql
CREATE TABLE IF NOT EXISTS reverse_predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_desc_id INTEGER NOT NULL,
    predictor_model TEXT NOT NULL,  -- 'claude' or 'codex'
    predicted_codes TEXT NOT NULL,  -- JSON array
    confidence REAL,
    processing_time REAL,
    batch_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (generated_desc_id) REFERENCES generated_descriptions(id),
    UNIQUE(generated_desc_id, predictor_model)  -- Prevent duplicates
);

CREATE INDEX IF NOT EXISTS idx_rev_pred_desc ON reverse_predictions(generated_desc_id);
CREATE INDEX IF NOT EXISTS idx_rev_pred_model ON reverse_predictions(predictor_model);
```

---

### Phase 5: Round-Robin Execution Strategy

#### Step 5.1: Description Generation Phase
```bash
# First: Generate all descriptions with Claude (1000 codes × 11 levels = 11,000 descriptions)
ENABLED_PLUGINS = ["generate_descriptions_claude"]
python3 main.py run --max-items 1000

# Then: Generate all descriptions with Codex
ENABLED_PLUGINS = ["generate_descriptions_codex"]
python3 main.py run --max-items 1000
```

**Result:** 22,000 total generated descriptions (1000 codes × 11 levels × 2 models)

#### Step 5.2: Reverse Prediction Phase
```bash
# First: Claude predicts ALL generated descriptions (22,000 predictions)
ENABLED_PLUGINS = ["reverse_predict_claude"]
python3 main.py run --max-items 22000

# Then: Codex predicts ALL generated descriptions
ENABLED_PLUGINS = ["reverse_predict_codex"]
python3 main.py run --max-items 22000
```

**Result:** 44,000 total reverse predictions (22,000 descriptions × 2 predictor models)

---

### Phase 6: Analysis & Report Generation

#### Step 6.1: Create Analysis Script
`analyze_bidirectional.py` computes:
- Round-trip accuracy per detail level
- Intra-model consistency (Claude→Claude, Codex→Codex)
- Cross-model consistency (Claude→Codex, Codex→Claude)
- Accuracy vs detail level curves
- Error taxonomy (complete miss, near miss, over/under specification)

#### Step 6.2: Update Report Generator
Add Chapter 2 sections to `generate_book_report.py`:
- 2.1: Description Generation Quality
- 2.2: Round-Trip Consistency Analysis
- 2.3: Cross-Model Generalization

#### Step 6.3: Generate Final Reports
```bash
python3 main.py report
```

---

## Execution Timeline

### Today (Session 1): Description Generation
- [x] Create `generate_descriptions_claude.py` plugin
- [x] Test with sample codes
- [ ] Iterate on prompts
- [ ] Document sample outputs
- [ ] Create `generate_descriptions_codex.py`
- [ ] Test both plugins with --max-items 100
- [ ] Review and approve quality

### Session 2: Full Description Generation
- [ ] Run Claude description generation (1000 codes)
- [ ] Run Codex description generation (1000 codes)
- [ ] Verify 22,000 descriptions in database
- [ ] Export samples for documentation

### Session 3: Reverse Prediction
- [ ] Create reverse prediction plugins
- [ ] Test with small subset
- [ ] Run full reverse prediction (44,000 predictions)

### Session 4: Analysis & Reporting
- [ ] Create analysis scripts
- [ ] Generate bidirectional metrics
- [ ] Update book report
- [ ] Create visualizations
- [ ] Final review

---

## Key Verification Points

### After Description Generation:
```sql
-- Should show 11,000 per model
SELECT generator_model, COUNT(*)
FROM generated_descriptions
GROUP BY generator_model;

-- Should show 1,000 codes × 11 levels for each model
SELECT generator_model, detail_level, COUNT(*)
FROM generated_descriptions
GROUP BY generator_model, detail_level
ORDER BY generator_model, detail_level;
```

### After Reverse Prediction:
```sql
-- Should show 22,000 per predictor model
SELECT predictor_model, COUNT(*)
FROM reverse_predictions
GROUP BY predictor_model;

-- Check round-trip accuracy
SELECT
    gd.generator_model,
    rp.predictor_model,
    gd.detail_level,
    AVG(CASE WHEN rp.predicted_codes LIKE '%' || ic.code || '%' THEN 1 ELSE 0 END) * 100 as accuracy
FROM reverse_predictions rp
JOIN generated_descriptions gd ON rp.generated_desc_id = gd.id
JOIN icd10_codes ic ON gd.code_id = ic.id
GROUP BY gd.generator_model, rp.predictor_model, gd.detail_level
ORDER BY gd.generator_model, rp.predictor_model, gd.detail_level;
```

---

## Documentation Updates

### README.md Sections to Add:
1. **Chapter 2 Overview** - Bidirectional consistency methodology
2. **Sample Outputs** - Examples at each detail level
3. **Running Chapter 2 Experiments** - Step-by-step guide
4. **Interpreting Results** - How to read accuracy curves

### EXPERIMENTS_ROADMAP.md Updates:
- Mark Phase 2 as "In Progress"
- Update database schema section
- Add sample queries for analysis

---

## Ready to Execute!

**Current Status:**
- ✅ Design complete
- ✅ Strategy defined (round-robin, detail levels 0-10)
- ✅ Database schema designed
- ✅ Verification queries prepared
- 🔄 Ready to implement plugins

**Next Action:** Create and test `generate_descriptions_claude.py`