# -*- coding: utf-8 -*-
"""Look for official team / leadership pages across the new company list."""
import re, html, json, subprocess
from urllib.parse import urljoin, urlparse

SITES = {
 "Sogrape":"https://www.sogrape.com/",
 "Bodega Pietroasa":"https://www.pietroasa.ro/",
 "Cricova":"https://www.cricova.md/",
 "Ostrovit":"https://www.domeniileostrov.ro/",
 "Rovinex":"https://www.rovinex.ro/",
 "Vinarte":"https://www.vinarte.ro/",
 "Vinexport":"https://www.vinexport.ro/",
 "Carpatvin":"https://www.carpatvin.ro/",
 "Chateau Vartely":"https://vartely.md/",
 "Bucium":"https://www.vinuribucium.ro/",
 "Domeniile Panciu":"https://www.domeniilepanciu.ro/",
 "Doina Vin":"https://www.doinavin.ro/",
 "Rifco Import":"https://www.rifco.ro/",
 "Corcova":"https://www.corcova.ro/",
 "DC Segarcea":"https://www.domeniulcoroanei.ro/",
 "Casa Isarescu":"https://www.casaisarescu.ro/",
 "Castel Mimi":"https://castelmimi.md/",
 "Alexandrion":"https://alexandriongroup.com/",
 "Suvorov Vin":"https://suvorov-vin.md/",
 "Barefoot Cellars":"https://www.barefootwine.com/",
 "Domeniul Bogdan":"https://domeniulbogdan.ro/",
 "Crama Basilescu":"https://cramabasilescu.ro/",
 "Avincis Vinuri":"https://avincis.ro/",
 "Crama La Salina":"https://cramalasalina.ro/",
 "Unicom":"https://www.unicomholding.ro/",
 "Antinori":"https://www.antinori.it/",
 "Fautor":"https://fautor.md/",
 "Caraprodvin":"https://www.caraprodvin.ro/",
 "Grand Tokaj":"https://grandtokaj.hu/",
 "Vinia":"https://www.vinia.ro/",
 "Domeniul Burcilor":"https://domeniulburcilor.ro/",
 "Prodimas":"https://www.prodimas.ro/",
 "WineRo":"https://www.winero.ro/",
 "Casa De Vinuri Ciumbrud":"https://www.casadevinuriciumbrud.ro/",
 "Domeniile Blaga":"https://domeniileblaga.ro/",
}
TEAM = re.compile(r"(echipa|team|despre[- ]noi|about[- ]us|conducere|management|"
                  r"oameni|people|leadership|cine[- ]suntem|istori|company)", re.I)
def get(u,t=25):
    try:
        r=subprocess.run(["curl","-sS","-L","--compressed","--max-time",str(t),
          "-A","Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
          "-H","Accept-Language: ro,en;q=0.8","-w","\n#HTTP:%{http_code}",u],
          capture_output=True,text=True,errors="ignore",timeout=t+10)
        b=r.stdout
        if "#HTTP:" not in b: return "ERR",""
        return b.rsplit("#HTTP:",1)[-1].strip(), b.rsplit("\n#HTTP:",1)[0]
    except Exception: return "ERR",""
out={}
for name,url in SITES.items():
    code, body = get(url)
    cands=[]
    if code.startswith("2"):
        host=urlparse(url).netloc.replace("www.","")
        for href,txt in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', body, re.S|re.I):
            full=urljoin(url,href)
            if urlparse(full).netloc.replace("www.","")!=host: continue
            t=re.sub(r"<[^>]+>"," ",txt); t=re.sub(r"\s+"," ",html.unescape(t)).strip()
            if TEAM.search(t) or TEAM.search(urlparse(full).path):
                cands.append(full)
    out[name]={"http":code,"team_links":sorted(set(cands))[:6]}
    print(f"{name:26} {code:>4}  " + ("; ".join(out[name]['team_links'][:3]) or "-"), flush=True)
json.dump(out, open("teams.json","w"), ensure_ascii=False, indent=1)
