#!/usr/bin/env python3
"""
Production-quality RAG Engine for Medical Coding

Uses TF-IDF embeddings on combined corpus:
- 46k real ICD-10 code descriptions
- Synthetic variants from Chapter 3

Provides fast semantic similarity search for context retrieval.
"""

import sqlite3
import numpy as np
import pickle
import os
from typing import List, Dict, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import json


class MedicalCodingRAG:
    """Production RAG engine with proper embeddings."""

    def __init__(self, db_path: str = "medical_coding.db", cache_dir: str = ".rag_cache", corpus_mode: str = "both"):
        """
        Initialize RAG engine.

        Args:
            db_path: Path to SQLite database
            cache_dir: Directory for caching embeddings
            corpus_mode: 'real_only', 'synthetic_only', or 'both'
        """
        self.db_path = db_path
        self.cache_dir = cache_dir
        self.corpus_mode = corpus_mode
        os.makedirs(cache_dir, exist_ok=True)

        self.vectorizer = None
        self.embeddings = None
        self.corpus = []
        self.corpus_metadata = []

        # Use separate cache for each corpus mode
        cache_suffix = f"_{corpus_mode}"

        # Try to load from cache
        if not self._load_cache(cache_suffix):
            # Build from scratch
            self._build_corpus()
            self._compute_embeddings()
            self._save_cache(cache_suffix)

    def _load_cache(self, suffix: str = "") -> bool:
        """Load pre-computed embeddings from cache."""
        cache_files = [
            os.path.join(self.cache_dir, f"vectorizer{suffix}.pkl"),
            os.path.join(self.cache_dir, f"embeddings{suffix}.npy"),
            os.path.join(self.cache_dir, f"corpus{suffix}.json"),
        ]

        if not all(os.path.exists(f) for f in cache_files):
            return False

        try:
            with open(cache_files[0], 'rb') as f:
                self.vectorizer = pickle.load(f)

            self.embeddings = np.load(cache_files[1])

            with open(cache_files[2], 'r') as f:
                data = json.load(f)
                self.corpus = data['corpus']
                self.corpus_metadata = data['metadata']

            print(f"✓ Loaded RAG cache: {len(self.corpus)} documents")
            return True
        except Exception as e:
            print(f"⚠ Failed to load cache: {e}")
            return False

    def _save_cache(self, suffix: str = ""):
        """Save embeddings to cache for fast loading."""
        try:
            with open(os.path.join(self.cache_dir, f"vectorizer{suffix}.pkl"), 'wb') as f:
                pickle.dump(self.vectorizer, f)

            np.save(os.path.join(self.cache_dir, f"embeddings{suffix}.npy"), self.embeddings)

            with open(os.path.join(self.cache_dir, f"corpus{suffix}.json"), 'w') as f:
                json.dump({
                    'corpus': self.corpus,
                    'metadata': self.corpus_metadata
                }, f)

            print(f"✓ Saved RAG cache ({self.corpus_mode}): {len(self.corpus)} documents")
        except Exception as e:
            print(f"⚠ Failed to save cache: {e}")

    def _build_corpus(self):
        """Build corpus based on corpus_mode."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get real ICD-10 codes from 46k dataset
        if self.corpus_mode in ['real_only', 'both']:
            cursor.execute("""
                SELECT code, description
                FROM icd10_codes
                ORDER BY code
            """)

            for code, description in cursor.fetchall():
                self.corpus.append(description)
                self.corpus_metadata.append({
                    'code': code,
                    'description': description,
                    'source': 'real',
                    'detail_level': None
                })

        # Get synthetic variants from Chapter 3
        if self.corpus_mode in ['synthetic_only', 'both']:
            cursor.execute("""
                SELECT ic.code, gd.description, gd.detail_level
                FROM generated_descriptions gd
                JOIN icd10_codes ic ON gd.code_id = ic.id
                ORDER BY ic.code, gd.detail_level
            """)

            for code, description, detail_level in cursor.fetchall():
                self.corpus.append(description)
                self.corpus_metadata.append({
                    'code': code,
                    'description': description,
                    'source': 'synthetic',
                    'detail_level': detail_level
                })

        conn.close()

        print(f"✓ Built corpus ({self.corpus_mode}): {len(self.corpus)} documents")
        print(f"  - Real entries: {sum(1 for m in self.corpus_metadata if m['source'] == 'real')}")
        print(f"  - Synthetic variants: {sum(1 for m in self.corpus_metadata if m['source'] == 'synthetic')}")

    def _compute_embeddings(self):
        """Compute TF-IDF embeddings for entire corpus."""
        print("Computing TF-IDF embeddings...")

        # Configure vectorizer for medical text
        self.vectorizer = TfidfVectorizer(
            max_features=5000,           # Top 5000 terms
            ngram_range=(1, 3),          # Unigrams, bigrams, trigrams
            stop_words='english',        # Remove common English words
            min_df=2,                    # Term must appear in at least 2 docs
            max_df=0.8,                  # Ignore terms in >80% of docs
            sublinear_tf=True,           # Use log scaling for term frequency
            norm='l2'                    # L2 normalization
        )

        self.embeddings = self.vectorizer.fit_transform(self.corpus).toarray()

        print(f"✓ Computed embeddings: {self.embeddings.shape}")

    def find_similar(
        self,
        query: str,
        top_k: int = 5,
        exclude_code: str = None,
        source_filter: str = None
    ) -> List[Dict]:
        """
        Find most similar documents to query.

        Args:
            query: Text to find similar documents for
            top_k: Number of results to return
            exclude_code: Optionally exclude this code from results
            source_filter: 'real', 'synthetic', or None for both

        Returns:
            List of dicts with 'code', 'description', 'similarity', 'source', 'detail_level'
        """
        # Encode query
        query_embedding = self.vectorizer.transform([query]).toarray()

        # Calculate cosine similarity with all documents
        similarities = cosine_similarity(query_embedding, self.embeddings)[0]

        # Get top-k indices
        top_indices = np.argsort(similarities)[::-1]

        results = []
        for idx in top_indices:
            metadata = self.corpus_metadata[idx]

            # Apply filters
            if exclude_code and metadata['code'] == exclude_code:
                continue

            if source_filter and metadata['source'] != source_filter:
                continue

            results.append({
                'code': metadata['code'],
                'description': metadata['description'],
                'similarity': float(similarities[idx]),
                'source': metadata['source'],
                'detail_level': metadata['detail_level']
            })

            if len(results) >= top_k:
                break

        return results

    def get_stats(self) -> Dict:
        """Get statistics about the RAG corpus."""
        real_count = sum(1 for m in self.corpus_metadata if m['source'] == 'real')
        synthetic_count = sum(1 for m in self.corpus_metadata if m['source'] == 'synthetic')

        return {
            'total_documents': len(self.corpus),
            'real_entries': real_count,
            'synthetic_variants': synthetic_count,
            'embedding_dimensions': self.embeddings.shape[1] if self.embeddings is not None else 0,
            'vocabulary_size': len(self.vectorizer.vocabulary_) if self.vectorizer else 0
        }

    def rebuild(self):
        """Force rebuild of corpus and embeddings."""
        print("Rebuilding RAG engine from scratch...")
        self.corpus = []
        self.corpus_metadata = []
        self._build_corpus()
        self._compute_embeddings()
        self._save_cache()
        print("✓ Rebuild complete")


def test_rag_engine():
    """Test the RAG engine with sample queries."""
    print("\n" + "="*60)
    print("Testing RAG Engine")
    print("="*60 + "\n")

    rag = MedicalCodingRAG()

    # Print stats
    stats = rag.get_stats()
    print("RAG Engine Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value:,}")

    # Test queries
    test_queries = [
        ("Patient has severe watery diarrhea", "A00.0"),
        ("High blood pressure", "I10"),
        ("Chest pain and shortness of breath", None),
    ]

    print("\n" + "-"*60)
    print("Sample Queries")
    print("-"*60 + "\n")

    for query, expected_code in test_queries:
        print(f"Query: '{query}'")
        if expected_code:
            print(f"Expected code: {expected_code}")

        # Find similar with and without excluding the expected code
        results = rag.find_similar(query, top_k=5, exclude_code=expected_code)

        print("\nTop 5 similar documents:")
        for i, result in enumerate(results, 1):
            source_badge = "📚" if result['source'] == 'real' else "🔬"
            print(f"{i}. [{result['code']}] {source_badge} (sim: {result['similarity']:.3f})")
            print(f"   {result['description'][:80]}...")

        print("\n" + "-"*60 + "\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Medical Coding RAG Engine")
    parser.add_argument('--rebuild', action='store_true', help='Force rebuild cache')
    parser.add_argument('--test', action='store_true', help='Run test queries')
    parser.add_argument('--query', type=str, help='Query for similar documents')
    parser.add_argument('--top-k', type=int, default=5, help='Number of results')

    args = parser.parse_args()

    rag = MedicalCodingRAG()

    if args.rebuild:
        rag.rebuild()

    if args.test:
        test_rag_engine()

    if args.query:
        print(f"\nQuery: {args.query}\n")
        results = rag.find_similar(args.query, top_k=args.top_k)
        for i, result in enumerate(results, 1):
            print(f"{i}. [{result['code']}] {result['source']} (similarity: {result['similarity']:.3f})")
            print(f"   {result['description']}")
            print()
