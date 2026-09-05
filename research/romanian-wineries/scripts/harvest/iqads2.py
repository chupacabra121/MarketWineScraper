import re, html, subprocess, json
BRANDS = ["cramele-recas","jidvei","cotnari","cramele-cotnari","purcari","crama-ceptura","murfatlar",
          "zarea","budureasca","davino","liliac","domeniile-ostrov","tohani","beciul-domnesc",
          "crama-oprisor","serve","domeniile-averesti","petro-vaselo","crama-rasova","licorna",
          "gitana","carastelec","girboiu","samburesti","negrini","aurelia-visinescu","vinju-mare"]
def get(u,t=25):
    r=subprocess.run(["curl","-sS","-L","--compressed","--max-time",str(t),
      "-A","Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
      "-H","Accept-Language: ro,en;q=0.8","-w","\n#HTTP:%{http_code}",u],
      capture_output=True,text=True,errors="ignore",timeout=t+10)
    b=r.stdout
    if "#HTTP:" not in b: return "ERR",""
    return b.rsplit("#HTTP:",1)[-1].strip(), b.rsplit("\n#HTTP:",1)[0]
PAT = re.compile(r'<a[^>]+href="(https://www\.iqads\.ro/(?:articol|creatie|campanie)/[^"]+)"[^>]*>(.*?)</a>', re.S|re.I)
out={}
for b in BRANDS:
    code,body=get(f"https://www.iqads.ro/relevant/{b}")
    arts=[]; seen=set()
    if code=="200":
        for href,txt in PAT.findall(body):
            t=re.sub(r"<[^>]+>"," ",txt); t=re.sub(r"\s+"," ",html.unescape(t)).strip()
            if len(t)<15 or href in seen: continue
            seen.add(href); arts.append((t[:135],href))
    out[b]={"http":code,"n":len(arts),"articles":arts}
    print(f"{b:20} {code} n={len(arts)}", flush=True)
    for t,h in arts[:14]: print(f"      {t[:112]}")
json.dump(out, open("iqads.json","w"), ensure_ascii=False, indent=1)
