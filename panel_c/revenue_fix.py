#!/usr/bin/env python3
"""Stage 4a: extended revenue chains for firms where the generic chain found nothing
(banks: effective-interest revenue; telecoms/others: additional ifrs-full variants).
Diagnoses available concepts too. Writes cache/rev_fix.jsonl. Resumable."""
import csv, json, os, sys, time, gzip, urllib.request
HERE=os.path.dirname(os.path.abspath(__file__)); CACHE=os.path.join(HERE,"cache")
JL=os.path.join(CACHE,"rev_fix.jsonl")
UA={"User-Agent":"Carlos Yalta, PhD research, jy9gvmhmks@privaterelay.appleid.com","Accept-Encoding":"gzip"}
EXT={"ifrs-full":["RevenueFromContractsWithCustomers","RevenueFromRenderingOfServices",
      "RevenueFromRenderingOfTelecommunicationServices","RevenueFromSaleOfGoods",
      "InterestRevenueCalculatedUsingEffectiveInterestMethod","RevenueFromInterest",
      "InterestIncomeOnLoansAndAdvancesToCustomers","OperatingRevenue","RevenueAndOperatingIncome"],
     "us-gaap":["RevenuesNetOfInterestExpense","InterestAndDividendIncomeOperating",
      "InterestIncomeOperating","RegulatedAndUnregulatedOperatingRevenue"]}
def get(u):
    r=urllib.request.Request(u,headers=UA)
    with urllib.request.urlopen(r,timeout=25) as x:
        raw=x.read()
        if x.headers.get("Content-Encoding")=="gzip": raw=gzip.decompress(raw)
    time.sleep(0.12); return raw
def run(batch=12):
    ciks=json.load(open(os.path.join(CACHE,"rev_missing_ciks.json")))
    done=set()
    if os.path.exists(JL):
        for l in open(JL):
            try: done.add(json.loads(l)["cik"])
            except: pass
    todo=[c for c in ciks if c not in done]
    print("todo:",len(todo)); n=0
    with open(JL,"a") as out:
        for cik in todo[:batch]:
            try:
                j=json.loads(get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"))
                facts=j.get("facts",{}); wrote=False
                for tax,concepts in EXT.items():
                    for concept in concepts:
                        c=facts.get(tax,{}).get(concept)
                        if not c: continue
                        for unit,vals in c.get("units",{}).items():
                            for v in vals:
                                if v.get("form") not in ("20-F","10-K") or v.get("fp")!="FY": continue
                                end=v.get("end","")
                                if not ("2016-06-30"<=end<="2026-06-30"): continue
                                st=v.get("start","")
                                if st:
                                    from datetime import date
                                    try:
                                        d=(date.fromisoformat(end)-date.fromisoformat(st)).days
                                        if d<300 or d>400: continue
                                    except: pass
                                out.write(json.dumps({"cik":cik,"var":"revenue","tax":tax,
                                    "concept":concept,"unit":unit,"end":end,"val":v.get("val"),
                                    "filed":v.get("filed","")})+"\n"); wrote=True
                        if wrote: break
                    if wrote: break
                if not wrote:
                    # diagnostic: list revenue-ish concepts available
                    avail=[f"{t}:{k}" for t in ("ifrs-full","us-gaap") for k in facts.get(t,{})
                           if any(s in k.lower() for s in ("revenue","interestincome","interestrevenue"))][:12]
                    out.write(json.dumps({"cik":cik,"var":None,"avail":avail})+"\n")
                n+=1
            except Exception as e: print("FAIL",cik,repr(e)[:60])
    print(f"fetched {n}; remaining {len(todo)-n}")
if __name__=="__main__":
    run(int(sys.argv[2]) if len(sys.argv)>2 else (int(sys.argv[1]) if len(sys.argv)>1 else 12))
