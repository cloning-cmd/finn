"""Spike 2: NSE corporate announcements API — cookie warm-up, field names, attachment URLs."""
import json, sys, time, datetime as dt
import httpx

H = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9", "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
}
sym = sys.argv[1] if len(sys.argv) > 1 else "INFY"
to = dt.date.today(); frm = to - dt.timedelta(days=30)
with httpx.Client(headers=H, timeout=20, follow_redirects=True) as c:
    t0 = time.time()
    r = c.get("https://www.nseindia.com/"); print("warmup", r.status_code, f"{time.time()-t0:.1f}s cookies={list(c.cookies.keys())}")
    r = c.get("https://www.nseindia.com/companies-listing/corporate-filings-announcements"); print("page", r.status_code)
    url = f"https://www.nseindia.com/api/corporate-announcements?index=equities&symbol={sym}&from_date={frm:%d-%m-%Y}&to_date={to:%d-%m-%Y}"
    r = c.get(url); print("api", r.status_code, r.headers.get("content-type"))
    data = r.json()
    print("count", len(data))
    if data:
        print("keys", sorted(data[0].keys()))
        for row in data[:8]:
            print(json.dumps({k: row.get(k) for k in ["symbol","desc","attchmntText","attchmntFile","an_dt","sort_date","exchdisstime","smIndustry"]}, ensure_ascii=False)[:600])
    # also try portfolio-wide (no symbol) for the same window — do we get everything?
    url2 = f"https://www.nseindia.com/api/corporate-announcements?index=equities&from_date={frm:%d-%m-%Y}&to_date={to:%d-%m-%Y}"
    t0 = time.time(); r = c.get(url2); print("all-equities", r.status_code, f"{time.time()-t0:.1f}s", "rows=", len(r.json()) if r.status_code == 200 else None)
