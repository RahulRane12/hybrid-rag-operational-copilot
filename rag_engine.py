"""
Hybrid Vector RAG Engine for Operational Diagnostics.
Indexes unstructured customer support tickets and post-delivery reviews.
Performs semantic vector search reconciled with structured SQL filters.
"""

import sqlite3
import os
from typing import List, Dict, Any, Optional
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from db_engine import get_db_connection, DB_PATH
from nlp_engine import analyze_sentiment

class HybridVectorRAG:
    """
    Hybrid RAG Vector Store indexing customer support logs, tickets, and reviews.
    Reconciles unstructured semantic similarity with structured operational attributes.
    """
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.tfidf_matrix: Optional[np.ndarray] = None
        self.documents: List[Dict[str, Any]] = []
        self._build_index()

    def _build_index(self) -> None:
        """Loads and vectorizes all tickets and reviews from SQLite."""
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()

        # 1. Load Customer Support Tickets
        cursor.execute("""
        SELECT 
            t.ticket_id AS doc_id,
            'SUPPORT_TICKET' AS doc_type,
            t.order_id,
            t.sku_id,
            s.name AS sku_name,
            s.category,
            t.channel,
            t.raw_text AS content,
            t.created_at AS doc_date,
            f.transit_latency_days,
            o.carrier
        FROM customer_tickets t
        JOIN orders o ON t.order_id = o.order_id
        JOIN skus s ON t.sku_id = s.sku_id
        LEFT JOIN fulfillments f ON o.order_id = f.order_id;
        """)
        tickets = [dict(row) for row in cursor.fetchall()]

        # 2. Load Reviews
        cursor.execute("""
        SELECT 
            r.review_id AS doc_id,
            'PRODUCT_REVIEW' AS doc_type,
            r.order_id,
            r.sku_id,
            s.name AS sku_name,
            s.category,
            'Review (Rating: ' || r.rating || '/5)' AS channel,
            r.review_title || ' - ' || r.review_text AS content,
            r.review_date AS doc_date,
            f.transit_latency_days,
            o.carrier
        FROM reviews r
        JOIN orders o ON r.order_id = o.order_id
        JOIN skus s ON r.sku_id = s.sku_id
        LEFT JOIN fulfillments f ON o.order_id = f.order_id;
        """)
        reviews = [dict(row) for row in cursor.fetchall()]
        conn.close()

        self.documents = tickets + reviews

        if not self.documents:
            return

        corpus = [doc["content"] for doc in self.documents]
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=5000,
            sublinear_tf=True,
            stop_words='english'
        )
        self.tfidf_matrix = self.vectorizer.fit_transform(corpus)

    def search(
        self,
        query: str,
        sku_id: Optional[str] = None,
        doc_type: Optional[str] = None,
        min_transit_latency: Optional[float] = None,
        carrier: Optional[str] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Executes hybrid semantic search: computes vector similarity of query against corpus
        and filters results against structured operational criteria.
        """
        if not self.vectorizer or self.tfidf_matrix is None or not self.documents:
            return []

        query_vec = self.vectorizer.transform([query])
        sim_scores = cosine_similarity(query_vec, self.tfidf_matrix).flatten()

        results = []
        for idx, score in enumerate(sim_scores):
            doc = self.documents[idx]

            # Apply structured metadata filters
            if sku_id and doc["sku_id"] != sku_id:
                continue
            if doc_type and doc["doc_type"] != doc_type:
                continue
            if min_transit_latency is not None and (doc.get("transit_latency_days") or 0.0) < min_transit_latency:
                continue
            if carrier and doc.get("carrier") != carrier:
                continue

            sentiment = analyze_sentiment(doc["content"])
            doc_result = dict(doc)
            doc_result["similarity_score"] = round(float(score), 4)
            doc_result["sentiment"] = sentiment
            results.append(doc_result)

        # Sort by similarity score descending
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results[:top_k]

    def get_sku_documents(self, sku_id: str) -> List[Dict[str, Any]]:
        """Retrieves all indexed customer logs for a target SKU."""
        return [doc for doc in self.documents if doc["sku_id"] == sku_id]

# Singleton instance
_rag_instance: Optional[HybridVectorRAG] = None

def get_rag_engine(db_path: str = DB_PATH) -> HybridVectorRAG:
    """Returns or initializes the singleton HybridVectorRAG instance."""
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = HybridVectorRAG(db_path)
    return _rag_instance
