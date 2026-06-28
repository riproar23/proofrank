#!/usr/bin/env python3
"""
Deterministic baseline ranker — Redrob Senior AI Engineer challenge.
Reproduce: python -m src.rank --candidates data/candidates.jsonl --output output/baseline.csv

Scoring architecture (Checkpoint 2 — no embeddings, no LLM calls):
  final_score = tier_base + sub_scores * behavioral_multiplier + epsilon

  tier_base  ∈ {0, 400, 800, 1200, 1600, 2000}   — gap 400 > sub_scores_max 207
  sub_scores = skill_coherence(0-80) + nice_to_have(0-20) + yoe_fit(0-20) + career_evidence(0-60)
  behavioral ∈ [0.70, 1.15]  applied only to sub_scores so tiers never collapse
  epsilon    = (100000 - cand_num) * 1e-6  → strictly distinct scores, no tie-break edge cases

Integrity guards (run before everything):
  Honeypot H1/H3/H6 → score = 0.0, excluded from top-100
  Keyword stuffer     → score = 2.0, excluded from top-100
"""

import argparse
import csv
import heapq
import subprocess
import sys
import time
import tracemalloc
from datetime import date, datetime
from pathlib import Path

import orjson

# ── Date anchor (deterministic) ───────────────────────────────────────────────
TODAY = date(2026, 6, 29)

# ── Tier base scores — gap 400 ensures no T(n-1) can outscore T(n) ───────────
TIER_BASE: dict[int, float] = {
    5: 2000.0,
    4: 1600.0,
    3: 1200.0,
    2: 800.0,
    1: 400.0,
    0: 0.0,
}

# ── Title → tier prior (from jd_rubric.yaml) ─────────────────────────────────
TITLE_TIER: dict[str, int] = {
    # T5 — core fit: production ranking / retrieval / recsys / search at scale
    "Recommendation Systems Engineer": 5,
    "Search Engineer": 5,
    "Applied ML Engineer": 5,
    "NLP Engineer": 5,
    "AI Engineer": 5,
    # T4 — strong adjacent: applied ML with retrieval/ranking exposure
    "ML Engineer": 4,
    "Data Scientist": 4,
    "AI Specialist": 4,
    "Senior Software Engineer (ML)": 4,
    "AI Research Engineer": 4,   # may demote to T1 if research-only
    # T3 — deployed ML / data-platform that shipped search-adjacent systems
    "Senior Data Engineer": 3,
    "Analytics Engineer": 3,
    "Data Engineer": 3,
    "Backend Engineer": 3,
    # T2 — generic SWE / data, limited retrieval ownership
    "Software Engineer": 2,
    "Full Stack Developer": 2,
    "Cloud Engineer": 2,
    "DevOps Engineer": 2,
    "Senior Software Engineer": 2,
    "Data Analyst": 2,
    # T1 — weak / superficial / domain mismatch
    "Java Developer": 1,
    ".NET Developer": 1,
    "Frontend Engineer": 1,
    "Mobile Developer": 1,
    "QA Engineer": 1,
    "Computer Vision Engineer": 1,  # may promote if also NLP/IR
    "Junior ML Engineer": 1,        # may promote to T2 if strong skills
    # T0 — non-technical / off-domain (forced T0 by title)
    "HR Manager": 0,
    "Marketing Manager": 0,
    "Sales Executive": 0,
    "Accountant": 0,
    "Content Writer": 0,
    "Graphic Designer": 0,
    "Operations Manager": 0,
    "Customer Support": 0,
    "Project Manager": 0,
    "Business Analyst": 0,
    "Civil Engineer": 0,
    "Mechanical Engineer": 0,
}

