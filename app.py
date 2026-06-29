"""
ProofRank — Candidate Shortlist (recruiter-friendly demo)
Fully-offline Streamlit demo for the Redrob AI submission.

Launch:  streamlit run app.py
Data:    demo/top100_data.json  (pre-baked top-100; instant load, no network)

Optional (takes ~1 min):
  Click "Re-rank current dataset" in the sidebar to re-analyze data/candidates.jsonl
  or upload a new dataset directly from the UI.
"""

from __future__ import annotations

import csv
import datetime
import gzip
import html
import io
import json
import re
import subprocess
import sys
import time
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
META_PATH = ROOT / "demo" / "ranking_meta.json"
FLAGGED_DEMO_PATH = ROOT / "demo" / "flagged.json"
FLAGGED_OUTPUT_PATH = ROOT / "output" / "flagged.json"
JSONL_PATH = ROOT / "data" / "candidates.jsonl"
UPLOADED_JSONL_PATH = ROOT / "data" / "candidates_uploaded.jsonl"
OUTPUT_CSV = ROOT / "output" / "final.csv"

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

/* dataset status banner */
.pr-meta{
  background:#F2EAE0; border:1px solid var(--line); border-radius:10px;
  padding:.55rem .95rem; margin:.3rem 0 1.2rem 0;
  font-size:.93rem; color:var(--muted); display:flex; gap:.5rem; align-items:center;
}
.pr-meta .dot{ width:8px; height:8px; border-radius:50%; background:var(--sage);
               flex:0 0 auto; }

/* cards (HTML <details>) */
details.pr-card{
  background:var(--card); border:1px solid var(--line); border-radius:16px;
  box-shadow:var(--shadow); padding:.35rem 1.25rem; margin:0 0 1rem 0;
  transition:box-shadow .2s ease;
}
details.pr-card[open]{ box-shadow:0 10px 34px rgba(120,90,60,.14); }
details.pr-card.manual-entry{ border-color:var(--sage); border-width:2px; }
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
details.pr-card.manual-entry .pr-rank{ background:var(--sage-soft); color:var(--sage); }
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
.pr-tech-h{ font-weight:700; margin:.75rem 0 .35rem 0; color:var(--ink); font-size:.93rem; }

/* behavioral 2-column grid */
.pr-beh-grid{
  display:grid; grid-template-columns:max-content 1fr;
  gap:.38rem .9rem; margin:.35rem 0; align-items:baseline;
}
.pr-beh-k{ color:var(--muted); font-size:.9rem; white-space:nowrap; }
.pr-beh-v{ font-size:.9rem; }

