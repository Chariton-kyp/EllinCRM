"""
AI/ML module for EllinCRM.

This module provides:
- Document embeddings using sentence-transformers
- Semantic similarity search using pgvector
- Optional LLM integration for complex extraction

Architecture follows the STRATEGIC_PLAN.md specifications.
"""

from app.ai.embeddings import EmbeddingService, get_embedding_service
from app.ai.similarity import SimilaritySearchService

__all__ = [
    "EmbeddingService",
    "get_embedding_service",
    "SimilaritySearchService",
]
