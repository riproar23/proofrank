"""
Local proxy evaluation harness — Checkpoint 4.

Computes NDCG@10, NDCG@50, MAP@100, P@10, P@5 for baseline.csv and final.csv
against the hand-labeled set in eval/labeled_set.py.

Approach: TREC-pool style.
  - All 46 labeled candidates have known grades (0-4).
  - For each ranker output, find each labeled candidate's rank (1-100) or 101 if absent.
  - Sort labeled candidates by their rank → gives the "pool ranked list."
  - Compute metrics over this sorted order.

This avoids penalizing unlabeled candidates (which are mostly on-target grade 3-4
in both lists) and avoids the circularity of using ranker scores to assign grades.

NDCG uses gain = 2^grade - 1 (standard graded NDCG).
MAP and P@K use binary relevance threshold grade >= REL_THRESHOLD = 2.
"""

from __future__ import annotations
import csv
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from eval.labeled_set import LABELED, GRADE_COUNTS, N_RELEVANT

REL_THRESHOLD = 2        # grade >= 2 counts as "relevant" for binary metrics
BINARY_P_THRESHOLD = 3   # grade >= 3 for P@K (strong/elite fit)


# ─── I/O ──────────────────────────────────────────────────────────────────────

def load_ranks(csv_path: str) -> dict[str, int]:
    """Return {candidate_id: rank} from a ranked CSV."""
    ranks: dict[str, int] = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ranks[row["candidate_id"]] = int(row["rank"])
    return ranks


# ─── Metric helpers ───────────────────────────────────────────────────────────

def _dcg(grades: list[int], k: int) -> float:
    total = 0.0
    for i, g in enumerate(grades[:k], start=1):
        total += (2**g - 1) / math.log2(i + 1)
    return total


def ndcg(sorted_grades: list[int], k: int) -> float:
    """NDCG@k over the pool-ranked list (already sorted by output rank)."""
    dcg = _dcg(sorted_grades, k)
    ideal = sorted(sorted_grades, reverse=True)
    idcg = _dcg(ideal, k)
    return dcg / idcg if idcg > 0 else 0.0


def average_precision(sorted_grades: list[int]) -> float:
    """AP over the pool-ranked list using binary relevance (grade >= REL_THRESHOLD)."""
    n_rel = sum(1 for g in sorted_grades if g >= REL_THRESHOLD)
    if n_rel == 0:
        return 0.0
    precision_sum = 0.0
    found = 0
    for i, g in enumerate(sorted_grades, start=1):
        if g >= REL_THRESHOLD:
            found += 1
            precision_sum += found / i
    return precision_sum / n_rel


def precision_at_k(sorted_grades: list[int], k: int, threshold: int = BINARY_P_THRESHOLD) -> float:
    """P@k: fraction of top-k pool positions that are grade >= threshold."""
    top = sorted_grades[:k]
    if len(top) < k:
        return sum(1 for g in top if g >= threshold) / k  # penalize missing
    return sum(1 for g in top if g >= threshold) / k


# ─── Top-end separation analysis ─────────────────────────────────────────────

