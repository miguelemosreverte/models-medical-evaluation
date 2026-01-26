#!/usr/bin/env python3
"""
Chapter 3.3: RAG Test with Dense Variants

Test if having 20 variants per code (10 short + 10 long) improves RAG predictions
compared to the standard 11 variants used in Chapter 3.1/3.2.

Hypothesis: Denser variant coverage → Better RAG retrieval → Higher correctness (approaching 100%)
"""

import sqlite3
import json
import subprocess
import time
from typing import List, Dict, Tuple

DB_PATH = "medical_coding.db"


def call_claude(prompt: str, timeout: int = 30) -> Dict[str, any]:
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
            'response_time': response_time
        }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'stdout': '',
            'stderr': 'timeout',
            'response_time': timeout
        }
    except Exception as e:
        return {
            'success': False,
            'stdout': '',
            'stderr': str(e),
            'response_time': time.time() - start_time
        }


def get_dense_variants_for_rag() -> List[Tuple[int, str, str, int]]:
    """Get all dense variants to use as RAG corpus."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT dv.id, ic.code, dv.description, dv.code_id
        FROM dense_variants dv
        JOIN icd10_codes ic ON dv.code_id = ic.id
        ORDER BY dv.id
    """)

    variants = cursor.fetchall()
    conn.close()
    return variants


def predict_with_rag(description: str, rag_examples: List[Tuple[str, str]]) -> Tuple[List[str], float]:
    """Predict ICD-10 code using RAG examples."""

    # Build RAG context
    examples_text = "\n".join([
        f"- Description: '{desc}' → Code: {code}"
        for code, desc in rag_examples[:5]  # Top 5 examples
    ])

    prompt = f"""You are a medical coding expert. Given a clinical description, predict the ICD-10 code.

Here are similar examples from our database:
{examples_text}

Now predict the code for this description:
Description: "{description}"

Output ONLY a JSON array of the top 3 most likely ICD-10 codes in order of confidence.
Example: ["A00.0", "A00.1", "A00.9"]"""

    result = call_claude(prompt)

    if not result['success']:
        return [], 0.0

    try:
        response_text = result['stdout'].strip()

        # Remove markdown code blocks if present
        if '```' in response_text:
            lines = response_text.split('\n')
            response_text = '\n'.join([l for l in lines if not l.startswith('```') and l.strip()])

        predicted_codes = json.loads(response_text)

        # Return top prediction with confidence (1.0 if matches, 0.0 if not)
        return predicted_codes, 1.0 if predicted_codes else 0.0

    except Exception as e:
        print(f"  ⚠ Error parsing prediction: {e}")
        return [], 0.0


def run_rag_predictions():
    """Run RAG predictions on all 60 dense variants."""
    print("\n" + "="*70)
    print("Chapter 3.3: RAG Test with Dense Variants")
    print("="*70)
    print()

    # Get all dense variants to use as RAG corpus
    rag_corpus = get_dense_variants_for_rag()
    print(f"RAG Corpus: {len(rag_corpus)} dense variants from 3 codes")
    print()

    # Create table for predictions
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dense_rag_predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dense_variant_id INTEGER NOT NULL,
            predicted_codes TEXT NOT NULL,
            actual_code TEXT NOT NULL,
            confidence REAL,
            processing_time REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (dense_variant_id) REFERENCES dense_variants(id)
        )
    """)

    conn.commit()

    # For each variant, predict using the other variants as RAG context
    total = len(rag_corpus)
    correct = 0

    for idx, (variant_id, actual_code, description, code_id) in enumerate(rag_corpus, 1):
        # Build RAG examples (exclude current variant)
        rag_examples = [(code, desc) for vid, code, desc, cid in rag_corpus if vid != variant_id]

        print(f"[{idx}/{total}] Testing: {actual_code} - {description[:50]}...")

        start_time = time.time()
        predicted_codes, confidence = predict_with_rag(description, rag_examples)
        processing_time = time.time() - start_time

        # Check if prediction is correct
        is_correct = predicted_codes and predicted_codes[0] == actual_code
        if is_correct:
            correct += 1
            print(f"  ✓ CORRECT: Predicted {predicted_codes[0]} (actual: {actual_code})")
        else:
            predicted = predicted_codes[0] if predicted_codes else "None"
            print(f"  ✗ WRONG: Predicted {predicted} (actual: {actual_code})")

        # Store prediction
        cursor.execute("""
            INSERT INTO dense_rag_predictions
            (dense_variant_id, predicted_codes, actual_code, confidence, processing_time)
            VALUES (?, ?, ?, ?, ?)
        """, (variant_id, json.dumps(predicted_codes), actual_code,
              1.0 if is_correct else 0.0, processing_time))

        conn.commit()

    conn.close()

    # Summary
    correctness = (correct / total * 100) if total > 0 else 0
    print()
    print("="*70)
    print(f"✓ Chapter 3.3 RAG Test Complete!")
    print(f"  Correctness: {correctness:.1f}% ({correct}/{total} correct)")
    print(f"  Hypothesis: Dense variants (20 per code) {'VALIDATED' if correctness > 70 else 'NOT validated'}")
    print("="*70)


if __name__ == "__main__":
    run_rag_predictions()
