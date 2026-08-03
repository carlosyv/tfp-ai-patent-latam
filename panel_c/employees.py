#!/usr/bin/env python3
"""
Panel C - Stage 3b: employee counts extracted from 20-F/10-K text.
Standard practice (counts are rarely XBRL-tagged). Collects all "N employees"-type
matches, keeps the median of plausible values (100..2,000,000) as the headcount and
stores min/max/n_matches for QA. Resumable via cache/employees.jsonl.
Usage: python3 employees.py run [SECONDS] | python3 employees.py emit
"""
import csv, glob, json, os, re, sys, time
HERE=os.path.dirname(os.path.abspath(__file__))
TXT=os.path.join(HERE,"filings_txt"); JL=os.path.join(HERE,"cache","employees.jsonl")

PATS=[re.compile(p,re.I) for p in [
 r"(?:approximately|about|around|had|have|employ(?:ed|s)?|total of|workforce of)\s+([\d][\d,\.]{2,12})\s+(?:full[- ]time\s+|part[- ]time\s+|permanent\s+)?employees",
 r"([\d][\d,\.]{2,12})\s+(?:full[- ]time|permanent)\s+employees",
 r"([\d][\d,\.]{2,12})\s+employees(?:\s+worldwide|\s+globally|,|\.|\s+as of)",
]]
def parse_num(s):
    s=s.replace(",","").rstrip(".")
    if "." in s:      # avoid decimals like "1.5" (usually not headcounts)
        parts=s.split(".")
        if len(parts[-1])==3: s="".join(parts)   # thousand separator style 1.234.567
        else: return None
    try: v=int(s)
    except: return None
    return v if 100<=v<=2_000_000 else None

def run(budget=32):
    done=set()
    if os.path.exists(JL):
        for l in open(JL):
            try: done.add(json.loads(l)["file"])
            except: pass
    todo=[f for f in sorted(glob.glob(os.path.join(TXT,"*.txt"))) if os.path.basename(f) not in done]
    print("todo:",len(todo)); t0=time.time(); n=0
    with open(JL,"a") as out:
        for fp in todo:
            if time.time()-t0>budget: break
            raw=open(fp,"rb").read().decode("utf-8","ignore")
            vals=[]
            for rx in PATS: vals+= [parse_num(m) for m in rx.findall(raw)]
            vals=[v for v in vals if v]
            vals.sort()
            rec={"file":os.path.basename(fp),"n_matches":len(vals),
                 "employees":vals[len(vals)//2] if vals else None,
                 "emp_min":vals[0] if vals else None,"emp_max":vals[-1] if vals else None}
            out.write(json.dumps(rec)+"\n"); n+=1
    print(f"processed {n}; remaining {len(todo)-n}")

def emit():
    rows=[]
    for l in open(JL):
        r=json.loads(l)
        cik,fy,form=r["file"].split("_")[0],r["file"].split("_")[1],r["file"].split("_")[2].split(".")[0]
        rows.append({"cik":int(cik),"fy":int(fy),"form":form,"employees":r["employees"] or "",
                     "emp_matches":r["n_matches"],"emp_min":r["emp_min"] or "","emp_max":r["emp_max"] or ""})
    rows.sort(key=lambda r:(r["cik"],r["fy"]))
    with open(os.path.join(HERE,"firm_employees.csv"),"w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    ok=sum(1 for r in rows if r["employees"])
    print(f"wrote firm_employees.csv: {len(rows)} rows, headcount found in {ok} ({ok/len(rows):.0%})")

if __name__=="__main__":
    c=sys.argv[1] if len(sys.argv)>1 else "run"
    if c=="run": run(int(sys.argv[2]) if len(sys.argv)>2 else 32)
    else: emit()
