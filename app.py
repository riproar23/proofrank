"""
ProofRank — Candidate Shortlist (recruiter-friendly demo)
Minimal, fully-offline Streamlit demo for the Redrob AI submission.

Launch:  streamlit run app.py
Data:    demo/top100_data.json  (pre-baked top-100; no network, instant load)

This file is the DEMO ONLY. It does not score, rank, or recompute anything —
it reads the pre-baked output the ranker already produced and presents it in
plain language for a non-technical recruiter.
"""

from __future__ import annotations

import csv
import html
import io
import json
from pathlib import Path

import streamlit as st

# ─── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Candidate Shortlist — Senior AI Engineer",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT = Path(__file__).parent
DATA_PATH = ROOT / "demo" / "top100_data.json"

# Evidence dimension → plain-language "what they've actually done", in the order
# a recruiter cares about. Each maps to a key in row["ev_dims"] (0.0–1.0).
DONE_ITEMS = [
    ("ranking",    "Has shipped ranking & recommendation systems"),
    ("retrieval",  "Has built production search / retrieval systems"),
    ("vector",     "Has worked with vector / semantic search"),
    ("evaluation", "Knows how to measure search quality (A/B tests, metrics)"),
    ("shipping",   "Has shipped to real users at scale"),
]

# ─── Warm, premium CSS (offline; system font stack, no web fonts) ─────────────

