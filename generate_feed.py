#!/usr/bin/env python3
"""
generate_feed.py

Hämtar live-feed från Webnode, filtrerar produkter med kategori 'norsk',
konverterar SEK -> NOK (1.3375), lägger till fraktinfo och skriver
lampster-norge-feed/norsk-feed.xml atomiskt.
Skriptet gör *bara* filgenereringen (ingen git/push här) — git hanteras i workflow.
"""

from __future__ import annotations
import requests
import lxml.etree as ET
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import os, time, re, tempfile, shutil, sys

# ---------- KONFIG ----------
SOURCE_BASE = "https://www.lampster.se/rss/pf-google_nok-no.xml"
OUTPUT_DIR = "lampster-norge-feed"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "norsk-feed.xml")

CONVERSION_RATE = Decimal("1.3375")   # SEK -> NOK
STANDARD_SEK_SHIPPING = Decimal("99")
FREE_SHIPPING_THRESHOLD = Decimal("735.00")  # NOK

FETCH_ATTEMPTS = 5
FETCH_DELAY_SECONDS = 2

G_NS = "http://base.google.com/ns/1.0"
ns = {"g": G_NS}

# ---------- HJÄLP ----------
def safe_decimal_from_str(s: str | None) -> Decimal | None:
    if not s:
        return None
    m = re.search(r"[-+]?[0-9\.,]+", s)
    if not m:
        return None
    num = m.group(0).replace(",", ".")
    try:
        return Decimal(num)
    except InvalidOperation:
        return None

def find_child_text(item: ET._Element, localname: str, nsmap) -> str | None:
    # Försök namespaced, sedan utan, sen fallback på tag-ändelse
    try:
        e = item.find(f"g:{localname}", nsmap)
    except Exception:
        e = None
    if e is not None and e.text:
        return e.text.strip()
    e = item.find(localname)
    if e is not None and e.text:
        return e.text.strip()
    for c in item:
        if isinstance(c.tag, str) and c.tag.endswith(localname):
            if c.text:
                return c.text.strip()
    return None

# ---------- skapa dir ----------
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------- hämta feed (cache-bust) ----------
session = requests.Session()
headers = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
    "User-Agent": "feed-updater/1.0 (+lampster)"
}

resp = None
for attempt in range(1, FETCH_ATTEMPTS + 1):
    cb = int(time.time())
    url = f"{SOURCE_BASE}?cb={cb}"
    print(f"[fetch] Attempt {attempt}/{FETCH_ATTEMPTS} -> {url}")
    try:
        r = session.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        if "<item" in r.text:
            resp = r
            print("[fetch] OK - feed appears to contain items")
            break
        else:
            print("[fetch] Warning: no <item> found; retrying")
    except Exception as e:
        print(f"[fetch] Error: {e}")
    time.sleep(FETCH_DELAY_SECONDS)

if resp is None:
    print("[error] Could not fetch feed after retries", file=sys.stderr)
    sys.exit(1)

# ---------- parse ----------
parser = ET.XMLParser(recover=True)
try:
    tree = ET.fromstring(resp.content, parser=parser)
except Exception as e:
    print(f"[error] XML parse error: {e}", file=sys.stderr)
    sys.exit(1)

# ---------- build output RSS ----------
rss = ET.Element("rss", version="2.0", nsmap={"g": G_NS})
channel = ET.SubElement(rss, "channel")

orig_channel = tree.find("channel")
if orig_channel is None:
    print("[error] Source feed has no <channel>", file=sys.stderr)
    sys.exit(1)

for tag in ("title", "link", "description"):
    t = orig_channel.find(tag)
    if t is not None and t.text:
        ET.SubElement(channel, tag).text = t.text

items = orig_channel.findall("item")
print(f"[info] Source items: {len(items)}")

included_count = 0
NOK_STANDARD_SHIPPING = (STANDARD_SEK_SHIPPING * CONVERSION_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

for item in items:
    product_type_text = (find_child_text(item, "product_type", ns) or "")
    google_cat_text = (find_child_text(item, "google_product_category", ns) or "")
    combined = (product_type_text + " " + google_cat_text).lower()
    if "norsk" not in combined:
        continue

    included_count += 1
    new_item = ET.SubElement(channel, "item")

    for tag in ("id", "title", "description", "link", "image_link", "availability", "product_type", "price"):
        val = find_child_text(item, tag, ns)
        if tag == "price":
            if val:
                d = safe_decimal_from_str(val)
                if d is not None:
                    nok = (d * CONVERSION_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    out_val = f"{nok:.2f} NOK"
                else:
                    out_val = f"{NOK_STANDARD_SHIPPING:.2f} NOK"
            else:
                out_val = f"{NOK_STANDARD_SHIPPING:.2f} NOK"
            ET.SubElement(new_item, f"{{{G_NS}}}{tag}").text = out_val
            continue
        ET.SubElement(new_item, f"{{{G_NS}}}{tag}").text = val if val else "N/A"

    # shipping block for Norway
    shipping_elem = ET.SubElement(new_item, f"{{{G_NS}}}shipping")
    ET.SubElement(shipping_elem, f"{{{G_NS}}}country").text = "NO"
    ET.SubElement(shipping_elem, f"{{{G_NS}}}service").text = "Standard"

    price_text = find_child_text(new_item, "price", ns) or "0"
    p = safe_decimal_from_str(price_text)
    price_val = p if p is not None else Decimal("0.00")
    shipping_price = Decimal("0.00") if price_val >= FREE_SHIPPING_THRESHOLD else NOK_STANDARD_SHIPPING
    ET.SubElement(shipping_elem, f"{{{G_NS}}}price").text = f"{shipping_price:.2f} NOK"

    # handling and transit times (workdays)
    ET.SubElement(shipping_elem, f"{{{G_NS}}}min_handling_time").text = "0"
    ET.SubElement(shipping_elem, f"{{{G_NS}}}max_handling_time").text = "1"
    ET.SubElement(shipping_elem, f"{{{G_NS}}}min_transit_time").text = "1"
    ET.SubElement(shipping_elem, f"{{{G_NS}}}max_transit_time").text = "9"

print(f"[info] Included norsk products: {included_count}")

# ---------- write atomiskt ----------
tmp_fd, tmp_path = tempfile.mkstemp(suffix=".xml", prefix="norsk-feed-", dir=OUTPUT_DIR)
os.close(tmp_fd)
tree_out = ET.ElementTree(rss)
try:
    tree_out.write(tmp_path, encoding="utf-8", xml_declaration=True, pretty_print=True)
    # move into place
    shutil.move(tmp_path, OUTPUT_FILE)
    print(f"[ok] Wrote {OUTPUT_FILE}")
except Exception as e:
    print(f"[error] Writing output failed: {e}", file=sys.stderr)
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
    sys.exit(1)

sys.exit(0)