def top_end_report(csv_path: str, label: str) -> None:
    """Print grade distribution of top-10 and top-20 labeled candidates."""
    ranks = load_ranks(csv_path)
    pool = [(ranks.get(cid, 101), cid, grade)
            for cid, grade in LABELED.items()]
    pool.sort()
    print(f"\n{label} — top-20 labeled candidates by rank:")
    print(f"  {'Pos':>4} {'Rank':>6} {'Cand':>15} {'Grade':>6}  Note")
    for pos, (rank, cid, grade) in enumerate(pool[:20], 1):
        note = ""
        from eval.labeled_set import REASONING
        if cid in REASONING:
            note = REASONING[cid][:60]
        in_top = f"(rank {rank})" if rank <= 100 else "(not in top-100)"
        print(f"  {pos:>4} {in_top:>14} {cid}  {grade:>5}  {note}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def evaluate(csv_path: str) -> dict[str, float]:
    ranks = load_ranks(csv_path)
    # Sort labeled set by output rank (ascending); candidates not in top-100 → rank 101
    pool = [(ranks.get(cid, 101), cid, grade)
            for cid, grade in LABELED.items()]
    pool.sort()
    sorted_grades = [g for _, _, g in pool]

    return {
        "NDCG@10":  ndcg(sorted_grades, 10),
        "NDCG@50":  ndcg(sorted_grades, 46),   # K=total labeled (no benefit going past N)
        "MAP":      average_precision(sorted_grades),
        "P@10":     precision_at_k(sorted_grades, 10),
        "P@5":      precision_at_k(sorted_grades, 5),
    }


def main() -> None:
    root = Path(__file__).parent.parent
    base_path = root / "output" / "baseline.csv"
    final_path = root / "output" / "final.csv"

    print("=" * 68)
    print("LOCAL PROXY EVALUATION — Checkpoint 4")
    print("(Pool-based metrics over 46 hand-labeled candidates)")
    print(f"Grade distribution: {GRADE_COUNTS}")
    print(f"Relevant (grade>=2): {N_RELEVANT} | Strong (grade>=3): {GRADE_COUNTS[3]+GRADE_COUNTS[4]}")
    print("=" * 68)

    results: dict[str, dict[str, float]] = {}
    for label, path in [("BASELINE", base_path), ("FINAL", final_path)]:
        if not path.exists():
            print(f"\n{label}: {path} not found — skipping.")
            continue
        results[label] = evaluate(str(path))

    if len(results) < 2:
        print("Need both baseline.csv and final.csv to compare.")
        return

    print(f"\n{'Metric':<12} {'Baseline':>10} {'Final':>10} {'Delta':>10}")
    print("-" * 44)
    metrics = ["NDCG@10", "NDCG@50", "MAP", "P@5", "P@10"]
    for m in metrics:
        b = results["BASELINE"][m]
        f = results["FINAL"][m]
        delta = f - b
        sign = "+" if delta >= 0 else ""
        print(f"{m:<12} {b:>10.4f} {f:>10.4f} {sign}{delta:>9.4f}")

    print("\nNOTE: These are LOCAL PROXY metrics, not the hidden leaderboard score.")
    print("Pool approach: labeled candidates sorted by output rank; unlabeled treated")
    print("as not evaluated. NDCG gain = 2^grade - 1. MAP/P@K threshold: grade >= 2/3.")

    print("\n--- Top-end separation analysis ---")
    for label, path in [("BASELINE", base_path), ("FINAL", final_path)]:
        if path.exists():
            top_end_report(str(path), label)

    # Per-group breakdown
    print("\n--- Group-level precision (how many grade>=3 in each group's top slots) ---")
    for label, path in [("BASELINE", base_path), ("FINAL", final_path)]:
        if not path.exists():
            continue
        ranks = load_ranks(str(path))
        # How many grade-0 (honeypots/off-domain) ended up in top-100?
        hp_in_top = [(cid, ranks[cid]) for cid, g in LABELED.items()
                     if g == 0 and cid in ranks]
        hp_in_top.sort(key=lambda x: x[1])
        print(f"\n{label}: grade-0 candidates found in top-100: {len(hp_in_top)}")
        for cid, r in hp_in_top[:5]:
            print(f"  {cid} @ rank {r}")
        # How many grade-4 candidates are in top-20?
        g4_in_top20 = sum(1 for cid, g in LABELED.items()
                          if g == 4 and ranks.get(cid, 101) <= 20)
        print(f"  grade-4 candidates in top-20: {g4_in_top20}/{GRADE_COUNTS[4]}")
        # How many grade-2 candidates are in top-30?
        g2_in_top30 = sum(1 for cid, g in LABELED.items()
                          if g == 2 and ranks.get(cid, 101) <= 30)
        print(f"  grade-2 candidates in top-30 (false positives): {g2_in_top30}/{GRADE_COUNTS[2]}")


if __name__ == "__main__":
    main()
