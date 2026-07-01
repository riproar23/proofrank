# ProofRank — Evidence-First Candidate Ranking

Ranks 100,000 candidates for Redrob AI's "Senior AI Engineer (Founding Team)" role
by career evidence of production retrieval, ranking, evaluation, and shipping — not
by listed skills or title alone. Runs fully offline on CPU in ~56 seconds.

---

## Complete beginner's guide

This guide assumes you have never used a terminal before and have no coding experience.
Follow every step in order and you will have everything running.

---

### Part 1 — What is a terminal and how do I open one?

A **terminal** (also called Command Prompt on Windows) is a text window where you type
instructions for your computer. Instead of clicking buttons, you type commands.

**How to open a terminal already pointed at the ProofRank folder (Windows):**

1. Open **File Explorer** — the folder icon in your taskbar, or press `Windows key + E`.
2. Navigate to wherever you downloaded or saved the **ProofRank** folder and open it.
   You should see files like `app.py`, `requirements.txt`, and a `Launch_ProofRank.bat`
   inside.
3. Look at the **address bar** at the very top of the File Explorer window. It shows
   something like `C:\Users\YourName\Downloads\ProofRank`. Click on it once — the text
   turns blue.
4. While that text is highlighted, type `cmd` (three letters, lowercase) and press
   **Enter**.
5. A black window called **Command Prompt** opens. You'll see a line ending in
   `C:\...\ProofRank>`. This means the terminal is already inside the ProofRank folder.
   **You don't need to cd anywhere** — it's already in the right place.

> **If step 4 didn't work:** close the window and try right-clicking anywhere inside the
> ProofRank folder (on the white background, not on a file). Look for **"Open in
> Terminal"**, **"Open PowerShell window here"**, or **"Open command window here"** and
> click it.

> **If you already have a terminal open but it's in the wrong folder:** type `cd ` (the
> letters c, d, and a space) then drag the ProofRank folder from File Explorer into the
> terminal window — the path fills in automatically. Press Enter.  
> For example: `cd C:\Users\YourName\Downloads\ProofRank`

---

### Part 2 — Check that Python is installed

In the terminal, type the following and press **Enter**:

```
python --version
```

**You should see:** `Python 3.9.x` or any higher number (3.10, 3.11, 3.12, etc.).

**If you see an error like `'python' is not recognized`:**
1. Go to https://www.python.org/downloads/ and click the big yellow **Download Python**
   button.
2. Run the installer. On the very first screen, tick the checkbox that says
   **"Add Python to PATH"** before clicking anything else. This is easy to miss.
3. Click **Install Now** and wait for it to finish.
4. Close your terminal window and open a new one (go back to Part 1 step 4).
5. Type `python --version` again — it should now show a version number.

---

### Part 3 — Put the data file in the right place

You need a file called **`candidates.jsonl`**. This is the candidate data file provided
for the challenge.

**What is a `.jsonl` file?** It's a plain text file where every line is one candidate's
data. You don't need to open or edit it — just place it in the right folder.

**Where to put it:**

Inside the ProofRank folder, there is a folder called **`data`**. Put `candidates.jsonl`
inside that `data` folder.

If you open File Explorer and look inside ProofRank, the result should look like this:

```
ProofRank\
├── data\
│     └── candidates.jsonl    ← the file goes here
├── app.py
├── requirements.txt
├── Launch_ProofRank.bat
└── ... (other files)
```

**How to put it there:** open the `data` folder in File Explorer, then copy and paste
(or drag and drop) `candidates.jsonl` into it.

**If you're placing the file from the terminal instead of File Explorer:**

```
copy "C:\path\to\wherever\candidates.jsonl" "C:\path\to\ProofRank\data\candidates.jsonl"
```

Replace `C:\path\to\wherever\` with the actual folder where `candidates.jsonl` currently
lives, and `C:\path\to\ProofRank\` with where you saved ProofRank.

---

### Part 4 — Install dependencies (first time only)

In the terminal, type this and press **Enter**:

```
pip install -r requirements.txt
```

**What this does:** downloads and installs all the code libraries that ProofRank needs.
Think of it like installing apps — but automatic.

**What you'll see:** a lot of text scrolling past with library names and progress bars.
This is normal. It may take 1–5 minutes depending on your internet speed.

**When it's done:** the scrolling stops and you see the `>` prompt again with no red
error messages.

**You only ever need to do this once.** Next time you use ProofRank, skip straight to
Part 5.

---

### Part 5 — Run the ranker (terminal method)

In the terminal, type this exactly and press **Enter**:

```
python -m src.rank --candidates data/candidates.jsonl --output output/final.csv
```

**What this does:** reads every candidate from `candidates.jsonl`, scores each one
against the job description, and saves the top 100 ranked candidates to a new file.

**What you'll see:** progress messages in the terminal. It takes about 56 seconds. Your
laptop fan may spin up — that's fine, the CPU is working.

**When it's done:** the terminal returns to the `>` prompt. No red error text means
success.

**What you get:** a file called `final.csv` inside the `output` folder inside ProofRank.
Full path: `ProofRank\output\final.csv`. This is the ranked shortlist and submission file.

---

### Part 6 — Check the output is correct

```
python data/validate_submission.py output/final.csv
```

**If everything worked, you'll see:**

```
Submission is valid.
```

If you see any other message or an error, re-run Part 5.

---

### Part 7 — Launch the interactive demo (the visual app)

The demo is a browser-based app that lets you explore the ranked candidates visually —
no terminal commands needed once it's running.

#### Option A — Double-click (easiest, Windows only)

Find **`Launch_ProofRank.bat`** in the ProofRank folder and **double-click it**. A
terminal window opens briefly, then your browser loads the demo automatically.

#### Option B — From the terminal

```
streamlit run app.py
```

**What happens:**
1. The terminal prints a few lines of startup text. Wait 5–10 seconds.
2. Your default browser opens automatically at `http://localhost:8501`.
3. If the browser doesn't open on its own, open Chrome, Edge, Firefox, or any browser
   yourself and type `http://localhost:8501` in the address bar, then press Enter.

