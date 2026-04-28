"""Embedding-Layer: Vektorisierung von Domain-Objekten und Persistierung.

Public API:
- EmbeddingRepository: DB-Zugriff fuer invoice_embeddings (tenant-aware).
- EmbeddingService:    Orchestriert Text-Build, PII-Masking, AI-Call und Persistierung.
- SimilarInvoice:      Ergebnis-Container fuer find_similar().
"""

from kontura.ai.embeddings.repository import EmbeddingRepository, SimilarInvoice
from kontura.ai.embeddings.service import EmbeddingService

__all__ = ["EmbeddingRepository", "EmbeddingService", "SimilarInvoice"]
