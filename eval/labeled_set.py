"""
Local proxy evaluation labeled set — Checkpoint 4.

METHODOLOGY (anti-circular):
  Grades are assigned from JD rubric + career evidence dimensions (computed via
  career_evidence() on the raw JSONL), NOT from ranker output scores or ranks.
  Grade formula:
    4  sig_dims >= 4 AND YoE in [5,10] AND product company AND NOT honeypot
    3  strong evidence but one dimension partial (rnk=0.5) OR ranking present
       but missing retrieval/vector dims (CAND_0000031 archetype)
    2  retrieval+eval evidence present BUT ranking dim = 0 (semantic search /
       RAG only, not a shipping-ranking system owner)
    1  adjacent title (frontend, QA, etc.), ev~0, no ML/IR career evidence
    0  off-domain (HR/marketing/etc.) OR honeypot (data integrity violation)

46 candidates cover: elite T5s, plain-language T5 rescues (RISER cases),
mid-tier T4s, title-only demotions (FALLER cases), H2b honeypots caught by
final but missed by baseline, documented honeypots, and off-domain negatives.

Evidence dimensions (from src/evidence.py phrase-bank matching on descriptions):
  retrieval, vector, ranking, evaluation, shipping — each [0,1], max-pooled
  across career roles; "sig" = count of dims >= 0.5.
"""

# candidate_id -> relevance grade (0-4)
LABELED: dict[str, int] = {

    # ── Grade 4: elite fit ──────────────────────────────────────────────────
    # ev=495-500, sig_dims=5, YoE 6-9, product company
    "CAND_0008425": 4,  # Senior NLP Eng 7.8y Ola         – all 5 dims; semantic search 35M + ranking pipeline + eval
    "CAND_0079387": 4,  # AI Eng 6.9y Microsoft            – all 5 dims; recsys 10M + ranking + RAG + eval
    "CAND_0027691": 4,  # NLP Eng 6.5y Haptik             – all 5 dims; semantic search + LTR ranking + eval
    "CAND_0033861": 4,  # Senior NLP Eng 8.0y Mad St Den  – all 5 dims; RAG 50M + recsys marketplace + finetune
    "CAND_0030953": 4,  # Search Eng 7.8y Nykaa           – all 5 dims; XGB ranking + recsys 10M + semantic search
    "CAND_0046064": 4,  # Senior NLP Eng 8.9y Salesforce  – all 5 dims; RAG 50M + ranking pipeline + finetune
    "CAND_0088025": 4,  # Staff ML Eng 8.6y Yellow.ai     – all 5 dims; ranking pipeline + embedding migration + A/B [RISER]
    "CAND_0075249": 4,  # Applied ML Eng 6.2y Zomato      – all 5 dims; recsys 10M + semantic search
    "CAND_0081686": 4,  # Search Eng 6.0y Netflix         – all 5 dims; LTR + semantic search + recsys 10M
    "CAND_0081846": 4,  # Lead AI Eng 6.7y Razorpay       – all 5 dims; RAG 50M + semantic search 35M [RISER]
    "CAND_0018499": 4,  # Senior ML Eng 7.2y Zomato       – all 5 dims; RAG 50M + ranking pipeline
    "CAND_0062247": 4,  # AI Eng 7.3y Google              – all 5 dims; semantic search + LTR ranking
    "CAND_0055905": 4,  # Senior ML Eng 8.1y Flipkart     – all 5 dims; semantic search 35M + RAG 50M
    "CAND_0041669": 4,  # RecSys Eng 8.0y CRED            – all 5 dims; LTR + recsys 10M + RAG
    "CAND_0071974": 4,  # Senior AI Eng 7.8y Netflix      – all 5 dims; ranking pipeline + finetune + recsys
    "CAND_0093912": 4,  # Senior DS 5.3y Razorpay         – all 5 dims; LTR + semantic search + ranking
    "CAND_0005649": 4,  # Senior DS 7.4y Sarvam AI        – all 5 dims; semantic search + RAG + XGB ranking
    "CAND_0049896": 4,  # Search Eng 7.3y Unacademy       – all 5 dims; recsys 10M + RAG chatbot

    # ── Grade 3: strong fit, one dimension partial or YoE slightly off ──────
    "CAND_0080766": 3,  # Staff ML Eng 8.8y Salesforce    – ev=470 sig_dims=5 but rnk=0.50 (discovery/personalization
                         #   rather than explicit ranking model ownership); YoE 8.8 at upper edge
    "CAND_0000031": 3,  # RecSys Eng 6.0y Swiggy          – ev=337 rnk=1 eval=1 ship=0.67 BUT ret=0 vec=0;
                         #   has XGB ranking models + offline-online eval (JD's own labeled example)
                         #   but lacks the vector/retrieval infrastructure dimension

    # ── Grade 2: partial fit — retrieval+eval present BUT ranking dim = 0 ──
    # These are the key "false positive" cases: title suggests fit but career
    # descriptions show semantic-search / RAG-chatbot only, not ranking system ownership.
    "CAND_0069905": 2,  # Applied ML Eng 6.6y Sarvam AI   – ev=343 ret=1 vec=1 eval=1 rnk=0 [was baseline #1!]
    "CAND_0007009": 2,  # RecSys Eng 7.9y Wysa            – ev=343 ret=1 vec=1 eval=1 rnk=0 [was baseline #3!]
    "CAND_0027801": 2,  # NLP Eng 7.4y InMobi             – ev=343 ret=1 vec=1 eval=1 rnk=0
    "CAND_0074735": 2,  # Applied ML Eng 5.5y Rephrase.ai – ev=308 ret=1 vec=0.5 eval=1 rnk=0 (RAG+MLflow)
    "CAND_0052328": 2,  # RecSys Eng 6.5y Amazon          – ev=278 ret=1 vec=0.5 eval=1 rnk=0 [was baseline #4!]
    "CAND_0013536": 2,  # Applied ML Eng 14.1y Haptik     – ev=337 rnk=1 eval=1 ship=0.67 ret=0 vec=0;
                         #   ranking evidence present but YoE=14.1 far outside 5-9 band; same
                         #   archetype as CAND_0000031 but demoted by YoE

    # ── Grade 1: weak fit — adjacent title, no ML/IR career evidence ────────
    "CAND_0000011": 1,  # QA Engineer 2.0y                – ev=33 no ranking/retrieval career evidence
    "CAND_0000014": 1,  # Frontend Eng 8.4y               – ev=33 UI dev, no ML/IR work
    "CAND_0000018": 1,  # Frontend Eng 6.6y               – ev=33 UI dev, no ML/IR work
    "CAND_0000025": 1,  # Frontend Eng 7.3y               – ev=33 UI dev, no ML/IR work

    # ── Grade 0: honeypots (H2b — caught by final, MISSED by baseline) ──────
    # These have plausible AI titles and descriptions but expert-skill durations
    # that exceed total career length by >24 months (data integrity violation).
    "CAND_0020708": 0,  # Search Eng 4.2y         – H2b honeypot; ev=313 [was baseline #9!]
    "CAND_0057701": 0,  # RecSys Eng 4.1y         – H2b honeypot; ev=307 ranking [was baseline #28]
    "CAND_0064270": 0,  # Applied ML Eng 4.2y     – H2b honeypot; ev=337 ranking [was baseline #30]
    "CAND_0064904": 0,  # AI Eng 4.9y             – H2b honeypot; ev=430 4-dims [was baseline #32]
    "CAND_0065195": 0,  # Search Eng 5.1y         – H2b honeypot; ev=278 [was baseline #49]

    # ── Grade 0: documented dangerous honeypots (caught by H2b) ─────────────
    "CAND_0005260": 0,  # Senior NLP Eng 5.2y Netflix – H2b; ev=500 would rank top without detection
    "CAND_0003977": 0,  # RecSys Eng 4.6y Google      – H2b; ev=343
    "CAND_0009024": 0,  # Search Eng 5.2y Google      – H2b; ev=460 [was baseline #99]

    # ── Grade 0: off-domain (non-technical titles, clearly irrelevant) ───────
    "CAND_0000002": 0,  # Operations Manager 12.5y – off-domain; ev=33
    "CAND_0000004": 0,  # Marketing Manager 3.8y   – off-domain; ev=33
    "CAND_0000005": 0,  # Accountant 11.0y         – off-domain; ev=33
    "CAND_0000008": 0,  # Operations Manager 3.6y  – off-domain; ev=33
    "CAND_0000012": 0,  # Operations Manager 1.1y  – off-domain; ev=33
    "CAND_0000016": 0,  # Accountant 5.3y          – off-domain; ev=33
    "CAND_0000017": 0,  # Accountant 12.3y         – off-domain; ev=33
    "CAND_0000024": 0,  # HR Manager 7.5y          – off-domain; ev=33
}

