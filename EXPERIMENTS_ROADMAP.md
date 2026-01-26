# Medical Coding Experiments Roadmap

## Overview
This document outlines the experimental framework for evaluating large language models' capabilities in medical coding tasks, organized into coherent chapters.

---

## Chapter 1: Intrinsic Knowledge Assessment
**Theme:** Evaluating the baseline knowledge that LLMs possess about ICD-10 medical coding

### 1.1 Direct Prediction (✅ COMPLETED)
**Status:** Currently running
**Plugins:** `claude.py`, `codex.py`

**Objective:** Measure how accurately models can predict ICD-10 codes from official descriptions without additional context.

**Method:**
- Input: Official ICD-10 description
- Task: Predict the corresponding ICD-10 code(s)
- Output: Array of predicted codes

**Metrics:**
- Exact match accuracy
- Partial match (code hierarchy awareness)
- Throughput (items/minute)
- Confidence scores

---

### 1.2 Hallucination-Aware Prediction (🔄 NEW SUBSECTION)
**Status:** To be implemented
**Plugin:** `claude_constrained.py`, `codex_constrained.py`

**Objective:** Test whether explicit instructions to avoid hallucination reduce false positives

**Hypothesis:** Models might over-specify codes (e.g., predicting "Cholera due to Vibrio cholerae 01, biovar cholerae" when description only says "Cholera")

**Method:**
- Input: Official ICD-10 description + constraint prompt
- Constraint Prompt:
  ```
  Given this medical description, provide ONLY the ICD-10 codes that can be
  definitively inferred from the description. Do NOT add specificity beyond
  what is explicitly stated. If the description is general, provide only
  the general code. Avoid false positives by not hallucinating details that
  aren't present in the description.

  Description: {description}

  Return codes as JSON array.
  ```
- Task: Predict codes with hallucination constraints
- Output: Array of predicted codes (expected to be more conservative)

**Metrics:**
- False positive rate (over-specification)
- False negative rate (under-specification)
- Comparison with 1.1: precision vs recall tradeoff
- Specificity level alignment (general vs specific codes)

**Implementation TODO:**
- [ ] Create `claude_constrained.py` plugin
- [ ] Create `codex_constrained.py` plugin
- [ ] Add hallucination detection logic to evaluation
- [ ] Implement code specificity hierarchy comparison
- [ ] Generate comparative report section: "1.2 Impact of Hallucination Constraints"

---

## Chapter 2: Bidirectional Consistency & Free-Text Understanding
**Theme:** Evaluating models' ability to maintain consistency when going from code → description → code

### 2.1 Description Generation (🔄 NEW CHAPTER - STEP 1)
**Status:** To be implemented
**Plugin:** `generate_descriptions.py`

**Objective:** Test models' ability to generate clinically plausible descriptions from ICD-10 codes

**Method:**
- Input: ICD-10 code + official description (as reference)
- Task: Generate 10 synthetic descriptions with decreasing detail levels
- Output: Array of 10 descriptions

**Detail Levels (from most to least detailed):**
1. **Hyper-detailed:** Full clinical presentation with symptoms, signs, lab findings
2. **Clinical narrative:** Comprehensive symptom description
3. **Standard clinical:** Typical presentation with key features
4. **Moderate detail:** Main symptoms and context
5. **Brief clinical:** Core symptoms only
6. **Minimal clinical:** Essential features
7. **Abbreviated:** Short symptom mention
8. **Terse:** Minimal wording
9. **Code-like:** Near code-level abstraction
10. **Ultra-minimal:** Absolute minimum to potentially infer code

**Example for A00.0 (Cholera due to Vibrio cholerae 01, biovar cholerae):**
```
Level 1: "Patient presents with severe acute watery diarrhea ('rice-water stools'),
         profuse vomiting, rapid dehydration, muscle cramps, and hypotension.
         Stool culture confirmed Vibrio cholerae O1, classical biotype, serotype Ogawa."

Level 5: "Acute cholera infection with severe diarrhea and dehydration,
         V. cholerae O1 classical biotype confirmed"

Level 10: "Cholera O1 classical"
```

**Prompt Template:**
```
You are a medical documentation expert. Given this ICD-10 code and its official
description, generate 10 synthetic clinical descriptions that would lead to this
diagnosis. Arrange them from most detailed (Level 1) to least detailed (Level 10).

ICD-10 Code: {code}
Official Description: {description}

Generate descriptions as JSON array: [
  {"level": 1, "description": "..."},
  {"level": 2, "description": "..."},
  ...
]

Ensure medical accuracy while varying specificity.
```

