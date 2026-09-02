#!/usr/bin/env python3
"""
Macro shift-share (Bartik) IV — opening report §4.7 / committee decision D6.

Implementable version with in-repo data: OECD.AI field-level publications
(fields: AI Safety, Computer Vision, LLMs, NLP, Robotics; 2016–2024).
  shares  s_{i,f,0} : country i's field composition in the base period (2016–2017)
  shifts  G_{f,t}   : ln global publications in field f at t, EXCLUDING all 17
                      LatAm countries (leave-region-out)
  Z_{i,t} = Σ_f s_{i,f,0} · G_{f,t}
Instruments LN_AI_pub in Panel B (primary) and LN_AI (patent stock) in the
Panel A 2016–2024 subwindow (cross-measure relevance tested via first stage).
Full-window Panel A patent-field Bartik requires a WIPO by-technology-field pull
(documented as pending).

Outputs: output/results/bartik_iv_results.csv + rotemberg_weights.csv
numpy-only estimators (verify with linearmodels on full install).
"""
import os
import numpy as np, pandas as pd

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root (this script lives in analysis/)
OUT=os.path.join(ROOT,"output","results")
LATAM=["Argentina","Brazil","Chile","Colombia","Costa Rica","Dominican Republic","Mexico","Peru",
 "Uruguay","Bolivia","Ecuador","El Salvador","Guatemala","Honduras","Nicaragua","Panama","Paraguay"]
FIELDS=["AI Safety","Computer Vision","Large language models","Natural Language Processing","Robotics"]

def build_z():
    d=pd.read_csv(os.path.join(ROOT,"data/cat-ai-patents-country-data/publications_yearly_articles.csv"))
    d=d[(d.field.isin(FIELDS))&(d.year.between(2016,2024))]
    base=d[(d.year.between(2016,2017))&(d.country.isin(LATAM))]
    s=base.groupby(["country","field"]).num_articles.sum().unstack(fill_value=0)
    s=s.reindex(columns=FIELDS,fill_value=0)
    s=(s.T/s.sum(axis=1).replace(0,np.nan)).T          # shares sum to 1 per country
    g=d[~d.country.isin(LATAM)].groupby(["field","year"]).num_articles.sum().unstack(0)
    G=np.log(g.reindex(columns=FIELDS))                # ln global ex-LatAm level by field-year
    z=pd.DataFrame({(c,y):(s.loc[c]*G.loc[y]).sum()
                    for c in s.index for y in G.index},index=["Z"]).T
    z.index=pd.MultiIndex.from_tuples(z.index,names=["CountryName","Year"])
    return z.reset_index(), s, G

def demean2(df,cols,i="Country",t="Year",iters=80):
    X=df[cols].astype(float).copy()
    for _ in range(iters):
        X=X-X.groupby(df[i]).transform("mean")
        X=X-X.groupby(df[t]).transform("mean")
    return X

def ols_cl(y,X,cl):
    XtXi=np.linalg.pinv(X.T@X); b=XtXi@X.T@y; u=y-X@b
    meat=sum(np.outer(X[cl==g].T@u[cl==g],X[cl==g].T@u[cl==g]) for g in np.unique(cl))
    G=len(np.unique(cl)); n,k=X.shape
    V=XtXi@meat@XtXi*(G/(G-1))*((n-1)/max(n-k,1))
    return b,np.sqrt(np.diag(V))

def tsls(y,x,z,W,cl):
    Z=np.column_stack([z]+([W] if W is not None else []))
    X=np.column_stack([x]+([W] if W is not None else []))
    b1,se1=ols_cl(x,Z,cl); F=(b1[0]/se1[0])**2
    Pz=Z@np.linalg.pinv(Z.T@Z)@Z.T
    b=np.linalg.pinv(X.T@Pz@X)@X.T@Pz@y
    u=y-X@b; A=np.linalg.pinv(X.T@Pz@X)@X.T@Pz
    meat=sum(np.outer(A[:,cl==g]@u[cl==g],A[:,cl==g]@u[cl==g]) for g in np.unique(cl))
    V=meat*len(np.unique(cl))/(len(np.unique(cl))-1)
    return b,np.sqrt(np.diag(V)),F

CTRL=["LNPGDP_constant2015","OPEN_trade","LN_HC_index","FDI_inflows","GOV_consumption","URB_urban_pop"]

