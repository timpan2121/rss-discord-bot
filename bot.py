#!/usr/bin/env python3
"""RSS -> Discord. Ett flöde per kanal via webhooks. Läser feeds.json, sparar sedda i seen.json."""
from zoneinfo import ZoneInfo
import email.utils, datetime, json, os, time, html, re, urllib.request, urllib.error, urllib.parse
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
                      "link": text(it, "link"), "summary": text(it, "description"), "date": text(it, "pubDate", "{http://purl.org/dc/elements/1.1/}date"),
                      "image": next((m.get("url") for m in list(it.iter("{http://search.yahoo.com/mrss/}content")) + list(it.iter("enclosure")) if (m.get("type") or "image").startswith("image")), "")})
    for it in root.iter(A + "entry"):
        items.append({"id": text(it, A + "id", A + "link"), "title": text(it, A + "title"),
                      "link": text(it, A + "link"), "summary": text(it, A + "summary", A + "content"), "date": text(it, A + "published", A + "updated")})
    return items

def parse_html(data, base, pattern):
    """Sidor utan RSS: plocka artikellänkar som matchar pattern, i sidordning."""
    items, done = [], set()
    for m in re.finditer(r'href="(' + pattern + ')"', data.decode("utf-8", "replace"), re.I):
        link = urllib.parse.urljoin(base, m.group(1))
        if link not in done:
            done.add(link); items.append({"id": link, "link": link, "title": "", "summary": "", "date": "", "image": "", "html": True})
    num = lambda i: int(m.group(1)) if (m := re.search(r"(\d+)\D*$", i["link"])) else 0
    return sorted(items, key=num, reverse=True)

def enrich(item):
    """Hämta rubrik/ingress/bild från artikelns og-taggar."""
    page = fetch(item["link"]).decode("utf-8", "replace")
    def og(k):
        m = re.search(r'<meta[^>]+property="og:' + k + r'"[^>]+content="([^"]*)"', page)
        return html.unescape(m.group(1)) if m else ""
    item.update(title=og("title"), summary=og("description"), image=og("image"))
    m = re.search(r'"datePublished"\s*:\s*"([^"]+)"|property="article:published_time"[^>]+content="([^"]+)"', page)
    item["date"] = (m.group(1) or m.group(2)) if m else datetime.datetime.now(datetime.timezone.utc).isoformat()

def matches(item, keywords):
    if not keywords: return True
    t = " ".join([item["title"], item["summary"], item["link"]]).lower()
    return any(k.lower() in t for k in keywords)

def clean(s, n=4000):
    s = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>", "\n", s or "")
    s = html.unescape(re.sub(r"<[^>]+>", "", s))
    s = re.sub(r"\n\s*\n+", "\n\n", s).strip()
    return s[:n] + ("…" if len(s) > n else "")

def iso(d):
    if not d: return None
    try:
        t = email.utils.parsedate_to_datetime(d)
    except Exception:
        try: t = datetime.datetime.fromisoformat(d.replace("Z", "+00:00"))
        except Exception: return None
    if t.tzinfo is None: t = t.replace(tzinfo=datetime.timezone.utc)
    return t.astimezone(datetime.timezone.utc).isoformat()

def post(webhook, feed_name, item, color=None, label=None):
    embed = {"title": clean(item["title"], 250) or "(utan rubrik)", "description": clean(item["summary"])}
    if color: embed["color"] = int(color.lstrip("#"), 16)
    ts = iso(item.get("date"))
    if ts: embed["timestamp"] = ts
    if label: embed["author"] = {"name": label}
    if item["link"]: embed["url"] = item["link"]
    if item.get("image"): embed["thumbnail"] = {"url": item["image"]}
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
    last = seen.setdefault("_last", {})
    now = datetime.datetime.now(ZoneInfo("Europe/Stockholm"))
    for f in feeds:
        iv = f.get("interval_sunday" if now.weekday() == 6 else "interval", 0)
        if iv and time.time() - last.get(f["url"], 0) < iv * 60 - 30:
            continue
        last[f["url"]] = time.time()
        hook = os.environ.get(f["webhook_secret"])
        if not hook:
            print(f"[{f['name']}] saknar secret {f['webhook_secret']}, hoppar över"); continue
        try:
            data = fetch(f["url"])
            items = parse_html(data, f["url"], f["link_pattern"]) if f.get("link_pattern") else parse(data)
            items = [i for i in items if matches(i, f.get("keywords"))]
        except Exception as e:
            print(f"[{f['name']}] kunde inte hämta: {e}"); continue
        old = seen.get(f["url"])
        if old is None:  # första körningen: posta bara de 3 senaste
            old = [i["id"] for i in items[3:]][:KEEP]
            print(f"[{f['name']}] första körning, postar 3 senaste")
        new = [i for i in items if i["id"] not in old][:MAX_PER_RUN]
        for i in reversed(new):
            try:
                if i.get("html"): enrich(i)
                post(hook, f["name"], i, f.get("color"), f.get("label"))
            except Exception as e:
                print(f"[{f['name']}] post misslyckades: {e}"); break
            old.insert(0, i["id"]); time.sleep(1)
        seen[f["url"]] = old[:KEEP]
        print(f"[{f['name']}] {len(new)} nya")
    json.dump(seen, open("seen.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)

if __name__ == "__main__":
    main()