CSS = """
<style>
:root{
  --bg:#FBF6EE; --card:#FFFDFA; --ink:#3B3531; --muted:#8C827A;
  --line:#ECE1D3; --accent:#DD7A5B; --accent-soft:#FBEBE2;
  --sage:#6E9E8E; --sage-soft:#E7F1ED; --amber:#C68A3A; --amber-soft:#FaF0DD;
  --shadow:0 6px 24px rgba(120,90,60,.10);
}
html, body, [data-testid="stAppViewContainer"], .stApp{
  background:var(--bg) !important;
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  color:var(--ink);
}
[data-testid="stHeader"]{ background:transparent; }
#MainMenu, footer{ visibility:hidden; }
.block-container{ padding-top:2.2rem; padding-bottom:3rem; max-width:1180px; }
[data-testid="stSidebar"]{ background:#F6EEE2; border-right:1px solid var(--line); }
[data-testid="stSidebar"] *{ color:var(--ink); }

/* hero */
.pr-hero h1{
  font-size:2.05rem; font-weight:740; letter-spacing:-.4px; margin:0 0 .35rem 0;
  color:var(--ink);
}
.pr-hero p{ font-size:1.06rem; line-height:1.6; color:var(--muted); margin:0; max-width:760px; }

/* cards (HTML <details>) */
details.pr-card{
  background:var(--card); border:1px solid var(--line); border-radius:16px;
  box-shadow:var(--shadow); padding:.35rem 1.25rem; margin:0 0 1rem 0;
  transition:box-shadow .2s ease, transform .2s ease;
}
details.pr-card[open]{ box-shadow:0 10px 34px rgba(120,90,60,.14); }
details.pr-card > summary{
  list-style:none; cursor:pointer; display:flex; align-items:center; gap:1rem;
  padding:.95rem .1rem; outline:none;
}
details.pr-card > summary::-webkit-details-marker{ display:none; }
details.pr-card > summary::after{
  content:"⌄"; margin-left:.35rem; color:var(--muted); font-size:1.4rem;
  line-height:1; transform:translateY(-2px); transition:transform .2s ease;
}
details.pr-card[open] > summary::after{ transform:rotate(180deg) translateY(0); }

.pr-rank{
  flex:0 0 auto; min-width:46px; height:46px; border-radius:12px;
  background:var(--accent-soft); color:var(--accent); font-weight:730;
  display:flex; align-items:center; justify-content:center; font-size:1.02rem;
}
.pr-sum-main{ flex:1 1 auto; min-width:0; display:flex; flex-direction:column; gap:.15rem; }
.pr-title{ font-size:1.16rem; font-weight:680; color:var(--ink); }
.pr-sub{ font-size:.97rem; color:var(--muted); }
.pr-sum-match{ flex:0 0 auto; text-align:right; display:flex; flex-direction:column; gap:.2rem; }
.pr-dots{ font-size:1.02rem; letter-spacing:2px; }
.pr-dots .on{ color:var(--accent); }
.pr-dots .off{ color:#E2D6C6; }
.pr-mlabel{ font-size:.9rem; font-weight:640; color:var(--ink); }
.pr-flag-pin{ flex:0 0 auto; font-size:1.15rem; }

/* body */
.pr-body{ padding:.25rem .15rem 1.1rem .15rem; }
.pr-facts{ display:flex; flex-wrap:wrap; gap:.5rem; margin:.2rem 0 1.1rem 0; }
.pr-chip{
  background:#F6EFE6; border:1px solid var(--line); border-radius:999px;
  padding:.32rem .8rem; font-size:.95rem; color:var(--ink);
}
.pr-chip.avail{ background:var(--sage-soft); border-color:#CFE6DD; color:#3F6F60; font-weight:600; }
.pr-sec-h{
  font-size:.82rem; font-weight:700; letter-spacing:.06em; text-transform:uppercase;
  color:var(--muted); margin:1.1rem 0 .55rem 0;
}
.pr-check{ display:flex; align-items:flex-start; gap:.6rem; padding:.32rem 0; font-size:1.02rem; }
.pr-check .ic{ font-size:1.05rem; line-height:1.5; }
.pr-check.no{ color:var(--muted); }

.pr-why{ border-radius:13px; padding:.85rem 1rem; margin:.55rem 0; line-height:1.55; font-size:1.01rem; }
.pr-why b{ display:block; font-size:.82rem; letter-spacing:.05em; text-transform:uppercase; margin-bottom:.25rem; }
.pr-why.good{ background:var(--sage-soft); }
.pr-why.good b{ color:#3F6F60; }
.pr-why.less{ background:#F6EFE6; }
.pr-why.less b{ color:var(--muted); }
.pr-flagbox{ background:var(--amber-soft); border-radius:13px; padding:.85rem 1rem; margin:.55rem 0; line-height:1.55; font-size:1.01rem; }
.pr-flagbox b{ display:block; font-size:.82rem; letter-spacing:.05em; text-transform:uppercase; color:var(--amber); margin-bottom:.25rem; }

.pr-role{ margin:.5rem 0; }
.pr-role .rh{ font-size:.99rem; font-weight:620; color:var(--ink); }
.pr-role .rd{ font-size:.96rem; color:var(--muted); line-height:1.55; margin-top:.15rem; }

/* technical details (nested) */
details.pr-tech{ margin-top:1rem; border-top:1px dashed var(--line); padding-top:.6rem; }
details.pr-tech > summary{
  list-style:none; cursor:pointer; font-size:.92rem; font-weight:620; color:var(--accent);
  padding:.3rem 0;
}
details.pr-tech > summary::-webkit-details-marker{ display:none; }
details.pr-tech > summary::before{ content:"🔍  "; }
.pr-tech-body{ font-size:.92rem; color:var(--ink); line-height:1.6; }
.pr-kv{ display:grid; grid-template-columns:max-content 1fr; gap:.2rem 1rem; margin:.4rem 0; }
.pr-kv .k{ color:var(--muted); }
.pr-tech-body code{ background:#F2EADF; padding:.05rem .35rem; border-radius:5px; font-size:.86rem; }
.pr-tech-h{ font-weight:700; margin:.7rem 0 .25rem 0; color:var(--ink); }

/* CSV download button — warm accent, readable */
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button{
  background:var(--accent); color:#fff; border:none; border-radius:11px;
  font-weight:650; padding:.55rem 1rem; box-shadow:0 4px 14px rgba(221,122,91,.30);
}
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button:hover{
  background:#C96846; color:#fff;
}
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button p{ color:#fff; font-weight:650; }
/* toggles & radios in the accent colour */
[data-testid="stSidebar"] [data-baseweb="radio"] svg{ fill:var(--accent); }
.stCheckbox [data-baseweb="checkbox"] [aria-checked="true"]{ background:var(--sage) !important; }
</style>
"""

