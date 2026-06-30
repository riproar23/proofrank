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
import shutil
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
                # scoring breakdown (use .get so honeypot candidates don't crash)
                "ev_score": info.get("ev_score", 0),
                "ev_dims": info.get("ev_dims", {}),
                "title_prior": info.get("title_prior", 0),
                "skill_coherence": info.get("skill_coherence", 0),
                "yoe_fit": info.get("yoe_fit", 0),
                "nice": info.get("nice", 0),
                "penalty": info.get("penalty", 0),
                "hard": info.get("hard", 0),
                "tiebreak": info.get("tiebreak", 0.0),
                "behavioral": info.get("behavioral", 0),
                "flags": info.get("flags", []),
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

    flagged_src = ROOT / "output" / "flagged.json"
    flagged_dst = ROOT / "demo" / "flagged.json"
    if flagged_src.exists():
        shutil.copy2(flagged_src, flagged_dst)
        n = len(json.loads(flagged_dst.read_text(encoding="utf-8")))
        print(f"Copied flagged.json ({n} entries) to {flagged_dst}")


if __name__ == "__main__":
    main()
