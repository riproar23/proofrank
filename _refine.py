import json, datetime, re, collections
D = r'C:/Users/vassi/Downloads/[PUB] India_runs_data_and_ai_challenge/[PUB] India_runs_data_and_ai_challenge/India_runs_data_and_ai_challenge'
PATH=D+'/candidates.jsonl'; TODAY=datetime.date(2026,6,29)
def pdate(s):
    try: return datetime.date.fromisoformat(s[:10])
    except: return None
def mb(a,b): return (b.year-a.year)*12+(b.month-a.month)

desc=collections.Counter()
desc_by_title=collections.defaultdict(set)
sharp=set(); rules=collections.Counter()
hp_detail=[]
n=0
with open(PATH,encoding='utf-8') as f:
 for line in f:
  line=line.strip()
  if not line: continue
  n+=1; c=json.loads(line); cid=c['candidate_id']
  p=c.get('profile',{}); yoe=p.get('years_of_experience',0) or 0
  ch=c.get('career_history',[]) or []; skills=c.get('skills',[]) or []
  for r in ch:
    d=re.sub(r'\s+',' ',(r.get('description') or '').strip())
    if d:
      desc[d]+=1
      desc_by_title[p.get('current_title','')].add(d)
  flags=[]
  for s in skills:
    if s.get('proficiency') in ('expert','advanced') and s.get('duration_months',999)==0:
      flags.append('H1_expert0mo'); break
  date_bad=start_gt_end=future=False; sumd=0
  for r in ch:
    sd=pdate(r.get('start_date') or ''); ed=pdate(r.get('end_date') or '') if r.get('end_date') else None
    dm=r.get('duration_months',0) or 0; sumd+=dm
    if sd and sd>TODAY: future=True
    if ed and ed>TODAY: future=True
    if sd and ed and sd>ed: start_gt_end=True
    eff=ed if ed else TODAY
    if sd and abs(mb(sd,eff)-dm)>4: date_bad=True
  if date_bad: flags.append('H3_datemismatch')
  if start_gt_end: flags.append('H4_start_gt_end')
  if future: flags.append('H5_future')
  if yoe and sumd>yoe*12*1.4+18: flags.append('H6_sum_gt_yoe')
  # skill duration > career, but TIGHTER: >24mo beyond career AND proficiency expert
  for s in skills:
    dm=s.get('duration_months')
    if dm is not None and yoe and s.get('proficiency')=='expert' and dm>yoe*12+24:
      flags.append('H2b_expertskill_gt_career'); break
  if flags:
    for fl in flags: rules[fl]+=1
    sharp.add(cid)
    if len(hp_detail)<40:
      hp_detail.append((cid,p.get('current_title',''),yoe,flags))

print('n=',n)
print('distinct descriptions total:',len(desc))
print('TOP DESCRIPTIONS (count | first 90 chars):')
for d,ct in desc.most_common(8):
  print(f'  {ct:6} | {d[:90]}')
print()
print('avg distinct descs per title (sample):')
for t in ['Recommendation Systems Engineer','ML Engineer','Data Engineer','HR Manager','Marketing Manager']:
  print(f'  {t:32} -> {len(desc_by_title.get(t,[]))} distinct desc strings')
print()
print('SHARP honeypot union (H1,H2b,H3,H4,H5,H6):',len(sharp))
print('by rule:',dict(rules))
print('sample honeypots:')
for cid,t,y,fl in hp_detail[:25]:
  print(f'  {cid} | {t[:26]:26} | yoe={y} | {fl}')
json.dump({'distinct_desc':len(desc),'sharp_union':len(sharp),'rules':dict(rules),
  'top_desc':[(ct,d[:140]) for d,ct in desc.most_common(8)],
  'hp_detail':hp_detail}, open('_refine_out.json','w',encoding='utf-8'),indent=1)