# ─── Data loading ─────────────────────────────────────────────────────────────

@st.cache_data
def load_candidates() -> list[dict]:
    if not DATA_PATH.exists():
        st.error(
            f"Demo data not found: {DATA_PATH}\n\n"
            f"Run  `python demo/extract_top100.py`  once to create it."
        )
        st.stop()
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


candidates = load_candidates()

# ─── Plain-language helpers ───────────────────────────────────────────────────

# 5 friendly match levels derived from rank band (filled dots out of 5).
def match_level(rank: int) -> tuple[str, int]:
    if rank <= 10:
        return "Excellent match", 5
    if rank <= 30:
        return "Strong match", 4
    if rank <= 60:
        return "Good match", 3
    if rank <= 85:
        return "Fair match", 2
    return "Possible match", 1


def dots_html(filled: int) -> str:
    return "".join(
        f'<span class="on">●</span>' if i < filled else f'<span class="off">○</span>'
        for i in range(5)
    )


def current_company(row: dict) -> str:
    career = row.get("career_history", [])
    cur = next((c.get("company") for c in career if c.get("is_current")), None)
    if cur:
        return cur
    return career[0]["company"] if career else "—"


def availability_text(row: dict) -> str | None:
    sig = row.get("redrob_signals", {}) or {}
    if sig.get("open_to_work_flag"):
        return "Open to new roles"
    npd = sig.get("notice_period_days")
    if isinstance(npd, (int, float)) and npd >= 0 and npd <= 30:
        return "Could start soon"
    rr = sig.get("recruiter_response_rate")
    if isinstance(rr, (int, float)) and rr > 0.6:
        return "Usually replies to recruiters"
    if sig.get("last_active_date"):
        return "Recently active"
    return None


def has(row: dict, dim: str) -> bool:
    return float(row.get("ev_dims", {}).get(dim, 0)) >= 0.5


def why_person_plain(row: dict) -> str:
    strengths = []
    if has(row, "ranking"):
        strengths.append("built the ranking and recommendation systems this role is about")
    if has(row, "retrieval"):
        strengths.append("shipped real search and retrieval features")
    if has(row, "vector"):
        strengths.append("worked hands-on with vector / semantic search")
    if has(row, "evaluation"):
        strengths.append("measured search quality properly with A/B tests and metrics")
    if has(row, "shipping"):
        strengths.append("delivered to real users at scale")
    if not strengths:
        return ("Their title and experience fit the role, though their work history "
                "shows fewer concrete examples than the people ranked above.")
    if len(strengths) == 1:
        body = strengths[0]
    else:
        body = ", ".join(strengths[:-1]) + ", and " + strengths[-1]
    return f"Their actual work history shows they have {body}."


def why_not_higher_plain(row: dict) -> str:
    rank = row["rank"]
    yoe = float(row.get("profile", {}).get("years_of_experience", 0) or 0)
    flags = [f for f in row.get("flags", []) if f != "honeypot"]

    if not has(row, "ranking"):
        return ("Their history doesn't yet show a shipped ranking or recommendation "
                "system — the single most important thing for this role.")
    if not has(row, "evaluation"):
        return ("We couldn't find clear examples of measuring search quality "
                "(like A/B testing or relevance metrics) in their history.")
    if not has(row, "retrieval"):
        return "We didn't see clear production search / retrieval work in their history."
    if not has(row, "vector"):
        return "We didn't see clear vector or semantic-search experience yet."
    if yoe < 5:
        return f"Their {yoe:.0f} years of experience sits just below the ideal range for this role."
    if yoe > 10:
        return f"Their {yoe:.0f} years of experience sits a little above the ideal range for this role."
    if flags:
        return "A few profile details would need a quick verification before reaching out."
    if rank == 1:
        return "Nothing — this is the strongest profile in the shortlist."
    return ("They're already among the very best. The ordering at this level comes down "
            "to fine details like how recently they coded and the scale they shipped at.")


