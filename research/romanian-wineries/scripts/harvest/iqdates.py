# -*- coding: utf-8 -*-
"""Keep the iqads articles that actually concern a winery, and date them."""
import json, re, subprocess, concurrent.futures as cf

iq=json.load(open("iqads.json"))
BRAND_WINERY={
 "cramele-recas":("Cramele Recas",r"reca[sș]"),
 "jidvei":("Jidvei",r"jidvei"),
 "cotnari":("Cramele Cotnari",r"cotnari"),
 "cramele-cotnari":("Cramele Cotnari",r"cotnari"),
 "purcari":("Purcari Wineries",r"purcari"),
 "crama-ceptura":("Crama Ceptura",r"ceptura"),
 "murfatlar":("Murfatlar",r"murfatlar"),
 "zarea":("Zarea",r"zarea"),
 "budureasca":("Budureasca",r"budureasca"),
 "davino":("Davino Winery",r"davino"),
 "liliac":("Liliac Winery",r"liliac"),
 "domeniile-ostrov":("Domeniile Ostrov",r"ostrov"),
 "tohani":("Tohani Romania",r"tohani"),
 "beciul-domnesc":("Beciul Domnesc",r"beciul domnesc"),
 "crama-oprisor":("Crama Oprișor",r"opri[sș]or"),
 "serve":("SERVE Ceptura",r"\bserve\b"),
 "domeniile-averesti":("Domeniile Averesti",r"avere[sș]ti"),
 "petro-vaselo":("Petro Vaselo",r"petro ?vaselo"),
 "crama-rasova":("Crama Rasova",r"rasova"),
 "licorna":("Licorna WineHouse",r"licorna"),
 "gitana":("Gitana Winery",r"gitana"),
 "carastelec":("Carastelec Winery",r"carastelec"),
 "girboiu":("Crama Gîrboiu",r"g[iî]rboiu"),
 "samburesti":("Domeniile Sâmburești",r"s[aâ]mbure[sș]ti"),
 "negrini":("Casa de Vinuri Negrini",r"negrini"),
 "aurelia-visinescu":("Domeniile Săhăteni",r"vi[sș]inescu|s[aă]h[aă]teni"),
 "vinju-mare":("Domeniile Vânju Mare",r"v[aâ]nju|v[iî]nju"),
}
jobs=[]
for brand,data in iq.items():
    if brand not in BRAND_WINERY: continue
    winery,pat=BRAND_WINERY[brand]
    for title,url in data["articles"]:
        jobs.append((winery,pat,title,url))
print("candidates:",len(jobs))

def work(j):
    winery,pat,title,url=j
    try:
        r=subprocess.run(["curl","-sS","-L","--compressed","--max-time","22",
          "-A","Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
          url],capture_output=True,text=True,errors="ignore",timeout=32)
        b=r.stdout
    except Exception: return None
    body=re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>"," ",b)
    txt=re.sub(r"<[^>]+>"," ",body)
    if not re.search(pat, txt, re.I): return None
    date=""
    for p in (r'article:published_time"\s+content="(\d{4}-\d{2}-\d{2})',
              r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})',
              r'<time[^>]+datetime="(\d{4}-\d{2}-\d{2})'):
        m=re.search(p,b)
        if m: date=m.group(1); break
    if not date:
        RO={"ianuarie":"01","februarie":"02","martie":"03","aprilie":"04","mai":"05","iunie":"06",
            "iulie":"07","august":"08","septembrie":"09","octombrie":"10","noiembrie":"11","decembrie":"12"}
        m=re.search(r"(\d{1,2})\s+("+"|".join(RO)+r")\s+(\d{4})",txt,re.I)
        if m: date=f"{m.group(3)}-{RO[m.group(2).lower()]}-{int(m.group(1)):02d}"
    return {"winery":winery,"date":date,"title":title,"url":url,"src":"iqads","excerpt":""}

res=[]
with cf.ThreadPoolExecutor(max_workers=10) as ex:
    for r in ex.map(work, jobs):
        if r: res.append(r)
res=[r for r in res if not r["date"] or r["date"]>="2021"]
json.dump(res, open("posts_iqads.json","w"), ensure_ascii=False, indent=1)
import collections
print("kept:",len(res))
for w,n in collections.Counter(r["winery"] for r in res).most_common(): print(f"  {w:24} {n}")
