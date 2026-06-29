"""
One-time extraction script: dump evidence + metadata for labeled-set candidates.
Run from project root:  python eval/extract_for_labeling.py > scratchpad/label_data.txt
"""
import sys
import orjson
sys.path.insert(0, r"C:\Users\vassi\OneDrive\Documents\ProofRank")
from src.evidence import career_evidence
from src.rank import detect_honeypot, is_keyword_stuffer, CONSULTING_TOKENS

PATH = r"C:\Users\vassi\OneDrive\Documents\ProofRank\data\candidates.jsonl"

# ── Candidates to label (by hand-picked ID) ──────────────────────────────────
# Final top-10 (expect grade 4)
FINAL_TOP10 = [
    "CAND_0008425", "CAND_0079387", "CAND_0027691", "CAND_0033861",
    "CAND_0030953", "CAND_0046064", "CAND_0088025", "CAND_0075249",
    "CAND_0081686", "CAND_0081846",
]
# Final mid-range (expect grade 3-4)
FINAL_MID = [
    "CAND_0018499",  # rank 16  Senior ML Eng Zomato
    "CAND_0062247",  # rank 17  AI Eng Google
    "CAND_0055905",  # rank 20  Senior ML Eng Flipkart
    "CAND_0041669",  # rank 22  RecSys Eng CRED
    "CAND_0071974",  # rank 24  Senior AI Eng Netflix
    "CAND_0093912",  # rank 25  Senior DS Razorpay
    "CAND_0005649",  # rank 58  Senior DS Sarvam AI
    "CAND_0080766",  # rank 59  Staff ML Salesforce
    "CAND_0049896",  # rank 60  Search Eng Unacademy
]
# Final bottom-of-100 (expect grade 2-3)
FINAL_BOTTOM = [
    "CAND_0069905",  # rank 88  Applied ML Sarvam AI  (was baseline #1!)
    "CAND_0007009",  # rank 89  RecSys Wysa           (was baseline #3!)
    "CAND_0027801",  # rank 90  NLP Eng InMobi
    "CAND_0000031",  # rank 94  RecSys Swiggy (JD example)
    "CAND_0013536",  # rank 99  Applied ML Haptik 14.1y
    "CAND_0074735",  # rank 100 Applied ML Rephrase.ai
]
# In baseline top-100 but NOT in final top-100 (title-only; expect grade 1)
BASELINE_ONLY = [
    "CAND_0052328",  # baseline #4   RecSys Amazon – RAG+MLflow, no ranking
    "CAND_0020708",  # baseline #9   Search Eng 4.2y PolicyBazaar
    "CAND_0057701",  # baseline #28  RecSys Eng 4.1y Verloop.io
    "CAND_0064270",  # baseline #30  Applied ML 4.2y Verloop.io
    "CAND_0064904",  # baseline #32  AI Eng 4.9y LinkedIn
    "CAND_0065195",  # baseline #49  Search Eng 5.1y CRED
]
# Honeypots (expect grade 0)
HONEYPOTS = ["CAND_0005260", "CAND_0003977", "CAND_0009024"]

ALL_TARGETS = set(FINAL_TOP10 + FINAL_MID + FINAL_BOTTOM + BASELINE_ONLY + HONEYPOTS)

# ── Off-domain candidates: we'll collect a few during the scan ────────────────
OFF_DOMAIN_TITLES = {
    "HR Manager", "Marketing Manager", "Sales Executive", "Content Writer",
    "Graphic Designer", "Operations Manager", "Accountant",
}
GENERIC_TITLES = {"Java Developer", ".NET Developer", "QA Engineer", "Frontend Engineer"}

off_domain: dict[str, dict] = {}
generic: dict[str, dict] = {}

found: dict[str, dict] = {}


def company_type(record: dict) -> str:
    career = record.get("career_history", [])
    consulting = sum(1 for r in career
                     if any(tok in (r.get("company") or "").lower() for tok in CONSULTING_TOKENS))
    if consulting == len(career) and career:
        return "consulting-only"
    research_tokens = {"university", "research lab", "institute", "iit", "nit", "college",
                       "academia", "research center", "r&d"}
    research = sum(1 for r in career
                   if any(tok in (r.get("company") or "").lower() for tok in research_tokens))
    if research == len(career) and career:
        return "research-only"
    return "product"