def flag_text(row: dict) -> str | None:
    if row.get("flags"):
        return ("Some details in this profile look inconsistent and would be worth "
                "verifying before you reach out.")
    return None


def career_html(row: dict) -> str:
    career = row.get("career_history", [])
    roles = [r for r in career if (r.get("description") or "").strip()]
    # current first, then keep order
    roles.sort(key=lambda r: (not r.get("is_current"),))
    if not roles:
        return ""
    out = ['<div class="pr-sec-h">Recent work</div>']
    for r in roles[:2]:
        end = "present" if r.get("is_current") else (r.get("end_date") or "")
        head = f"{r.get('title','')} · {r.get('company','')} ({r.get('start_date','?')} – {end})"
        desc = (r.get("description") or "").strip()
        desc = desc[:200] + ("…" if len(desc) > 200 else "")
        out.append(
            f'<div class="pr-role"><div class="rh">{html.escape(head)}</div>'
            f'<div class="rd">{html.escape(desc)}</div></div>'
        )
    return "".join(out)


def tech_html(row: dict) -> str:
    d = row.get("ev_dims", {})
    sig = row.get("redrob_signals", {}) or {}

    def sig_val(key, fmt="raw"):
        v = sig.get(key)
        if v is None or v == -1:
            return "—"
        if fmt == "pct":
            return f"{v:.0%}"
        if fmt == "int":
            return f"{int(v)}"
        return str(v)

    assess = sig.get("skill_assessment_scores") or {}
    assess_str = (", ".join(f"{k} {int(v)}/100" for k, v in assess.items())
                  if assess else "—")

    skills = row.get("skills", [])
    skill_str = (", ".join(
        f"{html.escape(s.get('name',''))} ({s.get('proficiency','?')}, {s.get('duration_months',0)}mo)"
        for s in skills[:8]) if skills else "—")

    breakdown = [
        ("Evidence × 3", f"{3 * row.get('ev_score', 0):.0f}"),
        ("Title prior", f"{row.get('title_prior', 0):.0f} / 200"),
        ("Skill coherence", f"{row.get('skill_coherence', 0):.0f} / 200"),
        ("Years-of-experience fit", f"{row.get('yoe_fit', 0):.0f} / 60"),
        ("Nice-to-have", f"{row.get('nice', 0):.0f} / 40"),
        ("Integrity penalties", f"−{row.get('penalty', 0):.0f}"),
        ("JD-aligned tiebreak", f"+{row.get('tiebreak', 0):.0f} / 60"),
        ("Behavioral modifier", f"{row.get('behavioral', 0):+.0f} / ±40"),
    ]

    parts = ['<div class="pr-tech-body">']
    parts.append('<div class="pr-tech-h">Raw fit score</div>')
    parts.append(
        f'<div class="pr-kv"><span class="k">Final score</span><span><code>{row.get("score",0):.2f}</code></span>'
        f'<span class="k">Evidence score</span><span><code>{row.get("ev_score",0):.0f} / 500</code></span></div>'
    )
    parts.append('<div class="pr-tech-h">Evidence dimensions (0–1)</div>')
    parts.append('<div class="pr-kv">' + "".join(
        f'<span class="k">{k}</span><span><code>{float(d.get(k,0)):.2f}</code></span>'
        for k in ["retrieval", "vector", "ranking", "evaluation", "shipping"]
    ) + '</div>')
    parts.append('<div class="pr-tech-h">Score breakdown</div>')
    parts.append('<div class="pr-kv">' + "".join(
        f'<span class="k">{html.escape(k)}</span><span><code>{v}</code></span>'
        for k, v in breakdown
    ) + '</div>')
    parts.append('<div class="pr-tech-h">Behavioral signals (raw)</div>')
    parts.append('<div class="pr-kv">'
        f'<span class="k">Recruiter response rate</span><span>{sig_val("recruiter_response_rate","pct")}</span>'
        f'<span class="k">Last active</span><span>{html.escape(str(sig.get("last_active_date") or "—"))}</span>'
        f'<span class="k">GitHub activity</span><span>{sig_val("github_activity_score","int")}</span>'
        f'<span class="k">Notice period</span><span>{sig_val("notice_period_days","int")} days</span>'
        f'<span class="k">Interview completion</span><span>{sig_val("interview_completion_rate","pct")}</span>'
        f'<span class="k">Skill assessments</span><span>{html.escape(assess_str)}</span>'
        '</div>')
    parts.append('<div class="pr-tech-h">Top skills (with durations)</div>')
    parts.append(f'<div class="pr-kv"><span>{skill_str}</span></div>')
    parts.append('</div>')
    return "".join(parts)