# ── JD must-have term sets (evidence in skill names) ─────────────────────────
MUST_HAVE_SETS: list[frozenset[str]] = [
    # 1. production embeddings / retrieval
    frozenset(["embeddings", "sentence-transformers", "sentence transformers", "bge", "e5",
               "dense retrieval", "semantic search", "vector search", "retrieval", "rag",
               "ann", "nearest neighbor"]),
    # 2. vector DB / hybrid search infrastructure
    frozenset(["pinecone", "weaviate", "qdrant", "milvus", "faiss", "opensearch",
               "elasticsearch", "bm25", "hybrid search", "vector database", "vector db",
               "inverted index", "lucene", "solr"]),
    # 3. strong Python
    frozenset(["python"]),
    # 4. ranking evaluation frameworks
    frozenset(["ndcg", "mrr", "map", "offline-online", "offline online", "a/b test", "ab test",
               "evaluation", "ranking metrics", "learning to rank", "ltr", "relevance",
               "experimentation", "holdout", "ground truth"]),
]

# ── JD nice-to-have term sets ─────────────────────────────────────────────────
NICE_SETS: list[frozenset[str]] = [
    frozenset(["lora", "qlora", "peft", "fine-tune", "fine-tuning", "sft", "instruction tuning"]),
    frozenset(["xgboost", "lightgbm", "learning to rank", "ltr", "gbdt", "ranknet", "lambdamart"]),
    frozenset(["hr-tech", "recruiting", "marketplace", "two-sided", "talent", "ats"]),
    frozenset(["distributed systems", "large-scale", "inference optimization", "low latency", "sharding"]),
    frozenset(["open source", "open-source", "oss", "contributor", "maintainer"]),
]

# ── Consulting firms (for consulting-only penalty) ────────────────────────────
CONSULTING_TOKENS: frozenset[str] = frozenset([
    "tcs", "tata consultancy", "infosys", "wipro", "accenture", "cognizant",
    "capgemini", "hcl", "tech mahindra", "mindtree", "ltimindtree", "mphasis", "dxc",
])

# ── Non-technical title set (for keyword-stuffer detection) ──────────────────
NON_TECH_LOWER: frozenset[str] = frozenset([
    "hr manager", "marketing manager", "sales executive", "accountant", "content writer",
    "graphic designer", "operations manager", "customer support", "project manager",
    "business analyst", "civil engineer", "mechanical engineer",
])

# ── Core-AI skill tokens (stuffer check: ≥4 in non-tech title) ───────────────
AI_SKILL_TOKENS: frozenset[str] = frozenset([
    "embeddings", "faiss", "pinecone", "qdrant", "milvus", "weaviate", "elasticsearch",
    "semantic search", "dense retrieval", "rag", "retrieval", "transformers", "bert",
    "llm", "mlops", "machine learning", "deep learning", "nlp", "information retrieval",
    "recommendation", "ranking", "pytorch", "tensorflow",
])

# ── AI/ML career role tokens ─────────────────────────────────────────────────
AI_ROLE_TOKENS: frozenset[str] = frozenset([
    "ml engineer", "machine learning", "ai engineer", "data scientist", "nlp",
    "search engineer", "recommendation", "ranking", "recsys", "retrieval",
    "applied ml", "ai specialist", "applied ai",
])

# ── Research/academic institution tokens (for AI Research Engineer demotion) ──
RESEARCH_TOKENS: frozenset[str] = frozenset([
    "university", "research lab", "institute", "iit", "nit", "iim", "college",
    "academia", "research center", "r&d", "deepmind", "openai research", "fair",
])

PROF_WEIGHT: dict[str, int] = {
    "expert": 4, "advanced": 3, "intermediate": 2, "beginner": 1,
}

