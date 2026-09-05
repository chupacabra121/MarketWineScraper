# -*- coding: utf-8 -*-
"""Try structured feeds first: WordPress REST, Shopify JSON/Atom, RSS."""
import json, re, subprocess, sys

HOSTS = {
 "Jidvei":"https://www.jidvei.ro",
 "Beciul Domnesc":"https://www.beciuldomnesc.ro",
 "Purcari Wineries":"https://purcariwineries.com",
 "Cramele Recas":"https://www.cramelerecas.ro",
 "Via Viticola":"https://www.vintruvianestates.com",
 "Budureasca":"https://budureascawines.com",
 "Zarea":"https://zarea.ro",
 "Cramele Cotnari":"https://www.cramelecotnari.ro",
 "Casa de Vinuri Cotnari SA":"https://www.vinuricotnari.ro",
 "Murfatlar":"https://murfatlar-vinul.ro",
 "Domeniile Averesti":"https://domeniile-averesti.ro",
 "Tohani Romania":"https://tohaniromania.com",
 "Davino Winery":"https://www.davino.ro",
 "Domeniile Ostrov":"https://www.domeniileostrov.ro",
 "Crama Ceptura":"https://crama-ceptura.eu",
 "Crama Gîrboiu":"https://cramagirboiu.ro",
 "Domeniile Vânju Mare":"https://domeniilevinjumare.ro",
 "Licorna WineHouse":"https://www.licornawinehouse.ro",
 "Gitana Winery":"https://www.gitanawinery.com",
 "Domeniile Sâmburești":"https://samburesti.com",
 "Crama Rasova":"https://www.cramarasova.ro",
 "Liliac Winery":"https://www.liliac.com",
 "Crama Oprișor":"https://www.crama-oprisor.com",
 "Domeniile Săhăteni":"https://aureliavisinescu.com",
 "Crama 1000 de Chipuri":"https://1000dechipuri.ro",
 "Casa de Vinuri Negrini":"https://www.negrini.ro",
 "Petro Vaselo":"https://petrovaselo.com",
 "Carastelec Winery":"https://carastelecwinery.com",
 "Domeniile Davidescu":"https://domeniiledavidescu.ro",
 "SERVE Ceptura":"https://www.serve.ro",
}

def get(url, t=25):
    try:
        r = subprocess.run(["curl","-sS","-L","--compressed","--max-time",str(t),
          "-A","Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
          "-H","Accept-Language: ro,en;q=0.8","-w","\n#HTTP:%{http_code}",url],
          capture_output=True,text=True,errors="ignore",timeout=t+10)
        b=r.stdout
        if "#HTTP:" not in b: return "ERR",""
        code=b.rsplit("#HTTP:",1)[-1].strip()
        return code, b.rsplit("\n#HTTP:",1)[0]
    except Exception:
        return "ERR",""

res={}
for name,host in HOSTS.items():
    info={"wp":0,"shopify":0,"rss":0}
    # WordPress REST
    code,body = get(f"{host}/wp-json/wp/v2/posts?per_page=1")
    if code=="200" and body.strip().startswith("["):
        try:
            json.loads(body); info["wp"]=1
        except Exception: pass
    # Shopify blogs
    if not info["wp"]:
        code,body = get(f"{host}/blogs.json")
        if code=="200" and '"blogs"' in body: info["shopify"]=1
    # generic RSS
    if not info["wp"] and not info["shopify"]:
        for p in ("/feed/","/feed","/rss","/rss.xml","/blog/feed/"):
            code,body = get(host+p)
            if code=="200" and ("<rss" in body[:600] or "<feed" in body[:600]):
                info["rss"]=p; break
    res[name]=info
    print(f"{name:26} wp={info['wp']} shopify={info['shopify']} rss={info['rss']}", flush=True)
json.dump(res, open("feeds.json","w"))