def candidate_card(row: dict, open_default: bool) -> str:
    rank = row["rank"]
    prof = row.get("profile", {})
    title = html.escape(prof.get("current_title", "Candidate"))
    yoe = float(prof.get("years_of_experience", 0) or 0)
    company = html.escape(current_company(row))
    label, filled = match_level(rank)
    flagged = bool(row.get("flags"))

    # summary header
    flag_pin = '<span class="pr-flag-pin" title="Needs verifying">⚠️</span>' if flagged else ""
    summary = (
        f'<summary>'
        f'<span class="pr-rank">#{rank}</span>'
        f'<span class="pr-sum-main"><span class="pr-title">{title}</span>'
        f'<span class="pr-sub">{yoe:.0f} yrs experience · {company}</span></span>'
        f'<span class="pr-sum-match"><span class="pr-dots">{dots_html(filled)}</span>'
        f'<span class="pr-mlabel">{label}</span></span>'
        f'{flag_pin}'
        f'</summary>'
    )

    # facts chips
    chips = [f'<span class="pr-chip">💼 {title}</span>',
             f'<span class="pr-chip">🗓 {yoe:.0f} years</span>',
             f'<span class="pr-chip">🏢 {company}</span>']
    avail = availability_text(row)
    if avail:
        chips.append(f'<span class="pr-chip avail">🟢 {avail}</span>')
    facts = '<div class="pr-facts">' + "".join(chips) + '</div>'

    # "what they've actually done" checklist
    checks = ['<div class="pr-sec-h">What they\'ve actually done</div>']
    for dim, text in DONE_ITEMS:
        if has(row, dim):
            checks.append(f'<div class="pr-check"><span class="ic">✅</span>'
                          f'<span>{html.escape(text)}</span></div>')
        else:
            checks.append(f'<div class="pr-check no"><span class="ic">➖</span>'
                          f'<span>{html.escape(text)}</span></div>')
    checks_html = "".join(checks)

    why_good = (f'<div class="pr-why good"><b>Why this person</b>'
                f'{html.escape(why_person_plain(row))}</div>')
    why_less = (f'<div class="pr-why less"><b>Why not ranked higher</b>'
                f'{html.escape(why_not_higher_plain(row))}</div>')

    ftext = flag_text(row)
    flag_box = (f'<div class="pr-flagbox"><b>⚠️ Worth verifying</b>{html.escape(ftext)}</div>'
                if ftext else "")

    tech = (f'<details class="pr-tech"><summary>See the details</summary>'
            f'{tech_html(row)}</details>')

    open_attr = " open" if open_default else ""
    return (
        f'<details class="pr-card"{open_attr}>'
        f'{summary}'
        f'<div class="pr-body">'
        f'{facts}{checks_html}{why_good}{why_less}{flag_box}'
        f'{career_html(row)}{tech}'
        f'</div></details>'
    )


