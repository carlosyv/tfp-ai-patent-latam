#!/usr/bin/env python3
"""Stage 4c: FH1/FH2 regressions + leave-one-out sector shift-share IV.
Two-way FE via iterated demeaning; cluster-robust (firm) SEs; 2SLS by hand
(numpy only — reproduces with linearmodels PanelOLS/IV2SLS on a full install).
"""
import os
import numpy as np, pandas as pd
HERE=os.path.dirname(os.path.abspath(__file__))

def demean_two_way(df, cols, firm="cik", year="fy", iters=60):
    X=df[cols].astype(float).copy()
    for _ in range(iters):
        X=X-X.groupby(df[firm]).transform("mean")
        X=X-X.groupby(df[year]).transform("mean")
        if X.groupby(df[firm]).transform("mean").abs().to_numpy().max()<1e-10: break
    return X

def ols_cluster(y,X,cl):
    X=np.column_stack([X])
    XtX=X.T@X; XtXi=np.linalg.pinv(XtX)
    b=XtXi@X.T@y
    u=y-X@b
    meat=np.zeros((X.shape[1],X.shape[1]))
    for g in np.unique(cl):
        m=cl==g
        s=X[m].T@u[m]
        meat+=np.outer(s,s)
    G=len(np.unique(cl)); n,k=X.shape
    V=XtXi@meat@XtXi*(G/(G-1))*((n-1)/(n-k))
    se=np.sqrt(np.diag(V))
    return b,se,u

def tsls_cluster(y,x,z,W,cl):
    """single endogenous x, single instrument z, exog W (already demeaned)."""
    Z=np.column_stack([z]+([W] if W is not None and W.size else []))
    X=np.column_stack([x]+([W] if W is not None and W.size else []))
    # first stage
    b1,se1,_=ols_cluster(x,Z,cl)
    F=(b1[0]/se1[0])**2
    xhat=Z@np.linalg.pinv(Z.T@Z)@Z.T@X
    b=np.linalg.pinv(xhat.T@X)@xhat.T@y
    u=y-X@b
    meat=np.zeros((X.shape[1],X.shape[1]))
    P=np.linalg.pinv(xhat.T@X)@xhat.T
    for g in np.unique(cl):
        m=cl==g
        meat+=np.outer(P[:,m]@u[m],P[:,m]@u[m])
    G=len(np.unique(cl))
    V=meat*(G/(G-1))
    return b,np.sqrt(np.diag(V)),F

def run():
    df=pd.read_csv(os.path.join(HERE,"firm_panel_clean.csv"))
    df=df.dropna(subset=["lprod","exp"]).copy()
    df["lexp"]=np.log1p(df["exp"]); df["lexp_tot"]=np.log1p(df["exp_tot"])
    # leave-one-out sector-year mean exposure (shift-share style instrument)
    g=df.groupby(["sic2","fy"])["exp"]
    df["sec_sum"]=g.transform("sum"); df["sec_n"]=g.transform("count")
    df["z_loo"]=np.where(df.sec_n>1,(df.sec_sum-df.exp)/(df.sec_n-1),np.nan)
    df["z_lloo"]=np.log1p(df["z_loo"])
    # standardized moderators (within estimation sample)
    for m in ("intang_int","size"):
        df[f"{m}_z"]=(df[m]-df[m].mean())/df[m].std()
    df["exp_x_intang"]=df["lexp"]*df["intang_int_z"]
    df["exp_x_size"]=df["lexp"]*df["size_z"]
    # one-year lagged exposure (J-curve / adjustment-cost timing; cited in dissertation 6.3)
    df=df.sort_values(["cik","fy"])
    df["lexp_l1"]=df.groupby("cik")["lexp"].shift(1)
    df["prev_fy"]=df.groupby("cik")["fy"].shift(1)
    df.loc[df.fy-df.prev_fy!=1,"lexp_l1"]=np.nan   # no gap-spanning lags
    df["nonfin"]=~df["sic2"].isin([60,61,62,63,64,65,67])

    rows=[]
    def fe_reg(dat,ycol,xcols,label,ivpair=None):
        dat=dat.dropna(subset=[ycol]+xcols+([ivpair[1]] if ivpair else [])).copy()
        dm=demean_two_way(dat,[ycol]+xcols+([ivpair[1]] if ivpair else []))
        y=dm[ycol].to_numpy(); cl=dat["cik"].to_numpy()
        if ivpair is None:
            X=dm[xcols].to_numpy()
            b,se,_=ols_cluster(y,X,cl)
            for c,bi,si in zip(xcols,b,se):
                rows.append({"model":label,"var":c,"coef":bi,"se":si,"t":bi/si,
                             "n":len(dat),"firms":dat.cik.nunique()})
        else:
            xend,zcol=ivpair
            W=dm[[c for c in xcols if c!=xend]].to_numpy()
            b,se,F=tsls_cluster(y,dm[xend].to_numpy(),dm[zcol].to_numpy(),W,cl)
            names=[xend]+[c for c in xcols if c!=xend]
            for c,bi,si in zip(names,b,se):
                rows.append({"model":label,"var":c,"coef":bi,"se":si,"t":bi/si,
                             "n":len(dat),"firms":dat.cik.nunique(),"KP_F_approx":F if c==xend else ""})
    # FH1
    fe_reg(df,"lprod",["lexp"],"FH1 baseline (log1p exposure)")
    fe_reg(df,"lprod",["lexp_tot"],"FH1 total-exposure variant")
    fe_reg(df[df.ias29_ars==0],"lprod",["lexp"],"FH1 excl. ARS (IAS-29)")
    fe_reg(df,"lprod",["lexp_l1"],"FH1 lagged exposure (t-1)")
    fe_reg(df[df.nonfin],"lprod",["lexp_l1"],"FH1 lagged exposure, non-financials")
    # FH2
    fe_reg(df,"lprod",["lexp","exp_x_intang"],"FH2 x intangibles")
    fe_reg(df,"lprod",["lexp","exp_x_size"],"FH2 x size")
    fe_reg(df,"lprod",["lexp","exp_x_intang","exp_x_size"],"FH2 both moderators")
    # IV
    fe_reg(df,"lprod",["lexp"],"IV: leave-one-out sector-year exposure",ivpair=("lexp","z_lloo"))
    out=pd.DataFrame(rows)
    out.to_csv(os.path.join(HERE,"regression_results.csv"),index=False)
    pd.set_option("display.width",160)
    print(out.to_string(index=False,float_format=lambda v:f"{v: .4f}" if isinstance(v,float) else v))

if __name__=="__main__": run()
