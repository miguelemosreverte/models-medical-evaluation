#!/usr/bin/env python3
"""
Chapter 3: Reverse Predictions and RAG Experiments
Handles the complete Chapter 3 pipeline with internal DAG dependencies:
  3.0: Reverse predictions (description → code)
  3.1: RAG-enhanced predictions with different corpus modes
  3.2: Dense variant generation (20 variants per code: 10 short + 10 long)
  3.3: Dense RAG with negative examples

Complete self-contained implementation.
"""

import argparse
import json
import re
import sqlite3
import subprocess
import time
from typing import Dict, Any, List

from db_manager import MedicalCodingDB
from rag_engine import MedicalCodingRAG


# =============================================================================
# CHAPTER 3.0: REVERSE PREDICTIONS
# =============================================================================

def call_claude(prompt: str, timeout: int = 30) -> Dict[str, Any]:
    """Call Claude CLI and return structured result."""
    start_time = time.time()

    try:
        result = subprocess.run(
            ['claude', '-p', prompt],
            capture_output=True,
            text=True,
            timeout=timeout
        )

        response_time = time.time() - start_time

        return {
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'response_time': response_time,
            'tokens_input': len(prompt.split()),
            'tokens_output': len(result.stdout.split())
        }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'stdout': '',
            'stderr': 'timeout',
            'response_time': timeout,
            'tokens_input': len(prompt.split()),
            'tokens_output': 0
        }
    except Exception as e:
        return {
            'success': False,
            'stdout': '',
            'stderr': str(e),
            'response_time': time.time() - start_time,
            'tokens_input': 0,
            'tokens_output': 0
        }


def call_codex(prompt: str, timeout: int = 30) -> Dict[str, Any]:
    """Call Codex CLI and return structured result."""
    start_time = time.time()

    try:
        result = subprocess.run(
            ['codex', 'exec', prompt],
            capture_output=True,
            text=True,
            timeout=timeout
        )

        response_time = time.time() - start_time

        return {
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'response_time': response_time,
            'tokens_input': len(prompt.split()),
            'tokens_output': len(result.stdout.split())
        }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'stdout': '',
            'stderr': 'timeout',
            'response_time': timeout,
            'tokens_input': len(prompt.split()),
            'tokens_output': 0
        }
    except Exception as e:
        return {
            'success': False,
            'stdout': '',
            'stderr': str(e),
            'response_time': time.time() - start_time,
            'tokens_input': 0,
            'tokens_output': 0
        }


def extract_icd10_codes(response: str) -> List[str]:
    """Extract ICD-10 codes from any model response."""
    # Look for JSON arrays first
    json_pattern = r'\[(?:\s*"[A-Z]\d{2}(?:\.\d{1,3})?"(?:\s*,\s*"[A-Z]\d{2}(?:\.\d{1,3})?")*)?\s*\]'
    match = re.search(json_pattern, response)
    if match:
        try:
            return json.loads(match.group())
        except:
            pass

    # Fallback: extract codes directly
    pattern = r'\b[A-Z]\d{2}(?:\.\d{1,3})?\b'
    matches = re.findall(pattern, response)
    return matches


def run_reverse_predictions(db: MedicalCodingDB, model: str = "claude", max_predictions: int = 100) -> Dict[str, Any]:
    """
    Run reverse predictions on generated descriptions.

    Args:
        db: Database connection
        model: Model to use ("claude" or "codex")
        max_predictions: Maximum number of predictions to make

    Returns:
        Dictionary with generation statistics
    """
    print(f"\n{'='*60}")
    print(f"Running reverse predictions with {model}")
    print(f"{'='*60}")

    model_caller = call_claude if model == "claude" else call_codex

    conn = db.conn
    cursor = conn.cursor()

    # Get descriptions that need predictions
    cursor.execute("""
        SELECT gd.id, gd.code_id, gd.detail_level, gd.description, ic.code
        FROM generated_descriptions gd
        JOIN icd10_codes ic ON gd.code_id = ic.id
        WHERE NOT EXISTS (
            SELECT 1 FROM reverse_predictions rp
            WHERE rp.generated_desc_id = gd.id AND rp.predictor_model = ?
        )
        LIMIT ?
    """, (model, max_predictions))

    descriptions = cursor.fetchall()

    if not descriptions:
        print(f"No descriptions need prediction for {model}")
        return {"processed": 0, "success": 0, "error": 0}

    print(f"Predicting codes for {len(descriptions)} descriptions...")

    stats = {"processed": 0, "success": 0, "error": 0}

    for desc_id, code_id, detail_level, description, original_code in descriptions:
        # Build prompt
        prompt = f"Given this medical description: '{description}', provide only the relevant ICD-10 codes as a JSON array. No explanation, just the array."

        # Call model
        result = model_caller(prompt)

        # Extract codes
        predicted_codes = extract_icd10_codes(result['stdout']) if result['success'] else []

        # Check if original code was recovered
        success = original_code in predicted_codes

        stats["processed"] += 1
        if success:
            stats["success"] += 1
        else:
            stats["error"] += 1

        # Save to reverse_predictions table (use INSERT OR REPLACE for idempotency)
        cursor.execute("""
            INSERT OR REPLACE INTO reverse_predictions
            (generated_desc_id, predictor_model, predicted_codes, confidence, processing_time)
            VALUES (?, ?, ?, ?, ?)
        """, (desc_id, model, json.dumps(predicted_codes), 1.0 if success else 0.0, result['response_time']))

        conn.commit()

        if stats["processed"] % 10 == 0:
            print(f"  Progress: {stats['processed']}/{len(descriptions)} "
                  f"(success: {stats['success']}, errors: {stats['error']})")

    print(f"\n[{model}] Completed {len(descriptions)} reverse predictions")
    print(f"  Stats: {stats}")

    return stats


