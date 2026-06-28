# DATA_AUDIT.md — 100k candidate pool profile

> Profiled by streaming `candidates.jsonl` (487 MB) line-by-line from disk (`_profile_dataset.py`,
> `_refine.py`); the dataset was never loaded whole or pasted into context. **n = 100,000**
> candidates confirmed. Reference "today" = 2026-06-29. Runtime of the full streaming
> profile: **~15 s** on this CPU — a good sign the production ranker can hit the 5-min budget.

---

## 1. Integrity / field coverage
- **0** records missing any required top-level key (`candidate_id, profile, career_history,
  education, skills, redrob_signals`). Schema is clean.
- `candidate_id` values are `CAND_0000001 … CAND_0100000` (contiguous, zero-padded 7 digits).

## 2. Title distribution (the core signal)
47 distinct `current_title` values. The pool is **deliberately stacked with non-target
roles**:

| Band | Titles (count each ≈) | Pool share |
|---|---|---|
| **Non-technical / off-domain** (≈5.5–5.8k each) | Business Analyst (5833), HR Manager (5830), Mechanical Engineer (5791), Accountant (5764), Project Manager (5754), Customer Support (5750), Operations Manager (5744), Content Writer (5727), Sales Executive (5713), Civil Engineer (5702), Graphic Designer (5689), Marketing Manager (5524) | **~68%** |
| **Generic software** (≈2.7–3.5k each) | Software Engineer (3450), Full Stack (2873), Cloud (2836), Java (2809), .NET (2788), DevOps (2787), Mobile (2757), Frontend (2738), QA (2682) | ~26% |
| **Data-adjacent** (≈0.7k each) | Analytics Engineer (764), Data Engineer (744), Data Analyst (728), Backend Engineer (704), Senior Data Engineer (687), Senior Software Engineer (653) | ~4% |
| **On-target AI/ML (tiny)** | AI Research Engineer (153), Data Scientist (145), Senior SWE-ML (142), Computer Vision Engineer (132), Junior ML Engineer (131), AI Specialist (130), ML Engineer (167), **Recommendation Systems Engineer (26)**, plus rare Search/NLP/Applied-ML Engineers seen in honeypot sampling | **<1%** |

**Implication:** the true top-100 is drawn from a *very* small on-target subpopulation
(low thousands at most). The JD warns it expects "10 great matches, not 1000 maybes."

## 3. Years of experience
min 1.0, max 16.9, mean **7.17**, median **6.8**. Percentiles: p10 2.2, p25 3.9, p50 6.8,
p75 9.9, p90 13.0. **34,375** candidates fall in the JD's 5–9 soft band. (Band membership
is necessary-ish but nowhere near sufficient given the title distribution.)

## 4. Geography
- **India 75,113 (75%)**; rest spread over USA (9,978), Australia, Canada, UK, Germany,
  Singapore, UAE (~2.4–2.6k each).
- JD target Indian Tier-1 cities are well represented: Hyderabad 4283, Noida 4283,
  Bhubaneswar 4321, Jaipur 4268, Bangalore 4238, Kolkata 4230, Indore 4198, Pune 4186,
  Delhi 4161, Trivandrum 4151, Ahmedabad 4143, Chandigarh 4128, Coimbatore 4113, Vizag
  4093, Mumbai 4043, Gurgaon 4037, Chennai 4164. (Non-India locs ~2.4–2.6k each.)
- Location is a **minor tie-breaker** per JD (Noida/Pune preferred; Hyd/Mum/Delhi-NCR
  welcome; outside India case-by-case, no visa sponsorship).

## 5. Behavioral-signal coverage (the 23 signals)
- `skill_assessment_scores` **empty for 75,756 (76%)** → having *any* assessment is itself
  a quality/effort signal (only ~24% do).
- `github_activity_score == −1` (no GitHub) for **64,637 (65%)** → a real GitHub score is
  discriminating, esp. given JD's "external validation / OSS" language.
- `offer_acceptance_rate == −1` (no history) for **59,554 (60%)**.
- `recruiter_response_rate`: p10 0.14, p25 0.25, **median 0.44**, p75 0.62, p90 0.73 →
  wide spread; low end = "not actually available" per JD/signals doc.
- `last_active_date` staleness (days since active): p10 53, **median 138 (~4.5 mo)**,
  p90 239, p95 256 → many candidates are stale; the JD explicitly down-weights 6-mo-dormant
  profiles (≈ >180 days ⇒ ~top quartile of staleness).
- `notice_period_days`: p10 30, **median 90**, p90 150 (cap 180). JD: sub-30 ideal, buy-out
  ≤30, 30+ raises the bar.
- `profile_completeness_score`: p10 32.8, median 56.8, p90 80.4.
- `open_to_work` 35%, `willing_to_relocate` 29%, `verified_email` 72%, `verified_phone` 62%,
  `linkedin_connected` 36%. Skill count: mean 9.6, p90 14, max 23.

**Implication:** signals are a **multiplicative availability/credibility modifier**, not a
primary ranker (matches redrob_signals_doc.md). They separate "great + reachable" from
"great on paper but gone."

