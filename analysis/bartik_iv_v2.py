#!/usr/bin/env python3
"""
Bartik shift-share IV v2 — WIPO patent publications by 35 technology fields (2000–2022).
shares: country field composition 2000–2004 (predetermined); shifts: ln global ex-LatAm
publications by field-year. Z instruments LN_AI on Panel A 2000–2022 (full window).
Deviation from §4.7 documented: all 35 WIPO fields (not only G06N-adjacent) — relevance
runs through computer/digital-field specialization capturing AI-relevant global shocks.
"""
import os
import numpy as np, pandas as pd
# repo root (this script lives in analysis/)
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT=os.path.join(ROOT,"output","results")
LAT2=["AR","BR","CL","CO","CR","DO","MX","PE","UY","BO","EC","SV","GT","HN","NI","PA","PY"]
NAME={"AR":"Argentina","BR":"Brazil","CL":"Chile","CO":"Colombia","CR":"Costa Rica",
      "DO":"Dominican Republic","MX":"Mexico","PE":"Peru","UY":"Uruguay"}

def build():
    d=pd.read_csv(os.path.join(ROOT,"data/wipo_field/dc_indicator_patent_4_publication_by_technology.csv"))
    d=d[(d.office=="**")&(d.tec_id.between(1,35))]
    base=d[(d.origin.isin(NAME))&(d.year.between(2000,2004))]
    s=base.groupby(["origin","tec_id"])["count"].sum().unstack(fill_value=0)
    s=s.reindex(columns=range(1,36),fill_value=0)
    s=(s.T/s.sum(axis=1).replace(0,np.nan)).T
    g=d[~d.origin.isin(LAT2)].groupby(["tec_id","year"])["count"].sum().unstack(0)
    G=np.log(g.reindex(columns=range(1,36)).replace(0,np.nan))
    Z=pd.DataFrame([{"CountryName":NAME[c],"Year":y,"Z2":float(np.nansum(s.loc[c].to_numpy()*G.loc[y].to_numpy()))}
                    for c in s.index for y in G.index])
    # Rotemberg-approx: field weight = mean share x shift variance
    w=(s.mean(axis=0)*G.var(axis=0)); w=w/w.sum()
    return Z,s,G,w

def demean2(df,cols,i="Country",t="Year",iters=100):
    X=df[cols].astype(float).copy()
    for _ in range(iters):
        X=X-X.groupby(df[i]).transform("mean"); X=X-X.groupby(df[t]).transform("mean")
    return X
def ols_cl(y,X,cl):
    XtXi=np.linalg.pinv(X.T@X); b=XtXi@X.T@y; u=y-X@b
    meat=sum(np.outer(X[cl==g].T@u[cl==g],X[cl==g].T@u[cl==g]) for g in np.unique(cl))
    G_=len(np.unique(cl)); n,k=X.shape
    V=XtXi@meat@XtXi*(G_/(G_-1))*((n-1)/max(n-k,1)); return b,np.sqrt(np.diag(V))
def tsls(y,x,z,W,cl):
    Z_=np.column_stack([z,W]); X=np.column_stack([x,W])
    b1,se1=ols_cl(x,Z_,cl); F=(b1[0]/se1[0])**2
    P=Z_@np.linalg.pinv(Z_.T@Z_)@Z_.T
    b=np.linalg.pinv(X.T@P@X)@X.T@P@y; u=y-X@b
    A=np.linalg.pinv(X.T@P@X)@X.T@P
    meat=sum(np.outer(A[:,cl==g]@u[cl==g],A[:,cl==g]@u[cl==g]) for g in np.unique(cl))
    V=meat*len(np.unique(cl))/(len(np.unique(cl))-1)
    return b,np.sqrt(np.diag(V)),F

CTRL=["LNPGDP_constant2015","OPEN_trade","LN_HC_index","FDI_inflows","GOV_consumption","URB_urban_pop"]
if __name__=="__main__":
    Z,s,G,w=build()
    A=pd.read_csv(os.path.join(OUT,"merged_dissertation_v5.csv")).merge(Z,on=["CountryName","Year"],how="left")
    A=A[(A.Year>=2000)&(A.Year<=2022)].dropna(subset=["TFP","LN_AI","Z2"]+CTRL).copy()
    A["lnTFP"]=np.log(A.TFP)
    dm=demean2(A,["lnTFP","LN_AI","Z2"]+CTRL)
    y=dm.lnTFP.to_numpy(); cl=A.Country.to_numpy(); W=dm[CTRL].to_numpy()
    b,se=ols_cl(y,np.column_stack([dm.LN_AI,W]),cl)
    print(f"FE-OLS 2000-22        LN_AI b={b[0]: .4f} se={se[0]:.4f} t={b[0]/se[0]: .2f} n={len(A)}")
    b,se,F=tsls(y,dm.LN_AI.to_numpy(),dm.Z2.to_numpy(),W,cl)
    print(f"Bartik-v2 IV 2000-22  LN_AI b={b[0]: .4f} se={se[0]:.4f} t={b[0]/se[0]: .2f} n={len(A)}  FIRST-STAGE F={F:.2f}")
    # interactions H3/H4 under IV (Z and ZxM as instruments)
    for mod,nm in (("INST_rule_of_law","RuleOfLaw"),("INF_broadband","Broadband")):
        d2=A.dropna(subset=[mod]).copy()
        mz=(d2[mod]-d2[mod].mean())/d2[mod].std()
        d2["AXM"]=d2.LN_AI*mz; d2["ZXM"]=d2.Z2*mz; d2["MZ"]=mz
        dm2=demean2(d2,["lnTFP","LN_AI","AXM","Z2","ZXM","MZ"]+CTRL)
        Wx=np.column_stack([dm2.MZ,dm2[CTRL].to_numpy()])
        ZZ=np.column_stack([dm2.Z2,dm2.ZXM,Wx]); XX=np.column_stack([dm2.LN_AI,dm2.AXM,Wx])
        P=ZZ@np.linalg.pinv(ZZ.T@ZZ)@ZZ.T
        bb=np.linalg.pinv(XX.T@P@XX)@XX.T@P@dm2.lnTFP.to_numpy()
        u=dm2.lnTFP.to_numpy()-XX@bb; Aa=np.linalg.pinv(XX.T@P@XX)@XX.T@P
        cl2=d2.Country.to_numpy()
        meat=sum(np.outer(Aa[:,cl2==g]@u[cl2==g],Aa[:,cl2==g]@u[cl2==g]) for g in np.unique(cl2))
        V=meat*len(np.unique(cl2))/(len(np.unique(cl2))-1); ss=np.sqrt(np.diag(V))
        print(f"IV x {nm:10s}  AI b={bb[0]: .4f} (t={bb[0]/ss[0]: .2f})  AIx{nm} b={bb[1]: .4f} (t={bb[1]/ss[1]: .2f})")
    print("\nTop-8 Rotemberg-approx field weights:")
    fn=pd.read_excel(os.path.join(ROOT,"data/wipo_field/patent_technology_field_names.xlsx"))[["class_id","field_en"]] if os.path.exists(os.path.join(ROOT,"data/wipo_field/patent_technology_field_names.xlsx")) else None
    top=w.sort_values(ascending=False).head(8)
    for fid,val in top.items():
        lbl=fn[fn.class_id==fid].field_en.iloc[0] if fn is not None and (fn.class_id==fid).any() else fid
        print(f"  {val: .3f}  {lbl}")
    Z.to_csv(os.path.join(OUT,"bartik_v2_instrument.csv"),index=False)
