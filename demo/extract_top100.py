"""
One-time data prep: extract top-100 candidates from candidates.jsonl
(streamed) and bake scoring info into demo/top100_data.json.

Run from project root:
  python demo/extract_top100.py
  python demo/extract_top100.py --candidates data/candidates_uploaded.jsonl
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import orjson

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.rank import score_candidate_final

FINAL_CSV = ROOT / "output" / "final.csv"
JSONL = ROOT / "data" / "candidates.jsonl"
OUT = ROOT / "demo" / "top100_data.json"


def load_ranked_meta() -> dict[str, dict]:
    ranked: dict[str, dict] = {}
    with open(FINAL_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ranked[row["candidate_id"]] = {
                "rank": int(row["rank"]),
                "score": float(row["score"]),
                "reasoning": row["reasoning"],
            }
    return ranked


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path,
                        default=ROOT / "data" / "candidates.jsonl",
                        help="Path to candidates JSONL file (default: data/candidates.jsonl)")
    args = parser.parse_args()
    jsonl_path = args.candidates

    ranked = load_ranked_meta()
    print(f"Loaded {len(ranked)} ranked entries from {FINAL_CSV}")

    records: dict[str, dict] = {}
    with open(jsonl_path, "rb") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            rec = orjson.loads(raw)
            cid = rec["candidate_id"]
            if cid not in ranked:
                continue
            _, info = score_candidate_final(rec)
            meta = ranked[cid]
            records[cid] = {
                "candidate_id": cid,
                "rank": meta["rank"],
                "score": meta["score"],
                "reasoning": meta["reasoning"],
                # scoring breakdown
                "ev_score": info["ev_score"],
                "ev_dims": info["ev_dims"],
                "title_prior": info["title_prior"],
                "skill_coherence": info["skill_coherence"],
                "yoe_fit": info["yoe_fit"],
                "nice": info["nice"],
                "penalty": info["penalty"],
                "hard": info["hard"],
                "tiebreak": info.get("tiebreak", 0.0),
                "behavioral": info["behavioral"],
                "flags": info["flags"],
                # candidate profile (display only — trimmed to save space)
                "profile": rec.get("profile", {}),
                "career_history": [
                    {
                        "title": r.get("title", ""),
                        "company": r.get("company", ""),
                        "start_date": r.get("start_date", ""),
                        "end_date": r.get("end_date", ""),
                        "is_current": r.get("is_current", False),
                        "duration_months": r.get("duration_months", 0),
                        "description": (r.get("description") or "")[:350],
                    }
                    for r in rec.get("career_history", [])
                ],
                "skills": [
                    {
                        "name": s.get("name", ""),
                        "proficiency": s.get("proficiency", ""),
                        "duration_months": s.get("duration_months", 0),
                        "endorsements": s.get("endorsements", 0),
                    }
                    for s in rec.get("skills", [])[:12]
                ],
                "redrob_signals": rec.get("redrob_signals", {}),
            }
            if len(records) == len(ranked):
                break

    ordered = sorted(records.values(), key=lambda x: x["rank"])
    OUT.write_text(json.dumps(ordered, indent=2), encoding="utf-8")
    print(f"Saved {len(ordered)} candidates to {OUT}  "
          f"({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
