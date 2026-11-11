"""Spike 3: BSE announcements API (fallback). INFY scrip code 500209."""
import json, sys, time, datetime as dt
import httpx

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36",
     "Referer": "https://www.bseindia.com/", "Origin": "https://www.bseindia.com", "Accept": "application/json, text/plain, */*"}
scrip = sys.argv[1] if len(sys.argv) > 1 else "500209"
to = dt.date.today(); frm = to - dt.timedelta(days=30)
url = ("https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w"
       f"?pageno=1&strCat=-1&strPrevDate={frm:%Y%m%d}&strScrip={scrip}&strSearch=P&strToDate={to:%Y%m%d}&strType=C&subcategory=-1")
with httpx.Client(headers=H, timeout=20) as c:
    t0 = time.time(); r = c.get(url); print("status", r.status_code, f"{time.time()-t0:.1f}s", r.headers.get("content-type"))
    d = r.json(); rows = d.get("Table", []); print("rows", len(rows), "Table1", d.get("Table1"))
    if rows:
        print("keys", sorted(rows[0].keys()))
        for row in rows[:8]:
            print(json.dumps({k: row.get(k) for k in ["SCRIP_CD","SLONGNAME","HEADLINE","NEWSSUB","CATEGORYNAME","SUBCATNAME","ATTACHMENTNAME","NEWS_DT","DT_TM","PDFFLAG","NSURL"]}, ensure_ascii=False)[:600])
    # attachment URL pattern: https://www.bseindia.com/xml-data/corpfiling/AttachLive/<ATTACHMENTNAME>
    # scrip-code lookup for symbol → code
    r = c.get("https://api.bseindia.com/BseIndiaAPI/api/PeerSmartSearch/w?Type=SS&text=INFY"); print("search", r.status_code, r.text[:300])
