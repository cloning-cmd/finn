"""Spike 6: NSE financial results XBRL — find a results filing with XBRL for a symbol and parse key tags."""
import sys, re, json, time, datetime as dt
import httpx
from lxml import etree

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36",
     "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9", "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-financial-results"}
sym = sys.argv[1] if len(sys.argv) > 1 else "INFY"
with httpx.Client(headers=H, timeout=30, follow_redirects=True) as c:
    c.get("https://www.nseindia.com/"); c.get("https://www.nseindia.com/companies-listing/corporate-filings-financial-results")
    url = f"https://www.nseindia.com/api/corporates-financial-results?index=equities&symbol={sym}&period=Quarterly"
    r = c.get(url); print("results api", r.status_code)
    rows = r.json(); print("rows", len(rows));
    if rows: print("keys", sorted(rows[0].keys())); print(json.dumps(rows[0], ensure_ascii=False)[:800])
    xb = next((row for row in rows if row.get("xbrl")), None)
    if not xb: print("no xbrl link in rows"); sys.exit()
    xurl = xb["xbrl"]; print("xbrl url", xurl)
    r = c.get(xurl); print("xbrl fetch", r.status_code, len(r.content))
    root = etree.fromstring(r.content)
    ns = {k or "default": v for k, v in root.nsmap.items()}
    vals = {}
    for el in root.iter():
        tag = etree.QName(el).localname
        if el.get("contextRef") and el.text and re.match(r"^-?[\d.]+$", el.text.strip()):
            vals.setdefault(tag, []).append((el.get("contextRef"), el.text.strip(), el.get("unitRef")))
    want = [t for t in vals if re.search(r"Revenue|Income|FinanceCost|Depreciation|ProfitBeforeTax|ProfitLoss|Tax|Interest|Provision", t)]
    for t in sorted(want)[:40]: print(t, vals[t][:3])
    # contexts: period mapping
    for ctx in root.iter("{*}context"):
        cid = ctx.get("id"); per = ctx.find("{*}period")
        if per is not None and cid and re.search(r"OneD|ThreeM|Quarter|CurrentYTD|PreviousYear|OneI|OneM", cid, re.I):
            print("ctx", cid, [ (etree.QName(x).localname, x.text) for x in per ])
