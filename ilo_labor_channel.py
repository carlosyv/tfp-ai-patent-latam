#!/usr/bin/env python3
"""
Labor-market channel exercise (opening report §1.2/§2.7; Shen Yao displacement channel).
Occupational employment shares (ILOSTAT EMP_TEMP_SEX_OCU) vs lagged AI patent stock,
two-way FE, country-clustered SEs. Panel A countries.

Two classification schemes:
  A. ISCO-08 major groups (harmonized level; unbalanced availability 2002–2025)
     displacement-exposed: group 4 (clerical); also 9 (elementary), 2 (professionals),
     3 (technicians), 1 (managers).
  B. SKILL buckets (L1 low / L2 medium / L3-4 high) — longer, more balanced coverage.
Framing: suggestive channel evidence, small N; NOT causal.
"""
import os
import numpy as np, pandas as pd
HERE=os.path.dirname(os.path.abspath(__file__)); OUT=os.path.join(HERE,"output","results")
ISO3={"ARG":"Argentina","BRA":"Brazil","CHL":"Chile","COL":"Colombia","CRI":"Costa Rica",
      "DOM":"Dominican Republic","MEX":"Mexico","PER":"Peru","URY":"Uruguay"}

def demean2(df,cols,i="Country",t="Year",iters=100):
    X=df[cols].astype(float).copy()
    for _ in range(iters):
        X=X-X.groupby(df[i]).transform("mean"); X=X-X.groupby(df[t]).transform("mean")
    return X
def ols_cl(y,X,cl):
    XtXi=np.linalg.pinv(X.T@X); b=XtXi@X.T@y; u=y-X@b
    meat=sum(np.outer(X[cl==g].T@u[cl==g],X[cl==g].T@u[cl==g]) for g in np.unique(cl))
    G=len(np.unique(cl)); n,k=X.shape
    V=XtXi@meat@XtXi*(G/(G-1))*((n-1)/max(n-k,1)); return b,np.sqrt(np.diag(V))

CTRL=["LNPGDP_constant2015","OPEN_trade","LN_HC_index","GOV_consumption","URB_urban_pop"]
if __name__=="__main__":
    d=pd.read_csv(os.path.join(HERE,"data/ilostat/EMP_TEMP_SEX_OCU_NB_A_latam.csv"))
    d=d[d.sex=="SEX_T"].copy(); d["CountryName"]=d.ref_area.map(ISO3); d["Year"]=d.time
    A=pd.read_csv(os.path.join(OUT,"merged_dissertation_v5.csv"))
    A=A.sort_values(["Country","Year"])
    A["LN_AI_L1"]=A.groupby("Country")["LN_AI"].shift(1)
    rows=[]
    def run_scheme(codes,tot_code,scheme):
        sub=d[d.classif1.isin(codes+[tot_code])]
        p=sub.pivot_table(index=["CountryName","Year"],columns="classif1",values="obs_value",aggfunc="first")
        for c in codes:
            p[f"sh_{c.split('_')[-1]}"]=p[c]/p[tot_code]*100
        p=p.reset_index()
        m=A.merge(p,on=["CountryName","Year"],how="inner")
        for c in codes:
            sh=f"sh_{c.split('_')[-1]}"
            dd=m.dropna(subset=[sh,"LN_AI_L1"]+CTRL).copy()
            if len(dd)<40: 
                rows.append({"scheme":scheme,"outcome":sh,"coef":np.nan,"se":np.nan,"t":np.nan,"n":len(dd)}); continue
            dm=demean2(dd,[sh,"LN_AI_L1"]+CTRL)
            b,se=ols_cl(dm[sh].to_numpy(),np.column_stack([dm.LN_AI_L1,dm[CTRL].to_numpy()]),dd.Country.to_numpy())
            rows.append({"scheme":scheme,"outcome":sh,"coef":b[0],"se":se[0],"t":b[0]/se[0],"n":len(dd)})
    run_scheme([f"OCU_ISCO08_{i}" for i in (1,2,3,4,5,7,8,9)],"OCU_ISCO08_TOTAL","ISCO08")
    run_scheme(["OCU_SKILL_L1","OCU_SKILL_L2","OCU_SKILL_L3-4"],"OCU_SKILL_TOTAL","SKILL")
    R=pd.DataFrame(rows); R.to_csv(os.path.join(OUT,"ilo_labor_channel.csv"),index=False)
    LBL={"sh_1":"Managers","sh_2":"Professionals","sh_3":"Technicians","sh_4":"Clerical (routine-exposed)",
         "sh_5":"Services/sales","sh_7":"Craft","sh_8":"Machine operators","sh_9":"Elementary",
         "sh_L1":"Low skill","sh_L2":"Medium skill","sh_L3-4":"High skill"}
    for _,r in R.iterrows():
        nm=LBL.get(r.outcome,r.outcome)
        star="*" if abs(r.t)>1.65 else " "
        if abs(r.t)>1.96: star="**"
        if abs(r.t)>2.58: star="***"
        print(f"{r.scheme:7s} {nm:28s} b={r.coef: 8.4f} se={r.se:7.4f} t={r.t: 6.2f}{star:3s} n={int(r.n)}")