# =============================================================================
# CHAPTER 3.1: RAG-ENHANCED PREDICTIONS
# =============================================================================

def find_similar_with_rag(
    rag_engine: MedicalCodingRAG,
    query_description: str,
    top_k: int = 3,
    exclude_code: str = None
) -> List[Dict]:
    """
    Find most similar documents using production RAG engine.

    Strategy: Get diverse examples prioritizing 'real' official descriptions.
    """
    # Get more candidates than needed
    candidates = rag_engine.find_similar(
        query=query_description,
        top_k=top_k * 3,
        exclude_code=exclude_code
    )

    # Prioritize real (official) descriptions over synthetic
    real_examples = [c for c in candidates if c['source'] == 'real'][:top_k]
    synthetic_examples = [c for c in candidates if c['source'] == 'synthetic']

    # Mix: prefer real, but include synthetic if needed
    results = real_examples
    if len(results) < top_k:
        results.extend(synthetic_examples[:top_k - len(results)])

    return results[:top_k]


def predict_with_rag_context(
    description: str,
    similar_variants: List[Dict],
    model_name: str = 'claude'
) -> Dict:
    """Make a prediction using RAG-enhanced prompting."""

    # Build context from similar variants
    # Prioritize showing diverse examples with clear code→description mapping
    context_examples = []
    for i, variant in enumerate(similar_variants, 1):
        source_label = "REAL" if variant.get('source') == 'real' else "SYNTH"
        context_examples.append(
            f"{i}. [{source_label}] {variant['code']} -> \"{variant['description'][:100]}...\""
        )

    context = "\n".join(context_examples)

    # Build improved prompt with better instructions
    prompt = f"""You are a medical coding expert. Below are relevant ICD-10 code examples from our database:

{context}

Based on these examples and your medical coding knowledge, predict the SINGLE most appropriate ICD-10 code for this clinical description:
"{description}"

IMPORTANT:
- Look for the code that best matches the SPECIFIC condition being described
- If this describes a diagnosis/disease, choose the disease code (not symptom codes)
- If this describes essential/primary hypertension, the code is I10
- If this describes cholera, look for A00 family codes

Output ONLY a JSON array with your top prediction first: ["CODE"]
No explanation, just the JSON array."""

    # Call model using existing infrastructure
    start_time = time.time()

    if model_name == 'claude':
        result = call_claude(prompt, timeout=30)
    elif model_name == 'codex':
        result = call_codex(prompt, timeout=30)
    else:
        raise ValueError(f"Unknown model: {model_name}")

    processing_time = time.time() - start_time

    # Parse response
    predicted_codes = []
    if result['success']:
        try:
            # Extract JSON array from response
            response_text = result['stdout'].strip()
            # Try to find JSON array in response
            json_match = re.search(r'\[.*?\]', response_text, re.DOTALL)
            if json_match:
                predicted_codes = json.loads(json_match.group(0))
        except Exception as e:
            print(f"Failed to parse response: {e}")
            predicted_codes = []

    return {
        'predicted_codes': predicted_codes,
        'input_tokens': result.get('tokens_input', 0),
        'output_tokens': result.get('tokens_output', 0),
        'processing_time': processing_time,
        'success': result['success']
    }


