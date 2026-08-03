#!/usr/bin/env python3
"""
Panel C - Stage 2b: text-based AI-exposure measure from 20-F/10-K filings.
Dictionary follows Babina, Fedyk, He & Hodson (2024 JFE) core AI terms plus applied
terms; bare "AI" token counted only as a diagnostic (noisy). Risk-factor-section
mentions separated from the rest (boilerplate concern); primary exposure = non-risk
mentions per 10,000 words.
Resumable: appends to cache/ai_counts.jsonl, skips processed files.
Usage: python3 ai_exposure.py run [SECONDS] | python3 ai_exposure.py emit
"""
import csv, json, os, re, sys, time, glob

HERE=os.path.dirname(os.path.abspath(__file__))
TXT=os.path.join(HERE,"filings_txt"); CACHE=os.path.join(HERE,"cache")
JL=os.path.join(CACHE,"ai_counts.jsonl")

CORE = ["artificial intelligence","machine learning","deep learning",
        r"neural network\w*","natural language processing","computer vision",
        r"large language model\w*","generative ai","reinforcement learning",
        "speech recognition","image recognition"]
APPLIED = [r"chatbot\w*","predictive analytics",
           r"recommendation (?:algorithm|system|engine)\w*",
           "ai-powered","ai-driven","ai-based","ai-enabled",
           r"ai (?:model|technolog|solution|tool|capabilit)\w*",
           "facial recognition","autonomous driving","robotic process automation"]
RX_CORE=[re.compile(p,re.I) for p in CORE]
RX_APPL=[re.compile(p,re.I) for p in APPLIED]
RX_BARE=re.compile(r"\bAI\b")
WORD=re.compile(r"\b\w+\b")

RISK_START=re.compile(r"(item\s*3\.?\s*d\.?\s*[\.\-–—:]?\s*risk factors|item\s*1a\.?\s*[\.\-–—:]?\s*risk factors|^\s*risk factors\s*$)",re.I|re.M)
RISK_END=re.compile(r"(item\s*4\.?\s*[\.\-–—:]?\s*information on|item\s*1b\.?\s*[\.\-–—:]?\s*unresolved|item\s*2\.?\s*[\.\-–—:]?\s*propert)",re.I)

def counts(text):
    c_core=sum(len(rx.findall(text)) for rx in RX_CORE)
    c_appl=sum(len(rx.findall(text)) for rx in RX_APPL)
    return c_core,c_appl

def process(fp):
    raw=open(fp,"rb").read().decode("utf-8","ignore")
    total_words=len(WORD.findall(raw))
    core,appl=counts(raw)
    bare=len(RX_BARE.findall(raw))
    # risk-factor section span (best-effort)
    m=RISK_START.search(raw)
    risk_core=risk_appl=0; risk_found=0
    if m:
        e=RISK_END.search(raw,m.end())
        seg=raw[m.start():(e.start() if e else min(len(raw),m.start()+800_000))]
        risk_core,risk_appl=counts(seg); risk_found=1
    return {"total_words":total_words,"ai_core":core,"ai_applied":appl,"ai_bare":bare,
            "risk_found":risk_found,"ai_core_risk":risk_core,"ai_applied_risk":risk_appl}

def run(budget=32):
    done=set()
    if os.path.exists(JL):
        for line in open(JL):
            try: done.add(json.loads(line)["file"])
            except: pass
    files=sorted(glob.glob(os.path.join(TXT,"*.txt")))
    todo=[f for f in files if os.path.basename(f) not in done]
    print("todo:",len(todo))
    t0=time.time(); n=0
    with open(JL,"a") as out:
        for fp in todo:
            if time.time()-t0>budget: break
            r=process(fp); r["file"]=os.path.basename(fp)
            out.write(json.dumps(r)+"\n"); n+=1
    print(f"processed {n} in {time.time()-t0:.0f}s; remaining {len(todo)-n}")

def emit():
    uni={int(r["cik"]):r for r in csv.DictReader(open(os.path.join(HERE,"firm_universe.csv")))}
    rows=[]
    for line in open(JL):
        r=json.loads(line)
        cik,fy,form=r["file"].split("_")[0],r["file"].split("_")[1],r["file"].split("_")[2].split(".")[0]
        u=uni.get(int(cik),{})
        ai_total=r["ai_core"]+r["ai_applied"]
        ai_risk=r["ai_core_risk"]+r["ai_applied_risk"]
        nonrisk=max(ai_total-ai_risk,0)
        w=max(r["total_words"],1)
        rows.append({"cik":int(cik),"name":u.get("name",""),"country":u.get("country_operating",""),
            "fy":fy,"form":form,"total_words":r["total_words"],
            "ai_core":r["ai_core"],"ai_applied":r["ai_applied"],"ai_total":ai_total,
            "ai_bare_diag":r["ai_bare"],"risk_section_found":r["risk_found"],
            "ai_in_risk":ai_risk,"ai_nonrisk":nonrisk,
            "exposure_nonrisk_per10k":round(nonrisk*10000/w,4),
            "exposure_total_per10k":round(ai_total*10000/w,4)})
    rows.sort(key=lambda r:(r["cik"],r["fy"]))
    dst=os.path.join(HERE,"firm_ai_exposure.csv")
    with open(dst,"w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print(f"wrote {dst}: {len(rows)} firm-FY rows")

if __name__=="__main__":
    c=sys.argv[1] if len(sys.argv)>1 else "run"
    if c=="run": run(int(sys.argv[2]) if len(sys.argv)>2 else 32)
    else: emit()
