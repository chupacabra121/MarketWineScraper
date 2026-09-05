# -*- coding: utf-8 -*-
"""Find each winery's news/blog section from its homepage navigation."""
import re, html, json, subprocess
from urllib.parse import urljoin, urlparse

SITES = {
 "Jidvei":"https://www.jidvei.ro/",
 "Beciul Domnesc":"https://www.beciuldomnesc.ro/",
 "Purcari Wineries":"https://purcariwineries.com/en/",
 "Cramele Recas":"https://www.cramelerecas.ro/",
 "Via Viticola":"https://www.vintruvianestates.com/",
 "Budureasca":"https://budureascawines.com/",
 "Zarea":"https://zarea.ro/",
 "Cramele Cotnari":"https://www.cramelecotnari.ro/",
 "Casa de Vinuri Cotnari SA":"https://www.vinuricotnari.ro/",
 "Murfatlar":"https://murfatlar-vinul.ro/",
 "Domeniile Averesti":"https://domeniile-averesti.ro/",
 "Tohani Romania":"https://tohaniromania.com/",
 "Davino Winery":"https://www.davino.ro/",
 "Domeniile Ostrov":"https://www.domeniileostrov.ro/",
 "Crama Ceptura":"https://crama-ceptura.eu/",
 "Crama Gîrboiu":"https://cramagirboiu.ro/",
 "Domeniile Vânju Mare":"https://domeniilevinjumare.ro/",
 "Licorna WineHouse":"https://www.licornawinehouse.ro/",
 "Gitana Winery":"https://www.gitanawinery.com/en/",
 "Domeniile Sâmburești":"https://samburesti.com/",
 "Crama Rasova":"https://www.cramarasova.ro/",
 "Liliac Winery":"https://www.liliac.com/",
 "Crama Oprișor":"https://www.crama-oprisor.com/",
 "Domeniile Săhăteni":"https://aureliavisinescu.com/",
 "Crama 1000 de Chipuri":"https://1000dechipuri.ro/",
 "Casa de Vinuri Negrini":"https://www.negrini.ro/",
 "Petro Vaselo":"https://petrovaselo.com/",
 "Carastelec Winery":"https://carastelecwinery.com/",
 "Domeniile Davidescu":"https://domeniiledavidescu.ro/",
 "SERVE Ceptura":"https://www.serve.ro/",
}
NEWS = re.compile(r"(noutat|stiri|știri|blog|news|eveniment|event|articol|press|presa|presă|media|jurnal|povesti|povești|campani)", re.I)

def get(url, t=30):
    try:
        r = subprocess.run(["curl","-sS","-L","--compressed","--max-time",str(t),
          "-A","Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
          "-H","Accept-Language: ro,en;q=0.8","-w","\n#HTTP:%{http_code}",url],
          capture_output=True,text=True,errors="ignore",timeout=t+15)
        b=r.stdout
        return b.rsplit("#HTTP:",1)[-1].strip(), b
    except Exception as e:
        return "ERR", str(e)

out={}
for name,url in SITES.items():
    code, body = get(url)
    cands=[]
    if code.startswith("2"):
        host=urlparse(url).netloc
        for href,txt in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', body, re.S|re.I):
            t=html.unescape(re.sub(r'<[^>]+>','',txt)).strip()
            full=urljoin(url,href)
            if urlparse(full).netloc.replace("www.","")!=host.replace("www.",""): continue
            if NEWS.search(t) or NEWS.search(urlparse(full).path):
                cands.append((t[:35], full))
    seen=set(); uniq=[]
    for t,u in cands:
        if u in seen: continue
        seen.add(u); uniq.append((t,u))
    out[name]={"home":url,"http":code,"news_candidates":uniq[:12]}
print(json.dumps(out,ensure_ascii=False,indent=1))
