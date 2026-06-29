#!/usr/bin/env python3
"""
Career-evidence extraction — the decisive Checkpoint-3 layer.

Descriptions are templated (44 distinct strings across the pool). We map each
description STRING to an evidence vector ONCE (cached), then aggregate per
candidate.  This is deterministic phrase matching over archetypes, NOT fuzzy
text similarity.

Evidence dimensions (each normalized to [0,1] per role, max-pooled across roles):
  retrieval   — production embeddings / dense / semantic retrieval
  vector      — vector DB / hybrid (FAISS, Pinecone, BM25, HNSW, sparse+dense)
  ranking     — ranking / learning-to-rank / recsys / relevance
  evaluation  — NDCG/MRR/MAP/recall@K, offline-online correlation, A/B, judgments
  shipping    — production ownership, scale, measured impact
  hedge       — self-declared weakness ("experience limited", "secondary", ...)

evidence_score (0..500) = Σ weight·dim − hedge_penalty, clamped.
"""

from __future__ import annotations

# ── Phrase banks (lowercased substring match) ────────────────────────────────
RETRIEVAL_PHRASES = (
    "embedding", "sentence-transformer", "sentence transformer", "dense retrieval",
    "semantic search", "bge", "minilm", "mpnet", "nearest-neighbor", "nearest neighbor",
    "item-item similarity", "dense vector", "openai embeddings",
)
VECTOR_PHRASES = (
    "faiss", "pinecone", "hnsw", "bm25", "hybrid", "milvus", "qdrant", "weaviate",
    "elasticsearch", "inverted index", "sparse and dense", "sparse + dense",
    "vector index", "vector db",
)
RANKING_PHRASES = (
    "ranking model", "ranking layer", "ranking pipeline", "ranking models",
    "learning-to-rank", "learning to rank", "re-rank", "rerank", "re-ranking",
    "recommendation system", "recommendation-style", "discovery feed",
    "relevance labeling", "collaborative filtering", "matrix factorization",
    "content-based ranking", "ltr", "scoring function",
)
EVALUATION_PHRASES = (
    "ndcg", "mrr", "recall@", "map@", "offline-online", "offline/online",
    "online/offline", "a/b test", "a/b engagement", "ab test",
    "human relevance judgment", "relevance judgments", "human judgments",
    "human-in-the-loop", "held-out eval", "held out eval", "eval harness",
    "evaluation framework", "experimentation framework", "online a/b", "live a/b",
    "offline metrics", "offline eval", "training/eval", "eval workflow",
    "click-through", "going from offline experimentation", "a/b testing",
)
SHIPPING_PHRASES = (
    "shipped", "serving", "in production", "production ", "deployed", "owned the",
    "p95", "led a team", "rollout", "10m+", "50m+", "35m+", "500k", "200k",
    "real users", "live a/b", "improved", "reduced", "increased", "cut ",
    "drove the migration", "going from offline",
)
HEDGE_PHRASES = (
    "experience there is limited", "transitioning toward", "wouldn't call myself",
    "was secondary", "lighter weight than", "handled by the platform team",
    "not the model itself", "adjacent ml exposure", "some adjacent",
    "didn't make it to production", "my role was more on the modeling side",
    "experience there is limited", "i'm building competence", "still learning",
    "pure ml side", "my own modeling work was secondary",
)

# per-dimension caps and weights (Σ weights = 500)
_CAP = {"retrieval": 2, "vector": 2, "ranking": 2, "evaluation": 2, "shipping": 3}
_WEIGHT = {"retrieval": 90, "vector": 70, "ranking": 120, "evaluation": 120, "shipping": 100}
_HEDGE_CAP = 2
_HEDGE_PENALTY = 60

_DESC_CACHE: dict[str, dict[str, float]] = {}


def _count(text: str, phrases: tuple[str, ...]) -> int:
    return sum(1 for p in phrases if p in text)


def desc_evidence(desc: str) -> dict[str, float]:
    """Evidence vector for ONE description string (cached by exact string)."""
    cached = _DESC_CACHE.get(desc)
    if cached is not None:
        return cached
    t = desc.lower()
    vec = {
        "retrieval": min(_count(t, RETRIEVAL_PHRASES), _CAP["retrieval"]) / _CAP["retrieval"],
        "vector": min(_count(t, VECTOR_PHRASES), _CAP["vector"]) / _CAP["vector"],
        "ranking": min(_count(t, RANKING_PHRASES), _CAP["ranking"]) / _CAP["ranking"],
        "evaluation": min(_count(t, EVALUATION_PHRASES), _CAP["evaluation"]) / _CAP["evaluation"],
        "shipping": min(_count(t, SHIPPING_PHRASES), _CAP["shipping"]) / _CAP["shipping"],
        "hedge": min(_count(t, HEDGE_PHRASES), _HEDGE_CAP) / _HEDGE_CAP,
    }
    _DESC_CACHE[desc] = vec
    return vec


def career_evidence(record: dict) -> tuple[float, dict[str, float]]:
    """
    Aggregate evidence across all career roles (max-pool per dimension), apply a
    breadth bonus for ≥2 substantive roles, return (score_0_500, agg_dims).
    """
    roles = record.get("career_history", [])
    agg = {"retrieval": 0.0, "vector": 0.0, "ranking": 0.0,
           "evaluation": 0.0, "shipping": 0.0, "hedge": 0.0}
    substantive = 0
    for r in roles:
        desc = (r.get("description") or "").strip()
        if not desc:
            continue
        v = desc_evidence(desc)
        for k in agg:
            if k == "hedge":
                continue
            if v[k] > agg[k]:
                agg[k] = v[k]
        # hedge: take the MIN hedge across roles (a strong role offsets a hedged one)
        agg["hedge"] = max(agg["hedge"], 0.0)
        if (v["retrieval"] + v["ranking"] + v["evaluation"]) >= 1.0:
            substantive += 1
    # hedge taken as the minimum across roles (best-foot-forward); recompute
    hedges = [desc_evidence((r.get("description") or "").strip())["hedge"]
              for r in roles if (r.get("description") or "").strip()]
    agg["hedge"] = min(hedges) if hedges else 0.0

    score = sum(_WEIGHT[k] * agg[k] for k in _WEIGHT)
    score -= _HEDGE_PENALTY * agg["hedge"]
    if substantive >= 2:
        score += 30.0  # consistency: more than one real role
    return max(0.0, min(500.0, score)), agg
