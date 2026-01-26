#!/usr/bin/env python3
"""
Chapter 3.3: Dense Variant Generation for RAG Testing (10×10 Matrix)

Hypothesis: If we generate a 10×10 matrix of variants per code (100 total):
- 10 detail levels (0=shortest to 9=longest)
- 10 similar variants per detail level
RAG will have significantly better retrieval examples and achieve higher correctness.

Test with 10 billable codes as proof of concept.
"""

import sqlite3
import json
import subprocess
import time
from typing import List, Dict

DB_PATH = "medical_coding.db"


def call_claude(prompt: str, timeout: int = 60) -> Dict[str, any]:
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

def get_test_codes() -> List[Dict]:
    """Get 10 billable test codes from the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get 10 billable codes that already have base descriptions
    cursor.execute("""
        SELECT DISTINCT ic.id, ic.code, ic.description
        FROM icd10_codes ic
        JOIN generated_descriptions gd ON ic.id = gd.code_id
        WHERE LENGTH(ic.code) > 3
        ORDER BY ic.code
        LIMIT 10
    """)

    codes = [{"id": row[0], "code": row[1], "description": row[2]} for row in cursor.fetchall()]
    conn.close()
    return codes


def generate_variants_for_detail_level(code: str, description: str, detail_level: int) -> List[str]:
    """Generate 10 similar variants for a specific detail level using Claude CLI."""

    detail_instructions = {
        0: "ultra-concise (3-5 words, minimal detail)",
        1: "very brief (5-8 words, essential info only)",
        2: "brief (8-12 words, key clinical facts)",
        3: "concise (12-15 words, main clinical points)",
        4: "moderate-short (15-20 words, clinical summary)",
        5: "moderate (20-25 words, balanced clinical description)",
        6: "moderate-detailed (25-30 words, thorough clinical notes)",
        7: "detailed (30-35 words, comprehensive documentation)",
        8: "very detailed (35-40 words, extensive clinical details)",
        9: "maximum detail (40-50 words, exhaustive clinical documentation)"
    }

    length_guide = detail_instructions[detail_level]

    prompt = f"""You are a medical documentation expert. Generate 10 DIFFERENT but SIMILAR clinical descriptions for this ICD-10 code at detail level {detail_level}/9:

Code: {code}
Official Description: {description}

Detail Level {detail_level}: {length_guide}

Generate exactly 10 variants that:
1. All have approximately the SAME length ({length_guide})
2. Describe the SAME medical condition in DIFFERENT words
3. Use varied clinical terminology (formal, informal, technical, colloquial)
4. Are realistic for clinical documentation
5. DO NOT mention the ICD-10 code number itself
6. Each variant should feel like a different doctor wrote it

Output ONLY a JSON array of 10 strings.
Example format: ["variant 1", "variant 2", ..., "variant 10"]"""

    result = call_claude(prompt, timeout=90)

    if not result['success']:
        raise Exception(f"Claude call failed: {result['stderr']}")

    # Parse response
    response_text = result['stdout'].strip()

    # Try to extract JSON
    if response_text.startswith('```'):
        # Remove markdown code blocks
        lines = response_text.split('\n')
        response_text = '\n'.join([l for l in lines if not l.startswith('```')])

    variants = json.loads(response_text)

    if len(variants) != 10:
        raise ValueError(f"Expected 10 variants for detail level {detail_level}, got {len(variants)}")

    return variants


def ensure_table_exists():
    """Ensure dense_variants table exists with correct schema."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check if table exists with old schema
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dense_variants'")
    table_exists = cursor.fetchone() is not None

    if table_exists:
        # Check if it has the new schema (detail_level column)
        cursor.execute("PRAGMA table_info(dense_variants)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'detail_level' not in columns:
            print("⚠ Old schema detected, dropping and recreating table...")
            cursor.execute("DROP TABLE dense_variants")
            table_exists = False

    if not table_exists:
        # Create table for dense variants (10×10 matrix)
        cursor.execute("""
            CREATE TABLE dense_variants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code_id INTEGER NOT NULL,
                detail_level INTEGER NOT NULL CHECK(detail_level >= 0 AND detail_level <= 9),
                variant_index INTEGER NOT NULL CHECK(variant_index >= 0 AND variant_index <= 9),
                description TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (code_id) REFERENCES icd10_codes(id),
                UNIQUE(code_id, detail_level, variant_index)
            )
        """)
        print("✓ Created dense_variants table")
    else:
        print("✓ dense_variants table already exists with correct schema")

    conn.commit()
    conn.close()


def get_missing_variants(code_id: int) -> List[int]:
    """Get list of detail levels that need variants for this code."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check which detail levels are complete (have all 10 variants)
    cursor.execute("""
        SELECT detail_level, COUNT(*) as count
        FROM dense_variants
        WHERE code_id = ?
        GROUP BY detail_level
    """, (code_id,))

    complete_levels = {row[0] for row in cursor.fetchall() if row[1] == 10}
    conn.close()

    # Return list of missing levels
    all_levels = set(range(10))
    missing = sorted(list(all_levels - complete_levels))
    return missing


def store_dense_variants(code_id: int, code: str, detail_level: int, variants: List[str]):
    """Store dense variants in the database (10×10 matrix structure)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Store variants for this detail level
    for variant_index, variant in enumerate(variants):
        cursor.execute("""
            INSERT OR REPLACE INTO dense_variants (code_id, detail_level, variant_index, description)
            VALUES (?, ?, ?, ?)
        """, (code_id, detail_level, variant_index, variant))

    conn.commit()
    conn.close()
    print(f"  ✓ Stored {len(variants)} variants for detail level {detail_level}")


def main():
    print("\n" + "="*70)
    print("Chapter 3.3: Dense Variant Generation (10×10 Matrix)")
    print("="*70)
    print()

    # Ensure table exists (only once at start)
    ensure_table_exists()
    print()

    # Get test codes
    test_codes = get_test_codes()
    print(f"Selected {len(test_codes)} billable test codes for proof of concept:")
    for code in test_codes:
        print(f"  • {code['code']}: {code['description'][:60]}...")
    print()

    # Generate 10×10 matrix of variants for each code (idempotent)
    for code_num, code in enumerate(test_codes, 1):
        print(f"\n[{code_num}/{len(test_codes)}] Processing {code['code']}...")
        print(f"  {code['description'][:70]}...")

        # Check what's missing
        missing_levels = get_missing_variants(code['id'])

        if not missing_levels:
            print(f"  ✓ All 100 variants already exist for {code['code']} - skipping")
            continue

        print(f"  Missing detail levels: {missing_levels} ({len(missing_levels)} levels)")

        total_variants = 0
        # Generate only missing detail levels
        for detail_level in missing_levels:
            print(f"  Detail level {detail_level}/9: ", end='', flush=True)
            variants = generate_variants_for_detail_level(
                code['code'],
                code['description'],
                detail_level
            )

            # Store in database
            store_dense_variants(code['id'], code['code'], detail_level, variants)
            total_variants += len(variants)

        print(f"  ✓ Generated {total_variants} new variants for {code['code']}")

    print()
    print("="*70)
    print("✓ Dense variant generation complete!")
    print(f"  Generated {len(test_codes) * 100} total variants")
    print(f"  Structure: 10 codes × 10 detail levels × 10 variants = 1000 variants")
    print()
    print("Next step: Run RAG predictions on these dense 10×10 matrices")
    print("="*70)


if __name__ == "__main__":
    main()
