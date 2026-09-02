#!/usr/bin/env python3
"""
AI-capability composite index (opening report §5.6) + 2017–2024 robustness re-estimation.

Components (z-scores over the 2017–24 estimation sample, equal weights):
  1. ln AI patent stock per capita (LN_AI, Panel A)
  2. ln AI publications (OECD.AI 'All' field)
  3. National AI-strategy adoption indicator (dates from opening report §1.1.2;
     Mexico coded 0 through 2024 — strategy remained draft)
  4. Digital infrastructure (mean z of WDI broadband + internet; documented substitute
     for ITU IDI, which was discontinued 2018–2022)
  5. Government AI readiness (Oxford Insights) — OPTIONAL: auto-included if
     data/oxford_ai_readiness.csv exists (columns: CountryName,Year,score)

Outputs: output/results/composite_index.csv, composite_robustness_results.csv
"""
import os
import numpy as np, pandas as pd

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root (this script lives in analysis/)
OUT=os.path.join(ROOT,"output","results")

STRATEGY={"Argentina":2019,"Brazil":2021,"Chile":2021,"Colombia":2019,"Costa Rica":2024,
          "Dominican Republic":2024,"Mexico":9999,"Peru":2021,"Uruguay":2020}

def z(s): return (s-s.mean())/s.std()

def build():
    A=pd.read_csv(os.path.join(OUT,"merged_dissertation_v5.csv"))
    A=A[(A.Year>=2017)&(A.Year<=2024)].copy()
    pub=pd.read_csv(os.path.join(ROOT,"data/cat-ai-patents-country-data/publications_yearly_articles.csv"))
    pub=pub[(pub.field=="All")].groupby(["country","year"]).num_articles.sum().reset_index()
    pub.columns=["CountryName","Year","pubs"]
    A=A.merge(pub,on=["CountryName","Year"],how="left")
    A["ln_pubs"]=np.log1p(A["pubs"])
    A["strategy"]=[1 if y>=STRATEGY.get(c,9999) else 0 for c,y in zip(A.CountryName,A.Year)]
    comp={"c_pat":z(A["LN_AI"]),"c_pub":z(A["ln_pubs"]),
          "c_str":z(A["strategy"]),
          "c_inf":(z(A["INF_broadband"])+z(A["INF_internet"]))/2}
    ox=os.path.join(ROOT,"data","oxford_ai_readiness.csv")
    n_comp=4
    if os.path.exists(ox):
        o=pd.read_csv(ox); A=A.merge(o,on=["CountryName","Year"],how="left")
        comp["c_ox"]=z(A["score"]); n_comp=5
        print("Oxford component INCLUDED")
    else:
        print("Oxford component not present (data/oxford_ai_readiness.csv) — 4-component composite")
    C=pd.concat(comp,axis=1)
    A=pd.concat([A.reset_index(drop=True),C.reset_index(drop=True)],axis=1)
    A["AI_COMPOSITE"]=C.mean(axis=1).to_numpy()
    # simple PCA check (first component loadings)
    M=C.dropna().to_numpy(); M=(M-M.mean(0))/M.std(0)
    w,v=np.linalg.eigh(np.cov(M.T)); pc1=v[:,-1]*np.sign(v[:,-1].sum())
    print("PCA-1 loadings:",dict(zip(C.columns,pc1.round(3))),"| var share:",round(w[-1]/w.sum(),3))
    A[["Country","CountryName","Year","AI_COMPOSITE"]+list(C.columns)].to_csv(
        os.path.join(OUT,"composite_index.csv"),index=False)
    return A

def demean2(df,cols,i="Country",t="Year",iters=80):
    X=df[cols].astype(float).copy()
    for _ in range(iters):
        X=X-X.groupby(df[i]).transform("mean"); X=X-X.groupby(df[t]).transform("mean")
    return X
def ols_cl(y,X,cl):
    XtXi=np.linalg.pinv(X.T@X); b=XtXi@X.T@y; u=y-X@b
    meat=sum(np.outer(X[cl==g].T@u[cl==g],X[cl==g].T@u[cl==g]) for g in np.unique(cl))
    G=len(np.unique(cl)); n,k=X.shape
    V=XtXi@meat@XtXi*(G/(G-1))*((n-1)/max(n-k,1))
    return b,np.sqrt(np.diag(V))

CTRL=["LNPGDP_constant2015","OPEN_trade","LN_HC_index","FDI_inflows","GOV_consumption","URB_urban_pop"]
def reg(df,xvar,label,rows,inter=None):
    need=["TFP",xvar]+CTRL+([inter] if inter else [])
    d=df.dropna(subset=[c for c in need if c in df.columns]).copy()
    d["lnTFP"]=np.log(d.TFP)
    cols=["lnTFP",xvar]+CTRL
    if inter:
        mz=(d[inter]-d[inter].mean())/d[inter].std()
        d["XM"]=d[xvar]*mz; d["MZ"]=mz; cols+=["XM","MZ"]
    dm=demean2(d,cols)
    xs=[xvar]+(["XM"] if inter else [])
    X=np.column_stack([dm[xs].to_numpy(),dm[CTRL+( ["MZ"] if inter else [])].to_numpy()])
    b,se=ols_cl(dm["lnTFP"].to_numpy(),X,d.Country.to_numpy())
    for i,name in enumerate(xs):
        rows.append({"model":label,"var":name,"coef":b[i],"se":se[i],"t":b[i]/se[i],"n":len(d)})

if __name__=="__main__":
    A=build(); rows=[]
    reg(A,"LN_AI","H1 patents-only, 2017-24",rows)
    reg(A,"AI_COMPOSITE","H1 composite, 2017-24",rows)
    reg(A,"AI_COMPOSITE","H3 composite x RuleOfLaw",rows,inter="INST_rule_of_law")
    reg(A,"AI_COMPOSITE","H4 composite x Broadband",rows,inter="INF_broadband")
    reg(A,"LN_AI","H3 patents x RuleOfLaw (compare)",rows,inter="INST_rule_of_law")
    reg(A,"LN_AI","H4 patents x Broadband (compare)",rows,inter="INF_broadband")
    R=pd.DataFrame(rows); R.to_csv(os.path.join(OUT,"composite_robustness_results.csv"),index=False)
    print(R.to_string(index=False,float_format=lambda v:f"{v: .4f}" if isinstance(v,float) else str(v)))