**Implementation TODO:**
- [ ] Create `generate_descriptions.py` plugin
- [ ] Define detail level prompting strategy
- [ ] Store generated descriptions in new table: `generated_descriptions`
- [ ] Validate medical plausibility (avoid nonsensical descriptions)
- [ ] Generate report section: "2.1 Description Generation Quality"

---

### 2.2 Reverse Prediction (Round-Trip Consistency) (🔄 NEW CHAPTER - STEP 2)
**Status:** To be implemented
**Plugin:** `reverse_predict_claude.py`, `reverse_predict_codex.py`

**Objective:** Measure bidirectional consistency - can models recover the original code from their own generated descriptions?

**Method:**
- Input: Generated descriptions from 2.1 (10 descriptions per code)
- Task: Predict ICD-10 code from each synthetic description
- Output: Predicted code for each description level

**Key Questions:**
- At what detail level does prediction accuracy drop?
- Do models maintain consistency across the detail spectrum?
- Where do models "get lost" and predict different codes?
- Is there a detail threshold below which prediction becomes unreliable?

**Metrics:**
- **Round-trip accuracy:** % of descriptions that map back to original code
- **Detail level curve:** Accuracy vs description detail level (1-10)
- **Error analysis:** Where do mis-predictions occur?
  - Complete misses (wrong code family)
  - Near misses (same category, wrong specificity)
  - Hallucinated specificity (too specific)
  - Loss of specificity (too general)
- **Consistency score:** How stable are predictions across detail levels?

**Expected Patterns:**
```
Level 1-3:  High accuracy (90%+) - lots of clinical detail
Level 4-6:  Moderate accuracy (70-90%) - adequate information
Level 7-9:  Declining accuracy (40-70%) - minimal information
Level 10:   Low accuracy (<40%) - insufficient detail
```

**Implementation TODO:**
- [ ] Create `reverse_predict_claude.py` plugin
- [ ] Create `reverse_predict_codex.py` plugin
- [ ] Build pipeline to feed generated descriptions back to models
- [ ] Implement round-trip accuracy calculation
- [ ] Create detail-level stratified analysis
- [ ] Map prediction drift patterns
- [ ] Generate report section: "2.2 Bidirectional Consistency Analysis"

---

### 2.3 Cross-Model Consistency (🔄 BONUS ANALYSIS)
**Status:** To be implemented
**Analysis Script:** `cross_model_analysis.py`

**Objective:** Test if Claude-generated descriptions can be correctly coded by Codex and vice-versa

**Method:**
- Claude generates descriptions → Codex predicts codes
- Codex generates descriptions → Claude predicts codes
- Compare intra-model vs inter-model consistency

**Metrics:**
- Same-model consistency (Claude→Claude, Codex→Codex)
- Cross-model consistency (Claude→Codex, Codex→Claude)
- Description quality difference between models

**Implementation TODO:**
- [ ] Cross-reference generated descriptions across models
- [ ] Calculate cross-model accuracy matrix
- [ ] Identify model-specific biases in description generation
- [ ] Generate report section: "2.3 Cross-Model Generalization"

---

## Chapter 3: Report Generation (📊 ONGOING)
**Status:** Continuously updated

### 3.1 Book Report Structure
```
Chapter 1: Intrinsic Knowledge Assessment
├── 1.1 Direct Prediction Accuracy
│   ├── Overall Metrics
│   ├── Model Comparison (Claude vs Codex)
│   ├── Throughput Analysis
│   └── Error Patterns
└── 1.2 Hallucination-Aware Prediction
    ├── Constraint Impact Analysis
    ├── Precision vs Recall Tradeoff
    ├── False Positive Reduction
    └── Comparison with Baseline (1.1)

Chapter 2: Bidirectional Consistency & Free-Text Understanding
├── 2.1 Description Generation Quality
│   ├── Detail Level Distribution
│   ├── Medical Plausibility Assessment
│   ├── Model Comparison (Claude vs Codex)
│   └── Sample Descriptions Showcase
├── 2.2 Round-Trip Consistency
│   ├── Accuracy vs Detail Level Curves
│   ├── Prediction Drift Analysis
│   ├── Error Taxonomy
│   └── Consistency Scores
└── 2.3 Cross-Model Generalization
    ├── Inter-Model vs Intra-Model Accuracy
    ├── Description Style Differences
    └── Generalization Capability

Chapter 3: Synthesis & Conclusions
├── 3.1 Key Findings
├── 3.2 Model Strengths & Weaknesses
├── 3.3 Clinical Implications
└── 3.4 Future Directions
```

