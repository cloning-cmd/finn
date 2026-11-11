"""Spike 1: verify all portfolio + research symbols resolve on yfinance (.NS) and batch-download 400d works."""
import json, sys, time
import yfinance as yf
import pandas as pd

PORTFOLIO = ["RELIANCE","HDFCBANK","INFY","BAJFINANCE","LT","SUNPHARMA","TRENT","TITAN","ETERNAL","ASIANPAINT",
             "INDIGO","ADANIPORTS","DIXON","POLYCAB","PERSISTENT","CDSL","DEEPAKNTR","SUZLON"]
RESEARCH = ["PIDILITIND","TATAPOWER"]
syms = [s + ".NS" for s in PORTFOLIO + RESEARCH]

t0 = time.time()
df = yf.download(syms, period="400d", group_by="ticker", auto_adjust=False, threads=True, progress=False)
print(f"batch download: {time.time()-t0:.1f}s, shape={df.shape}")
report = {}
for s in syms:
    try:
        sub = df[s].dropna(subset=["Close"])
        last = sub.iloc[-1]
        report[s] = {"rows": int(len(sub)), "last_date": str(sub.index[-1].date()), "close": round(float(last["Close"]), 2),
                     "volume": int(last["Volume"])}
    except Exception as e:  # noqa
        report[s] = {"error": repr(e)}
print(json.dumps(report, indent=1))
bad = [s for s, r in report.items() if "error" in r or r.get("rows", 0) < 200]
print("BAD:", bad)
# info call cost check for one ticker (sector/industry for lender detection)
t0 = time.time(); info = yf.Ticker("HDFCBANK.NS").info
print("info keys sample:", {k: info.get(k) for k in ["shortName","sector","industry","marketCap","exchange"]}, f"{time.time()-t0:.1f}s")