# Convenience views
GRADE_COUNTS = {g: sum(1 for v in LABELED.values() if v == g) for g in range(5)}
N_RELEVANT = sum(1 for v in LABELED.values() if v >= 2)   # for MAP binary threshold

REASONING: dict[str, str] = {
    k: v.strip() for k, v in {
        "CAND_0088025": "RISER: Staff ML Eng title not canonical → missed by baseline; ev=495 all-5-dims ranking pipeline + A/B",
        "CAND_0081846": "RISER: Lead AI Eng title → missed by baseline; ev=500 RAG-50M + semantic search 35M",
        "CAND_0069905": "FALLER: Applied ML Eng title → baseline #1 (title-tier); ev=343 semantic search only, rnk=0",
        "CAND_0007009": "FALLER: RecSys Eng title → baseline #3; ev=343 RAG chatbot only, rnk=0",
        "CAND_0052328": "FALLER: RecSys Eng title → baseline #4; ev=278 RAG+MLflow only, rnk=0",
        "CAND_0000031": "JD example: 'must rank near top'; ranking+eval but missing retrieval/vector",
        "CAND_0020708": "H2b honeypot: baseline #9, caught by final (ev=313 but expert skill > career+24mo)",
        "CAND_0064904": "H2b honeypot: baseline #32, ev=430 4-dims but fabricated skill durations",
        "CAND_0005260": "Documented AI-titled honeypot; ev=500 would top baseline without H2b",
    }.items()
}
