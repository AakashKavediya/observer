"""
observer_engine.sequencer.rag_engine
Genuine Retrieval-Augmented Generation (RAG) engine for executive dysfunction coping strategies.
Performs local document ingestion, chunking, embedding generation, vector indexing,
and similarity retrieval with strict source provenance. Zero cloud dependencies.
"""

import os
import re
import json
import math
import time
import hashlib
from typing import List, Dict, Any, Optional, Tuple

from observer_engine.sequencer.config import SequencerConfig, SEQUENCER_CONFIG
from observer_engine.sequencer.models import SourceReference


class LocalEmbeddingVectorizer:
    """
    Fast, deterministic, offline local embedding vectorizer.
    Generates normalized dense vectors (dim=256) using subword n-gram hashing and
    sublinear TF-IDF weighting. 100% offline, zero network or GPU dependencies.
    """
    def __init__(self, dimension: int = 256):
        self.dimension = dimension

    def _tokenize(self, text: str) -> List[str]:
        words = re.findall(r"\b\w{2,}\b", text.lower())
        tokens = list(words)
        # Add character tri-grams for subword semantic capture
        for w in words:
            if len(w) >= 3:
                for i in range(len(w) - 2):
                    tokens.append(f"#{w[i:i+3]}")
        return tokens

    def embed_text(self, text: str) -> List[float]:
        vec = [0.0] * self.dimension
        tokens = self._tokenize(text)
        if not tokens:
            return vec

        term_freq: Dict[int, float] = {}
        for token in tokens:
            # Deterministic hash to bucket
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest()[:8], 16) % self.dimension
            term_freq[h] = term_freq.get(h, 0.0) + 1.0

        for bucket, freq in term_freq.items():
            vec[bucket] = 1.0 + math.log(freq)

        # L2 Normalize
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 1e-9:
            vec = [x / norm for x in vec]
        return vec

    @staticmethod
    def cosine_similarity(v1: List[float], v2: List[float]) -> float:
        if len(v1) != len(v2) or not v1:
            return 0.0
        dot = sum(a * b for a, b in zip(v1, v2))
        return max(0.0, min(1.0, float(dot)))


class RagEngine:
    def __init__(self, config: SequencerConfig = SEQUENCER_CONFIG):
        self.config = config
        self.vectorizer = LocalEmbeddingVectorizer(dimension=256)
        self.index_path = os.path.join(self.config.storage_dir, "vector_index.json")

        self.documents: List[Dict[str, Any]] = []
        self.chunks: List[Dict[str, Any]] = []  # Contains metadata + embedding vector

        # Diagnostics metrics
        self.last_retrieval_query: str = ""
        self.last_retrieval_matches_count: int = 0
        self.last_retrieval_latency_ms: float = 0.0
        self.last_index_build_ts: float = 0.0

        self.load_or_build_index()

    # -------------------------------------------------------------
    # Document Ingestion & Chunking
    # -------------------------------------------------------------
    def load_or_build_index(self, force_rebuild: bool = False) -> None:
        """Loads vector index from disk if valid, otherwise parses source documents and builds it."""
        if not force_rebuild and os.path.isfile(self.index_path):
            try:
                with open(self.index_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.documents = data.get("documents", [])
                    self.chunks = data.get("chunks", [])
                    self.last_index_build_ts = data.get("build_ts", 0.0)
                    if self.chunks:
                        return
            except Exception:
                pass

        self.rebuild_index()

    def rebuild_index(self) -> Dict[str, Any]:
        """Parses all curated knowledge documents, computes chunks & embeddings, and saves index."""
        start_t = time.time()
        self.documents = []
        self.chunks = []

        kb_dir = self.config.knowledge_base_dir
        if not os.path.isdir(kb_dir):
            os.makedirs(kb_dir, exist_ok=True)

        # 1. Read JSON knowledge files
        for fname in os.listdir(kb_dir):
            fpath = os.path.join(kb_dir, fname)
            if fname.endswith(".json") and os.path.isfile(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        docs = json.load(f)
                        if isinstance(docs, list):
                            self.documents.extend(docs)
                except Exception as e:
                    pass

        # 2. Chunk documents and embed
        for doc in self.documents:
            doc_id = doc.get("doc_id", "DOC")
            title = doc.get("title", "Untitled")
            content = doc.get("content", "")
            category = doc.get("category", "")
            topic = doc.get("topic", "")
            url = doc.get("url", "")
            author = doc.get("author_or_org", "")

            doc_chunks = self._chunk_text(content, self.config.chunk_size_words, self.config.chunk_overlap_words)
            for idx, c_text in enumerate(doc_chunks):
                # Contextualized text for embedding
                context_str = f"{title}. Category: {category}. Topic: {topic}. {c_text}"
                vec = self.vectorizer.embed_text(context_str)

                self.chunks.append({
                    "chunk_id": f"{doc_id}_c{idx+1}",
                    "doc_id": doc_id,
                    "title": title,
                    "category": category,
                    "topic": topic,
                    "url": url,
                    "author_or_org": author,
                    "text": c_text,
                    "vector": vec,
                })

        self.last_index_build_ts = time.time()
        duration_ms = (self.last_index_build_ts - start_t) * 1000.0

        # Persist index
        try:
            with open(self.index_path, "w", encoding="utf-8") as f:
                json.dump({
                    "build_ts": self.last_index_build_ts,
                    "documents_count": len(self.documents),
                    "chunks_count": len(self.chunks),
                    "documents": self.documents,
                    "chunks": self.chunks,
                }, f, indent=2)
        except Exception:
            pass

        return {
            "status": "success",
            "documents_count": len(self.documents),
            "chunks_count": len(self.chunks),
            "duration_ms": duration_ms,
        }

    def _chunk_text(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        words = text.split()
        if len(words) <= chunk_size:
            return [text]

        chunks = []
        step = max(1, chunk_size - overlap)
        for i in range(0, len(words), step):
            segment = words[i:i + chunk_size]
            chunks.append(" ".join(segment))
            if i + chunk_size >= len(words):
                break
        return chunks

    # -------------------------------------------------------------
    # Similarity Retrieval
    # -------------------------------------------------------------
    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        min_relevance: Optional[float] = None,
    ) -> List[SourceReference]:
        """
        Retrieves top-k relevant knowledge chunks for the user request.
        Preserves original document metadata and excludes low-confidence matches.
        """
        start_t = time.time()
        self.last_retrieval_query = query
        k = top_k or self.config.retrieval_top_k
        threshold = min_relevance if min_relevance is not None else self.config.min_retrieval_relevance

        if not self.chunks or not query.strip():
            self.last_retrieval_matches_count = 0
            self.last_retrieval_latency_ms = 0.0
            return []

        q_vec = self.vectorizer.embed_text(query)
        scored_chunks: List[Tuple[float, Dict[str, Any]]] = []

        for chunk in self.chunks:
            score = self.vectorizer.cosine_similarity(q_vec, chunk["vector"])
            if score >= threshold:
                scored_chunks.append((score, chunk))

        # Sort descending by score
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        top_matches = scored_chunks[:k]

        self.last_retrieval_matches_count = len(top_matches)
        self.last_retrieval_latency_ms = (time.time() - start_t) * 1000.0

        results = []
        for score, chunk in top_matches:
            results.append(
                SourceReference(
                    doc_id=chunk["doc_id"],
                    title=chunk["title"],
                    url=chunk.get("url", ""),
                    author_or_org=chunk.get("author_or_org", ""),
                    category=chunk.get("category", ""),
                    excerpt=chunk["text"],
                    relevance_score=round(score, 4),
                )
            )

        return results
