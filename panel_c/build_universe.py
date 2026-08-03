#!/usr/bin/env python3
"""
Panel C - Stage 1: Build the universe of US-listed Latin American firms (20-F + 10-K filers).

Two passes per firm_level_chapter_scoping.md §0 and edgar_data_acquisition_guide.md:
  Pass 1 (address): EDGAR company search by business-address country code.
  Pass 2 (curation): known LatAm-operating firms incorporated/addressed offshore
                     (Cayman/Luxembourg/Delaware holdcos), matched by name.

Usage:
  python3 build_universe.py stage1          # candidates via browse-edgar (fast, ~20 requests)
  python3 build_universe.py fetch [N]       # fetch N submissions JSONs (resumable, default 60)
  python3 build_universe.py assemble        # emit firm_universe.csv

All endpoints free/public. UA + <=8 req/s per SEC policy.
"""
import json, os, re, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
os.makedirs(CACHE, exist_ok=True)
UA = {"User-Agent": "Carlos Yalta, PhD research, jy9gvmhmks@privaterelay.appleid.com"}

# Official EDGAR country codes (sec.gov state-country list, fetched 2026-07-11)
# Both code generations: legacy (pre-2023) and current EDGAR country codes.
COUNTRIES = {"C1":"Argentina","1B":"Argentina","D5":"Brazil","D6":"Brazil",
             "F3":"Chile","F4":"Chile","F8":"Colombia","F9":"Colombia",
             "G0":"Costa Rica","L7":"Costa Rica","G8":"Dominican Republic","H1":"Dominican Republic",
             "O5":"Mexico","1K":"Mexico","R1":"Peru","R6":"Peru","X3":"Uruguay","2K":"Uruguay"}
OFFSHORE = {"F0":"Cayman Islands","N5":"Luxembourg","D2":"Bermuda","VI":"BVI"}

# Pass-2 curation: name fragments of LatAm-operating firms often addressed/incorporated offshore.
CURATION_NAMES = [
 "MERCADOLIBRE","GLOBANT","DLOCAL","NU HOLDINGS","STONECO","PAGSEGURO","PAGS",
 "VTEX","DESPEGAR","ARCOS DORADOS","BIOCERES","CORPORACION AMERICA","SOUTHERN COPPER",
 "XP INC","INTER & CO","PATRIA INVEST","VINCI PARTNERS","VINCI COMPASS","AFYA","ARCO PLATFORM",
 "ZENVIA","VITRU","AUNA","TERNIUM","TENARIS","CREDICORP","VISTA ENERGY","VISTA OIL",
 "TECNOGLASS","GRUPO SUPERVIELLE","ADECOAGRO","ATLAS LITHIUM","AMBIPAR","SEMANTIX",
 "LATAM AIRLINES","AZUL","GOL LINHAS","EMBRAER","BRASILAGRO","GAUCHO GROUP",
 "BETTERWARE","VOLARIS","GRUPO AEROPORTUARIO","AMERICA MOVIL","COCA-COLA FEMSA",
 "FOMENTO ECONOMICO","GRUPO TELEVISA","CEMEX","GRUPO FINANCIERO GALICIA","BBVA ARGENTINA",
 "BANCO MACRO","TELECOM ARGENTINA","PAMPA ENERGIA","TRANSPORTADORA DE GAS","EDENOR",
 "IRSA","CRESUD","LOMA NEGRA","YPF","CENTRAL PUERTO","GRUPO FINANCIERO BANORTE",
 "BANCOLOMBIA","ECOPETROL","GRUPO AVAL","GEOPARK","GRAN TIERRA","FRONTERA ENERGY",
 "BUENAVENTURA","SQM","SOCIEDAD QUIMICA","ENEL CHILE","BANCO DE CHILE","BANCO SANTANDER-CHILE",
 "ITAU","BRADESCO","VALE S","PETROBRAS","AMBEV","GERDAU","SUZANO","BRASKEM","SABESP",
 "ELETROBRAS","CEMIG","COPEL","TIM S.A","TELEFONICA BRASIL","ULTRAPAR","CSN","SID NACIONAL",
 "BRF S.A","JBS","NATURA","COSAN","NEXA RESOURCES","ORLA MINING","SIGMA LITHIUM",
]

def get(url, binary=False, retries=3):
    for k in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=20) as r:
                data = r.read()
            time.sleep(0.13)
            return data if binary else data.decode("utf-8", "ignore")
        except Exception as e:
            if k == retries-1: raise
            time.sleep(1.0+k)

def stage1(only_codes=None):
    """Candidates via browse-edgar company search per country code x form type. Resumable per code."""
    path = os.path.join(CACHE, "candidates_address.json")
    cands = {int(k): v for k, v in (json.load(open(path)).items() if os.path.exists(path) else [])}
    codes = only_codes or list(COUNTRIES)
    for code in codes:
        for form in ("20-F","10-K"):
            start = 0
            while True:
                url = (f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
                       f"&State={code}&SIC=&type={form}&dateb=&owner=include"
                       f"&count=100&start={start}&output=atom")
                atom = get(url)
                ciks = re.findall(r"<cik>(\d+)</cik>", atom)
                n_before = len(cands)
                for cik in ciks:
                    cands.setdefault(int(cik), {"name": "",
                                                "addr_code": code,
                                                "addr_country": COUNTRIES[code],
                                                "via": f"address:{form}"})
                entries = atom.count("<entry")
                print(f"{COUNTRIES[code]:20s} {form:5s} start={start:4d} entries={entries:3d} new={len(cands)-n_before}")
                if entries < 100: break
                start += 100
    with open(os.path.join(CACHE, "candidates_address.json"), "w") as f:
        json.dump(cands, f, indent=1)
    print(f"address-pass candidates: {len(cands)}")