def run_panel(df,ai_col,label,rows):
    df=df.merge(Z,on=["CountryName","Year"],how="inner").dropna(subset=["TFP",ai_col,"Z"]+CTRL)
    df["lnTFP"]=np.log(df["TFP"])
    dm=demean2(df,["lnTFP",ai_col,"Z"]+CTRL)
    y=dm["lnTFP"].to_numpy(); cl=df["Country"].to_numpy(); W=dm[CTRL].to_numpy()
    # OLS-FE benchmark
    b,se=ols_cl(y,np.column_stack([dm[ai_col].to_numpy(),W]),cl)
    rows.append({"panel":label,"model":"FE-OLS","var":ai_col,"coef":b[0],"se":se[0],"t":b[0]/se[0],"n":len(df),"F1":""})
    # IV
    b,se,F=tsls(y,dm[ai_col].to_numpy(),dm["Z"].to_numpy(),W,cl)
    rows.append({"panel":label,"model":"Bartik-IV","var":ai_col,"coef":b[0],"se":se[0],"t":b[0]/se[0],"n":len(df),"F1":round(F,2)})
    # H3/H4 interactions, IV'd with Z x moderator
    for mod,mname in (("INST_rule_of_law","RuleOfLaw"),("INF_broadband","Broadband")):
        d2=df.dropna(subset=[mod]).copy()
        mz=(d2[mod]-d2[mod].mean())/d2[mod].std()
        d2["AXM"]=d2[ai_col]*mz; d2["ZXM"]=d2["Z"]*mz; d2["MOD"]=mz
        dm2=demean2(d2,["lnTFP",ai_col,"AXM","Z","ZXM","MOD"]+CTRL)
        y2=dm2["lnTFP"].to_numpy(); cl2=d2["Country"].to_numpy()
        Wx=np.column_stack([dm2["MOD"].to_numpy(),dm2[CTRL].to_numpy()])
        ZZ=np.column_stack([dm2["Z"],dm2["ZXM"],Wx]); XX=np.column_stack([dm2[ai_col],dm2["AXM"],Wx])
        Pz=ZZ@np.linalg.pinv(ZZ.T@ZZ)@ZZ.T
        bb=np.linalg.pinv(XX.T@Pz@XX)@XX.T@Pz@y2
        u=y2-XX@bb; A=np.linalg.pinv(XX.T@Pz@XX)@XX.T@Pz
        meat=sum(np.outer(A[:,cl2==g]@u[cl2==g],A[:,cl2==g]@u[cl2==g]) for g in np.unique(cl2))
        Vv=meat*len(np.unique(cl2))/(len(np.unique(cl2))-1); sese=np.sqrt(np.diag(Vv))
        rows.append({"panel":label,"model":f"Bartik-IV x {mname}","var":"AI","coef":bb[0],"se":sese[0],"t":bb[0]/sese[0],"n":len(d2),"F1":""})
        rows.append({"panel":label,"model":f"Bartik-IV x {mname}","var":f"AI x {mname}","coef":bb[1],"se":sese[1],"t":bb[1]/sese[1],"n":len(d2),"F1":""})

if __name__=="__main__":
    Z,s,G=build_z()
    # Rotemberg-style weights: field share of aggregate Z variation (GPSS approximation)
    w=(s.mean(axis=0)*G.var(axis=0)); w=w/w.sum()
    w.rename("rotemberg_weight_approx").to_csv(os.path.join(OUT,"rotemberg_weights.csv"))
    rows=[]
    B=pd.read_csv(os.path.join(OUT,"merged_panelB_v5.csv")); run_panel(B,"LN_AI_pub","PanelB 2016-24",rows)
    A=pd.read_csv(os.path.join(OUT,"merged_dissertation_v5.csv"))
    run_panel(A[A.Year>=2016].copy(),"LN_AI","PanelA 2016-24 subwindow",rows)
    R=pd.DataFrame(rows); R.to_csv(os.path.join(OUT,"bartik_iv_results.csv"),index=False)
    print(R.to_string(index=False,float_format=lambda v:f"{v: .4f}" if isinstance(v,float) else str(v)))
    print("\nRotemberg-approx field weights:"); print(w.round(3).to_string())
