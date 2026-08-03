#!/usr/bin/env python3
"""
Period-robustness table (opening report §5.8): H1/H3/H4 across
  (a) full window 2000-2024, patents        (main result)
  (b) subwindow  2016-2024, patents         (P3's preferred window)
  (c) subwindow  2017-2024, patents         (composite-comparable window)
  (d) subwindow  2017-2024, composite       (§5.6 alternative treatment)
Panel A (9 countries). Two-way FE, country-clustered SEs (numpy; cross-check
with FE-DK in pipeline_v5 on full install).
"""
import os
import numpy as np, pandas as pd
HERE=os.path.dirname(os.path.abspath(__file__)); OUT=os.path.join(HERE,"output","results")

def demean2(df,cols,i="Country",t="Year",iters=100):
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
def reg(df,xvar,label,rows,inter=None,intername=""):
    d=df.dropna(subset=["TFP",xvar]+CTRL+([inter] if inter else [])).copy()
    d["lnTFP"]=np.log(d.TFP); cols=["lnTFP",xvar]+CTRL
    if inter:
        mz=(d[inter]-d[inter].mean())/d[inter].std()
        d["XM"]=d[xvar]*mz; d["MZ"]=mz; cols+=["XM","MZ"]
    dm=demean2(d,cols)
    xs=[xvar]+(["XM"] if inter else [])
    X=np.column_stack([dm[xs].to_numpy(),dm[CTRL+(["MZ"] if inter else [])].to_numpy()])
    b,se=ols_cl(dm["lnTFP"].to_numpy(),X,d.Country.to_numpy())
    for i,nm in enumerate(xs):
        rows.append({"window":label,"treatment":xvar,"var":nm if nm!="XM" else f"AI x {intername}",
                     "coef":b[i],"se":se[i],"t":b[i]/se[i],"n":len(d)})

if __name__=="__main__":
    A=pd.read_csv(os.path.join(OUT,"merged_dissertation_v5.csv"))
    comp=pd.read_csv(os.path.join(OUT,"composite_index.csv"))[["Country","Year","AI_COMPOSITE"]]
    A=A.merge(comp,on=["Country","Year"],how="left")
    rows=[]
    for lo,hi,tag in ((2000,2024,"2000-24 full"),(2016,2024,"2016-24"),(2017,2024,"2017-24")):
        d=A[(A.Year>=lo)&(A.Year<=hi)]
        reg(d,"LN_AI",tag,rows)
        reg(d,"LN_AI",tag,rows,inter="INST_rule_of_law",intername="RuleOfLaw")
        reg(d,"LN_AI",tag,rows,inter="INF_broadband",intername="Broadband")
    d=A[(A.Year>=2017)&(A.Year<=2024)]
    reg(d,"AI_COMPOSITE","2017-24",rows)
    reg(d,"AI_COMPOSITE","2017-24",rows,inter="INST_rule_of_law",intername="RuleOfLaw")
    reg(d,"AI_COMPOSITE","2017-24",rows,inter="INF_broadband",intername="Broadband")
    R=pd.DataFrame(rows)
    R.to_csv(os.path.join(OUT,"period_robustness_table.csv"),index=False)
    print(R.to_string(index=False,float_format=lambda v:f"{v: .4f}" if isinstance(v,float) else str(v)))