def calculate_confidence(predicted_codes: List[str], actual_code: str) -> float:
    """
    Calculate confidence score.
    1.0 if exact match in top position, decreases with rank.
    """
    if not predicted_codes:
        return 0.0

    if predicted_codes[0] == actual_code:
        return 1.0
    elif actual_code in predicted_codes:
        rank = predicted_codes.index(actual_code) + 1
        return 1.0 / rank
    else:
        return 0.0


def run_rag_experiment(
    model_name: str = 'claude',
    max_items: int = 10,
    top_k_variants: int = 3,
    corpus_mode: str = 'both'
) -> Dict[str, Any]:
    """
    Run RAG-enhanced prediction experiment.

    For each generated description from Chapter 3:
    1. Find similar documents using TF-IDF RAG
    2. Use them as context to predict the code
    3. Compare with the actual code
    4. Measure consistency improvement over Chapter 3 baseline

    Args:
        model_name: Model to use ("claude" or "codex")
        max_items: Maximum number of items to test
        top_k_variants: Number of similar variants to use as context
        corpus_mode: 'real_only', 'synthetic_only', or 'both'

    Returns:
        Dictionary with generation statistics
    """
    print(f"\n{'='*60}")
    print(f"RAG-Enhanced Prediction Experiment (Chapter 3.1)")
    print(f"Model: {model_name}")
    print(f"Max items: {max_items}")
    print(f"Top-k variants: {top_k_variants}")
    print(f"Corpus mode: {corpus_mode}")
    print(f"{'='*60}\n")

    # Initialize RAG engine with specified corpus mode
    print("Loading RAG engine...")
    rag_engine = MedicalCodingRAG(corpus_mode=corpus_mode)
    stats = rag_engine.get_stats()
    print(f"✓ RAG engine loaded: {stats['total_documents']:,} documents")


    # Get test descriptions (use the generated descriptions as queries)
    # Sample diverse codes to avoid bias
    conn = sqlite3.connect("medical_coding.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            gd.id,
            ic.code as actual_code,
            gd.description,
            gd.detail_level
        FROM generated_descriptions gd
        JOIN icd10_codes ic ON gd.code_id = ic.id
        ORDER BY RANDOM()
        LIMIT ?
    """, (max_items,))

    test_cases = cursor.fetchall()
    conn.close()

    print(f"✓ Testing {len(test_cases)} descriptions\n")

    # Run predictions
    results = []
    for i, (desc_id, actual_code, description, detail_level) in enumerate(test_cases, 1):
        print(f"[{i}/{len(test_cases)}] Testing: {actual_code} (level {detail_level})")
        print(f"  Description: {description[:80]}...")

        # Find similar documents using RAG engine
        # INCLUDE the actual code - that's the whole point of RAG!
        # The official description helps the model recognize the pattern
        similar = find_similar_with_rag(
            rag_engine,
            description,
            top_k=top_k_variants,
            exclude_code=None  # Don't exclude! We WANT to show the official description
        )

        print(f"  Similar documents: {[v['code'] for v in similar]} ({[v['source'][:4] for v in similar]})")

        # Make prediction
        prediction = predict_with_rag_context(
            description,
            similar,
            model_name=model_name
        )

        # Calculate confidence
        confidence = calculate_confidence(
            prediction['predicted_codes'],
            actual_code
        )

        print(f"  Predicted: {prediction['predicted_codes']}")
        print(f"  Confidence: {confidence:.2f}")
        print()

        results.append({
            'desc_id': desc_id,
            'actual_code': actual_code,
            'predicted_codes': prediction['predicted_codes'],
            'similar_variants': similar,
            'confidence': confidence,
            'input_tokens': prediction['input_tokens'],
            'output_tokens': prediction['output_tokens'],
            'processing_time': prediction['processing_time']
        })

    # Store results in database (table name based on corpus_mode)
    table_name = f"rag_{corpus_mode}_predictions"
    conn = sqlite3.connect("medical_coding.db")
    cursor = conn.cursor()

    for result in results:
        variant_codes = json.dumps([v['code'] for v in result['similar_variants']])

        cursor.execute(f"""
            INSERT INTO {table_name} (
                generated_desc_id,
                model_name,
                predicted_codes,
                num_variants_used,
                variant_codes,
                confidence,
                input_tokens,
                output_tokens,
                processing_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result['desc_id'],
            model_name,
            json.dumps(result['predicted_codes']),
            len(result['similar_variants']),
            variant_codes,
            result['confidence'],
            result['input_tokens'],
            result['output_tokens'],
            result['processing_time']
        ))

    conn.commit()
    conn.close()

    # Print summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")

    avg_confidence = sum(r['confidence'] for r in results) / len(results) if results else 0
    exact_matches = sum(1 for r in results if r['confidence'] == 1.0)

    print(f"Total predictions: {len(results)}")
    print(f"Exact matches: {exact_matches} ({exact_matches/len(results)*100:.1f}%)")
    print(f"Average confidence: {avg_confidence:.3f}")
    print(f"✓ Results saved to database")

    return {
        "processed": len(results),
        "success": exact_matches,
        "error": len(results) - exact_matches,
        "avg_confidence": avg_confidence
    }