---

## Implementation Plan

### Phase 1: Complete Current Baseline ✅
- [x] Run claude.py and codex.py to 1000 items
- [ ] Generate baseline report (Chapter 1.1)

### Phase 2: Hallucination Constraints (Chapter 1.2)
**Priority:** HIGH (quick win, same architecture)
1. [ ] Create constrained prompt variants
2. [ ] Implement `claude_constrained.py`
3. [ ] Implement `codex_constrained.py`
4. [ ] Run experiments (1000 items each)
5. [ ] Generate comparative analysis report
6. [ ] Update book report with Chapter 1.2

**Estimated Time:** 2-3 hours implementation + runtime

### Phase 3: Description Generation (Chapter 2.1)
**Priority:** MEDIUM (foundation for Chapter 2)
1. [ ] Design detail level taxonomy
2. [ ] Create generation prompts
3. [ ] Implement `generate_descriptions.py`
4. [ ] Add `generated_descriptions` database table
5. [ ] Test on small subset (100 codes)
6. [ ] Validate medical plausibility
7. [ ] Run full generation (1000 codes)
8. [ ] Generate quality report

**Estimated Time:** 4-6 hours implementation + runtime

### Phase 4: Reverse Prediction (Chapter 2.2)
**Priority:** MEDIUM (depends on Phase 3)
1. [ ] Create reverse prediction plugins
2. [ ] Implement round-trip pipeline
3. [ ] Run reverse predictions on all generated descriptions
4. [ ] Calculate bidirectional metrics
5. [ ] Generate consistency analysis report
6. [ ] Update book report with Chapter 2

**Estimated Time:** 3-5 hours implementation + runtime

### Phase 5: Cross-Model Analysis (Chapter 2.3)
**Priority:** LOW (bonus insights)
1. [ ] Implement cross-model evaluation
2. [ ] Generate cross-model matrices
3. [ ] Add to final report

**Estimated Time:** 2-3 hours

### Phase 6: Final Report Polish
1. [ ] Integrate all chapters
2. [ ] Add visualizations
3. [ ] Write synthesis chapter
4. [ ] Review narrative flow
5. [ ] Export final report

---

## Database Schema Updates

### New Tables Needed:

```sql
-- Generated descriptions for bidirectional testing
CREATE TABLE generated_descriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code_id INTEGER NOT NULL,
    generator_model TEXT NOT NULL,  -- 'claude' or 'codex'
    detail_level INTEGER NOT NULL,  -- 1-10
    description TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (code_id) REFERENCES icd10_codes(id)
);

-- Reverse predictions (descriptions -> codes)
CREATE TABLE reverse_predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_desc_id INTEGER NOT NULL,
    predictor_model TEXT NOT NULL,  -- 'claude' or 'codex'
    predicted_codes TEXT NOT NULL,  -- JSON array
    confidence REAL,
    processing_time REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (generated_desc_id) REFERENCES generated_descriptions(id)
);
```

---

## Plugin Architecture

All plugins follow the standardized interface:

```python
class PluginName:
    def __init__(self, db: MedicalCodingDB):
        self.name = "plugin_name"
        self.version = "1.0.0"
        self.db = db

    def process_batch(self, items: List[Dict], batch_size: int) -> List[Dict]:
        """Process batch and return results."""
        pass
```

---

## Success Criteria

### Chapter 1.2 (Hallucination Constraints)
- ✅ False positive rate decreases by >20%
- ✅ Precision improves without major recall drop
- ✅ Clear analysis of specificity alignment

### Chapter 2.1 (Description Generation)
- ✅ Generate 10 distinct detail levels
- ✅ Descriptions are medically plausible
- ✅ Clear progression from detailed to minimal

### Chapter 2.2 (Reverse Prediction)
- ✅ Measure accuracy across all detail levels
- ✅ Identify detail threshold for reliable prediction
- ✅ Clear visualization of detail vs accuracy curve
- ✅ Error taxonomy showing where models fail

### Chapter 2.3 (Cross-Model)
- ✅ Cross-model accuracy comparison
- ✅ Insights into model-specific biases

---

## Notes
- All experiments are **idempotent** - safe to restart anytime
- Plugins can be tested with small batches using arguments
- Report generation is continuous - regenerate anytime
- Focus on beautiful, narrative-driven report chapters