with open(PATH, "rb") as fh:
    for raw in fh:
        raw = raw.strip()
        if not raw:
            continue
        rec = orjson.loads(raw)
        cid = rec["candidate_id"]
        title = rec.get("profile", {}).get("current_title", "")

        if cid in ALL_TARGETS:
            ev_score, ev_dims = career_evidence(rec)
            found[cid] = {
                "title": title,
                "yoe": rec.get("profile", {}).get("years_of_experience", 0),
                "company_type": company_type(rec),
                "is_hp": detect_honeypot(rec),
                "is_stuffer": is_keyword_stuffer(rec),
                "ev_score": ev_score,
                "ev_dims": ev_dims,
                "descs": [(r.get("title", "?"), (r.get("description") or "")[:220])
                          for r in rec.get("career_history", [])],
            }

        if title in OFF_DOMAIN_TITLES and cid not in off_domain and len(off_domain) < 8:
            ev_score, ev_dims = career_evidence(rec)
            off_domain[cid] = {"title": title,
                               "yoe": rec.get("profile", {}).get("years_of_experience", 0),
                               "ev_score": ev_score, "ev_dims": ev_dims,
                               "is_hp": detect_honeypot(rec)}

        if title in GENERIC_TITLES and cid not in generic and len(generic) < 4:
            ev_score, ev_dims = career_evidence(rec)
            generic[cid] = {"title": title,
                            "yoe": rec.get("profile", {}).get("years_of_experience", 0),
                            "ev_score": ev_score, "ev_dims": ev_dims}

        if (len(found) == len(ALL_TARGETS)
                and len(off_domain) >= 8
                and len(generic) >= 4):
            break

print(f"Found {len(found)}/{len(ALL_TARGETS)} targets | "
      f"{len(off_domain)} off-domain | {len(generic)} generic")

GROUPS = [
    ("FINAL TOP-10", FINAL_TOP10),
    ("FINAL MID", FINAL_MID),
    ("FINAL BOTTOM", FINAL_BOTTOM),
    ("BASELINE ONLY", BASELINE_ONLY),
    ("HONEYPOTS", HONEYPOTS),
]

for group_name, ids in GROUPS:
    print(f"\n{'='*70}")
    print(f"GROUP: {group_name}")
    print('='*70)
    for cid in ids:
        if cid not in found:
            print(f"  {cid}: NOT FOUND")
            continue
        d = found[cid]
        dims = d["ev_dims"]
        sig_dims = sum(1 for k in ("retrieval","vector","ranking","evaluation","shipping")
                       if dims.get(k, 0) >= 0.5)
        print(f"\n  {cid}: {d['title']} | yoe={d['yoe']:.1f} | co={d['company_type']} | "
              f"hp={d['is_hp']} | ev={d['ev_score']:.0f} | sig_dims={sig_dims}")
        print(f"    dims: ret={dims['retrieval']:.2f} vec={dims['vector']:.2f} "
              f"rnk={dims['ranking']:.2f} eval={dims['evaluation']:.2f} "
              f"ship={dims['shipping']:.2f} hedge={dims['hedge']:.2f}")
        for role_title, desc in d["descs"]:
            print(f"    [{role_title}]: {desc[:180]}")

print(f"\n{'='*70}")
print("OFF-DOMAIN SAMPLES")
print('='*70)
for cid, d in off_domain.items():
    print(f"  {cid}: {d['title']} | yoe={d['yoe']:.1f} | hp={d['is_hp']} | ev={d['ev_score']:.0f}")

print(f"\n{'='*70}")
print("GENERIC TITLE SAMPLES")
print('='*70)
for cid, d in generic.items():
    print(f"  {cid}: {d['title']} | yoe={d['yoe']:.1f} | ev={d['ev_score']:.0f}")
