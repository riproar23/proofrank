"""Stream-profile the 100k candidate pool. Never loads the whole file into memory.
Writes a JSON summary to _audit_summary.json and prints a concise digest."""
import json, datetime, hashlib, re, collections, statistics

D = r'C:/Users/vassi/Downloads/[PUB] India_runs_data_and_ai_challenge/[PUB] India_runs_data_and_ai_challenge/India_runs_data_and_ai_challenge'
PATH = D + '/candidates.jsonl'
TODAY = datetime.date(2026, 6, 29)

def pdate(s):
    if not s: return None
    try: return datetime.date.fromisoformat(s[:10])
    except Exception: return None

def months_between(a, b):
    return (b.year - a.year) * 12 + (b.month - a.month)

REQ_TOP = ["candidate_id","profile","career_history","education","skills","redrob_signals"]
AI_CORE = {"embeddings","information retrieval","sentence transformers","faiss","pinecone",
    "weaviate","qdrant","milvus","elasticsearch","opensearch","bm25","vector search",
    "semantic search","learning to rank","recommendation systems","ranking","retrieval",
    "rag","hugging face transformers","llm","nlp","transformers","mlflow","mlops"}

n=0
field_missing=collections.Counter()
title_ctr=collections.Counter()
country_ctr=collections.Counter()
loc_ctr=collections.Counter()
yoe_list=[]
nskill_list=[]
desc_hash=collections.Counter()
# behavioral coverage
gh_neg1=0; offer_neg1=0; assess_empty=0; open_work=0; reloc=0
resp_list=[]; notice_list=[]; complete_list=[]
last_active_days=[]
verified_email=0; verified_phone=0; linkedin=0
# honeypot heuristics
H=collections.Counter()
hp_examples=collections.defaultdict(list)
hp_union=set()
# ai-skill on non-tech title
TECH_TITLE = re.compile(r'engineer|developer|scientist|ml|ai|data|architect|researcher|programmer|sde|devops|backend|frontend|full ?stack', re.I)
nontech_ai_stuffer=0

with open(PATH, 'r', encoding='utf-8') as f:
    for line in f:
        line=line.strip()
        if not line: continue
        n+=1
        c=json.loads(line)
        for k in REQ_TOP:
            if k not in c: field_missing[k]+=1
        p=c.get('profile',{})
        title=p.get('current_title','').strip()
        title_ctr[title]+=1
        country_ctr[p.get('country','?')]+=1
        loc_ctr[p.get('location','?')]+=1
        yoe=p.get('years_of_experience',0) or 0
        yoe_list.append(yoe)
        skills=c.get('skills',[]) or []
        nskill_list.append(len(skills))
        ch=c.get('career_history',[]) or []
        rs=c.get('redrob_signals',{}) or {}

        # behavioral
        if rs.get('github_activity_score',0)==-1: gh_neg1+=1
        if rs.get('offer_acceptance_rate',0)==-1: offer_neg1+=1
        if not rs.get('skill_assessment_scores'): assess_empty+=1
        if rs.get('open_to_work_flag'): open_work+=1
        if rs.get('willing_to_relocate'): reloc+=1
        if rs.get('verified_email'): verified_email+=1
        if rs.get('verified_phone'): verified_phone+=1
        if rs.get('linkedin_connected'): linkedin+=1
        if 'recruiter_response_rate' in rs: resp_list.append(rs['recruiter_response_rate'])
        if 'notice_period_days' in rs: notice_list.append(rs['notice_period_days'])
        if 'profile_completeness_score' in rs: complete_list.append(rs['profile_completeness_score'])
        la=pdate(rs.get('last_active_date'))
        if la: last_active_days.append((TODAY-la).days)

        # description templating
        for r in ch:
            d=(r.get('description') or '').strip().lower()
            d=re.sub(r'\s+',' ',d)
            if d: desc_hash[hashlib.md5(d.encode()).hexdigest()]+=1

        # ai-stuffer on nontech title
        ai_skill_ct=sum(1 for s in skills if s.get('name','').lower() in AI_CORE)
        if title and not TECH_TITLE.search(title) and ai_skill_ct>=4:
            nontech_ai_stuffer+=1

        # ---- honeypot heuristics ----
        cid=c['candidate_id']; flagged=False
        # H1: expert/advanced skill with 0 months used
        for s in skills:
            if s.get('proficiency') in ('expert','advanced') and s.get('duration_months',999)==0:
                H['H1_expert_skill_0mo']+=1
                if len(hp_examples['H1_expert_skill_0mo'])<8: hp_examples['H1_expert_skill_0mo'].append(cid)
                flagged=True; break
        # H2: skill used longer than entire career
        for s in skills:
            dm=s.get('duration_months')
            if dm is not None and yoe and dm > yoe*12 + 12:
                H['H2_skill_dur_gt_career']+=1
                if len(hp_examples['H2_skill_dur_gt_career'])<8: hp_examples['H2_skill_dur_gt_career'].append(cid)
                flagged=True; break
        # date-based per role
        date_bad=False; sum_dur=0; future=False; start_gt_end=False
        for r in ch:
            sd=pdate(r.get('start_date')); ed=pdate(r.get('end_date'))
            dm=r.get('duration_months',0) or 0; sum_dur+=dm
            if sd and sd>TODAY: future=True
            if ed and ed>TODAY: future=True
            if sd and ed and sd>ed: start_gt_end=True
            end_eff = ed if ed else TODAY
            if sd:
                mb=months_between(sd,end_eff)
                if abs(mb-dm)>4: date_bad=True
        if date_bad:
            H['H3_date_duration_mismatch']+=1
            if len(hp_examples['H3_date_duration_mismatch'])<8: hp_examples['H3_date_duration_mismatch'].append(cid)
            flagged=True
        if start_gt_end:
            H['H4_start_after_end']+=1
            if len(hp_examples['H4_start_after_end'])<8: hp_examples['H4_start_after_end'].append(cid)
            flagged=True
        if future:
            H['H5_future_date']+=1
            if len(hp_examples['H5_future_date'])<8: hp_examples['H5_future_date'].append(cid)
            flagged=True
        # H6: total career months far exceed stated yoe
        if yoe and sum_dur > yoe*12*1.4 + 18:
            H['H6_career_sum_gt_yoe']+=1
            if len(hp_examples['H6_career_sum_gt_yoe'])<8: hp_examples['H6_career_sum_gt_yoe'].append(cid)
            flagged=True
        if flagged: hp_union.add(cid)