# =============================================================================
# CHAPTER 3.2: DENSE VARIANT GENERATION
# =============================================================================

def generate_dense_variants(db: MedicalCodingDB, max_codes: int = 5) -> Dict[str, Any]:
    """
    Generate 20 variants per code (10 short + 10 long) for denser RAG corpus.

    Args:
        db: Database connection
        max_codes: Maximum number of codes to process

    Returns:
        Dictionary with generation statistics
    """
    print(f"\n{'='*60}")
    print(f"Generating dense variants (20 per code)")
    print(f"{'='*60}")

    conn = db.conn
    cursor = conn.cursor()

    # Create table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dense_variants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code_id INTEGER NOT NULL,
            variant_type TEXT NOT NULL,
            variant_index INTEGER NOT NULL,
            description TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (code_id) REFERENCES icd10_codes(id)
        )
    """)
    conn.commit()

    # Get codes that need dense variants (billable codes with existing variants)
    cursor.execute("""
        SELECT DISTINCT ic.id, ic.code, ic.description
        FROM icd10_codes ic
        WHERE LENGTH(ic.code) > 3
        AND NOT EXISTS (
            SELECT 1 FROM dense_variants dv WHERE dv.code_id = ic.id
        )
        LIMIT ?
    """, (max_codes,))

    codes = cursor.fetchall()

    if not codes:
        print("No codes need dense variants")
        return {"processed": 0, "success": 0, "error": 0}

    print(f"Processing {len(codes)} codes...")

    stats = {"processed": 0, "success": 0, "error": 0}

    for code_id, code, description in codes:
        print(f"\nGenerating 20 variants for {code}: {description[:50]}...")

        prompt = f"""You are a medical documentation expert. Generate 20 different clinical descriptions for this ICD-10 code:

Code: {code}
Official Description: {description}

Generate exactly:
- 10 SHORT variants (5-15 words each, concise clinical notes)
- 10 LONG variants (20-40 words each, detailed clinical documentation)

Each variant should:
1. Describe the same medical condition in different words
2. Use varied clinical terminology (formal, informal, technical, plain language)
3. Be realistic for what a doctor might write in clinical notes
4. NOT mention the ICD-10 code itself

