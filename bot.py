#!/usr/bin/env python3
"""RSS -> Discord. Ett flöde per kanal via webhooks. Läser feeds.json, sparar sedda i seen.json."""
import json, os, time, html, re, urllib.request, urllib.error
import xml.etree.ElementTree as ET

UA = "Mozilla/5.0 (X11; Linux x86_64) rss-discord-bot"
MAX_PER_RUN = 10
KEEP = 500

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for n in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except Exception:
            if n == 3: raise
            time.sleep(10 * (n + 1))

def text(el, *tags):
    for t in tags:
        x = el.find(t)
        if x is not None:
            if x.get("href"): return x.get("href")
            if x.text: return x.text.strip()
    return ""

def parse(data):
    root = ET.fromstring(data)
    A = "{http://www.w3.org/2005/Atom}"
    items = []
    for it in root.iter("item"):
        items.append({"id": text(it, "guid", "link", "title"), "title": text(it, "title"),
                      "link": text(it, "link"), "summary": text(it, "description")})
    for it in root.iter(A + "entry"):
        items.append({"id": text(it, A + "id", A + "link"), "title": text(it, A + "title"),
                      "link": text(it, A + "link"), "summary": text(it, A + "summary", A + "content")})
    return items

def clean(s, n=4000):
    s = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>", "\n", s or "")
    s = html.unescape(re.sub(r"<[^>]+>", "", s))
    s = re.sub(r"\n\s*\n+", "\n\n", s).strip()
    return s[:n] + ("…" if len(s) > n else "")

def post(webhook, feed_name, item, color=None, label=None):
    embed = {"title": clean(item["title"], 250) or "(utan rubrik)", "description": clean(item["summary"])}
    if color: embed["color"] = int(color.lstrip("#"), 16)
    if label: embed["author"] = {"name": label}
    if item["link"]: embed["url"] = item["link"]
    body = json.dumps({"username": feed_name, "embeds": [embed]}).encode()
    req = urllib.request.Request(webhook, data=body, headers={"Content-Type": "application/json", "User-Agent": UA})
    for _ in range(3):
        try:
            urllib.request.urlopen(req, timeout=30); return
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(float(json.loads(e.read() or b"{}").get("retry_after", 2))); continue
            raise

def main():
    feeds = json.load(open("feeds.json", encoding="utf-8"))
    seen = json.load(open("seen.json")) if os.path.exists("seen.json") else {}
    for f in feeds:
        hook = os.environ.get(f["webhook_secret"])
        if not hook:
            print(f"[{f['name']}] saknar secret {f['webhook_secret']}, hoppar över"); continue
        try:
            items = parse(fetch(f["url"]))
        except Exception as e:
            print(f"[{f['name']}] kunde inte hämta: {e}"); continue
        old = seen.get(f["url"])
        if old is None:  # första körningen: markera allt som sett
            seen[f["url"]] = [i["id"] for i in items][:KEEP]
            print(f"[{f['name']}] första körning, {len(items)} markerade som sedda"); continue
        new = [i for i in items if i["id"] not in old][:MAX_PER_RUN]
        for i in reversed(new):
            try:
                post(hook, f["name"], i, f.get("color"), f.get("label"))
            except Exception as e:
                print(f"[{f['name']}] post misslyckades: {e}"); break
            old.insert(0, i["id"]); time.sleep(1)
        seen[f["url"]] = old[:KEEP]
        print(f"[{f['name']}] {len(new)} nya")
    json.dump(seen, open("seen.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)

if __name__ == "__main__":
    main()