def make_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["rank", "match", "candidate_id", "title", "years_experience",
                "current_company", "built_ranking", "built_retrieval",
                "vector_search", "measures_quality", "shipped_at_scale",
                "needs_verifying", "why_this_person", "why_not_higher",
                "raw_score", "evidence_score"])
    for r in rows:
        prof = r.get("profile", {})
        label, _ = match_level(r["rank"])
        w.writerow([
            r["rank"], label, r["candidate_id"],
            prof.get("current_title", ""), f'{float(prof.get("years_of_experience",0) or 0):.0f}',
            current_company(r),
            "yes" if has(r, "ranking") else "no",
            "yes" if has(r, "retrieval") else "no",
            "yes" if has(r, "vector") else "no",
            "yes" if has(r, "evaluation") else "no",
            "yes" if has(r, "shipping") else "no",
            "yes" if r.get("flags") else "no",
            why_person_plain(r), why_not_higher_plain(r),
            f'{r.get("score",0):.2f}', f'{r.get("ev_score",0):.0f}',
        ])
    return buf.getvalue()


# ─── Render ───────────────────────────────────────────────────────────────────

st.markdown(CSS, unsafe_allow_html=True)

# Sidebar — plain-language controls
with st.sidebar:
    st.markdown("### 🌿 ProofRank")
    st.caption("Candidate shortlist for Redrob AI")
    st.divider()

    show = st.radio("Show", ["All", "Top 10", "Top 50"], index=0)
    strong_only = st.toggle("Only show strong matches", value=False,
                            help="Strong or Excellent matches (top 30).")
    flagged_only = st.toggle("Flagged profiles only", value=False,
                             help="Profiles with details worth verifying.")
    st.divider()

    # apply filters
    filtered: list[dict] = []
    for c in candidates:
        r = c["rank"]
        if show == "Top 10" and r > 10:
            continue
        if show == "Top 50" and r > 50:
            continue
        if strong_only and r > 30:
            continue
        if flagged_only and not c.get("flags"):
            continue
        filtered.append(c)

    st.markdown(f"**Showing {len(filtered)} of {len(candidates)} candidates**")

    if filtered:
        st.download_button(
            "⬇  Download shortlist (CSV)",
            data=make_csv(filtered),
            file_name="candidate_shortlist.csv",
            mime="text/csv",
            use_container_width=True,
        )

# Hero
st.markdown(
    '<div class="pr-hero">'
    '<h1>Candidate Shortlist — Senior AI Engineer</h1>'
    '<p>The 100 strongest candidates for Redrob AI\'s founding-team role, ranked by what '
    'their real work history shows — not by buzzwords on a profile. Open any card to see, '
    'in plain language, what each person has actually built and why they sit where they do.</p>'
    '</div>',
    unsafe_allow_html=True,
)

with st.expander("ℹ️  How this works"):
    st.markdown(
        "We read every candidate's real career history and look for **evidence of the work "
        "this role needs**: building search and retrieval systems, shipping ranking and "
        "recommendation models, and measuring their quality properly.\n\n"
        "People are ranked by what they've **actually done**, not by the keywords or job "
        "titles they list. Profiles whose details look inconsistent or too good to be true "
        "are automatically **flagged for verification** and kept out of the top results.\n\n"
        "Each card leads with a plain-language verdict. The raw scores and technical "
        "breakdown are tucked away under **“See the details”** if you want them."
    )

st.write("")

if not filtered:
    st.info("No candidates match the current filters. Try turning a filter off.")
    st.stop()

# Candidate cards (top-5 open by default)
for row in filtered:
    st.markdown(candidate_card(row, open_default=row["rank"] <= 5),
                unsafe_allow_html=True)

st.write("")
st.caption(
    "ProofRank · Redrob AI Senior AI Engineer challenge · 100,000 candidates ranked "
    "offline on CPU in ~56s · no embeddings, no API calls, no network required."
)
