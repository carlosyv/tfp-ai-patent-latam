#!/usr/bin/env python3
"""
Panel C - Stage 3a: firm financials from SEC XBRL companyfacts (us-gaap + ifrs-full).

Concept fallback chains per tfp-ai/edgar_data_acquisition_guide.md. For each firm-FY
takes the annual (fp=FY, form 20-F/10-K) fact with the latest filing; records which
concept and currency unit was used (data-appendix requirement).

Usage:
  python3 xbrl_financials.py fetch [N]   # resumable: download companyfacts, extract, discard raw
  python3 xbrl_financials.py emit        # firm_financials.csv
"""
import csv, json, os, sys, time, gzip
import urllib.request

HERE=os.path.dirname(os.path.abspath(__file__))
CACHE=os.path.join(HERE,"cache")
JL=os.path.join(CACHE,"xbrl_facts.jsonl")
UA={"User-Agent":"Carlos Yalta, PhD research, jy9gvmhmks@privaterelay.appleid.com",
    "Accept-Encoding":"gzip"}

CHAINS = {
 "revenue":{"us-gaap":["RevenueFromContractWithCustomerExcludingAssessedTax","Revenues",
                       "RevenueFromContractWithCustomerIncludingAssessedTax","SalesRevenueNet"],
            "ifrs-full":["Revenue","RevenueFromContractsWithCustomers","RevenueFromSaleOfGoods"]},
 "cogs":{"us-gaap":["CostOfRevenue","CostOfGoodsAndServicesSold","CostOfGoodsSold"],
         "ifrs-full":["CostOfSales"]},
 "ppe_net":{"us-gaap":["PropertyPlantAndEquipmentNet"],
            "ifrs-full":["PropertyPlantAndEquipment"]},
 "assets":{"us-gaap":["Assets"],"ifrs-full":["Assets"]},
 "intangibles":{"us-gaap":["IntangibleAssetsNetExcludingGoodwill","FiniteLivedIntangibleAssetsNet"],
                "ifrs-full":["IntangibleAssetsOtherThanGoodwill"]},
 "goodwill":{"us-gaap":["Goodwill"],"ifrs-full":["Goodwill"]},
 "rnd":{"us-gaap":["ResearchAndDevelopmentExpense"],
        "ifrs-full":["ResearchAndDevelopmentExpense","ExpenditureOnResearchAndDevelopment"]},
 "liabilities":{"us-gaap":["Liabilities"],"ifrs-full":["Liabilities"]},
}
STOCK_VARS={"ppe_net","assets","intangibles","goodwill","liabilities"}  # instant; else duration

def get(url):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=25) as r:
        raw=r.read()
        if r.headers.get("Content-Encoding")=="gzip": raw=gzip.decompress(raw)
    time.sleep(0.12); return raw

def extract(cik, j):
    out=[]
    facts=j.get("facts",{})
    for var,tax_chain in CHAINS.items():
        for tax,concepts in tax_chain.items():
            node=facts.get(tax,{})
            for concept in concepts:
                c=node.get(concept)
                if not c: continue
                for unit,vals in c.get("units",{}).items():
                    for v in vals:
                        if v.get("form") not in ("20-F","10-K"): continue
                        if v.get("fp")!="FY": continue
                        end=v.get("end","")
                        if not ("2016-06-30"<=end<="2026-06-30"): continue
                        # duration facts: require a start ~1yr before end (annual, not quarterly)
                        if var not in STOCK_VARS:
                            st=v.get("start","")
                            if st:
                                try:
                                    from datetime import date
                                    d=(date.fromisoformat(end)-date.fromisoformat(st)).days
                                    if d<300 or d>400: continue
                                except: pass
                        out.append({"cik":cik,"var":var,"tax":tax,"concept":concept,
                                    "unit":unit,"end":end,"val":v.get("val"),
                                    "fy_label":v.get("fy"),"filed":v.get("filed","")})
                if any(o["var"]==var for o in out): break   # concept fallback: stop at first with data
            if any(o["var"]==var for o in out): break        # taxonomy: stop at first with data
    return out

def fetch(batch=25):
    ciks=[int(r["cik"]) for r in csv.DictReader(open(os.path.join(HERE,"firm_universe.csv")))]
    done=set()
    if os.path.exists(JL):
        for line in open(JL):
            try: done.add(json.loads(line)["cik"])
            except: pass
    todo=[c for c in ciks if c not in done]
    print("todo:",len(todo))
    n=0
    with open(JL,"a") as out:
        for cik in todo[:batch]:
            try:
                j=json.loads(get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"))
                rows=extract(cik,j)
                for r in rows: out.write(json.dumps(r)+"\n")
                if not rows: out.write(json.dumps({"cik":cik,"var":None})+"\n")  # mark done even if empty
                n+=1
            except Exception as e:
                print("FAIL",cik,repr(e)[:80])
    print(f"fetched {n}; remaining {len(todo)-n}")

def emit():
    uni={int(r["cik"]):r for r in csv.DictReader(open(os.path.join(HERE,"firm_universe.csv")))}
    best={}
    for line in open(JL):
        r=json.loads(line)
        if not r.get("var"): continue
        fy=int(r["end"][:4]) if int(r["end"][5:7])>6 else int(r["end"][:4])-1  # FY = year of end (Dec FYE) else prior
        k=(r["cik"],fy,r["var"])
        if k not in best or r["filed"]>best[k]["filed"]: best[k]=r
    firms=sorted({k[0] for k in best}); fys=sorted({k[1] for k in best})
    rows=[]
    for cik in firms:
        for fy in fys:
            if not any((cik,fy,v) in best for v in CHAINS): continue
            row={"cik":cik,"name":uni.get(cik,{}).get("name",""),
                 "country":uni.get(cik,{}).get("country_operating",""),"fy":fy}
            units=set()
            for var in CHAINS:
                b=best.get((cik,fy,var))
                row[var]=b["val"] if b else ""
                row[f"{var}_concept"]=f'{b["tax"]}:{b["concept"]}' if b else ""
                if b: units.add(b["unit"])
            row["units"]=";".join(sorted(units))
            rows.append(row)
    dst=os.path.join(HERE,"firm_financials.csv")
    cols=list(rows[0].keys())
    with open(dst,"w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=cols); w.writeheader(); w.writerows(rows)
    print(f"wrote {dst}: {len(rows)} firm-FY rows, {len(firms)} firms")

if __name__=="__main__":
    c=sys.argv[1] if len(sys.argv)>1 else "fetch"
    if c=="fetch": fetch(int(sys.argv[2]) if len(sys.argv)>2 else 25)
    else: emit()