TIER_LABEL: dict[int, str] = {
    5: "core fit — production ranking/retrieval/recsys",
    4: "strong adjacent — applied ML with search/ranking exposure",
    3: "deployed ML / data-platform engineer",
    2: "general SWE/data, limited retrieval ownership",
    1: "weak fit — domain mismatch or research-only",
    0: "disqualified — off-domain or integrity flag",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _is_consulting(company: str) -> bool:
    co = company.lower()
    return any(tok in co for tok in CONSULTING_TOKENS)


# ── Integrity guards ───────────────────────────────────────────────────────────

def detect_honeypot(record: dict) -> bool:
    """
    H1: expert/advanced skill with duration_months == 0
    H3: role duration_months inconsistent with start→end dates (>4 mo off)
    H6: sum career months > 1.4 × yoe_months + 18
    Returns True → force score = 0.0, exclude from top-100.
    """
    # H1
    for sk in record.get("skills", []):
        if sk.get("proficiency") in ("expert", "advanced") and (sk.get("duration_months") or 0) == 0:
            return True

    career = record.get("career_history", [])
    total_months = 0

    for role in career:
        dm = role.get("duration_months") or 0
        total_months += dm

        # H3: date-duration consistency
        sd = _parse_date(role.get("start_date"))
        end_str = role.get("end_date")
        if end_str:
            ed = _parse_date(end_str)
        elif role.get("is_current"):
            ed = TODAY
        else:
            ed = None

        if sd and ed and ed >= sd:
            actual = (ed.year - sd.year) * 12 + (ed.month - sd.month)
            if abs(actual - dm) > 4:
                return True

    # H6: impossible total tenure
    yoe = float(record.get("profile", {}).get("years_of_experience") or 0)
    if total_months > 1.4 * yoe * 12 + 18:
        return True

    return False


def is_keyword_stuffer(record: dict) -> bool:
    """Non-technical title + ≥4 core-AI skills with weak backing."""
    title = (record.get("profile", {}).get("current_title") or "").lower()
    if title not in NON_TECH_LOWER:
        return False
    skills = record.get("skills", [])
    name_tokens = [s.get("name", "").lower() for s in skills]
    ai_count = sum(
        1 for name in name_tokens
        if any(tok in name for tok in AI_SKILL_TOKENS)
    )
    return ai_count >= 4


# ── Sub-score components ───────────────────────────────────────────────────────

def skill_coherence_score(record: dict) -> float:
    """0–80: match of skill section against JD must-haves, weighted by proficiency + duration."""
    skills = record.get("skills", [])
    # Build term → best (prof_weight, duration_months, endorsements) mapping
    best: dict[str, tuple[int, int, int]] = {}
    for sk in skills:
        name_lo = (sk.get("name") or "").lower()
        pw = PROF_WEIGHT.get(sk.get("proficiency") or "", 0)
        dm = sk.get("duration_months") or 0
        en = sk.get("endorsements") or 0
        for term_set in MUST_HAVE_SETS:
            for t in term_set:
                if t in name_lo:
                    existing = best.get(t)
                    if existing is None or (pw, dm, en) > existing:
                        best[t] = (pw, dm, en)

    total = 0.0
    for term_set in MUST_HAVE_SETS:
        bpw, bdm, ben = 0, 0, 0
        for t in term_set:
            if t in best:
                pw, dm, en = best[t]
                if (pw, dm, en) > (bpw, bdm, ben):
                    bpw, bdm, ben = pw, dm, en
        if bpw == 0:
            continue
        pts = {4: 15, 3: 12, 2: 8, 1: 4}[bpw]
        pts += 3 if bdm > 12 else (2 if bdm > 6 else (1 if bdm > 0 else 0))
        pts += 2 if ben > 5 else 0
        total += min(pts, 20)

    return min(total, 80.0)


def nice_to_have_score(record: dict) -> float:
    """0–20: 4 pts per matched nice-to-have (5 groups × 4 pts)."""
    skills = record.get("skills", [])
    names_lo = " ".join((s.get("name") or "").lower() for s in skills)
    total = 0.0
    for term_set in NICE_SETS:
        if any(t in names_lo for t in term_set):
            total += 4.0
    return min(total, 20.0)


def yoe_fit_score(yoe: float) -> float:
    """0–20: soft band centered on JD's 5–9 year range."""
    if 5.0 <= yoe <= 9.0:
        return 20.0
    if 4.0 <= yoe < 5.0 or 9.0 < yoe <= 10.0:
        return 15.0
    if 3.0 <= yoe < 4.0 or 10.0 < yoe <= 11.0:
        return 10.0
    if 2.0 <= yoe < 3.0 or 11.0 < yoe <= 13.0:
        return 5.0
    return 2.0


def career_evidence_score(record: dict) -> float:
    """
    0–60: structured evidence beyond title.
    +20 at least one product (non-consulting) company
    +10 2+ career roles with AI/ML/search titles
    +10 currently employed or ended role within 24 months
    +10 skill assessment scores present (proxy for active effort)
    +10 meaningful skill endorsements
    """
    career = record.get("career_history", [])
    signals = record.get("redrob_signals", {})
    score = 0.0

    # Product company presence
    if any(not _is_consulting(r.get("company") or "") for r in career):
        score += 20.0

    # AI/ML role count in career history
    ai_roles = sum(
        1 for r in career
        if any(tok in (r.get("title") or "").lower() for tok in AI_ROLE_TOKENS)
    )
    score += 10.0 if ai_roles >= 2 else (5.0 if ai_roles == 1 else 0.0)

    # Recency: is_current or ended within 24 months
    for r in career:
        if r.get("is_current"):
            score += 10.0
            break
        ed = _parse_date(r.get("end_date"))
        if ed:
            months_ago = (TODAY.year - ed.year) * 12 + (TODAY.month - ed.month)
            if months_ago <= 24:
                score += 5.0
                break

    # Assessment scores: proxy for real skill validation
    assess = signals.get("skill_assessment_scores") or {}
    if assess:
        avg = sum(assess.values()) / len(assess)
        score += min(avg / 10.0, 10.0)

    # Endorsements depth
    total_end = sum((s.get("endorsements") or 0) for s in record.get("skills", []))
    score += 10.0 if total_end > 50 else (6.0 if total_end > 20 else (3.0 if total_end > 5 else 0.0))

    return min(score, 60.0)


def behavioral_multiplier(record: dict) -> float:
    """
    [0.70, 1.15] availability + credibility modifier.
    Applied only to sub_scores so tier ordering is preserved.
    """
    sig = record.get("redrob_signals", {})
    mult = 1.0

    # Recruiter response rate
    rr = sig.get("recruiter_response_rate")
    if rr is not None:
        if rr < 0.15:
            mult -= 0.15
        elif rr > 0.60:
            mult += 0.05

    # Staleness
    la = _parse_date(sig.get("last_active_date"))
    if la:
        days = (TODAY - la).days
        if days > 180:
            mult -= 0.10
        elif days < 60:
            mult += 0.05

    # Active job-seeking
    if sig.get("open_to_work_flag"):
        mult += 0.05

    # GitHub presence
    gh = sig.get("github_activity_score")
    if gh is not None and gh > 0:
        mult += 0.03

    # Skill assessments taken
    if sig.get("skill_assessment_scores"):
        mult += 0.03

    # Verified contact details
    if sig.get("verified_email") and sig.get("verified_phone"):
        mult += 0.02

    # Interview completion
    icr = sig.get("interview_completion_rate")
    if icr is not None and icr < 0.30:
        mult -= 0.05

    return max(0.70, min(1.15, mult))


# ── Title tier with adjustments ───────────────────────────────────────────────

def _get_title_tier(title: str) -> int:
    """Lookup title tier; keyword-based fallback for unseen titles."""
    if title in TITLE_TIER:
        return TITLE_TIER[title]
    lo = title.lower()
    if any(kw in lo for kw in ["recsys", "recommendation", "search engineer", "nlp engineer", "applied ml"]):
        return 5
    if any(kw in lo for kw in ["ml ", "machine learning", "ai engineer", "nlp", "applied ai"]):
        return 4
    if "data scientist" in lo or "data engineer" in lo:
        return 3
    if any(kw in lo for kw in ["software", "developer", "engineer", "data"]):
        return 2
    return 2


# ── Main scorer ───────────────────────────────────────────────────────────────

def score_candidate(record: dict) -> tuple[float, int, bool]:
    """Returns (final_score, tier, is_honeypot)."""
    # Honeypot: hard exclusion
    is_hp = detect_honeypot(record)
    if is_hp:
        return 0.0, 0, True

    profile = record.get("profile", {})
    title = profile.get("current_title") or ""
    yoe = float(profile.get("years_of_experience") or 0)

    # Keyword stuffer: near-zero score, not honeypot
    if is_keyword_stuffer(record):
        return 2.0, 0, False

    tier = _get_title_tier(title)

    # T0 by title: short-circuit
    if tier == 0:
        cid = record.get("candidate_id", "CAND_0100000")
        num = int(cid[-7:]) if len(cid) >= 7 else 100000
        return (100000 - num) * 1e-9, 0, False

    # AI Research Engineer: demote to T1 if all career is research/academic
    if title == "AI Research Engineer":
        career = record.get("career_history", [])
        all_research = all(
            any(tok in (r.get("company") or "").lower() for tok in RESEARCH_TOKENS)
            for r in career
        ) if career else False
        if all_research:
            tier = 1

    # Junior ML Engineer: promote to T2 if skills are meaningful
    if title == "Junior ML Engineer":
        sc_preview = skill_coherence_score(record)
        if sc_preview > 40:
            tier = 2

    # Computer Vision Engineer: promote to T3 if also has NLP/IR
    if title == "Computer Vision Engineer":
        skill_names = " ".join((s.get("name") or "").lower() for s in record.get("skills", []))
        if any(t in skill_names for t in ["nlp", "retrieval", "search", "information retrieval", "rag"]):
            tier = 3

    base = TIER_BASE[tier]
    sc = skill_coherence_score(record)
    nt = nice_to_have_score(record)
    yf = yoe_fit_score(yoe)
    ce = career_evidence_score(record)
    bm = behavioral_multiplier(record)

    sub = (sc + nt + yf + ce) * bm

    # Epsilon: strictly distinct scores, lower-numbered candidate wins ties
    cid = record.get("candidate_id", "CAND_0100000")
    num = int(cid[-7:]) if len(cid) >= 7 else 100000
    epsilon = (100000 - num) * 1e-6

    return base + sub + epsilon, tier, False


# ── Reasoning generator ────────────────────────────────────────────────────────

def build_reasoning(record: dict, tier: int) -> str:
    """1–2 sentences: specific facts from the profile, grounded, varied."""
    profile = record.get("profile", {})
    title = profile.get("current_title") or "Unknown"
    yoe = profile.get("years_of_experience") or 0
    signals = record.get("redrob_signals", {})
    career = record.get("career_history", [])
    skills = record.get("skills", [])

    # Current employer
    company = next(
        (r.get("company", "") for r in career if r.get("is_current")),
        career[0].get("company", "") if career else "",
    )

    # Top skills by proficiency then endorsements
    ranked = sorted(
        skills,
        key=lambda s: (PROF_WEIGHT.get(s.get("proficiency") or "", 0), s.get("endorsements") or 0),
        reverse=True,
    )
    top_skills = [s["name"] for s in ranked[:3] if s.get("name")]

    gh = signals.get("github_activity_score")
    rr = signals.get("recruiter_response_rate") or 0
    assess = signals.get("skill_assessment_scores") or {}

    s1 = f"{title} ({yoe:.1f} yr)"
    s1 += f" at {company}" if company else ""
    s1 += f" — {TIER_LABEL.get(tier, 'scored')}."

    parts: list[str] = []
    if top_skills:
        parts.append(f"Top skills: {', '.join(top_skills)}")
    if assess:
        best_k = max(assess, key=assess.get)
        parts.append(f"assessed {best_k} at {assess[best_k]:.0f}/100")
    if gh is not None and gh > 0:
        parts.append(f"GitHub score {gh:.0f}")
    if rr > 0.60:
        parts.append(f"response rate {rr:.0%}")
    elif rr > 0 and rr < 0.15:
        parts.append(f"low response rate {rr:.0%} — availability concern")

    s2 = ("; ".join(parts) + ".") if parts else ""
    return (s1 + (" " + s2 if s2 else "")).strip()


# ── Honeypot rate check on a pre-built top-100 list ──────────────────────────

def honeypot_rate_in_top100(top100_records: list[dict]) -> tuple[int, float]:
    count = sum(1 for r in top100_records if detect_honeypot(r))
    return count, count / len(top100_records)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic baseline ranker")
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    candidates_path = Path(args.candidates)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tracemalloc.start()
    t0 = time.perf_counter()

    size_mb = candidates_path.stat().st_size / 1e6
    print(f"Scoring: {candidates_path}  ({size_mb:.0f} MB)")

    # Min-heap of (score, cid) — keeps top-100 in O(n log 100) time
    # Separate dict stores (tier, record) for only those 100 candidates.
    heap: list[tuple[float, str]] = []   # min-heap: smallest score = easiest to evict
    heap_payload: dict[str, tuple[int, dict]] = {}  # cid → (tier, record)
    n_total = 0
    n_honeypot_flagged = 0

    with open(candidates_path, "rb") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            record = orjson.loads(raw)
            n_total += 1

            score, tier, is_hp = score_candidate(record)
            if is_hp:
                n_honeypot_flagged += 1

            cid = record["candidate_id"]

            if len(heap) < 100:
                heapq.heappush(heap, (score, cid))
                heap_payload[cid] = (tier, record)
            elif score > heap[0][0]:
                _, evicted_cid = heapq.heapreplace(heap, (score, cid))
                del heap_payload[evicted_cid]
                heap_payload[cid] = (tier, record)

    t_score = time.perf_counter() - t0
    print(f"Scored {n_total:,} candidates in {t_score:.1f}s")
    print(f"Honeypot flags (H1/H3/H6) in full pool: {n_honeypot_flagged}")

    # Sort top-100 descending by score
    top100 = sorted(heap, reverse=True)  # [(score, cid), ...]

    # Honeypot rate in top-100
    top100_records = [heap_payload[cid][1] for _, cid in top100]
    hp_count, hp_rate = honeypot_rate_in_top100(top100_records)

    # Write CSV
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        for rank, (score, cid) in enumerate(top100, 1):
            tier, record = heap_payload[cid]
            reasoning = build_reasoning(record, tier)
            writer.writerow([cid, rank, f"{score:.6f}", reasoning])

    t_total = time.perf_counter() - t0
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f"\n{'='*60}")
    print(f"Output:       {output_path}")
    print(f"Runtime:      {t_total:.2f}s")
    print(f"Peak memory:  {peak_bytes / 1e6:.1f} MB")
    print(f"{'='*60}")
    print(f"Honeypot rate in top-100: {hp_count}/100 = {hp_rate:.1%}  "
          f"({'PASS — under 10%' if hp_rate <= 0.10 else 'FAIL — DISQUALIFIED'})")
    print(f"{'='*60}")

    print("\nTop-10 candidates:")
    print(f"  {'Rank':>4}  {'CID':<14}  {'Tier':>4}  {'Score':>12}  {'YoE':>5}  Title")
    print("  " + "-" * 70)
    for rank, (score, cid) in enumerate(top100[:10], 1):
        tier, rec = heap_payload[cid]
        prof = rec.get("profile", {})
        title = prof.get("current_title", "?")
        yoe = prof.get("years_of_experience", 0)
        print(f"  {rank:>4}  {cid:<14}  T{tier:>1}    {score:>12.4f}  {yoe:>5.1f}  {title}")

    # Run official validator
    print("\nRunning data/validate_submission.py ...")
    result = subprocess.run(
        [sys.executable, str(Path("data/validate_submission.py")), str(output_path)],
        capture_output=True, text=True,
    )
    validator_out = (result.stdout + result.stderr).strip()
    print(validator_out or "(no output)")
    validator_ok = result.returncode == 0
    print(f"Validator: {'PASS' if validator_ok else 'FAIL'}")

    return 0 if (validator_ok and hp_rate <= 0.10) else 1


if __name__ == "__main__":
    sys.exit(main())