**To stop the demo:** click on the terminal window that's running it and press
**Ctrl + C** (hold Ctrl and press C). The app will shut down.

**The demo works immediately even without running Parts 5–6.** It comes with a
pre-loaded snapshot of the top 100 candidates. Run Parts 5–6 first only if you want a
fresh ranking from your own data file.

---

### Part 8 — Using the demo (full guide to every feature)

Once the demo is open in your browser, here's everything you can do:

#### The sidebar (left panel)

The left panel controls what's displayed and lets you upload data.

**Show filter (All / Strong matches / Flagged):**
Three radio buttons at the top. "All" shows every ranked candidate. "Strong matches"
filters to only the top candidates the ranker is most confident about. "Flagged" isn't
a separate tab here — use the Flagged Profiles tab in the main area instead.

**Only show strong matches checkbox:**
Tick this to instantly hide weaker candidates and see only the top tier.

**Showing X of Y candidates:**
Tells you how many candidates are currently visible after your filters.

**Download shortlist (CSV):**
Click this button to download the ranked shortlist as a spreadsheet file you can open
in Excel or Google Sheets. It contains the candidate ID, rank, score, and the
plain-language reasoning for each person.

**Data section:**
Shows which dataset is currently loaded and how large it is (e.g. `candidates.jsonl
(465 MB)`). Below it is the Re-rank button.

**Re-rank current dataset:**
Click this to re-run the full ranking pipeline on whichever dataset is currently
active. The app updates automatically when it finishes — no restart needed.

**Upload a new dataset (expandable section):**
Click the arrow next to "Upload a new dataset" to expand it. You can drag and drop
one or more `.jsonl` or `.jsonl.gz` files. Each file shows its validation status and
two buttons:
- **Save to data/** — saves the file to the `data` folder without ranking it yet.
- **Save & Rank** — saves the file and immediately runs the ranker on it. The results
  appear in the main view when done.

**Manage datasets (expandable section):**
Click the arrow to see all `.jsonl` files in your `data` folder listed here.
- **Active** label — shown next to whichever dataset is currently being displayed.
- **Use this** button — switches to that dataset and re-ranks it immediately.
- **✕ button** — removes that dataset file from the `data` folder. The default
  `candidates.jsonl` cannot be removed.

**Add a candidate manually (expandable section):**
Fill in a candidate's details (name, title, company, years of experience, skills, etc.)
and click **Score this candidate**. The ranker scores them using the exact same logic as
the full pipeline and adds them to the shortlist. Useful for testing a specific person.

---

#### The main area (right side)

**Candidate Shortlist tab:**
Shows every ranked candidate as a card. Each card has:
- The rank number (#1, #2, etc.) on the left.
- The candidate's title, years of experience, company, location, and availability.
- The verdict (STRONG MATCH / GOOD FIT / BORDERLINE / WEAK) in the top-right corner.
- Click anywhere on the card to expand it and see the full evidence breakdown —
  what specific career history and skills drove the score, what the ranker liked, and
  what held them back.

**Flagged Profiles tab:**
Candidates the ranker excluded because they triggered integrity checks (fake-looking
profiles, impossible timelines, inflated experience). Each flagged card shows exactly
which check failed and why.

**How this works (expandable):**
Click "ℹ️ How this works" to read a plain-language explanation of the scoring model
without needing to look at any code.

**Status bar:**
Below the title, shows the last time the ranking was run, which data file it used, and
how many candidates were processed (e.g. `100,000 candidates → top 100`).

---

### Optional — run the proxy evaluation

Only needed if you want to measure ranking quality. Requires Part 5 to be done first.

```
python eval/eval.py
```

Compares the ranker's output against a 46-candidate hand-labeled set and prints
NDCG, MAP, and Precision scores. Results are also written to `results.md`.

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
