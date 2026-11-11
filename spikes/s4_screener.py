"""Spike 4: screener.in consolidated page for INFY — tables + documents section (AR + concall links)."""
import sys, time, re, pathlib
import httpx
from selectolax.lexbor import LexborHTMLParser as HTMLParser

sym = sys.argv[1] if len(sys.argv) > 1 else "INFY"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36", "Accept-Language": "en-US,en;q=0.9"}
out = pathlib.Path("spikes/out"); out.mkdir(exist_ok=True)
with httpx.Client(headers=H, timeout=30, follow_redirects=True) as c:
    t0 = time.time(); r = c.get(f"https://www.screener.in/company/{sym}/consolidated/"); print("status", r.status_code, f"{time.time()-t0:.1f}s", len(r.text))
    (out / f"screener_{sym}.html").write_text(r.text, encoding="utf-8")
tree = HTMLParser(r.text)
print("title:", tree.css_first("h1").text(strip=True) if tree.css_first("h1") else None)
for sec in tree.css("section"):
    sid = sec.attributes.get("id");
    if not sid: continue
    tables = sec.css("table")
    print(f"section#{sid}: {len(tables)} tables")
    for t in tables[:1]:
        head = [th.text(strip=True) for th in t.css("thead th")]
        rows = [[td.text(strip=True) for td in tr.css("td")] for tr in t.css("tbody tr")]
        print("   head:", head[:8]);
        for row in rows[:4]: print("   row:", row[:8])
docs = tree.css_first("section#documents")
if docs:
    for a in docs.css("a"):
        href = a.attributes.get("href", ""); txt = re.sub(r"\s+", " ", a.text(strip=True))
        if href.startswith("http"): print("doc:", txt[:60], "|", href[:120])
# ratios block (top)
for li in tree.css("#top-ratios li")[:12]:
    print("ratio:", re.sub(r"\s+", " ", li.text(strip=True))[:80])
