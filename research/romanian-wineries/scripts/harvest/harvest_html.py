# -*- coding: utf-8 -*-
"""Harvest article links from the non-WordPress winery news sections."""
import json, re, html, subprocess
from urllib.parse import urljoin, urlparse

def get(url,t=35):
    try:
        r=subprocess.run(["curl","-sS","-L","--compressed","--max-time",str(t),
          "-A","Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
          "-H","Accept-Language: ro,en;q=0.8","-w","\n#HTTP:%{http_code}",url],
          capture_output=True,text=True,errors="ignore",timeout=t+10)
        b=r.stdout
        if "#HTTP:" not in b: return "ERR",""
        return b.rsplit("#HTTP:",1)[-1].strip(), b.rsplit("\n#HTTP:",1)[0]
    except Exception: return "ERR",""

def strip(s):
    s=re.sub(r"<[^>]+>"," ",s or "")
    return re.sub(r"\s+"," ",html.unescape(s)).strip()

ATOM = {
 "Domeniile Ostrov":["https://www.domeniileostrov.ro/blogs/blog.atom",
                     "https://www.domeniileostrov.ro/blogs/comunicate-de-presa.atom"],
}
LISTINGS = {
 "Davino Winery":["https://davino.ro/news"],
 "Budureasca":["https://budureascawines.com/blog/"],
 "Murfatlar":["https://murfatlar-vinul.ro/noutati/"],
 "Petro Vaselo":["https://petrovaselo.com/ro/blog/"],
 "Beciul Domnesc":["https://www.beciuldomnesc.ro/articles/all",
                   "https://www.beciuldomnesc.ro/articles/event"],
 "Domeniile Averesti":["https://domeniile-averesti.ro/ro/noutati-anunturi"],
 "Via Viticola":["https://www.vintruvianestates.com/noutati"],
 "Gitana Winery":["https://www.gitanawinery.com/en/our-blog/"],
 "Domeniile Sâmburești":["https://samburesti.com/articole/"],
 "Crama Rasova":["https://www.cramarasova.ro/evenimente-cramarasova.html"],
 "Liliac Winery":["https://www.liliac.com/news"],
}
SKIP = re.compile(r"(cart|login|account|policy|termeni|cookie|privacy|contact|shop/?$|product|colectii|/tag/|/author/|facebook|instagram|youtube|linkedin|\.pdf|\.jpg|\.png|mailto:|tel:)", re.I)

posts=[]
for name, feeds in ATOM.items():
    for f in feeds:
        code, body = get(f)
        if code!="200": continue
        for m in re.finditer(r"<entry>(.*?)</entry>", body, re.S):
            e=m.group(1)
            t=re.search(r"<title[^>]*>(.*?)</title>", e, re.S)
            l=re.search(r'<link[^>]+href="([^"]+)"', e)
            d=re.search(r"<published>(\d{4}-\d{2}-\d{2})", e) or re.search(r"<updated>(\d{4}-\d{2}-\d{2})", e)
            s=re.search(r"<summary[^>]*>(.*?)</summary>", e, re.S) or re.search(r"<content[^>]*>(.*?)</content>", e, re.S)
            posts.append({"winery":name,"date":d.group(1) if d else "","title":strip(t.group(1) if t else ""),
                          "excerpt":strip(s.group(1) if s else "")[:300],"url":l.group(1) if l else f,"src":"atom"})
    print(f"{name:26} atom entries: {sum(1 for p in posts if p['winery']==name)}", flush=True)

for name, urls in LISTINGS.items():
    found={}
    for u in urls:
        code, body = get(u)
        if code!="200": continue
        host=urlparse(u).netloc.replace("www.","")
        for href,txt in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', body, re.S|re.I):
            full=urljoin(u,href)
            if urlparse(full).netloc.replace("www.","")!=host: continue
            if SKIP.search(full): continue
            t=strip(txt)
            if len(t)<12 or len(t)>200: continue
            path=urlparse(full).path.rstrip("/")
            if path.count("/")<1 or full.rstrip("/")==u.rstrip("/"): continue
            found[full]=t
        # dates present in the listing markup
    for full,t in found.items():
        posts.append({"winery":name,"date":"","title":t,"excerpt":"","url":full,"src":"html"})
    print(f"{name:26} listing links: {len(found)}", flush=True)

json.dump(posts, open("posts_html.json","w"), ensure_ascii=False, indent=1)
print("TOTAL", len(posts))
