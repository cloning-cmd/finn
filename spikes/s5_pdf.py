"""Spike 5: download one concall transcript PDF (URL from s4 output or argv) and extract text with PyMuPDF."""
import sys, time, pathlib, hashlib, re
import httpx, fitz

url = sys.argv[1]
out = pathlib.Path("spikes/out"); out.mkdir(exist_ok=True)
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36", "Referer": "https://www.bseindia.com/"}
t0 = time.time(); r = httpx.get(url, headers=H, timeout=60, follow_redirects=True)
print("status", r.status_code, r.headers.get("content-type"), len(r.content), f"{time.time()-t0:.1f}s")
p = out / (hashlib.sha256(r.content).hexdigest()[:12] + ".pdf"); p.write_bytes(r.content)
doc = fitz.open(p); print("pages", doc.page_count)
total = 0; speakers = {}
for i, page in enumerate(doc):
    t = page.get_text(); total += len(t)
    for m in re.finditer(r"^([A-Z][A-Za-z .'-]{2,40}):", t, re.M): speakers[m.group(1)] = speakers.get(m.group(1), 0) + 1
    if i < 2: print(f"--- page {i+1} ---\n{t[:800]}")
print("total chars", total, "chars/page", total // max(doc.page_count, 1))
print("speaker-like prefixes:", sorted(speakers.items(), key=lambda x: -x[1])[:12])
