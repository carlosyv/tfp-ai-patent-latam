#!/usr/bin/env python3
"""Stage 4b: clean analysis panel.
- overlay extended-chain revenue recoveries (cache/rev_fix.jsonl)
- employee plausibility filter (USD rev/emp in [$5k, $10M]; fall back to emp_max/min; else missing)
- FX conversion (WB PA.NUS.FCRF year-avg) + US-CPI deflation (2017=1); IAS-29 flag for ARS
- moderators: intangible intensity, R&D intensity, size
Output: firm_panel_clean.csv
"""
import csv, json, os
import pandas as pd, numpy as np
HERE=os.path.dirname(os.path.abspath(__file__))

p=pd.read_csv(os.path.join(HERE,"firm_panel.csv"))
fx=pd.read_csv(os.path.join(HERE,"fx_rates.csv"))

# --- overlay revenue fixes (best per cik-fy by filed date)
fixes={}
with open(os.path.join(HERE,"cache","rev_fix.jsonl")) as f:
    for line in f:
        r=json.loads(line)
        if not r.get("var"): continue
        fy=int(r["end"][:4]) if int(r["end"][5:7])>6 else int(r["end"][:4])-1
        k=(r["cik"],fy)
        if k not in fixes or r["filed"]>fixes[k]["filed"]: fixes[k]=r
n=0
for k,r in fixes.items():
    m=(p.cik==k[0])&(p.fy==k[1])
    if m.any() and p.loc[m,"revenue"].isna().all():
        p.loc[m,"revenue"]=r["val"]; p.loc[m,"revenue_concept"]=f'{r["tax"]}:{r["concept"]}'
        cur=p.loc[m,"currency"].fillna("")
        p.loc[m,"currency"]=np.where(cur=="",r["unit"],cur)
        n+=1
print("revenue rows recovered:",n)

# --- currency: primary unit = first token; USD-share firms fine
p["cur"]=p["currency"].fillna("").str.split(";").str[0].replace("","USD")
fxp=fx.pivot(index="year",columns="currency",values="lcu_per_usd")
uscpi=fxp["USCPI"]; base=uscpi.loc[2017]
uscpi=uscpi.reindex(range(2016,2026)).ffill()   # 2025 = carry 2024 (WB lag), documented
def to_usd(row,col):
    v=row[col]
    if pd.isna(v): return np.nan
    cur=row["cur"]; y=min(max(int(row["fy"]),2016),2025)
    if cur=="USD": usd=v
    else:
        rate=fxp.get(cur,pd.Series(dtype=float)).get(y,np.nan)
        usd=v/rate if pd.notna(rate) else np.nan
    return usd/(uscpi.loc[y]/base)              # real 2017 USD
for col in ("revenue","assets","ppe_net","intangibles","goodwill","rnd","cogs"):
    p[f"{col}_usd"]=p.apply(lambda r: to_usd(r,col),axis=1)
p["ias29_ars"]=(p["cur"]=="ARS").astype(int)

# --- employees plausibility
emp_raw=pd.read_csv(os.path.join(HERE,"firm_employees.csv"))
p=p.merge(emp_raw[["cik","fy","emp_min","emp_max"]],on=["cik","fy"],how="left")
def emp_ok(e,rev): 
    return pd.notna(e) and e>0 and pd.notna(rev) and 5e3 <= rev/e <= 1e7
def fix_emp(r):
    rev=r["revenue_usd"]
    if pd.isna(rev): return r["employees"]     # can't test; keep
    for cand in (r["employees"],r["emp_max"],r["emp_min"]):
        if emp_ok(cand,rev): return cand
    return np.nan
p["employees_clean"]=p.apply(fix_emp,axis=1)
dropped=(p["employees"].notna()&p["employees_clean"].isna()).sum()
swapped=((p["employees_clean"].notna())&(p["employees_clean"]!=p["employees"])).sum()
print(f"employees: swapped-to-alt {swapped-dropped if swapped>=dropped else swapped}, set-missing {dropped}")

# --- outcomes and moderators
p["lprod"]=np.log(p["revenue_usd"]/p["employees_clean"])
p["intang_int"]=(p["intangibles_usd"].fillna(0)+p["goodwill_usd"].fillna(0))/p["assets_usd"]
p.loc[p["assets_usd"].isna(),"intang_int"]=np.nan
p["rnd_int"]=p["rnd_usd"]/p["revenue_usd"]
p["size"]=np.log(p["assets_usd"])
p["sic2"]=p["sic"].astype(str).str[:2]
p["exp"]=p["ai_exposure"].fillna(np.nan)
p["exp_tot"]=p["ai_exposure_total"]

out=p[(p.fy>=2017)&(p.fy<=2024)].copy()
out.to_csv(os.path.join(HERE,"firm_panel_clean.csv"),index=False)
core=out.dropna(subset=["lprod","exp"])
print(f"firm_panel_clean.csv: {len(out)} rows | regression-ready lprod+exposure: {len(core)} rows, {core.cik.nunique()} firms")
print("by country:",core.groupby('country').size().to_dict())