/* skill + assessment chip pills (flex-wrap, never overflow) */
.pr-chips{ display:flex; flex-wrap:wrap; gap:.4rem; margin:.4rem 0 .65rem 0; }
.pr-skill-chip{
  background:#F2EADF; border:1px solid var(--line); border-radius:8px;
  padding:.24rem .65rem; font-size:.85rem; color:var(--ink); line-height:1.45;
}
.pr-assess-chip{
  border-radius:8px; padding:.24rem .65rem; font-size:.85rem; line-height:1.45;
  display:inline-flex; align-items:center; gap:.4rem;
}
.pr-assess-chip.hi{ background:#E7F1ED; border:1px solid #CFE6DD; color:#3F6F60; }
.pr-assess-chip.md{ background:#FBF0E2; border:1px solid #E8CC88; color:#7A5C18; }
.pr-assess-chip.lo{ background:#FBEBE2; border:1px solid #EAB8A0; color:#8C3C28; }
.pr-assess-chip .as-band{
  font-size:.74rem; font-weight:720; text-transform:uppercase; letter-spacing:.05em;
}

/* expandable skill overflow */
details.pr-overflow-det{ margin-top:.35rem; }
details.pr-overflow-det > summary{
  list-style:none; cursor:pointer; display:inline-flex; align-items:center; gap:.35rem;
  background:#F2EADF; border:1px solid var(--line); border-radius:8px;
  padding:.24rem .65rem; font-size:.85rem; color:var(--accent);
  font-weight:620; line-height:1.45;
}
details.pr-overflow-det > summary::-webkit-details-marker{ display:none; }
details.pr-overflow-det > summary::after{ content:"▸"; font-size:.78rem; opacity:.7; }
details.pr-overflow-det[open] > summary::after{ content:"▾"; }
.pr-overflow-body{ display:flex; flex-wrap:wrap; gap:.4rem; margin-top:.4rem; }

/* flagged candidate cards */
.pr-flag-card{
  background:#FFFBF2; border:1px solid #E8CC88; border-left:3px solid var(--amber);
  border-radius:10px; padding:.75rem 1rem; margin:0 0 .65rem 0;
}
.pr-flag-title{ font-size:1rem; font-weight:660; color:var(--ink); margin-bottom:.1rem; }
.pr-flag-sub{ font-size:.87rem; color:var(--muted); margin-bottom:.5rem; }
.pr-flag-violation{
  font-size:.92rem; color:var(--ink); line-height:1.5; margin:.22rem 0;
}
.pr-flag-chips{ display:flex; flex-wrap:wrap; gap:.3rem .5rem; margin-top:.55rem; align-items:center; }
.pr-flag-code{
  display:inline-block; font-size:.74rem; font-weight:720; text-transform:uppercase;
  letter-spacing:.05em; color:var(--amber); background:var(--amber-soft);
  border:1px solid #E8CC88; border-radius:5px; padding:.05rem .38rem;
}
.pr-flag-code-label{ font-size:.82rem; color:var(--muted); margin-right:.35rem; }
.pr-flag-note{
  font-size:.82rem; color:var(--muted); margin-top:.5rem; padding-top:.4rem;
  border-top:1px dashed #E8CC88;
}

/* CSV download button */
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button{
  background:var(--accent); color:#fff; border:none; border-radius:11px;
  font-weight:650; padding:.55rem 1rem; box-shadow:0 4px 14px rgba(221,122,91,.30);
  width:100%;
}
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button:hover{
  background:#C96846; color:#fff;
}
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button p{
  color:#fff; font-weight:650;
}
</style>
"""

# ─── Meta helpers ─────────────────────────────────────────────────────────────

def load_meta() -> dict:
    try:
        return json.loads(META_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_meta(source: str, n_input: int, n_ranked: int) -> None:
    META_PATH.write_text(json.dumps({
        "last_ranked_utc": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "source": source,
        "n_input": n_input,
        "n_ranked": n_ranked,
    }, indent=2), encoding="utf-8")


def meta_banner_html(meta: dict, is_prebaked: bool) -> str:
    if is_prebaked or not meta:
        return ('<div class="pr-meta"><span class="dot" style="background:#C68A3A"></span>'
                '📸 Showing pre-baked snapshot — click <b>Re-rank</b> in the sidebar to refresh</div>')
    ts = meta.get("last_ranked_utc", "")
    src = meta.get("source", "")
    n_in = meta.get("n_input", 0)
    n_out = meta.get("n_ranked", 0)
    n_in_fmt = f"{n_in:,}" if n_in else "?"
    return (f'<div class="pr-meta"><span class="dot"></span>'
            f'🕐 Last analyzed: <b>{ts}</b> · Source: <b>{src}</b> · '
            f'{n_in_fmt} candidates → top {n_out}</div>')


# ─── Data loading (cache-key driven) ─────────────────────────────────────────

@st.cache_data
def load_candidates(cache_key: int = 0) -> list[dict]:
    if not DATA_PATH.exists():
        st.error(
            f"Demo data not found: {DATA_PATH}\n\n"
            f"Run  `python demo/extract_top100.py`  once to create it."
        )
        st.stop()
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


@st.cache_data
def load_flagged(cache_key: int = 0) -> list[dict]:
    for p in (FLAGGED_OUTPUT_PATH, FLAGGED_DEMO_PATH):
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
    return []


# ─── Schema validation ────────────────────────────────────────────────────────

REQUIRED_KEYS = {"candidate_id", "profile", "career_history", "skills", "redrob_signals"}


def validate_jsonl_bytes(raw: bytes, filename: str) -> str | None:
    try:
        if filename.endswith(".gz"):
            raw = gzip.decompress(raw)
        lines = [l for l in raw.decode("utf-8", errors="replace").splitlines() if l.strip()]
    except Exception as e:
        return f"Could not read the file: {e}"
    if not lines:
        return "The file appears to be empty."
    for i, line in enumerate(lines[:10]):
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            return (f"Line {i + 1} is not valid JSON. "
                    "Make sure the file is a JSONL (one JSON object per line).")
        missing = REQUIRED_KEYS - set(rec.keys())
        if missing:
            return (f"Line {i + 1} is missing required fields: {', '.join(sorted(missing))}. "
                    "Expected: candidate_id, profile, career_history, skills, redrob_signals.")
    return None


def save_upload_to_disk(uploaded_file, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    uploaded_file.seek(0)
    if uploaded_file.name.endswith(".gz"):
        tmp_gz = dest.with_suffix(".tmp.gz")
        with open(tmp_gz, "wb") as f:
            while chunk := uploaded_file.read(8 * 1024 * 1024):
                f.write(chunk)
        with gzip.open(tmp_gz, "rb") as gz_in, open(dest, "wb") as f_out:
            while chunk := gz_in.read(8 * 1024 * 1024):
                f_out.write(chunk)
        tmp_gz.unlink()
    else:
        with open(dest, "wb") as f:
            while chunk := uploaded_file.read(8 * 1024 * 1024):
                f.write(chunk)


# ─── Pipeline ─────────────────────────────────────────────────────────────────

def _run_subprocess_logged(cmd: list[str], label: str, status_obj) -> tuple[int, str]:
    status_obj.write(f"**{label}**")
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, cwd=str(ROOT), bufsize=1,
    )
    lines: list[str] = []
    log_area = status_obj.empty()
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            lines.append(line)
            log_area.code("\n".join(lines[-8:]), language=None)
    proc.wait()
    return proc.returncode, "\n".join(lines)


def run_pipeline(jsonl_path: Path) -> tuple[bool, str, dict]:
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with st.status("Analyzing candidates — this takes about a minute…", expanded=True) as status:
        ret, out = _run_subprocess_logged(
            [sys.executable, "-m", "src.rank",
             "--candidates", str(jsonl_path), "--output", str(OUTPUT_CSV)],
            "Step 1 of 2 — Ranking all candidates", status,
        )
        if ret != 0:
            status.update(label="Ranker failed ❌", state="error")
            return False, ("The ranker exited with an error. Check that the dataset file is "
                           "a valid JSONL with the expected schema."), {}
        n_input = 0
        for line in out.splitlines():
            m = re.search(r"Scored ([\d,]+) candidates", line)
            if m:
                n_input = int(m.group(1).replace(",", ""))
                break
        if "Validator: PASS" not in out:
            status.update(label="Output validation failed ❌", state="error")
            return False, ("The ranked output failed the submission validator. "
                           "The dataset may be malformed or too small."), {}
        ret2, out2 = _run_subprocess_logged(
            [sys.executable, "demo/extract_top100.py", "--candidates", str(jsonl_path)],
            "Step 2 of 2 — Building candidate cards", status,
        )
        if ret2 != 0:
            status.update(label="Card rebuild failed ❌", state="error")
            return False, f"Card rebuild failed: {out2[:300]}", {}
        status.update(label="Analysis complete ✅", state="complete")
    return True, "", {"source": jsonl_path.name, "n_input": n_input, "n_ranked": 100}


# ─── Plain-language card helpers ──────────────────────────────────────────────

def match_level(rank: int) -> tuple[str, int]:
    if rank <= 10:  return "Excellent match", 5
    if rank <= 30:  return "Strong match", 4
    if rank <= 60:  return "Good match", 3
    if rank <= 85:  return "Fair match", 2
    return "Possible match", 1


def dots_html(filled: int) -> str:
    return "".join(
        '<span class="on">●</span>' if i < filled else '<span class="off">○</span>'
        for i in range(5)
    )


def current_company(row: dict) -> str:
    career = row.get("career_history", [])
    cur = next((c.get("company") for c in career if c.get("is_current")), None)
    return cur or (career[0]["company"] if career else "—")


def availability_text(row: dict) -> str | None:
    sig = row.get("redrob_signals", {}) or {}
    if sig.get("open_to_work_flag"):
        return "Open to new roles"
    npd = sig.get("notice_period_days")
    if isinstance(npd, (int, float)) and 0 <= npd <= 30:
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
    if has(row, "ranking"):    strengths.append("built the ranking and recommendation systems this role is about")
    if has(row, "retrieval"):  strengths.append("shipped real search and retrieval features")
    if has(row, "vector"):     strengths.append("worked hands-on with vector / semantic search")
    if has(row, "evaluation"): strengths.append("measured search quality properly with A/B tests and metrics")
    if has(row, "shipping"):   strengths.append("delivered to real users at scale")
    if not strengths:
        return ("Their title and experience fit the role, though their work history "
                "shows fewer concrete examples than the people ranked above.")
    body = (strengths[0] if len(strengths) == 1
            else ", ".join(strengths[:-1]) + ", and " + strengths[-1])
    return f"Their actual work history shows they have {body}."


def why_not_higher_plain(row: dict) -> str:
    rank = row["rank"]
    yoe  = float(row.get("profile", {}).get("years_of_experience", 0) or 0)
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
    roles.sort(key=lambda r: (not r.get("is_current"),))
    if not roles:
        return ""
    out = ['<div class="pr-sec-h">Recent work</div>']
    for r in roles[:2]:
        end  = "present" if r.get("is_current") else (r.get("end_date") or "")
        head = f"{r.get('title','')} · {r.get('company','')} ({r.get('start_date','?')} – {end})"
        desc = (r.get("description") or "").strip()
        desc = desc[:200] + ("…" if len(desc) > 200 else "")
        out.append(
            f'<div class="pr-role"><div class="rh">{html.escape(head)}</div>'
            f'<div class="rd">{html.escape(desc)}</div></div>'
        )
    return "".join(out)


def tech_html(row: dict) -> str:
    d   = row.get("ev_dims", {})
    sig = row.get("redrob_signals", {}) or {}

    def _val(key, fmt="raw"):
        v = sig.get(key)
        if v is None or v == -1:
            return "—"
        if fmt == "pct":  return f"{v:.0%}"
        if fmt == "int":  return f"{int(v)}"
        return str(v)

    # ── Score breakdown ────────────────────────────────────────────────────────
    breakdown = [
        ("Evidence × 3",          f"{3 * row.get('ev_score', 0):.0f}"),
        ("Title prior",            f"{row.get('title_prior', 0):.0f} / 200"),
        ("Skill coherence",        f"{row.get('skill_coherence', 0):.0f} / 200"),
        ("YoE fit",                f"{row.get('yoe_fit', 0):.0f} / 60"),
        ("Nice-to-have",           f"{row.get('nice', 0):.0f} / 40"),
        ("Integrity penalties",    f"-{row.get('penalty', 0):.0f}"),
        ("JD tiebreak",            f"+{row.get('tiebreak', 0):.0f} / 60"),
        ("Behavioral modifier",    f"{row.get('behavioral', 0):+.0f} / +-40"),
    ]

    # ── Behavioral signals — 2-column grid ────────────────────────────────────
    npd = sig.get("notice_period_days")
    npd_str = (f"{int(npd)} days" if npd not in (None, -1) else "—")
    otw = sig.get("open_to_work_flag")
    otw_str = "Yes" if otw else ("No" if otw is False else "—")
    beh_rows = [
        ("Recruiter response rate", _val("recruiter_response_rate", "pct")),
        ("Last active",             html.escape(str(sig.get("last_active_date") or "—"))),
        ("GitHub activity score",   _val("github_activity_score", "int")),
        ("Notice period",           npd_str),
        ("Interview completion",    _val("interview_completion_rate", "pct")),
        ("Open to work",            otw_str),
    ]

    # ── Skill assessments — chip pills with score-band colour + text ──────────
    assess = sig.get("skill_assessment_scores") or {}
    assess_section = ""
    if assess:
        chips = []
        for skill, score in sorted(assess.items(), key=lambda x: -x[1]):
            if score >= 70:
                cls, label = "hi", "high"
            elif score >= 40:
                cls, label = "md", "ok"
            else:
                cls, label = "lo", "low"
            chips.append(
                f'<span class="pr-assess-chip {cls}">'
                f'{html.escape(skill)} {int(score)}/100'
                f'<span class="as-band">{label}</span>'
                f'</span>'
            )
        assess_section = (
            '<div class="pr-tech-h">Skill assessments</div>'
            '<div class="pr-chips">' + "".join(chips) + '</div>'
        )

    # ── Skills — chip pills (wrapped, capped at 8 + expandable overflow) ────
    skills = row.get("skills", [])
    SKILL_CAP = 8

    def _skill_chip(s: dict) -> str:
        name = html.escape(s.get("name", ""))
        prof = s.get("proficiency", "")
        dur  = s.get("duration_months", 0)
        parts = [p for p in [name, prof, f"{dur}mo" if dur else ""] if p]
        return f'<span class="pr-skill-chip">{" · ".join(parts)}</span>'

    visible_chips = [_skill_chip(s) for s in skills[:SKILL_CAP]]
    hidden_chips  = [_skill_chip(s) for s in skills[SKILL_CAP:]]

    if not visible_chips and not hidden_chips:
        skill_section = (
            '<div class="pr-tech-h">Top skills</div>'
            '<p style="color:var(--muted);font-size:.9rem">None listed</p>'
        )
    else:
        overflow_html = ""
        if hidden_chips:
            overflow_html = (
                f'<details class="pr-overflow-det">'
                f'<summary>+{len(hidden_chips)} more</summary>'
                f'<div class="pr-overflow-body">{"".join(hidden_chips)}</div>'
                f'</details>'
            )
        skill_section = (
            '<div class="pr-tech-h">Top skills</div>'
            '<div class="pr-chips">' + "".join(visible_chips) + '</div>'
            + overflow_html
        )

    parts = [
        '<div class="pr-tech-body">',
        # raw score + evidence score
        '<div class="pr-tech-h">Raw fit score</div>',
        f'<div class="pr-kv">'
        f'<span class="k">Final score</span><span><code>{row.get("score",0):.2f}</code></span>'
        f'<span class="k">Evidence score</span><span><code>{row.get("ev_score",0):.0f} / 500</code></span>'
        f'</div>',
        # evidence dims
        '<div class="pr-tech-h">Evidence dimensions (0–1)</div>',
        '<div class="pr-kv">' + "".join(
            f'<span class="k">{k}</span><span><code>{float(d.get(k, 0)):.2f}</code></span>'
            for k in ["retrieval", "vector", "ranking", "evaluation", "shipping"]
        ) + '</div>',
        # score breakdown
        '<div class="pr-tech-h">Score breakdown</div>',
        '<div class="pr-kv">' + "".join(
            f'<span class="k">{html.escape(k)}</span><span><code>{v}</code></span>'
            for k, v in breakdown
        ) + '</div>',
        # behavioral signals grid
        '<div class="pr-tech-h">Behavioral signals</div>',
        '<div class="pr-beh-grid">' + "".join(
            f'<span class="pr-beh-k">{html.escape(k)}</span>'
            f'<span class="pr-beh-v">{v}</span>'
            for k, v in beh_rows
        ) + '</div>',
        # assessment chips
        assess_section,
        # skill chips
        skill_section,
        '</div>',
    ]
    return "".join(parts)


def candidate_card(row: dict, open_default: bool, extra_class: str = "") -> str:
    rank    = row["rank"]
    prof    = row.get("profile", {})
    title   = html.escape(prof.get("current_title", "Candidate"))
    yoe     = float(prof.get("years_of_experience", 0) or 0)
    company = html.escape(current_company(row))
    label, filled = match_level(rank)
    flagged = bool(row.get("flags"))
    is_manual = bool(row.get("_manual"))

    rank_label = f"~#{rank}" if is_manual else f"#{rank}"
    flag_pin = '<span class="pr-flag-pin" title="Needs verifying">⚠️</span>' if flagged else ""
    summary = (
        f'<summary>'
        f'<span class="pr-rank">{rank_label}</span>'
        f'<span class="pr-sum-main"><span class="pr-title">{title}</span>'
        f'<span class="pr-sub">{yoe:.0f} yrs experience · {company}</span></span>'
        f'<span class="pr-sum-match"><span class="pr-dots">{dots_html(filled)}</span>'
        f'<span class="pr-mlabel">{label}</span></span>'
        f'{flag_pin}</summary>'
    )

    chips = [f'<span class="pr-chip">💼 {title}</span>',
             f'<span class="pr-chip">🗓 {yoe:.0f} years</span>',
             f'<span class="pr-chip">🏢 {company}</span>']
    avail = availability_text(row)
    if avail:
        chips.append(f'<span class="pr-chip avail">🟢 {avail}</span>')
    if is_manual:
        chips.append(f'<span class="pr-chip avail" style="background:var(--sage-soft);color:var(--sage)">✍️ Manual entry</span>')
    facts = '<div class="pr-facts">' + "".join(chips) + '</div>'

    checks = ['<div class="pr-sec-h">What they\'ve actually done</div>']
    for dim, text in DONE_ITEMS:
        if has(row, dim):
            checks.append(f'<div class="pr-check"><span class="ic">✅</span><span>{html.escape(text)}</span></div>')
        else:
            checks.append(f'<div class="pr-check no"><span class="ic">➖</span><span>{html.escape(text)}</span></div>')

    why_good = (f'<div class="pr-why good"><b>Why this person</b>{html.escape(why_person_plain(row))}</div>')
    why_less = (f'<div class="pr-why less"><b>Why not ranked higher</b>{html.escape(why_not_higher_plain(row))}</div>')
    ftext    = flag_text(row)
    flag_box = (f'<div class="pr-flagbox"><b>⚠️ Worth verifying</b>{html.escape(ftext)}</div>' if ftext else "")
    tech     = (f'<details class="pr-tech"><summary>See the details</summary>{tech_html(row)}</details>')

    open_attr = " open" if open_default else ""
    cls_str   = ("pr-card " + extra_class).strip()
    return (
        f'<details class="{cls_str}"{open_attr}>'
        f'{summary}'
        f'<div class="pr-body">{facts}{"".join(checks)}{why_good}{why_less}{flag_box}'
        f'{career_html(row)}{tech}</div></details>'
    )


_FLAG_LABELS: dict[str, str] = {
    "H1":  "Expert skill claimed with no recorded usage",
    "H2b": "Skill usage duration exceeds entire career length",
    "H3":  "Employment dates impossible given company founding date",
    "H6":  "Total career history longer than stated years of experience",
}


def flagged_card_html(entry: dict) -> str:
    title   = html.escape(entry.get("title", "Unknown"))
    yoe     = entry.get("years_of_experience", 0)
    loc     = entry.get("location", "")
    sub     = f"{yoe:.0f} yrs experience" + (f" · {html.escape(loc)}" if loc else "")
    reasons = entry.get("reasons", [])

    violations = "".join(
        f'<div class="pr-flag-violation">⚠️ {html.escape(r.get("plain", ""))}</div>'
        for r in reasons
    )

    # Deduplicated code chips for the technical reviewer
    seen: set[str] = set()
    chips: list[str] = []
    for r in reasons:
        code = r.get("code", "")
        if code not in seen:
            seen.add(code)
            label = html.escape(_FLAG_LABELS.get(code, code))
            chips.append(
                f'<span class="pr-flag-code">{html.escape(code)}</span>'
                f'<span class="pr-flag-code-label">{label}</span>'
            )

    return (
        f'<div class="pr-flag-card">'
        f'<div class="pr-flag-title">{title}</div>'
        f'<div class="pr-flag-sub">{sub}</div>'
        + violations +
        f'<div class="pr-flag-chips">{"".join(chips)}</div>'
        f'<div class="pr-flag-note">Excluded from shortlist · '
        f'Human review recommended before any employment decision</div>'
        f'</div>'
    )


def make_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["rank", "match", "candidate_id", "title", "years_experience", "current_company",
                "built_ranking", "built_retrieval", "vector_search", "measures_quality",
                "shipped_at_scale", "needs_verifying", "why_this_person", "why_not_higher",
                "raw_score", "evidence_score"])
    for r in rows:
        prof = r.get("profile", {})
        label, _ = match_level(r["rank"])
        w.writerow([
            r["rank"], label, r["candidate_id"],
            prof.get("current_title", ""), f'{float(prof.get("years_of_experience", 0) or 0):.0f}',
            current_company(r),
            "yes" if has(r, "ranking")    else "no",
            "yes" if has(r, "retrieval")  else "no",
            "yes" if has(r, "vector")     else "no",
            "yes" if has(r, "evaluation") else "no",
            "yes" if has(r, "shipping")   else "no",
            "yes" if r.get("flags")       else "no",
            why_person_plain(r), why_not_higher_plain(r),
            f'{r.get("score", 0):.2f}', f'{r.get("ev_score", 0):.0f}',
        ])
    return buf.getvalue()


# ─── Manual candidate entry helpers ──────────────────────────────────────────

def _parse_ym(s: str) -> tuple[int, int] | None:
    s = s.strip()
    for fmt in ("%Y-%m", "%Y"):
        try:
            d = datetime.datetime.strptime(s, fmt)
            return d.year, d.month
        except ValueError:
            pass
    return None


def _duration_months(start: str, end: str | None) -> int:
    s = _parse_ym(start)
    if not s:
        return 0
    if end and end.strip():
        e = _parse_ym(end.strip())
    else:
        e = None
    if not e:
        today = datetime.date.today()
        e = (today.year, today.month)
    return max(0, (e[0] - s[0]) * 12 + (e[1] - s[1]))


def _build_manual_record(
    name: str, title: str, company: str, yoe: float, location: str,
    raw_skills: str, roles: list[dict],
) -> dict:
    cid = f"MANUAL_{int(time.time())}"
    career = []
    for r in roles:
        if not (r.get("title", "").strip() or r.get("company", "").strip()):
            continue
        end_val  = r.get("end", "").strip()
        is_cur   = not end_val
        career.append({
            "title":          r.get("title", "").strip(),
            "company":        r.get("company", company or "").strip(),
            "start_date":     r.get("start", "").strip(),
            "end_date":       None if is_cur else end_val,
            "is_current":     is_cur,
            "duration_months": _duration_months(r.get("start", ""), None if is_cur else end_val),
            "description":    r.get("description", "").strip(),
        })
    if not career:
        career = [{
            "title": title, "company": company or "",
            "start_date": "", "end_date": None, "is_current": True,
            "duration_months": max(0, int(yoe * 12)),
            "description": "",
        }]
    skills_list = [
        {"name": s.strip(), "proficiency": "intermediate", "duration_months": 0, "endorsements": 0}
        for s in raw_skills.split(",") if s.strip()
    ][:12]
    return {
        "candidate_id": cid,
        "profile": {
            "name": name, "current_title": title,
            "years_of_experience": float(yoe), "location": location,
        },
        "career_history": career,
        "skills": skills_list,
        "redrob_signals": {
            "recruiter_response_rate": None, "last_active_date": None,
            "github_activity_score": -1, "skill_assessment_scores": {},
            "notice_period_days": None, "interview_completion_rate": None,
            "open_to_work_flag": False,
        },
    }


def _score_manual(record: dict, base_candidates: list[dict]) -> dict:
    """Score a manually-entered candidate using the real ranker (imported lazily)."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from src.rank import score_candidate_final  # noqa: PLC0415

    raw_score, info = score_candidate_final(record)
    rank_pos = sum(1 for c in base_candidates if c.get("score", 0) > raw_score) + 1
    return {
        "candidate_id": record["candidate_id"],
        "rank":         rank_pos,
        "score":        raw_score,
        "ev_score":     info["ev_score"],
        "ev_dims":      info["ev_dims"],
        "title_prior":  info["title_prior"],
        "skill_coherence": info["skill_coherence"],
        "yoe_fit":      info["yoe_fit"],
        "nice":         info["nice"],
        "penalty":      info["penalty"],
        "hard":         info["hard"],
        "tiebreak":     info.get("tiebreak", 0.0),
        "behavioral":   info["behavioral"],
        "flags":        info["flags"],
        "profile":      record.get("profile", {}),
        "career_history": record.get("career_history", []),
        "skills":       record.get("skills", []),
        "redrob_signals": record.get("redrob_signals", {}),
        "_manual":      True,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Render
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown(CSS, unsafe_allow_html=True)

# ── Pipeline execution ─────────────────────────────────────────────────────────
if st.session_state.get("pipeline_action") == "rerank":
    jsonl_p = Path(st.session_state.pop("pipeline_jsonl", str(JSONL_PATH)))
    st.session_state.pop("pipeline_action", None)
    ok, err, meta_new = run_pipeline(jsonl_p)
    if ok:
        save_meta(meta_new["source"], meta_new["n_input"], meta_new["n_ranked"])
        st.session_state["cache_key"]        = st.session_state.get("cache_key", 0) + 1
        st.session_state["pipeline_success"] = (
            f"Re-analysis complete — {meta_new['n_input']:,} candidates ranked, "
            f"top {meta_new['n_ranked']} shown below."
        )
    else:
        st.session_state["pipeline_error"] = f"❌ {err}"
    st.rerun()

if msg := st.session_state.pop("pipeline_success", None):
    st.success(msg)
if msg := st.session_state.pop("pipeline_error", None):
    st.error(msg)

# ── Load candidates ────────────────────────────────────────────────────────────
candidates  = load_candidates(st.session_state.get("cache_key", 0))
meta        = load_meta()
is_prebaked = not META_PATH.exists()

# ── Merge manual pool → re-sort, re-rank ──────────────────────────────────────
manual_pool: list[dict] = st.session_state.get("manual_pool", [])
if manual_pool:
    all_cands = [dict(c) for c in candidates] + [dict(m) for m in manual_pool]
    all_cands.sort(key=lambda c: c.get("score", 0), reverse=True)
    for i, c in enumerate(all_cands):
        c["rank"] = i + 1
    display_candidates = all_cands
else:
    display_candidates = candidates

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🌿 ProofRank")
    st.caption("Candidate shortlist for Redrob AI")
    st.divider()

    # View filters
    show        = st.radio("Show", ["All", "Top 10", "Top 50"], index=0)
    strong_only = st.toggle("Only show strong matches", value=False,
                            help="Strong or Excellent matches (top 30).")
    st.divider()

    # Apply filters
    filtered: list[dict] = []
    for c in display_candidates:
        r = c["rank"]
        if show == "Top 10" and r > 10: continue
        if show == "Top 50" and r > 50: continue
        if strong_only      and r > 30: continue
        filtered.append(c)

    n_manual = sum(1 for c in filtered if c.get("_manual"))
    label_extra = f" (incl. {n_manual} manual)" if n_manual else ""
    st.markdown(f"**Showing {len(filtered)} of {len(display_candidates)} candidates{label_extra}**")

    if filtered:
        st.download_button(
            "⬇  Download shortlist (CSV)",
            data=make_csv(filtered),
            file_name="candidate_shortlist.csv",
            mime="text/csv",
            use_container_width=True,
        )

    st.divider()

    # ── Data section ──────────────────────────────────────────────────────────
    st.markdown("#### 🗂 Data")
    jsonl_present = JSONL_PATH.exists()
    if jsonl_present:
        sz_mb = JSONL_PATH.stat().st_size / 1_048_576
        st.caption(f"📄 {JSONL_PATH.name} ({sz_mb:.0f} MB)")
    else:
        st.caption("📄 No dataset file found at `data/candidates.jsonl`")

    rerank_help = (
        "Re-analyze all candidates in data/candidates.jsonl and refresh the view."
        if jsonl_present
        else "No dataset found. Place candidates.jsonl in the data/ folder first."
    )
    if st.button(
        "🔄  Re-rank current dataset",
        disabled=not jsonl_present,
        help=rerank_help,
        type="primary",
        use_container_width=True,
    ):
        st.session_state["pipeline_action"] = "rerank"
        st.session_state["pipeline_jsonl"]  = str(JSONL_PATH)
        st.rerun()

    st.write("")

    with st.expander("📤  Upload a new dataset"):
        st.markdown(
            "Upload a `.jsonl` or `.jsonl.gz` file of candidates. "
            "It will be validated, saved, and ranked automatically.\n\n"
            "**Required fields per record:** `candidate_id`, `profile`, "
            "`career_history`, `skills`, `redrob_signals`\n\n"
            "_Large files (>200 MB) may take a moment to upload._"
        )
        uploaded = st.file_uploader(
            "Choose a candidate file",
            type=["jsonl", "gz"],
            key="dataset_upload",
            label_visibility="collapsed",
        )
        if uploaded is not None:
            already = st.session_state.get("processed_upload") == uploaded.name
            if not already:
                with st.spinner("Validating schema…"):
                    uploaded.seek(0)
                    sample = uploaded.read(1_048_576)
                    uploaded.seek(0)
                    err = validate_jsonl_bytes(sample, uploaded.name)
                if err:
                    st.error(f"⚠️ Invalid file: {err}")
                else:
                    with st.spinner("Saving to disk…"):
                        save_upload_to_disk(uploaded, UPLOADED_JSONL_PATH)
                    n_lines = sum(1 for _ in open(UPLOADED_JSONL_PATH, "rb"))
                    st.success(
                        f"✅ Saved **{uploaded.name}** "
                        f"({n_lines:,} candidates). Starting re-analysis…"
                    )
                    st.session_state["processed_upload"] = uploaded.name
                    st.session_state["pipeline_action"]  = "rerank"
                    st.session_state["pipeline_jsonl"]   = str(UPLOADED_JSONL_PATH)
                    st.rerun()
            else:
                st.info(f"✅ **{uploaded.name}** is already loaded.")

    # ── Manual candidate entry ─────────────────────────────────────────────────
    st.write("")
    with st.expander("✍️  Add a candidate manually"):
        st.markdown(
            "Score any candidate instantly using the **same logic as the submission "
            "ranker** — no data file needed. Paste in their title, experience, and "
            "career history to see where they'd rank."
        )
        with st.form("manual_entry", clear_on_submit=False):
            m_name  = st.text_input("Full name", placeholder="e.g. Priya Sharma")
            m_title = st.text_input(
                "Current job title *",
                placeholder="e.g. Senior NLP Engineer",
            )
            c1, c2 = st.columns(2)
            m_company = c1.text_input("Current company", placeholder="e.g. Ola")
            m_yoe     = c2.number_input(
                "Years of experience *", 0.0, 40.0, 5.0, 0.5,
            )
            m_location = st.text_input(
                "Location (optional)", placeholder="e.g. Bangalore",
            )
            m_skills = st.text_area(
                "Skills (comma-separated)",
                placeholder="Python, PyTorch, FAISS, Elasticsearch, LTR …",
                height=65,
            )
            st.markdown("**Career history** (most recent first)")
            st.caption(
                "Fill in at least Role 1. "
                "Career descriptions are the main evidence source."
            )
            roles_raw: list[dict] = []
            for i in range(3):
                if i > 0:
                    st.markdown("---")
                    st.caption(f"Role {i + 1} (optional)")
                else:
                    st.caption("Role 1 (most recent / current)")
                rc1, rc2 = st.columns(2)
                r_title   = rc1.text_input("Job title",  key=f"r_title_{i}",
                                            placeholder="e.g. ML Engineer")
                r_company = rc2.text_input("Company",    key=f"r_company_{i}",
                                            placeholder="e.g. Swiggy")
                rd1, rd2 = st.columns(2)
                r_start   = rd1.text_input("Start (YYYY-MM)", key=f"r_start_{i}",
                                            placeholder="2022-01")
                r_end     = rd2.text_input(
                    "End (YYYY-MM, blank = current)", key=f"r_end_{i}",
                    placeholder="2024-06",
                )
                r_desc = st.text_area(
                    "What they worked on",
                    key=f"r_desc_{i}", height=75,
                    placeholder=(
                        "e.g. Built a learning-to-rank pipeline using LambdaMART and "
                        "NDCG-optimised training data; shipped to 10M+ users."
                    ),
                )
                roles_raw.append({
                    "title": r_title, "company": r_company,
                    "start": r_start, "end": r_end, "description": r_desc,
                })

            submitted = st.form_submit_button(
                "Score this candidate", type="primary",
                use_container_width=True,
            )

        if submitted:
            if not m_title.strip():
                st.error("Please enter a current job title — the ranker needs it.")
            else:
                try:
                    record = _build_manual_record(
                        name=m_name.strip(), title=m_title.strip(),
                        company=m_company.strip(), yoe=float(m_yoe),
                        location=m_location.strip(), raw_skills=m_skills,
                        roles=roles_raw,
                    )
                    with st.spinner("Scoring…"):
                        result_row = _score_manual(record, candidates)
                    st.session_state["manual_result"] = result_row
                    st.rerun()
                except Exception as exc:
                    st.error(
                        f"Scoring failed: {exc}\n\n"
                        "Check that `src/rank.py` is accessible from the project root."
                    )


# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="pr-hero">'
    '<h1>Candidate Shortlist — Senior AI Engineer</h1>'
    '<p>The 100 strongest candidates for Redrob AI\'s founding-team role, ranked by what '
    'their real work history shows — not by buzzwords on a profile. Open any card to see, '
    'in plain language, what each person has actually built and why they sit where they do.</p>'
    '</div>',
    unsafe_allow_html=True,
)
st.markdown(meta_banner_html(meta, is_prebaked), unsafe_allow_html=True)

with st.expander("ℹ️  How this works"):
    st.markdown(
        "We read every candidate's real career history and look for **evidence of the work "
        "this role needs**: building search and retrieval systems, shipping ranking and "
        "recommendation models, and measuring their quality properly.\n\n"
        "People are ranked by what they've **actually done**, not by the keywords or job "
        "titles they list. Profiles whose details look inconsistent or too good to be true "
        "are automatically **flagged for verification** and kept out of the top results.\n\n"
        "Each card leads with a plain-language verdict. The raw scores and technical "
        "breakdown are tucked away under **\"See the details\"** if you want them.\n\n"
        "Use the **Data** section in the sidebar to re-rank the current dataset, upload "
        "a new one, or score a candidate manually."
    )

st.write("")

# ── Tabs ──────────────────────────────────────────────────────────────────────
flagged_all = load_flagged(st.session_state.get("cache_key", 0))
tab_shortlist, tab_flagged = st.tabs([
    f"📋 Shortlist ({len(display_candidates)})",
    f"⚠️ Flagged Profiles ({len(flagged_all)})" if flagged_all else "⚠️ Flagged Profiles",
])

# ── Shortlist tab ─────────────────────────────────────────────────────────────
with tab_shortlist:
    # Manual candidate preview
    if "manual_result" in st.session_state:
        mr       = st.session_state["manual_result"]
        rp       = mr["rank"]
        name_str = mr.get("profile", {}).get("name") or mr["candidate_id"]
        honeypot = mr.get("score", 0) < -1e8

        if honeypot:
            st.error(
                f"**{name_str}** was flagged as a likely honeypot / inconsistent profile "
                f"and would be excluded from the shortlist entirely. Check the 'See the "
                f"details' panel for the specific integrity flags."
            )
        else:
            st.markdown(
                f'<div class="pr-sec-h" style="margin-top:0">'
                f'🎯 Candidate preview — would rank ~#{rp} among the current pool'
                f'</div>',
                unsafe_allow_html=True,
            )

        col_card, col_btns = st.columns([5, 1])
        with col_btns:
            st.write("")
            if not honeypot:
                if st.button("Add to pool", key="add_to_pool", type="primary",
                             use_container_width=True):
                    pool = st.session_state.get("manual_pool", [])
                    pool.append(st.session_state.pop("manual_result"))
                    st.session_state["manual_pool"] = pool
                    st.rerun()
            if st.button("Clear", key="clear_preview", use_container_width=True):
                st.session_state.pop("manual_result", None)
                st.rerun()

        with col_card:
            st.markdown(
                candidate_card(mr, open_default=True, extra_class="manual-entry"),
                unsafe_allow_html=True,
            )

        if manual_pool:
            st.caption(
                f"Pool also contains {len(manual_pool)} manually-added candidate(s) "
                "ranked among the main list below."
            )
        st.divider()

    if not filtered:
        st.info("No candidates match the current filters. Try turning a filter off.")
    else:
        for row in filtered:
            extra = "manual-entry" if row.get("_manual") else ""
            st.markdown(candidate_card(row, open_default=row["rank"] <= 5, extra_class=extra),
                        unsafe_allow_html=True)

# ── Flagged Profiles tab ──────────────────────────────────────────────────────
with tab_flagged:
    if not flagged_all:
        st.success(
            "✅ No integrity violations detected in the current dataset. "
            "All candidates passed the honeypot and consistency checks."
        )
    else:
        # Sort / filter controls
        ctrl1, ctrl2, ctrl3 = st.columns([2, 3, 2])
        with ctrl1:
            sort_by = st.selectbox(
                "Sort by",
                ["Most severe first", "Most violations first", "Alphabetical by title"],
            )
        with ctrl2:
            all_codes = sorted({r["code"] for e in flagged_all for r in e.get("reasons", [])})
            code_options = [f"{c} — {_FLAG_LABELS.get(c, c)}" for c in all_codes]
            selected_opts = st.multiselect(
                "Filter by violation type", code_options, default=code_options,
            )
        with ctrl3:
            n_limit = st.number_input(
                "Show up to N (0 = all)", min_value=0, value=0, step=10,
            )

        # Apply sort
        if sort_by == "Most violations first":
            view = sorted(flagged_all, key=lambda e: -len(e.get("reasons", [])))
        elif sort_by == "Alphabetical by title":
            view = sorted(flagged_all, key=lambda e: e.get("title", "").lower())
        else:
            view = sorted(flagged_all, key=lambda e: -e.get("severity", 0))

        # Apply filter
        selected_codes = {s.split(" — ")[0] for s in selected_opts}
        view = [e for e in view if any(r["code"] in selected_codes for r in e.get("reasons", []))]

        # Apply limit
        n_total = len(view)
        if n_limit > 0:
            view = view[:n_limit]

        st.caption(
            f"Showing **{len(view)}** of **{len(flagged_all)}** flagged profiles. "
            "These candidates were automatically excluded from the shortlist."
        )
        st.write("")

        if view:
            st.markdown(
                "\n".join(flagged_card_html(e) for e in view),
                unsafe_allow_html=True,
            )
        else:
            st.info("No profiles match the selected filters.")

st.write("")
st.caption(
    "ProofRank · Redrob AI Senior AI Engineer challenge · 100,000 candidates ranked "
    "offline on CPU in ~56s · no embeddings, no API calls, no network required."
)
