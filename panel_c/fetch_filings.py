#!/usr/bin/env python3
"""
Panel C - Stage 2a: download 20-F/10-K primary documents for the firm universe,
convert to plain text immediately (HTML stripped), store text only.

Usage:
  python3 fetch_filings.py manifest          # build filings manifest from cached submissions
  python3 fetch_filings.py fetch [SECONDS]   # process as many as fit in time budget (default 36)
Resumable: skips docs whose .txt already exists.
"""
import csv, json, os, re, sys, time, gzip
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request

HERE=os.path.dirname(os.path.abspath(__file__))
CACHE=os.path.join(HERE,"cache")
TXT=os.path.join(HERE,"filings_txt"); os.makedirs(TXT,exist_ok=True)
UA={"User-Agent":"Carlos Yalta, PhD research, jy9gvmhmks@privaterelay.appleid.com",
    "Accept-Encoding":"gzip"}

def manifest():
    rows=[]
    for u in csv.DictReader(open(os.path.join(HERE,"firm_universe.csv"))):
        cik=int(u["cik"])
        j=json.load(open(os.path.join(CACHE,f"sub_{cik:010d}.json")))
        rec=j["filings"]["recent"]
        for form,fdate,rdate,acc,doc in zip(rec["form"],rec["filingDate"],
                rec.get("reportDate",[""]*len(rec["form"])),
                rec["accessionNumber"],rec["primaryDocument"]):
            if form not in ("20-F","10-K"): continue
            if not rdate or not ("2017-01-01"<=rdate<="2025-12-31"): continue
            rows.append({"cik":cik,"name":u["name"],"country":u["country_operating"],
                "form":form,"filing_date":fdate,"report_date":rdate,"fy":rdate[:4],
                "accession":acc,"primary_doc":doc})
    # If multiple originals for same firm-FY (rare), keep latest filing
    best={}
    for r in rows:
        k=(r["cik"],r["fy"])
        if k not in best or r["filing_date"]>best[k]["filing_date"]: best[k]=r
    rows=sorted(best.values(),key=lambda r:(r["cik"],r["fy"]))
    with open(os.path.join(HERE,"filings_manifest.csv"),"w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print(f"manifest: {len(rows)} firm-FY filings for {len({r['cik'] for r in rows})} firms")

TAG=re.compile(rb"<[^>]{1,2000}>")
SCRIPT=re.compile(rb"<(script|style)[^>]*>.*?</\1>",re.S|re.I)
WS=re.compile(rb"[ \t\r\f\v]+")
NL=re.compile(rb"\n{3,}")
def html_to_text(b):
    b=SCRIPT.sub(b" ",b)
    b=TAG.sub(b" ",b)
    for ent,ch in ((b"&nbsp;",b" "),(b"&amp;",b"&"),(b"&lt;",b"<"),(b"&gt;",b">"),
                   (b"&#8217;",b"'"),(b"&#8220;",b'"'),(b"&#8221;",b'"'),(b"&#160;",b" ")):
        b=b.replace(ent,ch)
    b=WS.sub(b" ",b); b=NL.sub(b"\n\n",b)
    return b

def _one(r):
    acc=r["accession"].replace("-","")
    dst=os.path.join(TXT,f"{int(r['cik']):010d}_{r['fy']}_{r['form'].replace('/','')}.txt")
    if os.path.exists(dst): return "skip"
    url=f"https://www.sec.gov/Archives/edgar/data/{int(r['cik'])}/{acc}/{r['primary_doc']}"
    try:
        req=urllib.request.Request(url,headers=UA)
        with urllib.request.urlopen(req,timeout=18) as resp:
            raw=resp.read()
            if resp.headers.get("Content-Encoding")=="gzip":
                raw=gzip.decompress(raw)
        txt=html_to_text(raw)
        open(dst,"wb").write(txt)
        return "ok"
    except Exception as e:
        return f"FAIL {r['cik']} {r['fy']}: {e}"

def fetch(budget=36):
    rows=list(csv.DictReader(open(os.path.join(HERE,"filings_manifest.csv"))))
    todo=[r for r in rows if not os.path.exists(
        os.path.join(TXT,f"{int(r['cik']):010d}_{r['fy']}_{r['form'].replace('/','')}.txt"))]
    print(f"todo: {len(todo)}")
    t0=time.time(); done=fail=0
    with ThreadPoolExecutor(max_workers=20) as ex:
        futs={}
        it=iter(todo)
        # keep a rolling window of 8 tasks; stop submitting near budget
        for r in todo:
            if time.time()-t0>budget: break
            futs[ex.submit(_one,r)]=r
            if len(futs)>=20:
                d,_=next(as_completed(futs)),None
                res=d.result(); futs.pop(d)
                if res=="ok": done+=1
                elif res!="skip": fail+=1; print(res)
        for f in as_completed(futs):
            res=f.result()
            if res=="ok": done+=1
            elif res!="skip": fail+=1; print(res)
    left=len([r for r in rows if not os.path.exists(
        os.path.join(TXT,f"{int(r['cik']):010d}_{r['fy']}_{r['form'].replace('/','')}.txt"))])
    print(f"done {done} fail {fail} | remaining {left} | elapsed {time.time()-t0:.0f}s")

if __name__=="__main__":
    c=sys.argv[1] if len(sys.argv)>1 else "manifest"
    if c=="manifest": manifest()
    else: fetch(int(sys.argv[2]) if len(sys.argv)>2 else 36)
