# -*- coding: utf-8 -*-
"""Pull every post published 2021-01-01 onward from the WordPress and RSS sites."""
import json, re, html, subprocess

WP = {
 "Jidvei":"https://www.jidvei.ro",
 "Purcari Wineries":"https://purcariwineries.com",
 "Budureasca":"https://budureascawines.com",
 "Zarea":"https://zarea.ro",
 "Murfatlar":"https://murfatlar-vinul.ro",
 "Crama Gîrboiu":"https://cramagirboiu.ro",
 "Crama 1000 de Chipuri":"https://1000dechipuri.ro",
 "Petro Vaselo":"https://petrovaselo.com",
 "Carastelec Winery":"https://carastelecwinery.com",
 "Domeniile Davidescu":"https://domeniiledavidescu.ro",
 "SERVE Ceptura":"https://www.serve.ro",
}
RSS = {
 "Casa de Vinuri Cotnari SA":"https://www.vinuricotnari.ro/feed/",
 "Crama Ceptura":"https://crama-ceptura.eu/feed/",
 "Domeniile Vânju Mare":"https://domeniilevinjumare.ro/feed/",
 "Licorna WineHouse":"https://www.licornawinehouse.ro/feed",
 "Domeniile Săhăteni":"https://aureliavisinescu.com/feed/",
}

def get(url, t=35):
    try:
        r = subprocess.run(["curl","-sS","-L","--compressed","--max-time",str(t),
          "-A","Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
          "-H","Accept-Language: ro,en;q=0.8","-w","\n#HTTP:%{http_code}",url],
          capture_output=True,text=True,errors="ignore",timeout=t+10)
        b=r.stdout
        if "#HTTP:" not in b: return "ERR",""
        return b.rsplit("#HTTP:",1)[-1].strip(), b.rsplit("\n#HTTP:",1)[0]
    except Exception:
        return "ERR",""

def strip(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()

posts = []
for name, host in WP.items():
    n = 0
    for page in range(1, 12):
        url = (f"{host}/wp-json/wp/v2/posts?per_page=100&page={page}"
               f"&after=2021-01-01T00:00:00&orderby=date&order=desc&_fields=date,link,title,excerpt")
        code, body = get(url)
        if code != "200":
            break
        try:
            items = json.loads(body)
        except Exception:
            break
        if not items:
            break
        for it in items:
            posts.append({"winery": name, "date": it.get("date", "")[:10],
                          "title": strip(it.get("title", {}).get("rendered", "")),
                          "excerpt": strip(it.get("excerpt", {}).get("rendered", ""))[:300],
                          "url": it.get("link", ""), "src": "wp"})
            n += 1
        if len(items) < 100:
            break
    print(f"{name:26} wp posts since 2021: {n}", flush=True)

for name, feed in RSS.items():
    code, body = get(feed)
    n = 0
    if code == "200":
        for m in re.finditer(r"<item>(.*?)</item>", body, re.S):
            blk = m.group(1)
            t = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", blk, re.S)
            l = re.search(r"<link>(.*?)</link>", blk, re.S)
            d = re.search(r"<pubDate>(.*?)</pubDate>", blk, re.S)
            desc = re.search(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", blk, re.S)
            date = ""
            if d:
                mm = re.search(r"(\d{1,2})\s+(\w{3})\s+(\d{4})", d.group(1))
                if mm:
                    mo = {"Jan":"01","Feb":"02","Mar":"03","Apr":"04","May":"05","Jun":"06",
                          "Jul":"07","Aug":"08","Sep":"09","Oct":"10","Nov":"11","Dec":"12"}.get(mm.group(2), "01")
                    date = f"{mm.group(3)}-{mo}-{int(mm.group(1)):02d}"
            posts.append({"winery": name, "date": date, "title": strip(t.group(1) if t else ""),
                          "excerpt": strip(desc.group(1) if desc else "")[:300],
                          "url": (l.group(1).strip() if l else ""), "src": "rss"})
            n += 1
    print(f"{name:26} rss items: {n}", flush=True)

json.dump(posts, open("posts_wp.json", "w"), ensure_ascii=False, indent=1)
print("TOTAL", len(posts))
