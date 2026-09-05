import re, html, subprocess, json
SLUGS = {
 "Crama Gîrboiu":"crama-girboiu","Domeniile Vînju Mare":"vie-vin-vinju-mare","Licorna WineHouse":"licorna-winehouse",
 "Domeniile Sâmburești":"viti-pomicola-samburesti","Crama Rasova":"crama-rasova","Liliac Winery":"amb-wine-company",
 "Crama Oprișor":"carl-reh-winery","Aurelia Vișinescu":"domeniile-sahateni","1000 de Chipuri":"1000-de-chipuri",
 "Casa de Vinuri Negrini":"casa-de-vinuri-negrini","Petro Vaselo":"petro-vaselo","Carastelec":"carastelec-winery",
 "SERVE Ceptura":"serve-ceptura","Davino":"davino","Budureasca":"budureasca","Domeniile Averesti":"domeniile-averesti",
}
out={}
for name,slug in SLUGS.items():
    url=f"https://www.bestjobs.eu/company-profile/{slug}"
    try:
        r=subprocess.run(["curl","-sS","-L","--compressed","--max-time","25",
          "-A","Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
          "-H","Accept-Language: ro,en;q=0.8","-w","\n#HTTP:%{http_code}",url],
          capture_output=True,text=True,errors="ignore",timeout=40)
        b=r.stdout; code=b.rsplit("#HTTP:",1)[-1].strip()
        t=re.sub(r'(?is)<(script|style)[^>]*>.*?</\1>',' ',b); t=re.sub(r'<[^>]+>',' ',t)
        t=html.unescape(t); t=re.sub(r'\s+',' ',t)
        found = "404" not in code and ("alumni" in t.lower() or slug.split('-')[0] in t.lower())
        out[name]={"http":code,"url":url,"snippet":t[:220] if found else None}
    except Exception as e: out[name]={"error":str(e)[:80]}
print(json.dumps(out,ensure_ascii=False,indent=1))
