"""
ProofRank — Senior AI Engineer Candidate Shortlist
Minimal offline Streamlit demo for Redrob AI submission.

Launch:  streamlit run app.py
Data:    demo/top100_data.json  (pre-extracted top-100; no network required)
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import streamlit as st

# ─── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="ProofRank — AI Engineer Shortlist",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Constants ────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent
DATA_PATH = ROOT / "demo" / "top100_data.json"

JD_DIMS = [
    ("Production retrieval",       "retrieval",  "embeddings / semantic search / dense retrieval"),
    ("Vector / hybrid search",     "vector",     "FAISS · Pinecone · BM25 · Qdrant · OpenSearch"),
    ("Ranking / recsys shipped",   "ranking",    "LTR · XGBoost · collaborative filtering · recsys"),
    ("Eval framework",             "evaluation", "NDCG · MAP · A/B · offline-online correlation"),
]

PROF_EMOJI = {"expert": "🟢", "advanced": "🔵", "intermediate": "🟡", "beginner": "🔴"}

# ─── Data loading (cached) ────────────────────────────────────────────────────

@st.cache_data
def load_candidates() -> list[dict]:
    if not DATA_PATH.exists():
        st.error(f"Demo data not found: {DATA_PATH}\n"
                 f"Run  `python demo/extract_top100.py`  first.")
        st.stop()
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


candidates = load_candidates()

# ─── Helpers ──────────────────────────────────────────────────────────────────

def ev_bar(ev_score: float) -> str:
    pct = int(ev_score / 5)          # 0-100
    filled = pct // 5
    empty = 20 - filled
    return f"{'█' * filled}{'░' * empty}  {ev_score:.0f}/500"


def dim_badge(present: bool, label: str) -> str:
    icon = "✅" if present else "❌"
    return f"{icon} {label}"


def why_selected(row: dict) -> str:
    dims = row["ev_dims"]
    parts = []
    if dims.get("ranking", 0) >= 0.5:
        parts.append("shipped ranking / recsys system")
    if dims.get("retrieval", 0) >= 0.5:
        parts.append("production embeddings & retrieval")
    if dims.get("vector", 0) >= 0.5:
        parts.append("vector / hybrid search infra")
    if dims.get("evaluation", 0) >= 0.5:
        parts.append("NDCG / MAP / A-B evaluation")
    if dims.get("shipping", 0) >= 0.5:
        parts.append("confirmed production scale")
    if not parts:
        return "Structural signals (title, YoE, skills) with limited career evidence."
    return "Career demonstrates: " + " · ".join(parts) + "."


def why_not_higher(row: dict) -> str:
    dims = row["ev_dims"]
    ev = row["ev_score"]
    yoe = row["profile"].get("years_of_experience", 0)
    flags = row.get("flags", [])
    bt = row.get("behavioral", 0.0)
    tp = row.get("title_prior", 0)

    reasons: list[str] = []

    # evidence gaps (most important first per JD)
    if dims.get("ranking", 0) < 0.5:
        reasons.append("no shipped ranking/recsys system in career descriptions")
    if dims.get("evaluation", 0) < 0.5:
        reasons.append("no explicit NDCG/MAP/A-B evaluation evidence")
    if dims.get("retrieval", 0) < 0.5:
        reasons.append("no production embeddings/retrieval evidence")
    if dims.get("vector", 0) < 0.5:
        reasons.append("no vector DB / hybrid search evidence")

    # YoE band
    if yoe < 5:
        reasons.append(f"YoE {yoe:.1f} below ideal 5-9 band")
    elif yoe > 10:
        reasons.append(f"YoE {yoe:.1f} above ideal 5-9 band")

    # evidence saturation
    if ev < 490 and not reasons:
        reasons.append(f"evidence score {ev:.0f}/500 — not all dims saturated")

    # integrity flags
    if flags:
        clean = [f for f in flags if f != "honeypot"]
        if clean:
            reasons.append("integrity flags: " + ", ".join(clean))

    # availability
    if bt < -10:
        reasons.append("low availability / responsiveness signals")

    # title prior
    if tp < 160:
        reasons.append(f"non-canonical title lowers title prior ({tp}/200)")

    return reasons[0] if reasons else "Within top cluster; ordering is JD-priority tiebreak then behavioral."


def signal_row(label: str, val, fmt: str = "") -> str:
    if val is None or val == -1:
        return f"**{label}:** —"
    if fmt == "pct":
        return f"**{label}:** {val:.0%}"
    if fmt == "int":
        return f"**{label}:** {int(val)}"
    return f"**{label}:** {val}"


def make_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["rank", "candidate_id", "title", "yoe", "company",
                "score", "ev_score", "ranking_dim", "retrieval_dim",
                "vector_dim", "eval_dim", "shipping_dim",
                "flags", "why_selected", "why_not_higher"])
    for r in rows:
        prof = r["profile"]
        dims = r["ev_dims"]
        career = r.get("career_history", [])
        company = next((c["company"] for c in career if c.get("is_current")),
                       career[0]["company"] if career else "")
        w.writerow([
            r["rank"], r["candidate_id"],
            prof.get("current_title", ""), prof.get("years_of_experience", ""),
            company, f"{r['score']:.4f}", f"{r['ev_score']:.0f}",
            f"{dims.get('ranking', 0):.2f}", f"{dims.get('retrieval', 0):.2f}",
            f"{dims.get('vector', 0):.2f}", f"{dims.get('evaluation', 0):.2f}",
            f"{dims.get('shipping', 0):.2f}",
            "|".join(r.get("flags", [])),
            why_selected(r), why_not_higher(r),
        ])
    return buf.getvalue()


# ─── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🏆 ProofRank")
    st.caption("Evidence-based candidate ranking · Redrob AI")
    st.divider()

    rank_band = st.radio(
        "Show rank band",
        options=["All (1–100)", "Top 10", "Top 11–50", "Top 51–100"],
        index=0,
    )

    min_ev = st.slider("Min evidence score", 0, 500, 0, step=50)

    show_flagged_only = st.toggle("Show flagged candidates only", value=False)

    st.divider()

    # Filter candidates
    filtered: list[dict] = []
    for c in candidates:
        r = c["rank"]
        if rank_band == "Top 10" and r > 10:
            continue
        if rank_band == "Top 11–50" and not (11 <= r <= 50):
            continue
        if rank_band == "Top 51–100" and r < 51:
            continue
        if c["ev_score"] < min_ev:
            continue
        if show_flagged_only and not c.get("flags"):
            continue
        filtered.append(c)

    st.metric("Candidates shown", len(filtered), delta=f"of {len(candidates)} total")

    if filtered:
        csv_data = make_csv(filtered)
        st.download_button(
            label="⬇ Download CSV",
            data=csv_data,
            file_name="proofrank_shortlist.csv",
            mime="text/csv",
        )

    st.divider()
    st.caption(
        "**Scoring formula (final mode)**\n\n"
        "score = 3×evidence(0-500) + title_prior(0-200) "
        "+ skill_coherence(0-200) + yoe_fit(0-60) + nice(0-40) "
        "− penalties\n\n"
        "× hard_demote · + jd_tiebreak(0-60) + behavioral(±40)\n\n"
        "Honeypots → forced bottom. Missing behavioral signals = neutral."
    )

# ─── Main header ──────────────────────────────────────────────────────────────

st.title("Senior AI Engineer — Candidate Shortlist")
st.markdown(
    "**Redrob AI** · Founding team hire · Evidence-based ranking over 100,000 candidates  \n"
    "Ranked by career evidence of production retrieval, ranking, evaluation, and shipping — "
    "not by listed skills or title alone."
)
st.divider()

if not filtered:
    st.info("No candidates match the current filters.")
    st.stop()

# ─── Candidate cards ──────────────────────────────────────────────────────────

for row in filtered:
    prof = row["profile"]
    title = prof.get("current_title", "Unknown")
    yoe = prof.get("years_of_experience", 0)
    career = row.get("career_history", [])
    company = next((c["company"] for c in career if c.get("is_current")),
                   career[0]["company"] if career else "—")
    dims = row["ev_dims"]
    flags = row.get("flags", [])
    ev = row["ev_score"]
    rank = row["rank"]
    score = row["score"]

    # header label for expander
    flag_tag = " ⚠️" if flags else ""
    header = (
        f"#{rank:>3}  ·  {row['candidate_id']}  ·  {title}  ·  "
        f"{yoe:.1f}y  ·  {company}  ·  score {score:.1f}{flag_tag}"
    )

    with st.expander(header, expanded=(rank <= 5)):

        # ── Top row: score + ev bar ──────────────────────────────────────────
        col_score, col_ev = st.columns([1, 3])
        with col_score:
            st.metric("Fit score", f"{score:.1f}")
            st.metric("Evidence", f"{ev:.0f} / 500")
        with col_ev:
            st.markdown("**Evidence coverage**")
            st.code(ev_bar(ev), language=None)
            pct = min(int(ev / 5), 100)
            st.progress(pct)

        st.divider()

        # ── JD requirements grid ─────────────────────────────────────────────
        st.markdown("**JD must-haves**")
        cols = st.columns(4)
        for (label, dim_key, detail), col in zip(JD_DIMS, cols):
            present = dims.get(dim_key, 0) >= 0.5
            col.markdown(dim_badge(present, label))
            col.caption(detail)

        # shipping as a 5th indicator (production scale)
        ship_val = dims.get("shipping", 0)
        ship_present = ship_val >= 0.5
        st.markdown(
            f"{'✅' if ship_present else '❌'} **Production scale** — "
            f"confirmed impact at scale (score {ship_val:.2f}/1.0)"
        )

        st.divider()

        # ── Career evidence snippets ─────────────────────────────────────────
        st.markdown("**Career evidence snippets**")
        ev_roles = [r for r in career if r.get("description", "").strip()]
        if ev_roles:
            for role in ev_roles:
                desc = role.get("description", "").strip()
                if not desc:
                    continue
                end_str = ("present" if role.get("is_current")
                           else (role.get("end_date") or ""))
                duration = f"{role.get('duration_months', 0)}mo"
                role_header = (
                    f"**{role['title']}** @ {role['company']} "
                    f"({role.get('start_date','?')} → {end_str}, {duration})"
                )
                st.markdown(role_header)
                st.markdown(f"> {desc[:320]}{'…' if len(desc) > 320 else ''}")
        else:
            st.caption("No career descriptions available in this record.")

        st.divider()

        # ── Score breakdown + why ────────────────────────────────────────────
        col_why, col_scores, col_signals = st.columns([2, 1, 1])

        with col_why:
            st.markdown("**Why selected**")
            st.success(why_selected(row))
            st.markdown("**Why not higher**")
            st.info(why_not_higher(row))
            if flags:
                st.warning("**Integrity flags:** " + ", ".join(flags))

        with col_scores:
            st.markdown("**Score breakdown**")
            breakdown = {
                "Evidence (×3)": f"{3 * ev:.0f}",
                "Title prior": f"{row.get('title_prior', 0):.0f} / 200",
                "Skill coh.": f"{row.get('skill_coherence', 0):.0f} / 200",
                "YoE fit": f"{row.get('yoe_fit', 0):.0f} / 60",
                "Nice-to-have": f"{row.get('nice', 0):.0f} / 40",
                "Penalties": f"−{row.get('penalty', 0):.0f}",
                "JD tiebreak": f"+{row.get('tiebreak', 0):.0f} / 60",
                "Behavioral": f"{row.get('behavioral', 0):+.0f} / ±40",
            }
            for k, v in breakdown.items():
                st.markdown(f"**{k}:** {v}")

        with col_signals:
            st.markdown("**Behavioral signals**")
            sig = row.get("redrob_signals", {})
            rr = sig.get("recruiter_response_rate")
            la = sig.get("last_active_date")
            gh = sig.get("github_activity_score")
            assess = sig.get("skill_assessment_scores") or {}
            npd = sig.get("notice_period_days")
            icr = sig.get("interview_completion_rate")

            if rr is not None:
                icon = "🟢" if rr > 0.60 else ("🔴" if rr < 0.15 else "🟡")
                st.markdown(f"{icon} Response rate: {rr:.0%}")
            if la:
                st.markdown(f"📅 Last active: {la}")
            if gh is not None and gh != -1:
                st.markdown(f"🐙 GitHub score: {gh:.0f}")
            else:
                st.markdown("🐙 GitHub: —")
            if assess:
                best_k = max(assess, key=assess.get)
                st.markdown(f"📋 Assessment: {best_k} {assess[best_k]:.0f}/100")
            else:
                st.markdown("📋 Assessment: —")
            if npd is not None:
                icon = "🟢" if npd <= 30 else ("🟡" if npd <= 90 else "🔴")
                st.markdown(f"{icon} Notice: {npd}d")
            if icr is not None:
                st.markdown(f"🤝 Interview completion: {icr:.0%}")
            if sig.get("open_to_work_flag"):
                st.markdown("✅ Open to work")

        # ── Top skills ───────────────────────────────────────────────────────
        skills = row.get("skills", [])
        if skills:
            st.divider()
            st.markdown("**Top skills**")
            skill_bits = []
            for s in skills[:10]:
                em = PROF_EMOJI.get(s.get("proficiency", ""), "⚪")
                dur = s.get("duration_months", 0)
                dur_str = f" ({dur}mo)" if dur else ""
                skill_bits.append(f"{em} {s['name']}{dur_str}")
            st.markdown("  ·  ".join(skill_bits))

# ─── Footer ───────────────────────────────────────────────────────────────────

st.divider()
st.caption(
    "ProofRank · Redrob AI Senior AI Engineer Challenge · "
    "Data: 100,000 candidates ranked offline on CPU in ~56s · "
    "No embeddings, no API calls, no network required · "
    "Evidence extracted via deterministic phrase-bank matching on 44 description archetypes"
)
