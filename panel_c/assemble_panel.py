#!/usr/bin/env python3
"""Panel C - Stage 3c: assemble firm panel = universe x FY + financials + AI exposure + employees."""
import csv, os
HERE=os.path.dirname(os.path.abspath(__file__))
def rd(f): return list(csv.DictReader(open(os.path.join(HERE,f))))

uni={int(r["cik"]):r for r in rd("firm_universe.csv")}
fin={(int(r["cik"]),int(r["fy"])):r for r in rd("firm_financials.csv")}
exp={(int(r["cik"]),int(r["fy"])):r for r in rd("firm_ai_exposure.csv")}
emp={(int(r["cik"]),int(r["fy"])):r for r in rd("firm_employees.csv")}

keys=sorted(set(fin)|set(exp))
rows=[]
for cik,fy in keys:
    if not (2017<=fy<=2025): continue
    u=uni.get(cik,{})
    f=fin.get((cik,fy),{}); e=exp.get((cik,fy),{}); m=emp.get((cik,fy),{})
    rows.append({
      "cik":cik,"name":u.get("name",""),"country":u.get("country_operating",""),
      "sic":u.get("sic",""),"sic_desc":u.get("sic_desc",""),"form":u.get("form_type",""),
      "status":u.get("status",""),"fy":fy,
      "revenue":f.get("revenue",""),"cogs":f.get("cogs",""),"assets":f.get("assets",""),
      "ppe_net":f.get("ppe_net",""),"intangibles":f.get("intangibles",""),
      "goodwill":f.get("goodwill",""),"rnd":f.get("rnd",""),"liabilities":f.get("liabilities",""),
      "currency":f.get("units",""),
      "revenue_concept":f.get("revenue_concept",""),
      "employees":m.get("employees",""),"emp_matches":m.get("emp_matches",""),
      "ai_exposure":e.get("exposure_nonrisk_per10k",""),
      "ai_exposure_total":e.get("exposure_total_per10k",""),
      "ai_total_mentions":e.get("ai_total",""),"filing_words":e.get("total_words",""),
    })
with open(os.path.join(HERE,"firm_panel.csv"),"w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

# coverage stats
n=len(rows)
def cov(k): return sum(1 for r in rows if r[k] not in ("",None))/n
print(f"firm_panel.csv: {n} firm-FY rows, {len({r['cik'] for r in rows})} firms, FY range "
      f"{min(r['fy'] for r in rows)}-{max(r['fy'] for r in rows)}")
for k in ("revenue","assets","ppe_net","intangibles","rnd","employees","ai_exposure"):
    print(f"  coverage {k:12s}: {cov(k):.0%}")
core=[r for r in rows if r["revenue"] and r["employees"] and r["ai_exposure"]!="" and 2017<=r["fy"]<=2024]
print(f"REGRESSION-READY rows (revenue+employees+exposure, FY2017-24): {len(core)} "
      f"({len({r['cik'] for r in core})} firms)")
from collections import Counter
print("currency mix (regression-ready):",dict(Counter(r['currency'] for r in core).most_common(8)))
