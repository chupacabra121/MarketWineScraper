import re, html, subprocess, json
SITES = {
 "Crama Gîrboiu":"https://cramagirboiu.ro/",
 "Domeniile Vînju Mare":"https://domeniilevinjumare.ro/",
 "Licorna WineHouse":"https://www.licornawinehouse.ro/",
 "Gitana Winery":"https://www.gitanawinery.com/en/",
 "Domeniile Sâmburești":"https://samburesti.com/en/",
 "Crama Rasova":"https://www.cramarasova.ro/",
 "Liliac Winery":"https://www.liliac.com/",
 "Crama Oprișor":"https://www.crama-oprisor.com/",
 "Aurelia Vișinescu":"https://aureliavisinescu.com/",
 "1000 de Chipuri":"https://1000dechipuri.ro/",
 "Casa de Vinuri Negrini":"https://www.negrini.ro/",
 "Petro Vaselo":"https://petrovaselo.com/en/",
 "Domeniile Davidescu":"https://domeniiledavidescu.ro/",
 "SERVE Ceptura":"https://www.serve.ro/",
 "Davino":"https://www.davino.ro/",
 "Budureasca":"https://budureascawines.com/",
 "Domeniile Averesti":"https://domeniile-averesti.ro/",
}
KW = re.compile(r"(carier[ae]|careers?|joburi|locuri de munc|angaj[ăa]m|recrut|vacanc|alătur[ăa]-te)", re.I)
out={}
for name,url in SITES.items():
    try:
        r = subprocess.run(["curl","-sS","-L","--compressed","--max-time","30",
            "-A","Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
            "-H","Accept-Language: ro,en;q=0.8","-w","\n#HTTP:%{http_code}",url],
            capture_output=True, text=True, errors="ignore", timeout=45)
        body=r.stdout
        code=body.rsplit("#HTTP:",1)[-1].strip() if "#HTTP:" in body else "?"
        txt=re.sub(r'(?is)<(script|style)[^>]*>.*?</\1>',' ',body)
        txt=re.sub(r'<[^>]+>',' ',txt); txt=html.unescape(txt); txt=re.sub(r'\s+',' ',txt)
        hits=sorted({m.group(0) for m in KW.finditer(txt)})
        ctx=[txt[max(0,m.start()-70):m.start()+70] for m in list(KW.finditer(txt))[:3]]
        out[name]={"http":code,"kw":hits,"ctx":ctx}
    except Exception as e:
        out[name]={"error":str(e)[:120]}
print(json.dumps(out, ensure_ascii=False, indent=1))
