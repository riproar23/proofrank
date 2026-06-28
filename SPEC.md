# SPEC.md — ProofRank / Redrob "Intelligent Candidate Discovery & Ranking Challenge"

> **Source of truth.** Every constraint below is quoted from an official file in the
> released bundle. Official files live at:
> `Downloads/[PUB] India_runs_data_and_ai_challenge/.../India_runs_data_and_ai_challenge/`
> (a duplicate copy exists under `OneDrive/Documents/ProofRank/data/...`).
> Files were shipped as `.docx`; the README refers to them as `.md`. I cite them by the
> README's `.md` names plus section numbers, and cite `validate_submission.py` /
> `*.yaml` / `*.json` by line number.
> **VERIFIED** = quoted from an official file. **AMBIGUITY** = spec vs. validator
> disagreement I had to resolve. **ASSUMED** = my inference, not stated.

---

## 1. What we submit (VERIFIED — submission_spec.md §1, §10)

A single **CSV** ranking the **top 100** candidates from `candidates.jsonl` for the
released JD (Senior AI Engineer, Redrob AI). Rank 1 = best fit, rank 100 = 100th best;
candidates 101+ are **not** ranked (submission_spec.md §1).

Full submission = three parts (submission_spec.md §10): (10.1) the CSV; (10.2) portal
metadata; (10.3) a GitHub repo with README, full source, pre-computed artifacts (or a
script to build them), `requirements.txt`, and a `submission_metadata.yaml`; plus
(10.5) a working **sandbox/demo link** (HF Spaces / Streamlit Cloud / Replit / Colab /
Docker / Binder) that runs the ranker on a ≤100-candidate sample within budget.

Three-submission cap; last valid submission counts (submission_spec.md §3).

---

## 2. Output contract (VERIFIED)

### Filename (submission_spec.md §2; validate_submission.py:22-25)
`<participant_id>.csv`, UTF-8. Validator only enforces: extension is `.csv` and stem is
non-empty. It does **not** verify the stem equals your registered participant ID.

### Header — EXACT, in this order (submission_spec.md §2; validate_submission.py:12,38)
```
candidate_id,rank,score,reasoning
```
Validator does a literal list-equality check (`header != REQUIRED_HEADER`) — any rename,
reorder, extra space, or BOM fails.

### Rows (submission_spec.md §3; validate_submission.py)
| Rule | Source |
|---|---|
| Exactly **100** data rows after the header (blank rows ignored). | spec §3; validator:15,48-49,58-64 |
| Each row has exactly **4** columns. | validator:73-78 |
| `candidate_id` matches `^CAND_[0-9]{7}$`, **unique**. | spec §3; validator:13,87-94 |
| `rank` is an integer, each of **1..100 exactly once** (string must equal `str(int)` — no `01`, no `1.0`). | spec §3; validator:96-108,119-123 |
| `score` parses as `float`. | validator:110-114 |
| `score` is **non-increasing by rank** (rank1 ≥ rank2 ≥ … ≥ rank100). | spec §3; validator:125-134 |
| On **equal scores**, `candidate_id` must be **ascending**. | validator:136-144 |
| `reasoning`: 1–2 sentence justification. | spec §2 table |

### Reasoning column (VERIFIED — submission_spec.md §2-3, §3 "Reasoning column" table)
Optional for the **validator** (it never reads column 4) but **scored at Stage 4**
manual review on a 10-row random sample. Penalized: empty; all-identical; name-insertion
templating; **hallucinated skills/employers not in the profile**; reasoning that
**contradicts the rank**. Rewarded: specific facts from the profile (years, title, named
skills, signal values), explicit JD connection, honest acknowledgement of gaps, variation
across rows, tone matching rank.

---

## 3. Compute constraints (VERIFIED — submission_spec.md §3 table; metadata yaml:45-53)

The **ranking step** that produces the CSV must satisfy, with **no network**:

| Constraint | Limit | Source |
|---|---|---|
| Runtime | ≤ **5 min** wall-clock | spec §3 table |
| Memory | ≤ **16 GB** RAM | spec §3 table |
| Compute | **CPU only**, no GPU | spec §3 table |
| Network | **Off** — no hosted-LLM API calls (OpenAI/Anthropic/Cohere/Gemini/etc.) | spec §3 table |
| Disk | ≤ **5 GB** intermediate state | spec §3 table |

