#!/usr/bin/env python3
"""
Candidate ranker — Redrob Senior AI Engineer challenge.

Modes:
  final     (default) — evidence-first ranker  → output/final.csv  (Checkpoint 3)
  baseline            — title-tier ranker       → output/baseline.csv (Checkpoint 2)

Reproduce (final):
  python -m src.rank --candidates data/candidates.jsonl --output output/final.csv
Reproduce (baseline):
  python -m src.rank --mode baseline --candidates data/candidates.jsonl --output output/baseline.csv

FINAL scoring (Checkpoint 3) — evidence is the decisive layer:
  merit = 3.0·evidence(0-500) + title_prior(0-200) + skill_coherence(0-200)
          + yoe_fit(0-60) + nice(0-40) − integrity_penalties
  core  = merit · hard_demote_mult        (research-only / keyword-stuffer → ×0.3)
  final = core + behavioral_term(±40)      (capped; missing signals neutral)
  honeypot (H1/H3/H6/H2b) → forced to bottom (−1e9), never in top-100.

Because evidence is weighted ×3 (range 0-1500) while the behavioral term is capped
at ±40, the behavioral modifier reorders near-ties but can NEVER lift a weak-evidence
candidate over a materially stronger one — the smallest meaningful evidence gap
(≈270 raw → 810 weighted) dwarfs ±40.
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

from src.evidence import career_evidence

# ── Date anchor (deterministic) ───────────────────────────────────────────────
TODAY = date(2026, 6, 29)

# ═══════════════════════════════════════════════════════════════════════════
# Shared lookups
# ═══════════════════════════════════════════════════════════════════════════

PROF_WEIGHT: dict[str, int] = {"expert": 4, "advanced": 3, "intermediate": 2, "beginner": 1}

# ── Title → baseline tier (Checkpoint 2) ─────────────────────────────────────
TITLE_TIER: dict[str, int] = {
    "Recommendation Systems Engineer": 5, "Search Engineer": 5, "Applied ML Engineer": 5,
    "NLP Engineer": 5, "AI Engineer": 5,
    "ML Engineer": 4, "Data Scientist": 4, "AI Specialist": 4,
    "Senior Software Engineer (ML)": 4, "AI Research Engineer": 4,
    "Senior Data Engineer": 3, "Analytics Engineer": 3, "Data Engineer": 3, "Backend Engineer": 3,
    "Software Engineer": 2, "Full Stack Developer": 2, "Cloud Engineer": 2, "DevOps Engineer": 2,
    "Senior Software Engineer": 2, "Data Analyst": 2,
    "Java Developer": 1, ".NET Developer": 1, "Frontend Engineer": 1, "Mobile Developer": 1,
    "QA Engineer": 1, "Computer Vision Engineer": 1, "Junior ML Engineer": 1,
    "HR Manager": 0, "Marketing Manager": 0, "Sales Executive": 0, "Accountant": 0,
    "Content Writer": 0, "Graphic Designer": 0, "Operations Manager": 0, "Customer Support": 0,
    "Project Manager": 0, "Business Analyst": 0, "Civil Engineer": 0, "Mechanical Engineer": 0,
}

TIER_BASE: dict[int, float] = {5: 2000.0, 4: 1600.0, 3: 1200.0, 2: 800.0, 1: 400.0, 0: 0.0}

# ── Title → evidence-first prior (0-200). Evidence (×3, 0-1500) still dominates. ──
TITLE_PRIOR: dict[str, int] = {
    "Senior NLP Engineer": 200, "Senior Search Engineer": 200, "Senior Software Engineer (ML)": 190,
    "Recommendation Systems Engineer": 180, "Search Engineer": 180, "NLP Engineer": 180,
    "AI Engineer": 180, "Applied ML Engineer": 180,
    "ML Engineer": 140, "Data Scientist": 140, "AI Specialist": 140,
    "AI Research Engineer": 120,
    "Senior Data Engineer": 95, "Analytics Engineer": 90, "Data Engineer": 90, "Backend Engineer": 90,
    "Junior ML Engineer": 80, "Computer Vision Engineer": 80,
    "Senior Software Engineer": 55, "Software Engineer": 50, "Full Stack Developer": 45,
    "Cloud Engineer": 45, "DevOps Engineer": 45, "Data Analyst": 45,
    "Java Developer": 35, ".NET Developer": 35, "Frontend Engineer": 35, "Mobile Developer": 35,
    "QA Engineer": 35,
}

# ── JD must-have skill term sets ─────────────────────────────────────────────
MUST_HAVE_SETS: list[frozenset[str]] = [
    frozenset(["embeddings", "sentence-transformers", "sentence transformers", "bge", "e5",
               "dense retrieval", "semantic search", "vector search", "retrieval", "rag",
               "ann", "nearest neighbor"]),
    frozenset(["pinecone", "weaviate", "qdrant", "milvus", "faiss", "opensearch",
               "elasticsearch", "bm25", "hybrid search", "vector database", "vector db",
               "inverted index", "lucene", "solr"]),
    frozenset(["python"]),
    frozenset(["ndcg", "mrr", "map", "offline-online", "offline online", "a/b test", "ab test",
               "evaluation", "ranking metrics", "learning to rank", "ltr", "relevance",
               "experimentation", "holdout", "ground truth"]),
]
NICE_SETS: list[frozenset[str]] = [
    frozenset(["lora", "qlora", "peft", "fine-tune", "fine-tuning", "sft", "instruction tuning"]),
    frozenset(["xgboost", "lightgbm", "learning to rank", "ltr", "gbdt", "ranknet", "lambdamart"]),
    frozenset(["hr-tech", "recruiting", "marketplace", "two-sided", "talent", "ats"]),
    frozenset(["distributed systems", "large-scale", "inference optimization", "low latency", "sharding"]),
    frozenset(["open source", "open-source", "oss", "contributor", "maintainer"]),
]
CONSULTING_TOKENS: frozenset[str] = frozenset([
    "tcs", "tata consultancy", "infosys", "wipro", "accenture", "cognizant",
    "capgemini", "hcl", "tech mahindra", "mindtree", "ltimindtree", "mphasis", "dxc",
])
NON_TECH_LOWER: frozenset[str] = frozenset([
    "hr manager", "marketing manager", "sales executive", "accountant", "content writer",
    "graphic designer", "operations manager", "customer support", "project manager",
    "business analyst", "civil engineer", "mechanical engineer",
])
AI_SKILL_TOKENS: frozenset[str] = frozenset([
    "embeddings", "faiss", "pinecone", "qdrant", "milvus", "weaviate", "elasticsearch",
    "semantic search", "dense retrieval", "rag", "retrieval", "transformers", "bert",
    "llm", "mlops", "machine learning", "deep learning", "nlp", "information retrieval",
    "recommendation", "ranking", "pytorch", "tensorflow",
])
RESEARCH_TOKENS: frozenset[str] = frozenset([
    "university", "research lab", "institute", "iit", "nit", "iim", "college",
    "academia", "research center", "r&d",
])

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


def _cand_num(cid: str) -> int:
    return int(cid[-7:]) if len(cid) >= 7 and cid[-7:].isdigit() else 100000


# ═══════════════════════════════════════════════════════════════════════════
# Integrity guards (shared by both modes)
# ═══════════════════════════════════════════════════════════════════════════

def detect_honeypot(record: dict) -> bool:
    """
    Hard-zero integrity rules (DATA_AUDIT §8 — union brackets the documented ~80):
      H1  expert/advanced skill claimed with duration_months == 0
      H3  role duration_months inconsistent with start→end dates (>4 mo off)
      H6  Σ career months far exceeds stated years_of_experience (>1.4×+18)
      H2b expert skill used LONGER than the whole career + 24 mo (tight threshold).
          Catches the dangerous AI-titled honeypots (CAND_0005260/0003977/0009024)
          while sparing legitimate long-tenure experts (e.g. CAND_0000031, 8 mo margin).
    """
    yoe = float(record.get("profile", {}).get("years_of_experience") or 0)
    career_len_months = yoe * 12.0

    for sk in record.get("skills", []):
        prof = sk.get("proficiency")
        dur = sk.get("duration_months") or 0
        # H1
        if prof in ("expert", "advanced") and dur == 0:
            return True
        # H2b (tight): only 'expert' claims that exceed the whole career by >24 mo
        if prof == "expert" and dur > career_len_months + 24:
            return True

    career = record.get("career_history", [])
    total_months = 0
    for role in career:
        dm = role.get("duration_months") or 0
        total_months += dm
        sd = _parse_date(role.get("start_date"))
        if role.get("end_date"):
            ed = _parse_date(role.get("end_date"))
        elif role.get("is_current"):
            ed = TODAY
        else:
            ed = None
        if sd and ed and ed >= sd:
            actual = (ed.year - sd.year) * 12 + (ed.month - sd.month)
            if abs(actual - dm) > 4:
                return True

    # H6
    if total_months > 1.4 * career_len_months + 18:
        return True
    return False


def is_keyword_stuffer(record: dict) -> bool:
    """Non-technical title + ≥4 core-AI skills (weak backing)."""
    title = (record.get("profile", {}).get("current_title") or "").lower()
    if title not in NON_TECH_LOWER:
        return False
    ai_count = sum(
        1 for s in record.get("skills", [])
        if any(tok in (s.get("name") or "").lower() for tok in AI_SKILL_TOKENS)
    )
    return ai_count >= 4


# ═══════════════════════════════════════════════════════════════════════════
# Skill coherence (shared shape, scaled per mode)
# ═══════════════════════════════════════════════════════════════════════════

def skill_match_raw(record: dict) -> float:
    """0–80: must-have skill coverage weighted by proficiency / duration / endorsements."""
    best: dict[str, tuple[int, int, int]] = {}
    for sk in record.get("skills", []):
        name_lo = (sk.get("name") or "").lower()
        pw = PROF_WEIGHT.get(sk.get("proficiency") or "", 0)
        dm = sk.get("duration_months") or 0
        en = sk.get("endorsements") or 0
        for term_set in MUST_HAVE_SETS:
            for t in term_set:
                if t in name_lo:
                    cur = best.get(t)
                    if cur is None or (pw, dm, en) > cur:
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


def nice_to_have_score(record: dict, cap: float) -> float:
    names_lo = " ".join((s.get("name") or "").lower() for s in record.get("skills", []))
    hits = sum(1 for term_set in NICE_SETS if any(t in names_lo for t in term_set))
    return min(hits * (cap / len(NICE_SETS)), cap)


def yoe_fit_score(yoe: float, cap: float) -> float:
    if 5.0 <= yoe <= 9.0:
        frac = 1.0
    elif 4.0 <= yoe < 5.0 or 9.0 < yoe <= 10.0:
        frac = 0.75
    elif 3.0 <= yoe < 4.0 or 10.0 < yoe <= 11.0:
        frac = 0.5
    elif 2.0 <= yoe < 3.0 or 11.0 < yoe <= 13.0:
        frac = 0.25
    else:
        frac = 0.1
    return frac * cap


# ═══════════════════════════════════════════════════════════════════════════
# CHECKPOINT 2 — baseline scorer (title-tier)
# ═══════════════════════════════════════════════════════════════════════════

def _baseline_tier(title: str) -> int:
    if title in TITLE_TIER:
        return TITLE_TIER[title]
    lo = title.lower()
    if any(k in lo for k in ["recsys", "recommendation", "search engineer", "nlp engineer", "applied ml"]):
        return 5
    if any(k in lo for k in ["ml ", "machine learning", "ai engineer", "nlp", "applied ai"]):
        return 4
    if "data scientist" in lo or "data engineer" in lo:
        return 3
    if any(k in lo for k in ["software", "developer", "engineer", "data"]):
        return 2
    return 2


def score_candidate_baseline(record: dict) -> tuple[float, int, bool]:
    if detect_honeypot(record):
        return 0.0, 0, True
    profile = record.get("profile", {})
    title = profile.get("current_title") or ""
    yoe = float(profile.get("years_of_experience") or 0)
    if is_keyword_stuffer(record):
        return 2.0, 0, False
    tier = _baseline_tier(title)
    num = _cand_num(record.get("candidate_id", "CAND_0100000"))
    if tier == 0:
        return (100000 - num) * 1e-9, 0, False
    base = TIER_BASE[tier]
    sub = (skill_match_raw(record) + nice_to_have_score(record, 20)
           + yoe_fit_score(yoe, 20) + _baseline_career(record)) * _baseline_behavioral(record)
    return base + sub + (100000 - num) * 1e-6, tier, False


def _baseline_career(record: dict) -> float:
    career = record.get("career_history", [])
    sig = record.get("redrob_signals", {})
    score = 0.0
    if any(not _is_consulting(r.get("company") or "") for r in career):
        score += 20.0
    ai_roles = sum(1 for r in career if any(
        t in (r.get("title") or "").lower()
        for t in ["ml engineer", "machine learning", "ai engineer", "data scientist", "nlp",
                  "search engineer", "recommendation", "ranking", "recsys", "retrieval"]))
    score += 10.0 if ai_roles >= 2 else (5.0 if ai_roles == 1 else 0.0)
    for r in career:
        if r.get("is_current"):
            score += 10.0
            break
    assess = sig.get("skill_assessment_scores") or {}
    if assess:
        score += min(sum(assess.values()) / len(assess) / 10.0, 10.0)
    total_end = sum((s.get("endorsements") or 0) for s in record.get("skills", []))
    score += 10.0 if total_end > 50 else (6.0 if total_end > 20 else (3.0 if total_end > 5 else 0.0))
    return min(score, 60.0)


def _baseline_behavioral(record: dict) -> float:
    sig = record.get("redrob_signals", {})
    mult = 1.0
    rr = sig.get("recruiter_response_rate")
    if rr is not None:
        mult += -0.15 if rr < 0.15 else (0.05 if rr > 0.60 else 0.0)
    la = _parse_date(sig.get("last_active_date"))
    if la:
        days = (TODAY - la).days
        mult += -0.10 if days > 180 else (0.05 if days < 60 else 0.0)
    if sig.get("open_to_work_flag"):
        mult += 0.05
    return max(0.70, min(1.15, mult))


# ═══════════════════════════════════════════════════════════════════════════
# CHECKPOINT 3 — evidence-first scorer
# ═══════════════════════════════════════════════════════════════════════════

def title_prior(title: str) -> int:
    if title in TITLE_PRIOR:
        return TITLE_PRIOR[title]
    lo = title.lower()
    if any(k in lo for k in ["recommendation", "recsys", "search engineer", "nlp engineer", "applied ml"]):
        return 180
    if any(k in lo for k in ["ml engineer", "machine learning", "ai engineer", "data scientist"]):
        return 140
    if "data engineer" in lo or "backend" in lo or "analytics engineer" in lo:
        return 90
    if any(k in lo for k in ["software", "developer", "engineer"]):
        return 50
    return 0


def integrity_penalties(record: dict, ev_score: float, ev_dims: dict, skill_match: float) -> tuple[float, float, list[str]]:
    """
    Returns (subtractive_penalty, hard_multiplier, flags).
    Subtractive penalties are bounded; hard_multiplier ∈ {1.0, 0.3} for disqualifier-grade demotions.
    Missing behavioral coverage is NEVER punished here.
    """
    profile = record.get("profile", {})
    title = profile.get("current_title") or ""
    skills = record.get("skills", [])
    career = record.get("career_history", [])
    flags: list[str] = []
    penalty = 0.0
    hard = 1.0

    # (a) Skills unsupported by career history: strong AI skill claims, no career evidence.
    if skill_match > 45 and ev_score < 50:
        unsup = min(80.0, (skill_match - 45) * 2.0)
        penalty += unsup
        flags.append("skills-not-backed-by-career")

    # (b) Expert claims with little/no duration (H1 already zeros dur==0).
    low_dur_expert = sum(
        1 for s in skills
        if s.get("proficiency") == "expert" and 0 < (s.get("duration_months") or 0) < 6
    )
    if low_dur_expert:
        penalty += min(60.0, low_dur_expert * 15.0)
        flags.append("expert-low-duration")

    # (c) Title-chaser: many short stints. JD targets the Senior→Staff→Principal
    #     hopper, so require ≥4 roles AND avg tenure < 16 mo (clearly hoppy, below
    #     the 1.5-yr line) — a lateral IC at ~18 mo/role is NOT a title-chaser.
    if len(career) >= 4:
        durs = [r.get("duration_months") or 0 for r in career]
        if durs and sum(durs) / len(durs) < 16:
            penalty += 60.0
            flags.append("title-chaser")

    # (d) Recent-LangChain-only / framework enthusiast: langchain skill, no ranking/eval evidence.
    has_langchain = any("langchain" in (s.get("name") or "").lower() for s in skills)
    if has_langchain and ev_dims["ranking"] == 0 and ev_dims["evaluation"] == 0:
        penalty += 50.0
        flags.append("langchain-only")

    # (e) No production code in last 18 months (JD: "this role writes code").
    if not any(r.get("is_current") for r in career):
        latest_end = None
        for r in career:
            ed = _parse_date(r.get("end_date"))
            if ed and (latest_end is None or ed > latest_end):
                latest_end = ed
        if latest_end is not None:
            months_ago = (TODAY.year - latest_end.year) * 12 + (TODAY.month - latest_end.month)
            if months_ago > 18:
                penalty += 50.0
                flags.append("no-prod-code-18mo")

    # (f) HARD: research-only / no production (JD: "we will not move forward").
    if career:
        all_research = all(
            any(tok in (r.get("company") or "").lower() for tok in RESEARCH_TOKENS) for r in career
        )
    else:
        all_research = False
    research_titleish = title == "AI Research Engineer"
    if (all_research or research_titleish) and ev_dims["shipping"] < 0.4 and ev_score < 120:
        hard = 0.3
        flags.append("research-only-no-prod")

    # (g) HARD: keyword stuffer (non-tech title + AI skills).
    if is_keyword_stuffer(record):
        hard = min(hard, 0.3)
        flags.append("keyword-stuffer")

    return penalty, hard, flags


def behavioral_term(record: dict) -> float:
    """
    Capped availability/credibility adjustment, additive in [-40, +40].
    Missing signals (github -1, empty assessments, null rates) are treated as
    NEUTRAL (0 contribution) — never punished. Bounded far below the evidence
    spread so it reorders near-ties but never overturns an evidence gap.
    """
    sig = record.get("redrob_signals", {})
    t = 0.0

    rr = sig.get("recruiter_response_rate")
    if rr is not None:
        t += 12.0 if rr > 0.60 else (-15.0 if rr < 0.15 else 0.0)

    la = _parse_date(sig.get("last_active_date"))
    if la is not None:
        days = (TODAY - la).days
        t += 10.0 if days < 60 else (-12.0 if days > 180 else 0.0)

    icr = sig.get("interview_completion_rate")
    if icr is not None:
        t += 6.0 if icr > 0.70 else (-10.0 if icr < 0.30 else 0.0)

    if sig.get("open_to_work_flag"):
        t += 8.0

    npd = sig.get("notice_period_days")
    if npd is not None:
        t += 8.0 if npd <= 30 else (-6.0 if npd > 90 else 0.0)

    gh = sig.get("github_activity_score")
    if gh is not None and gh > 0:          # -1 / missing → neutral
        t += 6.0

    if sig.get("skill_assessment_scores"):  # empty → neutral
        t += 6.0

    if sig.get("verified_email") and sig.get("verified_phone"):
        t += 4.0

    return max(-40.0, min(40.0, t))


def score_candidate_final(record: dict) -> tuple[float, dict]:
    """
    Returns (final_pre, info). Honeypots → -1e9 (forced bottom).
    info carries components for reasoning + reporting.
    """
    if detect_honeypot(record):
        return -1e9, {"honeypot": True, "ev_score": 0.0, "ev_dims": {}, "flags": ["honeypot"]}

    profile = record.get("profile", {})
    title = profile.get("current_title") or ""
    yoe = float(profile.get("years_of_experience") or 0)

    ev_score, ev_dims = career_evidence(record)
    tp = title_prior(title)
    sm_raw = skill_match_raw(record)                       # 0-80
    skill_coherence = sm_raw * 2.0                          # 0-160
    assess = record.get("redrob_signals", {}).get("skill_assessment_scores") or {}
    if assess:
        skill_coherence += min(40.0, sum(assess.values()) / len(assess) / 2.5)   # 0-40 backing
    skill_coherence = min(skill_coherence, 200.0)
    yf = yoe_fit_score(yoe, 60.0)
    nice = nice_to_have_score(record, 40.0)

    penalty, hard, flags = integrity_penalties(record, ev_score, ev_dims, sm_raw)

    merit = 3.0 * ev_score + tp + skill_coherence + yf + nice - penalty
    core = merit * hard
    bt = behavioral_term(record)
    final_pre = core + bt

    info = {
        "honeypot": False, "ev_score": ev_score, "ev_dims": ev_dims,
        "title_prior": tp, "skill_coherence": skill_coherence, "yoe_fit": yf,
        "nice": nice, "penalty": penalty, "hard": hard, "behavioral": bt,
        "merit": merit, "flags": flags, "tier_base": _baseline_tier(title),
    }
    return final_pre, info


# ── Reasoning (evidence-grounded, varied) ────────────────────────────────────

_EVIDENCE_REASON = {
    "ranking": "shipped ranking/recsys models",
    "retrieval": "production embeddings/retrieval",
    "vector": "vector/hybrid search infra",
    "evaluation": "ranking evaluation (NDCG/MAP/A-B)",
    "shipping": "production ownership at scale",
}


def evidence_reasons(ev_dims: dict, k: int = 3) -> list[str]:
    present = [(_EVIDENCE_REASON[d], ev_dims.get(d, 0.0)) for d in
               ("ranking", "retrieval", "vector", "evaluation", "shipping")]
    present = [(label, v) for label, v in present if v >= 0.5]
    present.sort(key=lambda x: -x[1])
    return [label for label, _ in present[:k]]


def build_reasoning_final(record: dict, info: dict) -> str:
    profile = record.get("profile", {})
    title = profile.get("current_title") or "Unknown"
    yoe = profile.get("years_of_experience") or 0
    career = record.get("career_history", [])
    sig = record.get("redrob_signals", {})

    company = next((r.get("company", "") for r in career if r.get("is_current")),
                   career[0].get("company", "") if career else "")

    reasons = evidence_reasons(info["ev_dims"])
    s1 = f"{title} ({yoe:.1f} yr)" + (f" at {company}" if company else "")
    if reasons:
        s1 += " - career shows " + ", ".join(reasons) + "."
    else:
        s1 += " - limited direct retrieval/ranking evidence in career history."

    bits: list[str] = []
    rr = sig.get("recruiter_response_rate")
    if rr is not None and rr > 0.60:
        bits.append(f"responsive ({rr:.0%})")
    elif rr is not None and rr < 0.15:
        bits.append(f"low responsiveness ({rr:.0%})")
    gh = sig.get("github_activity_score")
    if gh is not None and gh > 0:
        bits.append(f"GitHub {gh:.0f}")
    assess = sig.get("skill_assessment_scores") or {}
    if assess:
        bk = max(assess, key=assess.get)
        bits.append(f"assessed {bk} {assess[bk]:.0f}/100")
    if info["flags"]:
        clean = [f for f in info["flags"] if f != "honeypot"]
        if clean:
            bits.append("flags: " + ", ".join(clean))
    s2 = ("; ".join(bits) + ".") if bits else ""
    return (s1 + (" " + s2 if s2 else "")).strip()


# ═══════════════════════════════════════════════════════════════════════════
# Driver
# ═══════════════════════════════════════════════════════════════════════════

def _assign_distinct_scores(ordered: list[float]) -> list[float]:
    """Force strictly-decreasing, distinct floats while preserving the given order."""
    out: list[float] = []
    prev = None
    for raw in ordered:
        r = round(raw, 4)
        s = r if prev is None else min(r, prev - 1e-5)
        out.append(s)
        prev = s
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Redrob candidate ranker")
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--mode", choices=["final", "baseline"], default="final")
    args = ap.parse_args()

    candidates_path = Path(args.candidates)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tracemalloc.start()
    t0 = time.perf_counter()
    print(f"Mode: {args.mode}  |  Scoring {candidates_path} ({candidates_path.stat().st_size/1e6:.0f} MB)")

    heap: list[tuple[float, str]] = []
    payload: dict[str, dict] = {}   # cid → record
    info_by_cid: dict[str, dict] = {}
    n_total = 0
    n_honeypot = 0

    with open(candidates_path, "rb") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            record = orjson.loads(raw)
            n_total += 1
            cid = record["candidate_id"]

            if args.mode == "baseline":
                score, _tier, is_hp = score_candidate_baseline(record)
                info = None
            else:
                score, info = score_candidate_final(record)
                is_hp = info["honeypot"]
            if is_hp:
                n_honeypot += 1

            if len(heap) < 100:
                heapq.heappush(heap, (score, cid))
                payload[cid] = record
                if info is not None:
                    info_by_cid[cid] = info
            elif score > heap[0][0]:
                _, ev = heapq.heapreplace(heap, (score, cid))
                del payload[ev]
                info_by_cid.pop(ev, None)
                payload[cid] = record
                if info is not None:
                    info_by_cid[cid] = info

    t_score = time.perf_counter() - t0
    print(f"Scored {n_total:,} candidates in {t_score:.1f}s | honeypot flags in pool: {n_honeypot}")

    top = sorted(heap, key=lambda x: (-x[0], _cand_num(x[1])))   # score desc, cid asc
    top_records = [payload[cid] for _, cid in top]
    hp_in_top = sum(1 for r in top_records if detect_honeypot(r))
    hp_rate = hp_in_top / len(top)

    distinct_scores = _assign_distinct_scores([s for s, _ in top])

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["candidate_id", "rank", "score", "reasoning"])
        for rank, ((_, cid), score) in enumerate(zip(top, distinct_scores), 1):
            rec = payload[cid]
            if args.mode == "final":
                reasoning = build_reasoning_final(rec, info_by_cid[cid])
            else:
                prof = rec.get("profile", {})
                reasoning = f"{prof.get('current_title','?')} ({prof.get('years_of_experience',0):.1f} yr) baseline tier match."
            w.writerow([cid, rank, f"{score:.6f}", reasoning])

    t_total = time.perf_counter() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f"\n{'='*64}")
    print(f"Output: {output_path}  |  Runtime: {t_total:.2f}s  |  Peak mem: {peak/1e6:.1f} MB")
    print(f"Honeypot rate in top-100: {hp_in_top}/100 = {hp_rate:.1%}  "
          f"({'PASS' if hp_rate <= 0.10 else 'FAIL — DISQUALIFIED'})")
    print(f"Score spread: {distinct_scores[0]:.2f} (rank 1) -> {distinct_scores[-1]:.2f} (rank 100)")
    print('='*64)

    if args.mode == "final":
        print("\nTop-15 (evidence-first):")
        for rank, ((_, cid), score) in enumerate(zip(top[:15], distinct_scores[:15]), 1):
            rec = payload[cid]
            info = info_by_cid[cid]
            title = rec.get("profile", {}).get("current_title", "?")
            yoe = rec.get("profile", {}).get("years_of_experience", 0)
            reasons = evidence_reasons(info["ev_dims"]) or ["(no direct retrieval/ranking evidence)"]
            print(f"  {rank:>2}. {cid}  {score:>9.2f}  ev={info['ev_score']:>5.0f}  "
                  f"{title} ({yoe:.1f}y)")
            print(f"       -> {', '.join(reasons)}")

    print("\nRunning data/validate_submission.py ...")
    res = subprocess.run([sys.executable, "data/validate_submission.py", str(output_path)],
                         capture_output=True, text=True)
    print((res.stdout + res.stderr).strip() or "(no output)")
    ok = res.returncode == 0
    print(f"Validator: {'PASS' if ok else 'FAIL'}")
    return 0 if (ok and hp_rate <= 0.10) else 1


if __name__ == "__main__":
    sys.exit(main())