def pct(lst,*ps):
    lst=sorted(lst); out={}
    for q in ps:
        if not lst: out[q]=None; continue
        i=min(len(lst)-1,int(q/100*len(lst)))
        out[q]=lst[i]
    return out

dup_descs=sum(1 for h,ct in desc_hash.items() if ct>1)
dup_rows=sum(ct for h,ct in desc_hash.items() if ct>1)
top_desc=desc_hash.most_common(5)

summary={
 'n':n,
 'field_missing':dict(field_missing),
 'top_titles':title_ctr.most_common(35),
 'distinct_titles':len(title_ctr),
 'top_countries':country_ctr.most_common(15),
 'india_count':country_ctr.get('India',0),
 'target_city_locs':{k:loc_ctr.get(k,0) for k in list(loc_ctr)},
 'yoe':{'min':min(yoe_list),'max':max(yoe_list),'mean':round(statistics.mean(yoe_list),2),
        'pct':pct(yoe_list,10,25,50,75,90),'in_5_9':sum(1 for y in yoe_list if 5<=y<=9)},
 'nskill':{'mean':round(statistics.mean(nskill_list),2),'pct':pct(nskill_list,10,50,90),'max':max(nskill_list)},
 'behavioral':{
   'github_neg1':gh_neg1,'offer_acc_neg1':offer_neg1,'assess_empty':assess_empty,
   'open_to_work':open_work,'willing_relocate':reloc,
   'verified_email':verified_email,'verified_phone':verified_phone,'linkedin':linkedin,
   'resp_rate_pct':pct(resp_list,10,25,50,75,90),
   'notice_pct':pct(notice_list,10,50,90),
   'completeness_pct':pct(complete_list,10,50,90),
   'last_active_days_pct':pct(last_active_days,10,50,90,95),
 },
 'desc_templating':{'unique_descs':len(desc_hash),'desc_appearing_multi':dup_descs,
                    'rows_in_dup_descs':dup_rows,'top_desc_counts':[ct for _,ct in top_desc]},
 'nontech_ai_stuffer_ge4':nontech_ai_stuffer,
 'honeypot_firstpass':{'by_rule':dict(H),'union_count':len(hp_union),
                       'examples':{k:v for k,v in hp_examples.items()}},
}
json.dump(summary, open('_audit_summary.json','w',encoding='utf-8'), indent=1)
print('DONE n=',n)
print('honeypot union (first pass):', len(hp_union))
print('by rule:', dict(H))
print('nontech AI stuffers (>=4 core AI skills):', nontech_ai_stuffer)
print('dup descriptions: descs_multi=%d rows=%d top_counts=%s'%(dup_descs,dup_rows,[ct for _,ct in top_desc]))
print('india=',country_ctr.get('India',0),'/',n)
print('yoe 5-9:',summary['yoe']['in_5_9'])
print('assess_empty=',assess_empty,'github_neg1=',gh_neg1)
