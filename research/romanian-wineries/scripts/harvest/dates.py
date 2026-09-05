# -*- coding: utf-8 -*-
"""Fetch each undated article and read its published date from page metadata."""
import json, re, subprocess, concurrent.futures as cf

posts=json.load(open("posts_html.json"))
todo=[p for p in posts if not p["date"]]

RO={"ianuarie":"01","februarie":"02","martie":"03","aprilie":"04","mai":"05","iunie":"06",
    "iulie":"07","august":"08","septembrie":"09","octombrie":"10","noiembrie":"11","decembrie":"12"}

def fetch(p):
    try:
        r=subprocess.run(["curl","-sS","-L","--compressed","--max-time","25",
          "-A","Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
          p["url"]],capture_output=True,text=True,errors="ignore",timeout=35)
        b=r.stdout
    except Exception:
        return p
    for pat in (r'article:published_time"\s+content="(\d{4}-\d{2}-\d{2})',
                r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})',
                r'<time[^>]+datetime="(\d{4}-\d{2}-\d{2})',
                r'"published_at"\s*:\s*"(\d{4}-\d{2}-\d{2})'):
        m=re.search(pat,b)
        if m: p["date"]=m.group(1); return p
    m=re.search(r"(\d{1,2})\s+("+"|".join(RO)+r")\s+(\d{4})", b, re.I)
    if m:
        p["date"]=f"{m.group(3)}-{RO[m.group(2).lower()]}-{int(m.group(1)):02d}"; return p
    m=re.search(r"\b(20[12]\d)-(\d{2})-(\d{2})\b", b)
    if m: p["date"]=m.group(0)
    return p

with cf.ThreadPoolExecutor(max_workers=8) as ex:
    for i,_ in enumerate(ex.map(fetch, todo)):
        pass
dated=sum(1 for p in posts if p["date"])
print(f"dated {dated}/{len(posts)}")
json.dump(posts, open("posts_html.json","w"), ensure_ascii=False, indent=1)
by={}
for p in posts:
    by.setdefault(p["winery"],[0,0])
    by[p["winery"]][0]+=1
    if p["date"]: by[p["winery"]][1]+=1
for k,(n,d) in sorted(by.items()): print(f"  {k:26} {d}/{n} dated")
