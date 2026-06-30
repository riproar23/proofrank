# ProofRank — Evidence-First Candidate Ranking

Ranks 100,000 candidates for Redrob AI's "Senior AI Engineer (Founding Team)" role
by career evidence of production retrieval, ranking, evaluation, and shipping — not
by listed skills or title alone. Runs fully offline on CPU in ~56 seconds.

---

## Reproduce

```bash
pip install -r requirements.txt

python -m src.rank \
  --candidates data/candidates.jsonl \
  --output output/final.csv
```

`output/final.csv` is the submission artifact (top-100, distinct non-increasing scores,
`candidate_id,rank,score,reasoning` header).

### Validate output

```bash
python data/validate_submission.py output/final.csv
```

Expected: `Submission is valid.` + exit 0.

### Run the demo

```bash
streamlit run app.py
# → http://localhost:8501
```

The demo loads `demo/top100_data.json` (pre-baked, committed). No JSONL needed at
demo runtime. To regenerate the baked file after any re-rank:

```bash
python demo/extract_top100.py
```

### Proxy evaluation

```bash
python eval/eval.py
```

Compares `output/baseline.csv` vs `output/final.csv` against a 46-candidate labeled
set (TREC-pool style, grades 0-4). Results are in `results.md`.

---

## Interactive Demo

A recruiter-facing Streamlit demo is included. To launch it locally:

    Launch_ProofRank.bat        # Windows (double-click or run in terminal)
    # or
    streamlit run app.py

The demo shows:
- Ranked shortlist with plain-language evidence for every candidate
- Flagged profiles tab explaining why each was excluded
- Dataset upload and re-ranking without restarting
- Manual candidate entry scored by the real ranker
- CSV download of the shortlist

---

## Compute profile

| Constraint | Value |
|---|---|
| CPU only | Yes — no GPU, no CUDA |
| Peak memory | ~2.3 MB (streaming JSONL + 100-record min-heap) |
| Runtime | ~56 s on a single CPU core |
| Network | Not required — zero external calls |
| Python | 3.9+ |

---

## Architecture

### Scoring formula (final mode)

```
score = 3 × evidence(0-500)
      + title_prior(0-200)
      + skill_coherence(0-200)
      + yoe_fit(0-60)
      + nice_to_have(0-40)
      − integrity_penalties
    × hard_demote            # 0.3 for research-only / keyword-stuffer
      + jd_tiebreak(0-60)    # coding recency > eval rigor > shipping scale
      + behavioral(±40)      # capped; missing signals neutral
```

**Evidence layer (`src/evidence.py`)** — the decisive signal.  
Descriptions are templated: only 44 distinct strings exist across 300k career roles,
so fuzzy text similarity collapses to ~44 clusters. Instead, each description string
is mapped once (cached) to an evidence vector via deterministic phrase-bank matching:

| Dimension | Example phrases | Weight |
|---|---|---|
| `retrieval` | embedding, sentence-transformer, bge, dense retrieval, semantic search | 90 |
| `vector` | faiss, pinecone, hnsw, bm25, hybrid, milvus, qdrant | 70 |
| `ranking` | learning-to-rank, ranking model, recommendation system, rerank | 120 |
| `evaluation` | ndcg, mrr, a/b test, offline-online, relevance judgments | 120 |
| `shipping` | shipped, in production, 10m+, led a team, improved, p95 | 100 |

Evidence (0-500) × 3 = up to 1500 weight, dwarfing behavioral (±40). A candidate
with no ranking evidence cannot beat one who shipped a ranking system regardless of
response rate.

**Title prior (0-200)** — secondary; "Senior NLP Engineer" → 200, "AI Engineer" → 180,
"Staff ML Engineer" → looked up by substring → 140. Canonical titles get a head start;
evidence can rescue non-canonical ones (e.g. "Lead AI Engineer" with ev=500 ranks #10).

**Integrity layer (`src/rank.py` — `detect_honeypot`)** — hard-zeros:
- **H1** expert/advanced skill with `duration_months == 0`
- **H3** role `duration_months` inconsistent with `start_date → end_date` by >4 months
- **H6** Σ career months > 1.4 × `years_of_experience` × 12 + 18
- **H2b** expert skill `duration_months > career_months + 24` (catches AI-titled honeypots
  that pass H1/H3/H6; margin tuned so legitimate long-tenure experts are spared)

Honeypots score −1e9 and never appear in the top-100.

**JD-aligned tiebreak** — within the elite evidence cluster (ev ≈ 500), candidates are
separated by JD-stated priorities in order: (a) coding recency (`is_current` role → +25),
(b) evaluation rigor (NDCG/MAP/A-B evidence depth, up to +20), (c) production scale
(shipping dim × 15). Behavioral signals (response rate, GitHub, notice period) resolve
any remaining ties.

**Behavioral modifier (±40, additive, never multiplicative in final mode)** — missing
signals (GitHub −1 for 65% of pool, empty assessments for 76%) contribute 0, never
penalised. The ±40 cap ensures availability can reorder near-ties but never promotes a
weak-evidence candidate over a strong-evidence one (smallest evidence gap ≈ 270 raw pts →
810 weighted >> 40).

### File map

```
src/
  rank.py          main ranker — both modes (final / baseline)
  evidence.py      phrase-bank matching, evidence vector, desc cache
configs/
  jd_rubric.yaml   JD evidence rubric (reference; not loaded at runtime)
eval/
  labeled_set.py   46-candidate hand-labeled proxy set (grades 0-4)
  eval.py          TREC-pool NDCG/MAP/P@K harness
  extract_for_labeling.py  one-time extraction used to assign grades
demo/
  extract_top100.py  pre-bakes top-100 evidence JSON for the demo
  top100_data.json   committed 632 KB demo payload
app.py             Streamlit demo
results.md         proxy eval results (Checkpoint 4)
data/              .gitignored — put candidates.jsonl here
output/            .gitignored — ranked CSVs written here
```

---

## Local proxy metrics (Checkpoint 4)

Evaluated on 46 hand-labeled candidates (grades 0-4, JD rubric, no circularity).

| Metric | Baseline (Checkpoint 2) | Final (Checkpoint 3+) | Lift |
|---|---|---|---|
| NDCG@10 | 0.54 | **1.00** | +0.46 |
| NDCG@50 | 0.78 | **1.00** | +0.22 |
| MAP | 0.78 | **0.97** | +0.19 |
| P@5 | 0.40 | **1.00** | +0.60 |
| P@10 | 0.50 | **1.00** | +0.50 |

Baseline had 8 grade-0 candidates (honeypots) in its top-100 (8% — near the 10% DQ
threshold). The final ranker catches all 8 via H2b, achieving 0% honeypot rate.
