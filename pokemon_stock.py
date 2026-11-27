"""Pokémon-kort i svenska butiker -> Discord. Pingar när en förseglad produkt dyker upp eller blir köpbar online.
Butiker: Dragon's Lair (Shopify products.json), Alphaspel (kategorisida). Status sparas i stock_seen.json."""
import json, os, re, time, urllib.request, urllib.error, html

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
HOOK = os.environ.get("WEBHOOK_POKEMON")
SEEN = "stock_seen.json"
PRODUCT = re.compile(r"booster|elite trainer|\betb\b|\btin\b|blister|collection|bundle|display|\bbox\b|premium|build & battle|build and battle|\bpack\b|starter|battle deck|league battle|trainer kit|checklane", re.I)
SKIP = re.compile(r"deck ?box|sleeve|binder|pärm|playmat|kortlåd|toploader|acrylic|display for|förvaring|portfolio|ultra pro|dragon shield|figur|plush|gosedjur|pop mart|coin set|one piece|magic|lorcana|yu-?gi-?oh|digimon", re.I)
POKE = re.compile(r"pok[eé]mon", re.I)

def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30).read().decode("utf-8", "replace")

def wanted(title):
    return POKE.search(title) and PRODUCT.search(title) and not SKIP.search(title)

def dragonslair():
    out = []
    for page in (1, 2):
        for p in json.loads(get(f"https://www.dragonslair.se/products.json?limit=250&page={page}"))["products"]:
            if not wanted(p["title"]): continue
            v = p["variants"][0]
            out.append({"id": "dl:%s" % p["id"], "store": "Dragon's Lair", "title": p["title"],
                        "url": "https://www.dragonslair.se/products/" + p["handle"],
                        "price": f'{float(v["price"]):.0f} kr', "ok": any(x["available"] for x in p["variants"]),
                        "status": "Köpbar" if any(x["available"] for x in p["variants"]) else "Slut",
                        "img": (p.get("images") or [{}])[0].get("src")})
    return out

def alphaspel():
    out = []
    for page in range(1, 8):
        try: h = get(f"https://www.alphaspel.se/1762-pokemon-tcg/?page={page}")
        except urllib.error.HTTPError as e:
            if e.code == 404 and page > 1: break
            raise
        for m in re.finditer(r'class="product">.*?href="([^"]+)".*?<img[^>]*src="([^"]+)".*?product-name">\s*([^<]+).*?class="price[^"]*">\s*([^<]*?)\s*</div>.*?class="stock">(.*?)</div>', h, re.S):
            href, img, title, price, stock = m.groups()
            title = html.unescape(title.strip()); stock = re.sub(r"\s+", " ", re.sub(r"<br\s*/?>", " · ", stock)).strip()
            if not wanted(title): continue
            s = stock.lower()
            ok = ("postorder" in s or "förbok" in s or "beställ" in s) and "fullbokad" not in s and not re.search(r"(^|[^0-9])0 på postorder", s)
            out.append({"id": "as:" + href, "store": "Alphaspel", "title": title, "url": "https://www.alphaspel.se" + href,
                        "price": price.strip(), "ok": ok, "status": stock or "okänd", "img": "https://www.alphaspel.se" + img})
    return out

def post(p, why):
    e = {"title": p["title"][:250], "url": p["url"], "color": 0x2da44e if why == "new" else 0xffcb05,
         "description": ("🆕 **Ny produkt**" if why == "new" else "✅ **Köpbar igen**") + f"\n💰 {p['price']}\n📦 {p['status']}",
         "footer": {"text": p["store"]}}
    if p.get("img"): e["thumbnail"] = {"url": p["img"]}
    body = json.dumps({"username": f"🛒 {p['store'].upper()} · POKÉMON", "embeds": [e]}).encode()
    urllib.request.urlopen(urllib.request.Request(HOOK, body, {"Content-Type": "application/json", "User-Agent": UA}), timeout=30)
    time.sleep(1.2)

def main():
    if not HOOK: print("saknar WEBHOOK_POKEMON"); return
    seen = json.load(open(SEEN, encoding="utf-8")) if os.path.exists(SEEN) else {}
    for name, fn in (("dragonslair", dragonslair), ("alphaspel", alphaspel)):
        try: items = fn()
        except Exception as ex: print(f"[{name}] fel: {ex}"); continue
        first = not any(k.startswith(name[:2] + ":") for k in seen)
        n = 0
        for p in items:
            prev = seen.get(p["id"])
            if not first and p["ok"] and (prev is None or prev is False):
                try: post(p, "new" if prev is None else "back"); n += 1
                except Exception as ex: print(f"[{name}] post fel: {ex}"); continue
            seen[p["id"]] = p["ok"]
        print(f"[{name}] {len(items)} produkter, {n} pingar" + (" (första körning, tyst)" if first else ""))
    json.dump(seen, open(SEEN, "w", encoding="utf-8"), indent=0, ensure_ascii=False)

if __name__ == "__main__":
    main()
