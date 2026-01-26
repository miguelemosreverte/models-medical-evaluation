#!/usr/bin/env python3
"""
Chapter 3.3: Dense Variant Generation (10×10 Matrix) - Fast Version
Uses Azure OpenAI via VivioMed backend for much faster generation
"""

import sqlite3
import sys
from pathlib import Path
import time
from typing import List, Dict

# Add report_utils to path
sys.path.insert(0, str(Path(__file__).parent / 'report_utils'))
from azure_openai_client import AzureOpenAIClient

DB_PATH = "medical_coding.db"

# Initialize Azure OpenAI client
openai_client = AzureOpenAIClient()


def get_test_codes() -> List[Dict]:
    """Get 10 billable test codes from the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

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


def ensure_table_exists():
    """Ensure dense_variants table exists with correct schema."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dense_variants'")
    table_exists = cursor.fetchone() is not None

    if table_exists:
        cursor.execute("PRAGMA table_info(dense_variants)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'detail_level' not in columns:
            print("⚠ Old schema detected, dropping and recreating table...")
            cursor.execute("DROP TABLE dense_variants")
            table_exists = False

    if not table_exists:
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

    cursor.execute("""
        SELECT detail_level, COUNT(*) as count
        FROM dense_variants
        WHERE code_id = ?
        GROUP BY detail_level
    """, (code_id,))

    complete_levels = {row[0] for row in cursor.fetchall() if row[1] == 10}
    conn.close()

    all_levels = set(range(10))
    missing = sorted(list(all_levels - complete_levels))
    return missing


def generate_variants_for_detail_level(code: str, description: str, detail_level: int) -> List[str]:
    """Generate 10 similar variants for a specific detail level using Azure OpenAI."""

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

    system_prompt = "You are a medical documentation expert who generates realistic clinical descriptions."

    user_prompt = f"""Generate 10 DIFFERENT but SIMILAR clinical descriptions for this ICD-10 code at detail level {detail_level}/9:

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
Example format: ["variant 1", "variant 2", ..., "variant 10"]

JSON array:"""

    result = openai_client.generate_json(user_prompt, system_prompt, temperature=0.8, max_tokens=2000)

    if not result['success']:
        raise Exception(f"OpenAI call failed: {result.get('error', 'Unknown error')}")

    variants = result['data']

    if len(variants) != 10:
        raise ValueError(f"Expected 10 variants for detail level {detail_level}, got {len(variants)}")

    return variants


def store_dense_variants(code_id: int, code: str, detail_level: int, variants: List[str]):
    """Store dense variants in the database (10×10 matrix structure)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for variant_index, variant in enumerate(variants):
        cursor.execute("""
            INSERT OR REPLACE INTO dense_variants (code_id, detail_level, variant_index, description)
            VALUES (?, ?, ?, ?)
        """, (code_id, detail_level, variant_index, variant))

    conn.commit()
    conn.close()
    print(f"✓ Stored {len(variants)} variants for detail level {detail_level}")


def main():
    print("\n" + "="*70)
    print("Chapter 3.3: Dense Variant Generation (10×10 Matrix) - FAST VERSION")
    print("Using Azure OpenAI via VivioMed backend")
    print("="*70)
    print()

    ensure_table_exists()
    print()

    test_codes = get_test_codes()
    print(f"Selected {len(test_codes)} billable test codes for proof of concept:")
    for code in test_codes:
        print(f"  • {code['code']}: {code['description'][:60]}...")
    print()

    total_generated = 0
    total_time = 0

    for code_num, code in enumerate(test_codes, 1):
        print(f"\n[{code_num}/{len(test_codes)}] Processing {code['code']}...")
        print(f"  {code['description'][:70]}...")

        missing_levels = get_missing_variants(code['id'])

        if not missing_levels:
            print(f"  ✓ All 100 variants already exist for {code['code']} - skipping")
            continue

        print(f"  Missing detail levels: {missing_levels} ({len(missing_levels)} levels)")

        for detail_level in missing_levels:
            level_start = time.time()
            print(f"  Detail level {detail_level}/9: ", end='', flush=True)

            try:
                variants = generate_variants_for_detail_level(
                    code['code'],
                    code['description'],
                    detail_level
                )

                store_dense_variants(code['id'], code['code'], detail_level, variants)
                level_time = time.time() - level_start
                total_time += level_time
                total_generated += len(variants)

                print(f"({level_time:.1f}s)")

            except Exception as e:
                print(f"ERROR: {e}")
                continue

    print()
    print("="*70)
    print("✓ Dense variant generation complete!")
    print(f"  Generated {total_generated} new variants in {total_time:.1f}s")
    print(f"  Average: {total_time/max(total_generated, 1):.2f}s per variant")
    print("="*70)


if __name__ == "__main__":
    main()