- **Per-candidate LLM calls are explicitly ruled out** for 100k profiles within budget
  (spec §3: *"running an LLM call for each of 100,000 candidates will not fit the
  5-minute CPU budget… Plan for a small ranker over precomputed features, indexes, or
  compact local models."*).
- **Offline pre-computation is allowed** (embeddings/indexes/model training) and *may*
  exceed 5 min, but the CSV-producing command must not (spec §10.3; metadata yaml:53-54).
  It is declared separately (`pre_computation_required`, metadata yaml:53).
- **Enforcement is real:** at Stage 3 the top-N ranking step is re-run in a sandboxed
  Docker container matching these limits; failure to reproduce = disqualified regardless
  of score (spec §3 "Enforcement"; §5 stage 3).
- AI tools (Claude/GPT/etc.) are **allowed in the dev workflow** and declared for
  transparency, not penalized (spec §5 note, §10.4; metadata yaml:58-72).

> **Resolves the earlier offline-vs-LLM conflict:** the offline/CPU/no-API/5-min/16GB
> constraint is **official and Docker-enforced**, not assumed. A local LLM re-rank is
> only viable if it is a *compact local model over the top-K shortlist* that fits the
> budget — never a hosted API and never per-candidate over the full pool. Baseline is a
> feature/TF-IDF ranker (see DATA_AUDIT.md "Strategy implications").

---

## 4. Scoring (VERIFIED — submission_spec.md §4)

```
composite = 0.50·NDCG@10 + 0.30·NDCG@50 + 0.15·MAP + 0.05·P@10
```
- **NDCG@10 (0.50)** dominates — top-10 *order* matters most; uses graded relevance tiers.
- **NDCG@50 (0.30)** — quality/order of top-50.
- **MAP (0.15)** — precision across relevance levels.
- **P@10 (0.05)** — fraction of top-10 that are **"relevant" = tier 3+** (spec §4 table).
- Scored **once** on the **hidden** full ground truth; no public split, no live
  leaderboard, no per-submission feedback (spec §4, §8).
- Composite tiebreak between teams: higher P@5, then P@10, then earlier timestamp (spec §4).

**Honeypots (spec §7):** ~80 candidates with subtly impossible profiles are forced to
**relevance tier 0** in the ground truth. **Honeypot rate > 10% in the top 100 ⇒
disqualified** at Stage 3 (spec §7; README "Key things to know"). Detecting/excluding
them is mandatory; the spec says a profile-reading system should avoid them naturally.

**Pipeline stages (spec §5):** 1 format validation → 2 scoring → 3 code reproduction +
honeypot check → 4 manual review (reasoning, methodology, git-history authenticity) →
5 defend-your-work interview.

---

## 5. Candidate schema (VERIFIED — candidate_schema.json; profiled in DATA_AUDIT.md)

Top-level required keys: `candidate_id`, `profile`, `career_history`, `education`,
`skills`, `redrob_signals`. Optional: `certifications`, `languages`.
(In the full 100k pool, **0 records were missing any required key** — DATA_AUDIT.md.)

- **candidate_id** — `^CAND_[0-9]{7}$`.
- **profile** (all required): `anonymized_name`, `headline`, `summary`, `location`,
  `country`, `years_of_experience` (0–50, float), `current_title`, `current_company`,
  `current_company_size` (enum 1-10 … 10001+), `current_industry`.
- **career_history** — array, 1–10 items. Each: `company`, `title`, `start_date`,
  `end_date` (string|null), `duration_months` (int≥0), `is_current` (bool), `industry`,
  `company_size` (enum), `description`. → *Descriptions are templated; see DATA_AUDIT.md.*
- **education** — 0–5 items: `institution`, `degree`, `field_of_study`, `start_year`,
  `end_year`, `grade` (nullable), `tier` (tier_1..tier_4|unknown).
- **skills** — array of `{name, proficiency∈{beginner,intermediate,advanced,expert},
  endorsements (int≥0), duration_months (int≥0)}`. `duration_months` = "months the
  candidate has used this skill" → **key honeypot signal**.
- **certifications** — `{name, issuer, year}`.
- **languages** — `{language, proficiency∈{basic,conversational,professional,native}}`.

### The 23 `redrob_signals` (VERIFIED — candidate_schema.json:138-238; redrob_signals_doc.md)
1 `profile_completeness_score` (0–100) · 2 `signup_date` · 3 `last_active_date` ·
4 `open_to_work_flag` (bool) · 5 `profile_views_received_30d` (int) ·
6 `applications_submitted_30d` (int) · 7 `recruiter_response_rate` (0–1) ·
8 `avg_response_time_hours` (≥0) · 9 `skill_assessment_scores` (dict skill→0-100) ·
10 `connection_count` (int) · 11 `endorsements_received` (int) ·
12 `notice_period_days` (0–180) · 13 `expected_salary_range_inr_lpa{min,max}` ·
14 `preferred_work_mode` (remote/hybrid/onsite/flexible) · 15 `willing_to_relocate` (bool) ·
16 `github_activity_score` (**−1**=no GitHub, else 0–100) · 17 `search_appearance_30d` (int) ·
18 `saved_by_recruiters_30d` (int) · 19 `interview_completion_rate` (0–1) ·
20 `offer_acceptance_rate` (**−1**=no history, else 0–1) · 21 `verified_email` (bool) ·
22 `verified_phone` (bool) · 23 `linkedin_connected` (bool).

Per redrob_signals_doc.md, these are intended as a **multiplier/modifier** on top of
skill-match scoring; "a perfect-on-paper candidate who hasn't logged in for 6 months and
has a 5% response rate is, for hiring purposes, not actually available."

---

## 6. AMBIGUITIES (spec vs. validator) — resolved decisions

1. **Tie-break (most important).** Spec §3 says you may break score ties "using a
   secondary signal from your model, **or** by candidate_id ascending." But the validator
   (lines 136-144) *hard-enforces* candidate_id-ascending **whenever two scores are
   exactly equal**. → **Decision:** make scores **strictly distinct floats** (bake every
   secondary signal into the score). If any exact tie remains, the tied block must be
   emitted candidate_id-ascending. Never rely on the validator tolerating a model-ordered
   tie. (User's brief already confirmed this reading.)
2. **candidate_id existence.** Spec §3 says every id "must exist in candidates.jsonl,"
   but the validator only checks the **regex + uniqueness**, not existence. → **Decision:**
   passing the local validator is necessary, not sufficient; we verify all 100 ids exist
   in the pool ourselves before submitting.
3. **Reasoning not validated locally.** Validator ignores column 4. → **Decision:** treat
   reasoning quality as a Stage-4 requirement (deterministic, grounded, varied), not an
   optional nicety.
4. **score = float only.** `float('nan')`/`'inf'` would parse, and `nan` comparisons slip
   past the monotonic check. → **Decision:** emit finite, in-range, strictly-decreasing
   scores only.
5. **Honeypots not checked by local validator.** The >10% DQ is a Stage-3 check, not in
   `validate_submission.py`. → **Decision:** run our own honeypot screen before submit.

---

## 7. Constraints asserted in the original plan but NOT found / corrected

- "≤16GB / CPU-only / no-API / 5-min" — **VERIFIED** (was ASSUMED in the plan; now sourced
  to submission_spec.md §3 table + metadata yaml:45-53).
- "Disk ≤ 5GB intermediate" — **VERIFIED** (spec §3 table); the plan didn't mention it.
- Plan's claim that the public brief "allowed LLM ranking/embeddings/APIs with no
  prescribed architecture" is **partly wrong for the *ranking step***: hosted APIs and
  GPUs are explicitly forbidden during ranking. LLMs/embeddings are allowed only as
  **offline precomputation** or as a **compact local** model within the CPU/5-min budget.
- The pitch-deck (`ProofRank.pdf`) "0.61→0.86 NDCG" numbers are **illustrative targets**,
  not measured — ignore as quality evidence.
