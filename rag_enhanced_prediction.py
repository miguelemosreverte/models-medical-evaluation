"""
Chapter 3.1: RAG-Enhanced Medical Coding using Description Variants

Uses the bidirectional consistency variants (Chapter 3) as a retrieval corpus
to improve prediction accuracy and stability through semantic similarity matching.
"""

import sqlite3
import json
from typing import List, Dict, Tuple
from dataclasses import dataclass
import numpy as np
from anthropic import Anthropic
import os


@dataclass
class VariantMatch:
    """A matched variant description with its metadata."""
    code: str
    description: str
    detail_level: int
    similarity: float


class RAGEnhancedPredictor:
    """Predicts ICD-10 codes using RAG with description variants."""

    def __init__(self, db_path: str = "medical_coding.db"):
        self.db_path = db_path
        self.client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.variant_cache = None

    def load_variant_corpus(self) -> List[Dict]:
        """Load all description variants from the database."""
        if self.variant_cache is not None:
            return self.variant_cache

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                ic.code,
                gd.description,
                gd.detail_level
            FROM generated_descriptions gd
            JOIN icd10_codes ic ON gd.code_id = ic.id
            ORDER BY ic.code, gd.detail_level
        """)

        variants = []
        for code, desc, level in cursor.fetchall():
            variants.append({
                'code': code,
                'description': desc,
                'detail_level': level
            })

        conn.close()
        self.variant_cache = variants
        return variants

    def get_embeddings(self, texts: List[str]) -> np.ndarray:
        """Get embeddings for a list of texts using Claude's embeddings."""
        # For now, use a simple TF-IDF-like approach
        # In production, you'd use actual embeddings API
        # This is a placeholder for the concept
        from sklearn.feature_extraction.text import TfidfVectorizer

        vectorizer = TfidfVectorizer(max_features=100, stop_words='english')
        try:
            embeddings = vectorizer.fit_transform(texts).toarray()
            return embeddings
        except:
            # Fallback: return random embeddings if corpus is too small
            return np.random.rand(len(texts), 100)

    def find_similar_variants(
        self,
        query_text: str,
        top_k: int = 5
    ) -> List[VariantMatch]:
        """Find the most similar variant descriptions to the query."""
        variants = self.load_variant_corpus()

        if not variants:
            return []

        # Create corpus
        all_texts = [query_text] + [v['description'] for v in variants]

        # Get embeddings
        embeddings = self.get_embeddings(all_texts)
        query_emb = embeddings[0]
        variant_embs = embeddings[1:]

        # Calculate cosine similarity
        similarities = []
        for i, variant in enumerate(variants):
            sim = np.dot(query_emb, variant_embs[i]) / (
                np.linalg.norm(query_emb) * np.linalg.norm(variant_embs[i]) + 1e-8
            )
            similarities.append(sim)

        # Get top-k
        top_indices = np.argsort(similarities)[-top_k:][::-1]

        matches = []
        for idx in top_indices:
            matches.append(VariantMatch(
                code=variants[idx]['code'],
                description=variants[idx]['description'],
                detail_level=variants[idx]['detail_level'],
                similarity=float(similarities[idx])
            ))

        return matches

    def predict_with_rag(
        self,
        medical_note: str,
        model: str = "claude-3-5-sonnet-20241022",
        top_k_variants: int = 5
    ) -> Dict:
        """Predict ICD-10 codes using RAG-enhanced prompting."""

        # Find similar variants
        similar_variants = self.find_similar_variants(medical_note, top_k=top_k_variants)

        # Build context from variants
        context = "Here are some relevant ICD-10 code examples:\n\n"
        for i, match in enumerate(similar_variants, 1):
            context += f"{i}. Code {match.code}: {match.description}\n"

        # Build prompt
        prompt = f"""You are a medical coding expert. Based on the medical note below and the relevant examples provided, predict the most appropriate ICD-10 code(s).

{context}

Medical Note:
{medical_note}

Provide your answer as a JSON array of codes in order of relevance. Example: ["A00.0", "A00.1"]

Only output the JSON array, nothing else."""

        # Call Claude
        try:
            message = self.client.messages.create(
                model=model,
                max_tokens=200,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text.strip()

            # Parse response
            predicted_codes = json.loads(response_text)

            return {
                'predicted_codes': predicted_codes,
                'num_variants_used': len(similar_variants),
                'variants': [
                    {
                        'code': m.code,
                        'similarity': m.similarity,
                        'detail_level': m.detail_level
                    }
                    for m in similar_variants
                ],
                'input_tokens': message.usage.input_tokens,
                'output_tokens': message.usage.output_tokens
            }

        except Exception as e:
            print(f"Error during prediction: {e}")
            return {
                'predicted_codes': [],
                'error': str(e),
                'num_variants_used': len(similar_variants)
            }


def create_rag_experiment_tables():
    """Create database tables for RAG experiments."""
    conn = sqlite3.connect("medical_coding.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rag_predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sample_id INTEGER NOT NULL,
            model_name TEXT NOT NULL,
            predicted_codes TEXT NOT NULL,
            actual_codes TEXT NOT NULL,
            num_variants_used INTEGER,
            variant_metadata TEXT,
            input_tokens INTEGER,
            output_tokens INTEGER,
            processing_time REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sample_id) REFERENCES medical_coding_samples(id)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_rag_pred_sample
        ON rag_predictions(sample_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_rag_pred_model
        ON rag_predictions(model_name)
    """)

    conn.commit()
    conn.close()
    print("RAG experiment tables created successfully")


if __name__ == "__main__":
    # Create tables
    create_rag_experiment_tables()

    # Test the predictor
    predictor = RAGEnhancedPredictor()

    # Load variants
    variants = predictor.load_variant_corpus()
    print(f"Loaded {len(variants)} description variants")

    if len(variants) > 0:
        # Test with a sample medical note
        test_note = "Patient presents with acute watery diarrhea after consuming contaminated food."

        print("\nTesting RAG-enhanced prediction:")
        print(f"Medical note: {test_note}")

        result = predictor.predict_with_rag(test_note)
        print(f"\nPredicted codes: {result.get('predicted_codes', [])}")
        print(f"Variants used: {result.get('num_variants_used', 0)}")

        if 'variants' in result:
            print("\nTop similar variants:")
            for v in result['variants'][:3]:
                print(f"  - {v['code']} (similarity: {v['similarity']:.3f}, level: {v['detail_level']})")