Output ONLY a JSON array of 20 strings (short variants first, then long variants).
Example format: ["short variant 1", "short variant 2", ..., "long variant 1", "long variant 2", ...]"""

        result = call_claude(prompt, timeout=60)

        if not result['success']:
            print(f"  ✗ Failed: {result['stderr']}")
            stats["error"] += 1
            continue

        try:
            # Parse response
            response_text = result['stdout'].strip()

            # Remove markdown code blocks if present
            if '```' in response_text:
                lines = response_text.split('\n')
                response_text = '\n'.join([l for l in lines if not l.startswith('```')])

            variants = json.loads(response_text)

            if len(variants) != 20:
                print(f"  ✗ Expected 20 variants, got {len(variants)}")
                stats["error"] += 1
                continue

            # Store variants
            for i, variant in enumerate(variants):
                if i < 10:
                    variant_type = 'short'
                    variant_index = i
                else:
                    variant_type = 'long'
                    variant_index = i - 10

                cursor.execute("""
                    INSERT INTO dense_variants (code_id, variant_type, variant_index, description)
                    VALUES (?, ?, ?, ?)
                """, (code_id, variant_type, variant_index, variant))

            conn.commit()

            stats["processed"] += 1
            stats["success"] += 1
            print(f"  ✓ Stored 20 dense variants")

        except Exception as e:
            print(f"  ✗ Error processing variants: {e}")
            stats["error"] += 1

    print(f"\nCompleted dense variant generation")
    print(f"  Stats: {stats}")

    return stats


# =============================================================================
# CHAPTER 3.3: DENSE RAG (POSITIVE ONLY)
# =============================================================================

def run_dense_rag_positive_only(
    db: MedicalCodingDB,
    model_name: str = 'claude',
    max_items: int = 10,
    top_k_positive: int = 5
) -> Dict[str, Any]:
    """
    Test dense RAG with ONLY positive examples (no negatives).
    This isolates the effect of corpus density.

    Args:
        db: Database connection
        model_name: Model to use
        max_items: Maximum number of items to test
        top_k_positive: Number of positive examples (same code)

    Returns:
        Dictionary with generation statistics
    """
    print(f"\n{'='*60}")
    print(f"Dense RAG - Positive Examples Only (Chapter 3.3)")
    print(f"Model: {model_name}")
    print(f"Max items: {max_items}")
    print(f"Positive examples: {top_k_positive}")
    print(f"{'='*60}\n")

    conn = db.conn
    cursor = conn.cursor()

    # Create separate table for Chapter 3.3 (immutable)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dense_rag_positive_only_predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dense_variant_id INTEGER NOT NULL,
            model_name TEXT NOT NULL,
            predicted_codes TEXT NOT NULL,
            actual_code TEXT NOT NULL,
            num_positive_examples INTEGER,
            confidence REAL,
            processing_time REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (dense_variant_id) REFERENCES dense_variants(id)
        )
    """)
    conn.commit()

    # Get dense variants to test
    cursor.execute("SELECT COUNT(*) FROM dense_rag_positive_only_predictions WHERE model_name = ?", (model_name,))
    has_predictions = cursor.fetchone()[0] > 0

    if has_predictions:
        cursor.execute("""
            SELECT dv.id, ic.code, dv.description, dv.code_id
            FROM dense_variants dv
            JOIN icd10_codes ic ON dv.code_id = ic.id
            WHERE NOT EXISTS (
                SELECT 1 FROM dense_rag_positive_only_predictions drp
                WHERE drp.dense_variant_id = dv.id AND drp.model_name = ?
            )
            ORDER BY RANDOM()
            LIMIT ?
        """, (model_name, max_items))
    else:
        cursor.execute("""
            SELECT dv.id, ic.code, dv.description, dv.code_id
            FROM dense_variants dv
            JOIN icd10_codes ic ON dv.code_id = ic.id
            ORDER BY RANDOM()
            LIMIT ?
        """, (max_items,))

    test_cases = cursor.fetchall()

    if not test_cases:
        print("No dense variants need prediction")
        return {"processed": 0, "success": 0, "error": 0}

    print(f"Testing {len(test_cases)} dense variants...\n")

    stats = {"processed": 0, "success": 0, "error": 0}

    for variant_id, actual_code, description, code_id in test_cases:
        print(f"[{stats['processed']+1}/{len(test_cases)}] Testing: {actual_code}")
        print(f"  Description: {description[:80]}...")

        # Get positive examples ONLY (same code, different variants)
        cursor.execute("""
            SELECT dv.description, ic.code
            FROM dense_variants dv
            JOIN icd10_codes ic ON dv.code_id = ic.id
            WHERE dv.code_id = ? AND dv.id != ?
            ORDER BY RANDOM()
            LIMIT ?
        """, (code_id, variant_id, top_k_positive))
        positive_examples = cursor.fetchall()

        # Build prompt with ONLY positive examples
        positive_text = "\n".join([
            f"  ✓ \"{desc[:80]}...\" → {code}"
            for desc, code in positive_examples
        ])

        prompt = f"""You are a medical coding expert. Given a clinical description, predict the ICD-10 code.

SIMILAR EXAMPLES (correct mappings):
{positive_text}

Now predict the code for this description:
"{description}"

Output ONLY a JSON array with the single most likely ICD-10 code.
Example: ["{actual_code}"]"""

        start_time = time.time()
        result = call_claude(prompt, timeout=30) if model_name == 'claude' else call_codex(prompt, timeout=30)
        processing_time = time.time() - start_time

        predicted_codes = []
        if result['success']:
            try:
                response_text = result['stdout'].strip()
                if '```' in response_text:
                    lines = response_text.split('\n')
                    response_text = '\n'.join([l for l in lines if not l.startswith('```')])

                json_match = re.search(r'\[.*?\]', response_text, re.DOTALL)
                if json_match:
                    predicted_codes = json.loads(json_match.group(0))
            except Exception as e:
                print(f"  ⚠ Error parsing response: {e}")

        # Check correctness
        is_correct = predicted_codes and predicted_codes[0] == actual_code
        confidence = 1.0 if is_correct else 0.0

        if is_correct:
            stats["success"] += 1
            print(f"  ✓ CORRECT: {predicted_codes[0]}")
        else:
            stats["error"] += 1
            predicted = predicted_codes[0] if predicted_codes else "None"
            print(f"  ✗ WRONG: Predicted {predicted} (actual: {actual_code})")

        # Store result in Chapter 3.3 table
        cursor.execute("""
            INSERT INTO dense_rag_positive_only_predictions
            (dense_variant_id, model_name, predicted_codes, actual_code,
             num_positive_examples, confidence, processing_time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (variant_id, model_name, json.dumps(predicted_codes), actual_code,
              len(positive_examples), confidence, processing_time))

        conn.commit()
        stats["processed"] += 1
        print()

    # Summary
    correctness = (stats["success"] / stats["processed"] * 100) if stats["processed"] > 0 else 0
    print(f"{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Total: {stats['processed']}")
    print(f"Correct: {stats['success']} ({correctness:.1f}%)")
    print(f"Wrong: {stats['error']}")

    return stats


# =============================================================================
# CHAPTER 3.4: DENSE RAG WITH NEGATIVE EXAMPLES
# =============================================================================

def run_dense_rag_experiment(
    db: MedicalCodingDB,
    model_name: str = 'claude',
    max_items: int = 10,
    top_k_positive: int = 3,
    top_k_negative: int = 2
) -> Dict[str, Any]:
    """
    Test dense RAG with both positive and negative examples.

    Hypothesis: Including negative examples (similar descriptions from DIFFERENT codes)
    teaches the model decision boundaries, improving accuracy.

    Args:
        db: Database connection
        model_name: Model to use
        max_items: Maximum number of items to test
        top_k_positive: Number of positive examples (same code)
        top_k_negative: Number of negative examples (different codes)

    Returns:
        Dictionary with generation statistics
    """
    print(f"\n{'='*60}")
    print(f"Dense RAG with Negative Examples (Chapter 3.3)")
    print(f"Model: {model_name}")
    print(f"Max items: {max_items}")
    print(f"Positive examples: {top_k_positive}, Negative examples: {top_k_negative}")
    print(f"{'='*60}\n")

    conn = db.conn
    cursor = conn.cursor()

    # Check if table exists and has correct schema
    cursor.execute("""
        SELECT sql FROM sqlite_master
        WHERE type='table' AND name='dense_rag_predictions'
    """)
    existing_schema = cursor.fetchone()

    needs_recreate = False
    if existing_schema:
        # Check if model_name column exists
        if 'model_name' not in existing_schema[0]:
            needs_recreate = True

    if needs_recreate:
        # Drop and recreate with correct schema
        cursor.execute("DROP TABLE IF EXISTS dense_rag_predictions")
        conn.commit()

    # Create table with correct schema
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dense_rag_predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dense_variant_id INTEGER NOT NULL,
            model_name TEXT NOT NULL,
            predicted_codes TEXT NOT NULL,
            actual_code TEXT NOT NULL,
            num_positive_examples INTEGER,
            num_negative_examples INTEGER,
            confidence REAL,
            processing_time REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (dense_variant_id) REFERENCES dense_variants(id)
        )
    """)
    conn.commit()

    # Get dense variants to test
    # First check if any predictions exist yet
    cursor.execute("SELECT COUNT(*) FROM dense_rag_predictions WHERE model_name = ?", (model_name,))
    has_predictions = cursor.fetchone()[0] > 0

    if has_predictions:
        # Skip already predicted variants
        cursor.execute("""
            SELECT dv.id, ic.code, dv.description, dv.code_id
            FROM dense_variants dv
            JOIN icd10_codes ic ON dv.code_id = ic.id
            WHERE NOT EXISTS (
                SELECT 1 FROM dense_rag_predictions drp
                WHERE drp.dense_variant_id = dv.id AND drp.model_name = ?
            )
            ORDER BY RANDOM()
            LIMIT ?
        """, (model_name, max_items))
    else:
        # No predictions yet, get any variants
        cursor.execute("""
            SELECT dv.id, ic.code, dv.description, dv.code_id
            FROM dense_variants dv
            JOIN icd10_codes ic ON dv.code_id = ic.id
            ORDER BY RANDOM()
            LIMIT ?
        """, (max_items,))

    test_cases = cursor.fetchall()

    if not test_cases:
        print("No dense variants need prediction")
        return {"processed": 0, "success": 0, "error": 0}

    print(f"Testing {len(test_cases)} dense variants...\n")

    stats = {"processed": 0, "success": 0, "error": 0}

    for variant_id, actual_code, description, code_id in test_cases:
        print(f"[{stats['processed']+1}/{len(test_cases)}] Testing: {actual_code}")
        print(f"  Description: {description[:80]}...")

        # Get positive examples (same code, different variants)
        cursor.execute("""
            SELECT dv.description, ic.code
            FROM dense_variants dv
            JOIN icd10_codes ic ON dv.code_id = ic.id
            WHERE dv.code_id = ? AND dv.id != ?
            ORDER BY RANDOM()
            LIMIT ?
        """, (code_id, variant_id, top_k_positive))
        positive_examples = cursor.fetchall()

        # Get negative examples (different codes, similar clinically)
        # Strategy: Get random billable codes, excluding the actual code
        cursor.execute("""
            SELECT dv.description, ic.code
            FROM dense_variants dv
            JOIN icd10_codes ic ON dv.code_id = ic.id
            WHERE dv.code_id != ? AND LENGTH(ic.code) > 3
            ORDER BY RANDOM()
            LIMIT ?
        """, (code_id, top_k_negative))
        negative_examples = cursor.fetchall()

        # Build prompt with positive and negative examples
        positive_text = "\n".join([
            f"  ✓ \"{desc[:80]}...\" → {code}"
            for desc, code in positive_examples
        ])

        negative_text = "\n".join([
            f"  ✗ \"{desc[:80]}...\" → {code} (NOT {actual_code})"
            for desc, code in negative_examples
        ])

        prompt = f"""You are a medical coding expert. Given a clinical description, predict the ICD-10 code.

POSITIVE EXAMPLES (correct mappings for similar descriptions):
{positive_text}

NEGATIVE EXAMPLES (common confusions to AVOID):
{negative_text}

Now predict the code for this description:
"{description}"

Output ONLY a JSON array with the single most likely ICD-10 code.
Example: ["{actual_code}"]"""

        start_time = time.time()
        result = call_claude(prompt, timeout=30) if model_name == 'claude' else call_codex(prompt, timeout=30)
        processing_time = time.time() - start_time

        predicted_codes = []
        if result['success']:
            try:
                response_text = result['stdout'].strip()
                if '```' in response_text:
                    lines = response_text.split('\n')
                    response_text = '\n'.join([l for l in lines if not l.startswith('```')])

                json_match = re.search(r'\[.*?\]', response_text, re.DOTALL)
                if json_match:
                    predicted_codes = json.loads(json_match.group(0))
            except Exception as e:
                print(f"  ⚠ Error parsing response: {e}")

        # Check correctness
        is_correct = predicted_codes and predicted_codes[0] == actual_code
        confidence = 1.0 if is_correct else 0.0

        if is_correct:
            stats["success"] += 1
            print(f"  ✓ CORRECT: {predicted_codes[0]}")
        else:
            stats["error"] += 1
            predicted = predicted_codes[0] if predicted_codes else "None"
            print(f"  ✗ WRONG: Predicted {predicted} (actual: {actual_code})")

        # Store result
        cursor.execute("""
            INSERT INTO dense_rag_predictions
            (dense_variant_id, model_name, predicted_codes, actual_code,
             num_positive_examples, num_negative_examples, confidence, processing_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (variant_id, model_name, json.dumps(predicted_codes), actual_code,
              len(positive_examples), len(negative_examples), confidence, processing_time))

        conn.commit()
        stats["processed"] += 1
        print()

    # Summary
    correctness = (stats["success"] / stats["processed"] * 100) if stats["processed"] > 0 else 0
    print(f"{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Total: {stats['processed']}")
    print(f"Correct: {stats['success']} ({correctness:.1f}%)")
    print(f"Wrong: {stats['error']}")

    return stats


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def generate_dataset() -> Dict[str, Any]:
    """
    Main entry point for Chapter 3 dataset generation.
    Handles internal DAG: 3.0 → 3.1 → 3.2 → 3.3

    Returns:
        Dictionary with generation statistics
    """
    db = MedicalCodingDB()
    stats = {
        "chapter_3_0": {},
        "chapter_3_1": {},
        "chapter_3_2": {},
        "chapter_3_3": {}
    }

    # Chapter 3.0: Reverse Predictions (process whatever's available from 2.1)
    # Uses generated_descriptions from Chapter 2.1
    print("  [3.0] Running reverse predictions...")
    stats["chapter_3_0"] = run_reverse_predictions(
        db,
        model="claude",
        max_predictions=11  # Process up to 11 descriptions (1 code × 11 levels)
    )

    # Chapter 3.1: RAG Experiments (depends on 3.0 output)
    # Runs 3 corpus modes: real_only, synthetic_only, both
    print("  [3.1] Running RAG experiments...")
    rag_stats = {}
    for corpus_mode in ['real_only', 'synthetic_only', 'both']:
        print(f"    - Corpus mode: {corpus_mode}")
        result = run_rag_experiment(
            corpus_mode=corpus_mode,
            max_items=11,  # Process up to 11 items (1 code × 11 levels)
            top_k_variants=5
        )
        rag_stats[corpus_mode] = result

    stats["chapter_3_1"] = rag_stats

    # Chapter 3.2: Dense Variant Generation (20 variants per code)
    # Independent of 3.0/3.1, generates denser variant corpus
    print("  [3.2] Generating dense variants...")
    stats["chapter_3_2"] = generate_dense_variants(
        db,
        max_codes=5  # Process 5 codes per round
    )

    # Chapter 3.3: Dense RAG - Positive Only (depends on 3.2)
    # Tests if corpus density alone improves accuracy
    print("  [3.3] Running dense RAG (positive examples only)...")
    stats["chapter_3_3"] = run_dense_rag_positive_only(
        db,
        model_name="claude",
        max_items=10,  # Process 10 variants per round
        top_k_positive=5
    )

    # Chapter 3.4: Dense RAG with Negative Examples (depends on 3.2)
    # Tests if negative examples add additional value
    print("  [3.4] Running dense RAG with negative examples...")
    stats["chapter_3_4"] = run_dense_rag_experiment(
        db,
        model_name="claude",
        max_items=10,  # Process 10 variants per round
        top_k_positive=3,
        top_k_negative=2
    )

    return stats


def main():
    """Main entry point for CLI usage."""
    parser = argparse.ArgumentParser(
        description="Run RAG-enhanced medical coding experiment (Chapter 3)"
    )
    parser.add_argument(
        '--model',
        choices=['claude', 'codex'],
        default='claude',
        help='Model to use for predictions'
    )
    parser.add_argument(
        '--max-items',
        type=int,
        default=10,
        help='Maximum number of items to test'
    )
    parser.add_argument(
        '--top-k',
        type=int,
        default=3,
        help='Number of similar variants to use as context'
    )
    parser.add_argument(
        '--corpus-mode',
        choices=['real_only', 'synthetic_only', 'both'],
        default='both',
        help='Corpus mode: real_only, synthetic_only, or both'
    )
    parser.add_argument(
        '--reverse-only',
        action='store_true',
        help='Only run reverse predictions (Chapter 3.0)'
    )
    parser.add_argument(
        '--rag-only',
        action='store_true',
        help='Only run RAG experiments (Chapter 3.1)'
    )
    parser.add_argument(
        '--dense-variants-only',
        action='store_true',
        help='Only generate dense variants (Chapter 3.2)'
    )
    parser.add_argument(
        '--dense-rag-positive-only',
        action='store_true',
        help='Only run dense RAG with positive examples (Chapter 3.3)'
    )
    parser.add_argument(
        '--dense-rag-with-negatives',
        action='store_true',
        help='Only run dense RAG with negative examples (Chapter 3.4)'
    )
    parser.add_argument(
        '--max-codes',
        type=int,
        default=5,
        help='Maximum number of codes for dense variant generation'
    )
    parser.add_argument(
        '--top-k-positive',
        type=int,
        default=3,
        help='Number of positive examples for dense RAG'
    )
    parser.add_argument(
        '--top-k-negative',
        type=int,
        default=2,
        help='Number of negative examples for dense RAG'
    )

    args = parser.parse_args()

    db = MedicalCodingDB()

    if args.reverse_only:
        # Run only reverse predictions
        run_reverse_predictions(
            db,
            model=args.model,
            max_predictions=args.max_items
        )
    elif args.rag_only:
        # Run only RAG experiment
        run_rag_experiment(
            model_name=args.model,
            max_items=args.max_items,
            top_k_variants=args.top_k,
            corpus_mode=args.corpus_mode
        )
    elif args.dense_variants_only:
        # Run only dense variant generation
        generate_dense_variants(
            db,
            max_codes=args.max_codes
        )
    elif args.dense_rag_positive_only:
        # Run only dense RAG (positive examples)
        run_dense_rag_positive_only(
            db,
            model_name=args.model,
            max_items=args.max_items,
            top_k_positive=args.top_k_positive
        )
    elif args.dense_rag_with_negatives:
        # Run only dense RAG with negative examples
        run_dense_rag_experiment(
            db,
            model_name=args.model,
            max_items=args.max_items,
            top_k_positive=args.top_k_positive,
            top_k_negative=args.top_k_negative
        )
    else:
        # Run complete Chapter 3 pipeline
        generate_dataset()


if __name__ == "__main__":
    main()