def curation():
    tk = json.loads(get("https://www.sec.gov/files/company_tickers_exchange.json"))
    fields, rows = tk["fields"], tk["data"]
    i_cik, i_name = fields.index("cik"), fields.index("name")
    i_tkr, i_exch = fields.index("ticker"), fields.index("exchange")
    cur = {}
    for row in rows:
        nm = str(row[i_name]).upper()
        for frag in CURATION_NAMES:
            if frag in nm:
                cur.setdefault(int(row[i_cik]),
                    {"name": row[i_name], "ticker": row[i_tkr],
                     "exchange": row[i_exch], "via": f"curation:{frag}"})
                break
    with open(os.path.join(CACHE, "candidates_curation.json"), "w") as f:
        json.dump(cur, f, indent=1)
    print(f"curation-pass candidates: {len(cur)}")

def _load_candidates():
    a = json.load(open(os.path.join(CACHE, "candidates_address.json")))
    c = json.load(open(os.path.join(CACHE, "candidates_curation.json")))
    all_ciks = {}
    for k, v in a.items(): all_ciks[int(k)] = v
    for k, v in c.items():
        if int(k) in all_ciks: all_ciks[int(k)]["via"] += ";"+v["via"]
        else: all_ciks[int(k)] = v
    return all_ciks

def fetch(batch=60):
    """Resumable download of submissions JSON per candidate CIK (restricted to fetch_set if present)."""
    cands = _load_candidates()
    fs = os.path.join(CACHE, "fetch_set.json")
    if os.path.exists(fs):
        keep = set(json.load(open(fs)))
        cands = {k: v for k, v in cands.items() if k in keep}
    todo = [cik for cik in cands
            if not os.path.exists(os.path.join(CACHE, f"sub_{cik:010d}.json"))]
    print(f"remaining: {len(todo)}")
    for cik in todo[:batch]:
        try:
            data = get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", binary=True)
            open(os.path.join(CACHE, f"sub_{cik:010d}.json"), "wb").write(data)
        except Exception as e:
            print("FAIL", cik, e)
    left = len([c for c in cands
                if not os.path.exists(os.path.join(CACHE, f'sub_{c:010d}.json'))])
    print(f"fetched batch; remaining now: {left}")

def assemble():
    import csv
    cands = _load_candidates()
    out, skipped = [], {"no_json":0,"no_annual_2017":0,"fund_shell":0}
    for cik, meta in cands.items():
        p = os.path.join(CACHE, f"sub_{cik:010d}.json")
        if not os.path.exists(p): skipped["no_json"] += 1; continue
        j = json.load(open(p))
        recent = j.get("filings", {}).get("recent", {})
        forms = recent.get("form", []); dates = recent.get("filingDate", [])
        ann = [(f, d) for f, d in zip(forms, dates) if f in ("20-F","10-K","20-F/A","10-K/A")]
        ann2017 = [(f, d) for f, d in ann if d >= "2018-01-01"]
        if not ann2017: skipped["no_annual_2017"] += 1; continue
        sic = str(j.get("sic") or ""); sicd = j.get("sicDescription") or ""
        if sic in ("6770","6199") and "blank" in sicd.lower():
            skipped["fund_shell"] += 1; continue
        biz = (j.get("addresses", {}).get("business", {}) or {})
        form_type = "20-F" if any(f.startswith("20-F") for f, _ in ann2017) else "10-K"
        out.append({
            "cik": cik, "name": j.get("name",""),
            "ticker": ";".join(j.get("tickers", [])[:3]),
            "exchange": ";".join([e for e in j.get("exchanges", []) if e][:2]),
            "addr_country": biz.get("stateOrCountryDescription",""),
            "country_hq_guess": meta.get("addr_country",""),
            "sic": sic, "sic_desc": sicd,
            "form_type": form_type,
            "n_annual_2018plus": len(ann2017),
            "first_annual": min(d for _, d in ann2017),
            "last_annual": max(d for _, d in ann2017),
            "via": meta.get("via",""),
        })
    out.sort(key=lambda r: (str(r["form_type"] or ""), str(r["addr_country"] or ""), str(r["name"] or "")))
    dst = os.path.join(HERE, "firm_universe_raw.csv")
    with open(dst, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    print(f"wrote {dst}: {len(out)} firms  | skipped: {skipped}")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stage1"
    if cmd == "stage1": stage1(sys.argv[2].split(",") if len(sys.argv) > 2 else None)
    elif cmd == "curation": curation()
    elif cmd == "fetch": fetch(int(sys.argv[2]) if len(sys.argv) > 2 else 60)
    elif cmd == "assemble": assemble()