## 6. Career descriptions are TEMPLATED (critical)
- Across ~300k career roles there are **only 44 distinct `description` strings.** The 12
  non-technical archetypes each reuse the **same** template ~25k times (top template
  counts: 25515, 25290, 25237, 25207, 25164, …). Per-title there are only **~6–9** distinct
  description strings (e.g. Recommendation Systems Engineer → 6, ML Engineer → 6, Data
  Engineer → 6, HR Manager → 9, Marketing Manager → 9).
- The "specific" detail in any one description (e.g. the Swiggy ranking-models paragraph,
  the "$1.8M quota" sales paragraph) is **shared by thousands of candidates** — it is an
  **archetype label, not individual evidence.**

**Strategy implication (big):** this is **not** a free-text NLP problem. TF-IDF /
embeddings over `description` collapse to ~44 clusters ≈ the title taxonomy. So:
- Use title + career-archetype to assign an **evidence tier** (the dominant signal).
- Discriminate *within* a tier using structured features: years vs. JD band, skill
  coherence (do the listed retrieval/ranking/eval skills line up with the archetype, with
  real `duration_months`/`endorsements`/assessment backing — not keyword-stuffed),
  company type (product vs. consulting vs. research), recency of hands-on roles, and the
  behavioral modifier.
- A char+word **TF-IDF baseline is still worth building** (cheap, deterministic, satisfies
  every constraint) but expect it to behave as an archetype matcher; the lift comes from
  the structured tier + integrity + behavioral layers, exactly what the JD rewards.

## 7. The traps
**(a) Keyword stuffers.** **4,545** candidates have a **non-technical title** yet list
**≥4 core-AI skills** (embeddings/FAISS/Pinecone/IR/transformers/MLOps/etc.). Example
`CAND_0000004` — *Marketing Manager*, skills = Node.js/Content Writing/Six Sigma/SAP/Object
Detection, `skill_assessment_scores` empty, github −1, edu "B.Tech Machine Learning + PhD
Electronics." This is exactly the trap the JD calls out: "all the AI keywords… but whose
title is 'Marketing Manager' is not a fit." The sample_submission.csv **deliberately ranks
these high** (HR Managers / Content Writers / Designers with "9 AI core skills" at ranks
1–14) — it is a *bad* ranking, format reference only.

**(b) Plain-language Tier-5s.** The opposite trap: real fits whose skills section is modest
but whose **career history** shows the work. Example `CAND_0000031` — *Recommendation
Systems Engineer* @ Swiggy: coherent FAISS/Pinecone/Embeddings/IR/Sentence-Transformers/
MLOps skills with real durations + endorsements + assessments, description shows ranking
models + **offline-online correlation analysis** (= the eval must-have), response rate 0.91,
GitHub 32.6. Must rank near the top.

## 8. Honeypots — first-pass signatures (spec says ~80, forced to relevance 0)
Heuristics over the full pool (sharp rules only; `_refine.py`). Two of these are **exact
matches to the documented examples**:

| Rule | Hits | Notes |
|---|---|---|
| **H1** expert/advanced skill with `duration_months == 0` | **21** | Exact doc example: *"'expert' proficiency in 10 skills with 0 years used."* High precision. |
| **H3** role `duration_months` inconsistent with `start_date→end_date` (>4 mo off) | **33** | Exact doc example: *"8 years at a company founded 3 years ago."* High precision. |
| **H6** Σ career `duration_months` ≫ stated `years_of_experience` (>1.4×+18mo) | **22** | Overlaps with H3; impossible total tenure. |
| **H2b** `expert` skill `duration_months` > career length + 24 mo | **59** | Looser — likely some false positives (skill reused across overlapping roles); needs tuning. |
| H4 start_date > end_date / H5 future dates | 0 | None present. |

- **Sharp union (H1∪H2b∪H3∪H4∪H5∪H6) = 113.** Excluding the noisy H2b, **H1∪H3∪H6 ≈ 70–76**,
  which **brackets the documented ~80**. The exact honeypot set is in the hidden ground
  truth and unknowable; the *signatures* are confirmed and reliable.
- Sample flagged ids span both impossible non-tech profiles (e.g. `CAND_0005291` Business
  Analyst yoe 12.8, H3) and impossible *AI* profiles that would otherwise look like fits
  (e.g. `CAND_0003977` Recommendation Systems Eng, `CAND_0005260` Senior NLP Engineer,
  `CAND_0009024` Search Engineer — all H2b). The AI-titled honeypots are the dangerous ones:
  they'd be ranked high by a naïve system and trigger the >10% DQ.
- **Decision (Checkpoint 3):** detector = union of high-precision rules (H1, H3, H6) plus a
  *carefully thresholded* H2b, applied as a hard demotion to tier 0 / exclusion from top-100.
  Tune thresholds against the local audit set so we don't demote legitimate experts.

## 9. Net strategy implications
1. **Tier by title/career archetype first** (T0–T5, see `configs/jd_rubric.yaml`) — dominant
   signal because descriptions are archetypal, not individual.
2. **Within-tier ranking** from structured features: yoe vs 5–9 band, skill–career coherence
   with trust backing (duration/endorsements/assessment), product-vs-consulting-vs-research
   company history, recent hands-on code, evaluation evidence.
3. **Behavioral modifier** (availability/credibility) as a capped multiplier.
4. **Integrity layer** demotes honeypots + stuffers to keep top-100 honeypot rate ≪ 10%.
5. Everything **deterministic, offline, CPU, < 5 min** — the 15-s profile pass shows ample
   headroom.
